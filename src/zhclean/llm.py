"""LLM API 兜底客户端（可插拔）——三级流的第二级：规则 → LLM → HITL。

F: 规则低置信时走 LLM 语义清洗；OpenAI 兼容协议（deepseek / zhipu / openai）
R: loop.py（think 阶段作 `llm_fn` 调用）；只用 stdlib，不新增依赖
A: 被 loop.py 调用；自检 `python -m zhclean.llm [--demo]`（全程 mock，零网络请求）
S: GPT-6 系列用 max_completion_tokens；单条失败不得中断整体清洗（兜底失败即回 HITL）

三级流（S2 架构「规则 80% + LLM 20%」的 20% 部分）：
    规则有把握（conf ≥ hitl_threshold） ⇒ 直接用规则结果（不调 LLM，省钱）
    规则没把握（conf <  hitl_threshold） ⇒ 调 LLM 兜底：LLM 有把握 ⇒ 落 cleaned
                                          LLM 也没把握 ⇒ 原值交人工（HITL）
真调用控量（`llm_max_calls` + 批量）是使用方责任，本模块只给护栏，不发任何请求。

接口契约（脑定，TASK-016 §2.5）：
- LLMClient(base_url, api_key, model, timeout=30).complete(prompt) -> str
    POST `{base_url}/chat/completions`，body 用 `max_completion_tokens` + `messages`；
    非 200 抛 `LLMError`（带状态码与响应摘要）。
- llm_normalize(value, field, client) -> (规范值, 置信度)
    提示词只求规范值；响应 strip 后 == 原值 ⇒ `(原值, CONF_NONE)`；
    否则 ⇒ `(结果, CONF_LLM)`。解析失败 / 异常 ⇒ `(原值, CONF_NONE)`，不抛出。
- `CONF_LLM = 0.85`：LLM 兜底档，与 rules 的 0.95 / 0.9 / 0.7 / 0.1 区分开
  （报告里一眼能看出「这行是 LLM 补的」，不是规则确定性命中）。
"""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request

from ._compat import utf8_stdio
from .rules.common import CONF_NONE

# LLM 兜底置信档：高于 HITL 阈值（0.2）⇒ 能落 cleaned；低于 rules 的「结构清洗」0.9
# ⇒ 与规则命中在报告里可区分。
CONF_LLM = 0.85

# 适配 GPT-6 系（o 系 / GPT-5+）的新参数名。老接口是 max_tokens，这里按契约写死新名。
MAX_COMPLETION_TOKENS = 64

# provider → (base_url, API key 的环境变量名, 默认模型)。key 只从环境变量取，不读任何文件。
_PROVIDERS = {
    "deepseek": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "deepseek-chat"),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "ZHIPU_API_KEY", "glm-4-plus"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini"),
}


class LLMError(RuntimeError):
    """LLM 请求失败（非 2xx）。带状态码与响应摘要，便于排查。"""

    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"LLM 请求失败：HTTP {status} — {body[:200]}")


def build_prompt(value: str, field: str) -> str:
    """把「字段 + 原值 + 输出约束」拼成一条提示词（complete 只发这一条 user message）。"""
    return (
        f"你是中文数据清洗器，字段类型是「{field}」。\n"
        f"把下面的原始值规范化，只输出规范化后的值本身：不要解释、不要引号、不要多余文字。\n"
        f"若无法确定，就原样输出给定的原始值。\n"
        f"原始值：{value}"
    )


def _extract_content(payload: dict) -> str:
    """从 OpenAI 兼容响应里取文本；结构不对就抛异常，由 llm_normalize 兜底。"""
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise TypeError(f"响应 content 不是字符串：{content!r}")
    return content


class LLMClient:
    """OpenAI 兼容协议的极简客户端（stdlib urllib，无第三方依赖）。"""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 30):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _build_request(self, prompt: str) -> urllib.request.Request:
        """构造 POST 请求（纯函数，便于测试断言请求体，不发网络）。"""
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": MAX_COMPLETION_TOKENS,  # GPT-6 系参数名（契约写死）
            "temperature": 0,
        }
        return urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )

    def complete(self, prompt: str) -> str:
        """发一条 chat 请求，返回文本内容。非 2xx 抛 LLMError。"""
        req = self._build_request(prompt)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:            # 非 2xx（含 4xx / 5xx）
            raise LLMError(e.code, e.read().decode("utf-8", "replace")) from e
        return _extract_content(json.loads(raw.decode("utf-8")))


def llm_normalize(value: str, field: str, client) -> tuple[str, float]:
    """规则兜底：让 LLM 试着规范化 value（签名同 loop 的 `llm_fn`）。

    返回 (规范值, 置信度)：
    - LLM 给出了不同的值 ⇒ `(结果, CONF_LLM)`：可落 cleaned；
    - LLM 返回原值 / 空白 / 报错 / 解析失败 ⇒ `(原值, CONF_NONE)`：回 HITL，**不抛出**。
    """
    try:
        raw = client.complete(build_prompt(value, field))
    except Exception:                     # 网络错 / 非 200 / 解析失败 —— 一律当「没把握」
        return value, CONF_NONE
    result = raw.strip()
    if not result or result == value:
        return value, CONF_NONE           # 没改动（或空响应）⇒ 视为无把握，交人工
    return result, CONF_LLM


def client_from_env(provider: str = "deepseek") -> LLMClient:
    """按 provider 从环境变量取 key 造客户端。key **只读环境变量**，不碰任何凭据文件。"""
    try:
        base_url, key_env, model = _PROVIDERS[provider]
    except KeyError:
        raise ValueError(f"未知 provider：{provider!r}；可选 {sorted(_PROVIDERS)}") from None
    api_key = os.environ.get(key_env)
    if not api_key:
        raise RuntimeError(f"环境变量 {key_env} 未设置（provider={provider}）")
    return LLMClient(base_url, api_key, model)


# ---------------------------------------------------------------------------
# 自检（全程 mock，零网络请求）
# ---------------------------------------------------------------------------
class _MockClient:
    """假客户端：记录收到的 prompt，按预设 reply 返回（reply 是异常实例就抛）。"""

    def __init__(self, reply):
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class _FakeHTTPResponse:
    """urllib 响应的最小替身：read() 返回预设 JSON 字节。"""

    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _demo() -> None:
    """最小可运行检查：提示词 / 三分支 / 请求构造与解析 / 非 200 / 真子进程入口。"""
    # 1) 提示词含字段名、原值、输出约束
    p = build_prompt("王 小明", "person")
    assert "person" in p and "王 小明" in p and "只输出" in p, p

    # 2) LLM 给出新值 ⇒ (新值, CONF_LLM)
    assert llm_normalize("范同言", "person", _MockClient("范童言")) == ("范童言", CONF_LLM)
    # 3) LLM 返回原值（前后带空白）⇒ (原值, CONF_NONE)，回 HITL
    assert llm_normalize("范童", "person", _MockClient("  范童\n")) == ("范童", CONF_NONE)
    # 4) 空响应 ⇒ (原值, CONF_NONE)
    assert llm_normalize("范童", "person", _MockClient("   ")) == ("范童", CONF_NONE)
    # 5) 客户端报错 ⇒ (原值, CONF_NONE)，**不抛出**
    assert llm_normalize("范童", "person", _MockClient(RuntimeError("boom"))) == ("范童", CONF_NONE)

    # 6) complete() 构造对请求、解析对响应（mock urlopen，无网络）
    captured: dict = {}
    real_open = urllib.request.urlopen

    def fake_open(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["auth"] = dict(req.header_items()).get("Authorization")
        return _FakeHTTPResponse({"choices": [{"message": {"content": "范童言"}}]})

    urllib.request.urlopen = fake_open
    try:
        out = LLMClient("https://api.deepseek.com/v1", "sk-test", "deepseek-chat").complete("提示词")
    finally:
        urllib.request.urlopen = real_open
    assert out == "范童言"
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["body"]["model"] == "deepseek-chat"
    assert captured["body"]["max_completion_tokens"] == MAX_COMPLETION_TOKENS   # GPT-6 系参数名
    assert captured["body"]["messages"][0]["content"] == "提示词"
    assert captured["auth"] == "Bearer sk-test"

    # 7) 非 200 ⇒ LLMError（带状态码与响应摘要）
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {},
                                     io.BytesIO(b'{"error":"bad key"}'))

    urllib.request.urlopen = boom
    try:
        try:
            LLMClient("https://api.deepseek.com/v1", "sk-bad", "deepseek-chat").complete("p")
            raise AssertionError("非 200 应抛 LLMError")
        except LLMError as e:
            assert e.status == 401 and "bad key" in str(e)
    finally:
        urllib.request.urlopen = real_open

    print("llm._demo: OK")


if __name__ == "__main__":
    utf8_stdio()  # 用法/报错含中文，Windows 控制台默认 cp936 会写坏（TASK-015）
    # `--demo` 与无参等价（与 loop / audit / dedupe 三个入口保持一致）
    if len(sys.argv) > 1 and sys.argv[1] != "--demo":
        sys.exit(f"用法: python -m zhclean.llm [--demo]，未知参数 {sys.argv[1:]}")
    _demo()
