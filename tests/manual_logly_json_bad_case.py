"""运行：uv run python tests/manual_logly_json_bad_case.py"""

import json

from logly import logger


payload = {
    "messages": [{"role": "user", "content": "hello"}],
    "text": "before [hello] after",
    "end": "END",
}
json_text = json.dumps(payload, ensure_ascii=False, indent=2)

# print 仅用于这个复现脚本的原文对照，避免原文也被日志处理改变。
print("原始 JSON：", flush=True)
print(json_text, flush=True)

logger.opt(raw=True).info(json_text)

logger.remove()
logger.add("stdout", format="{message}", colorize=False)
logger.info("logly 实际输出：\n{}", json_text)
logger.complete()
