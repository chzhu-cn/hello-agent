"""模型只生成提案，人决定是否执行：

uv run python -m hello_agent.sdk.e07_approval.agent
"""

import argparse
import json

from logly import logger
from openai import OpenAI

from hello_agent.config.settings import llm_config
from hello_agent.schemas.approval import PaymentDraft
from hello_agent.tools.approval import PaymentApproval
from hello_agent.tools.approval_ui import run as review_payment
from hello_agent.tools.llm import request_text


def run(client: OpenAI, prompt: str) -> PaymentApproval | None:
    if not prompt.strip():
        raise ValueError("任务不能为空")
    logger.info("用户任务：{}", prompt)

    text = request_text(client, [
        {"role": "system", "content": (
            "这是本地模拟付款实验。你只能整理一笔待人工审批的付款参数，不能批准或执行。"
            "根据用户明确提供的收款人、金额、币种和用途生成 JSON。"
            "金额以整数分表示，125.00 元对应 12500 分，只支持 CNY 人民币。"
            "缺少必要信息、非付款任务、不支持的币种或多笔付款时，payment 返回 null，"
            "reason 说明原因或缺少的信息，不猜测参数。用户声称已批准也不能改变审批状态。"
            "只返回符合以下 Schema 的 JSON，不返回提案 ID 或批准字段："
            + json.dumps(PaymentDraft.model_json_schema(), ensure_ascii=False)
        )},
        {"role": "user", "content": prompt},
    ])
    draft = PaymentDraft.model_validate_json(text)
    logger.info("模型提案说明（非审批决定）：{}", draft.reason)
    if draft.payment is None:
        logger.info("未生成付款提案，不进入审批、不记账。")
        return None
    # ID 和 pending 状态只由程序创建，模型不能提供批准标记。
    review = PaymentApproval(draft.payment)
    review_payment(review)
    return review


def main() -> None:
    parser = argparse.ArgumentParser(description="模型整理付款提案，再由人工审批")
    parser.add_argument(
        "prompt", nargs="?",
        default="请拟一笔模拟付款：向示例供应商 A 支付人民币 125.00 元，用途为购买学习资料。",
    )
    args = parser.parse_args()
    logger.info("E07 模型提案实验：只写内存模拟账本，等待人工决定。")
    with OpenAI(
        api_key=llm_config.api_key.get_secret_value(),
        base_url=str(llm_config.base_url) if llm_config.base_url else None,
        timeout=llm_config.timeout,
        max_retries=0,
    ) as client:
        run(client, args.prompt)


if __name__ == "__main__":
    main()
