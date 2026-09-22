"""P2：生成计划，解析依赖，执行共享工具，再汇总。"""

import argparse
import json
from time import perf_counter

from logly import logger
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import ValidationError

from hello_agent.config.settings import llm_config, planning_config
from hello_agent.schemas.planning import Plan, StepReference, StepResult
from hello_agent.schemas.tools import AddArguments
from hello_agent.tools.arithmetic import add
from hello_agent.tools.llm import request_text


def execute(plan: Plan) -> list[StepResult]:
    results = {}
    records = []
    for step in plan.steps:
        a = results[step.a.step] if isinstance(step.a, StepReference) else step.a
        b = results[step.b.step] if isinstance(step.b, StepReference) else step.b
        arguments = AddArguments(a=a, b=b)
        logger.info("执行 {}：add({}, {})", step.id, arguments.a, arguments.b)
        try:
            result = add(arguments.a, arguments.b)
        except Exception:
            raise ValueError("工具执行失败，停止；不自动重新执行计划。") from None
        results[step.id] = result
        records.append(StepResult(step=step.id, result=result))
        logger.info("步骤 {} 结果：{}", step.id, result)
    return records


def run(client: OpenAI, prompt: str) -> str:
    if not prompt.strip():
        raise ValueError("输入不能为空。")
    started = perf_counter()
    requests = 0
    messages = [
        {
            "role": "system",
            "content": (
                "请生成可执行的加法计划，只输出 JSON，不加 Markdown。"
                '只允许 add；需要前一步结果时用 {"step":"步骤ID"} 引用，不能预先心算替代。'
                "步骤按依赖顺序排列；无需计算时 steps 为空；不支持的计算不要伪造为加法。"
                f"最多 {planning_config.max_steps} 步。JSON Schema："
                + json.dumps(Plan.model_json_schema(), ensure_ascii=False)
            ),
        },
        {"role": "user", "content": prompt},
    ]
    print(f"Messages: {messages}")
    for attempt in range(planning_config.max_repairs + 1):
        logger.info("生成计划，第 {} 次尝试。", attempt + 1)
        requests += 1
        text = request_text(client, messages)
        try:
            plan = Plan.model_validate_json(text)
            if len(plan.steps) > planning_config.max_steps:
                raise ValueError("计划超过最大步骤数。")
            break
        except ValueError:
            if attempt == planning_config.max_repairs:
                raise ValueError("计划校验失败且修正次数已耗尽；未执行工具。") from None
            logger.warning("计划无效，请求模型修正；尚未执行工具。")
            messages.extend(
                [
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": (
                            "计划校验失败。请检查 JSON、唯一 ID、仅引用前序步骤、add 参数类型与范围，"
                            f"以及最多 {planning_config.max_steps} 步的限制。重新输出完整 JSON。"
                        ),
                    },
                ]
            )
    print(f"已验证计划：{plan.model_dump_json()}")
    records = execute(plan)
    requests += 1
    answer = request_text(
        client,
        [
            {
                "role": "system",
                "content": "根据原始任务、计划及真实执行结果用中文回答。没有工具结果时不要声称执行过工具；不支持的任务应说明限制。",
            },
            {"role": "user", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "plan": plan.model_dump(),
                        "results": [record.model_dump() for record in records],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    logger.success("最终回答：\n{}", answer)
    logger.info(
        "正常完成：模型请求 {} 次，工具执行 {} 次，耗时 {:.2f} 秒。",
        requests,
        len(records),
        perf_counter() - started,
    )
    return answer


def main() -> None:
    parser = argparse.ArgumentParser(description="体验先规划再执行")
    parser.add_argument(
        "prompt", nargs="?", default="先计算 127 加 358，再将前一步结果加上 96。"
    )
    args = parser.parse_args()
    if llm_config.base_url is None:
        logger.error("请配置 LLM_BASE_URL。")
        raise SystemExit(1)
    try:
        with OpenAI(
            api_key=llm_config.api_key.get_secret_value(),
            base_url=str(llm_config.base_url),
            timeout=llm_config.timeout,
            max_retries=0,
        ) as client:
            run(client, args.prompt)
    except APITimeoutError:
        logger.error("停止原因：模型请求超时。")
        raise SystemExit(1) from None
    except APIConnectionError:
        logger.error("停止原因：模型连接失败。")
        raise SystemExit(1) from None
    except APIStatusError as exc:
        logger.error("停止原因：模型服务返回 HTTP {}。", exc.status_code)
        raise SystemExit(1) from None
    except ValidationError:
        logger.error("停止原因：执行参数无效，可能是前一步结果超过允许范围。")
        raise SystemExit(1) from None
    except ValueError as exc:
        logger.error("停止原因：{}", exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
