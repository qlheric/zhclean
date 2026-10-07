"""LLM API 兜底客户端（可插拔）。

F: 规则低置信时走 LLM 语义清洗；OpenAI 兼容协议（deepseek/qwen）
R: loop.py（think 阶段调用）
A: 被 loop.py 调用
S: GPT-6 系列用 max_completion_tokens；单条失败不得中断整体
"""
