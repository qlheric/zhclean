"""llm.py 兜底客户端的不变式测试（全程 mock，零网络请求）。

F: LLMClient 请求构造（max_completion_tokens / Bearer / 端点）+ 响应解析 + 非 200 抛 LLMError；
   llm_normalize 三分支（新值 0.85 / 原值 0.1 / 异常与解析失败 0.1）；client_from_env 读环境变量
R: src/zhclean/llm.py
A: uv run --project . pytest tests/test_llm.py -q
S: 一律 mock urlopen / mock client，**不联网、不发真 API 请求**
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from zhclean.llm import (CONF_LLM, MAX_COMPLETION_TOKENS, LLMClient, LLMError,
                         build_prompt, client_from_env, llm_normalize)

ROOT = Path(__file__).resolve().parents[1]


# ---- 替身 ---------------------------------------------------------------------
class FakeClient:
    """假客户端：记录 prompt，按预设 reply 返回（异常实例就抛）。"""

    def __init__(self, reply):
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class FakeResponse:
    """urllib 响应的最小替身：read() 返回预设 JSON 字节。"""

    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def patch_urlopen(monkeypatch, result):
    """把 `urllib.request.urlopen` 换成假实现，捕获请求；result 为 payload 或异常实例。"""
    captured: dict = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["timeout"] = timeout
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)

    monkeypatch.setattr("urllib.request.urlopen", fake)
    return captured


# ---- 常量 / 提示词 -------------------------------------------------------------
def test_conf_llm_is_between_threshold_and_structural():
    assert CONF_LLM == 0.85          # 高于 HITL 阈值 0.2、低于 rules 结构档 0.9
    assert 0.2 <= CONF_LLM < 0.9


def test_build_prompt_contains_field_value_and_constraint():
    p = build_prompt("王 小明", "person")
    assert "person" in p and "王 小明" in p
    assert "只输出" in p and "原样输出" in p   # 只求值 + 无法确定就回原值


# ---- llm_normalize 三分支 ------------------------------------------------------
def test_new_value_gets_llm_conf():
    assert llm_normalize("范同言", "person", FakeClient("范童言")) == ("范童言", CONF_LLM)


def test_echo_of_original_gets_none_conf():
    """响应 strip 后 == 原值 ⇒ (原值, 0.1)，回 HITL。"""
    assert llm_normalize("范童", "person", FakeClient("  范童\n")) == ("范童", 0.1)


@pytest.mark.parametrize("reply", ["", "   ", "\n\t"])
def test_blank_response_keeps_original(reply):
    assert llm_normalize("范童", "person", FakeClient(reply)) == ("范童", 0.1)


def test_client_exception_is_swallowed():
    """兜底失败即回 HITL：不抛出。"""
    assert llm_normalize("范童", "person", FakeClient(RuntimeError("boom"))) == ("范童", 0.1)


def test_malformed_payload_becomes_original(monkeypatch):
    patch_urlopen(monkeypatch, {"choices": []})          # 结构不对 ⇒ 解析抛 ⇒ 回原值
    assert llm_normalize("范童", "person", _client()) == ("范童", 0.1)


def test_prompt_sent_includes_field_and_value():
    c = FakeClient("随便")
    llm_normalize("范童", "person", c)
    assert len(c.prompts) == 1 and "person" in c.prompts[0] and "范童" in c.prompts[0]


# ---- LLMClient.complete（mock urlopen，零网络） --------------------------------
def _client():
    return LLMClient("https://api.deepseek.com/v1", "sk-test", "deepseek-chat")


def test_complete_builds_openai_compatible_request(monkeypatch):
    cap = patch_urlopen(monkeypatch, {"choices": [{"message": {"content": "范童言"}}]})
    out = _client().complete("提示词")
    assert out == "范童言"
    assert cap["url"] == "https://api.deepseek.com/v1/chat/completions"   # 端点拼接
    assert cap["body"]["model"] == "deepseek-chat"
    assert cap["body"]["max_completion_tokens"] == MAX_COMPLETION_TOKENS   # GPT-6 系参数名
    assert cap["body"]["messages"] == [{"role": "user", "content": "提示词"}]
    assert cap["headers"]["authorization"] == "Bearer sk-test"             # 认证头
    assert cap["headers"]["content-type"] == "application/json"
    assert cap["timeout"] == 30


def test_complete_respects_custom_timeout(monkeypatch):
    cap = patch_urlopen(monkeypatch, {"choices": [{"message": {"content": "x"}}]})
    LLMClient("https://x/v1", "k", "m", timeout=5).complete("p")
    assert cap["timeout"] == 5


def test_complete_non_200_raises_llm_error(monkeypatch):
    err = urllib.error.HTTPError("https://x/v1/chat/completions", 401, "Unauthorized", {},
                                 io.BytesIO(b'{"error":"bad key"}'))
    patch_urlopen(monkeypatch, err)
    with pytest.raises(LLMError) as ei:
        _client().complete("p")
    assert ei.value.status == 401 and "bad key" in str(ei.value)


@pytest.mark.parametrize("payload", [
    {"choices": []},                                              # 空 choices
    {"choices": [{"message": {}}]},                               # 无 content
    {"choices": [{"message": {"content": None}}]},                # content 非字符串
])
def test_complete_malformed_payload_raises(monkeypatch, payload):
    patch_urlopen(monkeypatch, payload)
    with pytest.raises(Exception):
        _client().complete("p")


def test_base_url_trailing_slash_is_normalized(monkeypatch):
    cap = patch_urlopen(monkeypatch, {"choices": [{"message": {"content": "x"}}]})
    LLMClient("https://x/v1/", "k", "m").complete("p")
    assert cap["url"] == "https://x/v1/chat/completions"     # 不出现 //chat


# ---- client_from_env（只读环境变量，不碰凭据文件） -----------------------------
def test_client_from_env_reads_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-xyz")
    c = client_from_env("deepseek")
    assert c.api_key == "sk-xyz" and "deepseek" in c.base_url and c.model == "deepseek-chat"


def test_client_from_env_zhipu(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "zk")
    assert client_from_env("zhipu").api_key == "zk"


def test_client_from_env_missing_key(monkeypatch):
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ZHIPU_API_KEY"):
        client_from_env("zhipu")


def test_client_from_env_unknown_provider():
    with pytest.raises(ValueError, match="未知 provider"):
        client_from_env("nope")


# ---- 入口自检（判据 2：`python -m zhclean.llm`，零网络） ------------------------
def test_m_entry_demo_runs_ok():
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    p = subprocess.run([sys.executable, "-m", "zhclean.llm"], capture_output=True, cwd=ROOT, env=env)
    assert p.returncode == 0
    assert "llm._demo: OK" in p.stdout.decode("utf-8", errors="replace")
