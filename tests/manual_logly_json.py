"""独立复现 logly JSON 输出；不加载项目配置，不请求模型。

运行：uv run python tests/manual_logly_json.py
全部内容为虚构数据，未实现 PII 脱敏。
"""

import json
from importlib.metadata import version

from logly import logger


def main() -> None:
    payload = {
        "user": {"name": "测试用户", "email": "demo@example.invalid"},
        "messages": [
            {"role": "user", "content": "我最喜欢青绿色。"},
            {"role": "assistant", "content": "收到。"},
        ],
        "tools": [{"name": "add", "arguments": {"a": 2, "b": 3}}],
        "enabled": True,
        "error": None,
        "text": '花括号 {name}、引号 "hello"、换行\n第二行',
        "end_marker": "JSON_END_123",
    }
    compact = json.dumps(payload, ensure_ascii=False)
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    logger.info("logly 版本：{}；所有数据均为虚构。", version("logly"))

    # 先保留默认 logger 配置，复现业务代码中的调用方式。
    for name, operation in [
        ("1 字典作为参数", lambda: logger.info("payload={}", payload)),
        ("2 JSON 字符串作为参数", lambda: logger.info("payload={}", compact)),
        ("3 缩进 JSON 作为参数", lambda: logger.info("payload=\n{}", pretty)),
        ("4 f-string", lambda: logger.info(f"payload={compact}")),
        ("5 raw 跳过消息格式化", lambda: logger.opt(raw=True).info(pretty)),
    ]:
        logger.info("案例：{}", name)
        try:
            operation()
        except Exception as exc:
            logger.error("本案例异常：{} {}", type(exc).__name__, str(exc))

    # 后两项替换输出配置，仅影响这个独立进程。
    logger.complete()
    logger.remove()
    sink = logger.add("stdout", serialize=True, colorize=False)
    logger.bind(payload=payload).info("6 bind 字典 + serialize")
    logger.complete()
    logger.remove(sink)
    logger.add("stdout", serialize=True, pretty_json=True, colorize=False)
    logger.bind(payload=payload).info("7 bind 字典 + pretty_json")
    logger.complete()


if __name__ == "__main__":
    main()
