"""E03-A：复用 E01 chat，六道固定题，规则判分。"""

from time import perf_counter

from logly import logger
from openai import APIError, OpenAI

from hello_agent.config.settings import llm_config
from hello_agent.schemas.evaluation import EvaluationCase, EvaluationResult
from hello_agent.schemas.memory import Conversation, ConversationMessage
from hello_agent.sdk.e01_memory.agent import SYSTEM_PROMPT, chat


def cases() -> list[EvaluationCase]:
    question = "我最喜欢什么颜色？仅输出颜色名称；没有明确记录时仅输出不知道。"
    examples = [
        ("记住颜色", ["我最喜欢青绿色。"], "青绿色"),
        (
            "更新偏好",
            ["我最喜欢红色。", "现在我最喜欢蓝色，之前的偏好不再适用。"],
            "蓝色",
        ),
        ("新会话隔离", [], "不知道"),
        ("无关历史", ["今天练习加法。"], "不知道"),
        ("否定不是偏好", ["我不喜欢红色，还没告诉你我最喜欢什么颜色。"], "不知道"),
        ("跨轮追问", ["我最喜欢紫色。", "今天整理了书桌。", "我刚学了加法。"], "紫色"),
    ]
    return [
        EvaluationCase(
            name=name,
            question=question,
            expected=expected,
            history=Conversation(
                messages=[
                    message
                    for text in texts
                    for message in (
                        ConversationMessage(role="user", content=text),
                        ConversationMessage(role="assistant", content="收到。"),
                    )
                ]
            ),
        )
        for name, texts, expected in examples
    ]


def grade(answer: str, expected: str) -> bool:
    # 严格短答案契约：只忽略首尾空白和末尾句号，不用关键词包含判分。
    return answer.strip().rstrip("。.").strip() == expected


def evaluate(client: OpenAI, items: list[EvaluationCase]) -> list[EvaluationResult]:
    results = []
    for case in items:
        print(
            f"案例 {case.name}：system={SYSTEM_PROMPT}；历史={case.history.model_dump_json()}；问题={case.question}"
        )
        started = perf_counter()
        answer, error = None, None
        try:
            answer = chat(client, case.history.model_copy(deep=True), case.question)
        except (APIError, ValueError) as exc:
            error = type(exc).__name__
        result = EvaluationResult(
            name=case.name,
            expected=case.expected,
            answer=answer,
            completed=answer is not None,
            passed=answer is not None and grade(answer, case.expected),
            error=error,
            requests=1,
            elapsed_seconds=round(perf_counter() - started, 3),
        )
        results.append(result)
        logger.info("评估结果：{}", result.model_dump_json())
    logger.info(
        "汇总：共 {} 题，完成 {}，规则通过 {}，请求尝试 {}，工具执行 0。",
        len(results),
        sum(r.completed for r in results),
        sum(r.passed for r in results),
        sum(r.requests for r in results),
    )
    return results


def main() -> None:
    if llm_config.base_url is None:
        logger.error("请配置 LLM_BASE_URL。")
        raise SystemExit(1)
    logger.info(
        "E03-A 固定案例 v1；模型 {}；每题一次请求，无工具，无自动重试。",
        llm_config.model,
    )
    with OpenAI(
        api_key=llm_config.api_key.get_secret_value(),
        base_url=str(llm_config.base_url),
        timeout=llm_config.timeout,
        max_retries=0,
    ) as client:
        results = evaluate(client, cases())
    if not all(result.passed for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
