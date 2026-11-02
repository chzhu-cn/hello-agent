"""工具中断恢复：uv run python -m hello_agent.sdk.e09_recovery.execution"""

import argparse
import os

from logly import logger
from pydantic import ValidationError

from hello_agent.config.settings import checkpoint_config, ledger_config
from hello_agent.tools.checkpoint import load_approval
from hello_agent.tools.ledger import PaymentLedger
from hello_agent.tools.recovery import execute_saved, prepare_execution, recover_execution


def main() -> None:
    parser = argparse.ArgumentParser(description="E09-B 保存执行阶段并恢复原操作")
    parser.add_argument("action", nargs="?", default="recover", choices=["execute", "recover"])
    parser.add_argument("--crash-at", choices=["before-call", "after-call"], help="测试专用：在指定位置立即退出当前进程")
    args = parser.parse_args()
    if args.crash_at and args.action != "execute":
        parser.error("故障注入只用于 execute")
    path = checkpoint_config.execution_path

    def interrupt(stage: str) -> None:
        if stage == args.crash_at:
            # 仅终止当前实验进程，已完成的文件或账本提交不会撤销。
            os._exit(73)

    if args.action == "execute":
        try:
            approval = load_approval(checkpoint_config.path)
        except FileNotFoundError:
            logger.error("审批检查点不存在：{}。请先运行 hello_agent.sdk.e09_recovery.local 完成审批。", checkpoint_config.path)
            raise SystemExit(1) from None
        except ValidationError:
            logger.error(
                "审批检查点校验失败：{}。请检查状态与批准 ID 是否一致，或从可信备份恢复；未执行工具。",
                checkpoint_config.path,
            )
            raise SystemExit(1) from None
        if approval.status != "approved":
            logger.error("当前审批状态为 {}。请先运行 hello_agent.sdk.e09_recovery.local，查看参数后输入 a 批准。", approval.status)
            raise SystemExit(1)
        prepare_execution(path, approval)
        ledger = PaymentLedger(ledger_config.path)
        result = execute_saved(path, ledger, interrupt=interrupt)
    else:
        ledger = PaymentLedger(ledger_config.path)
        result = recover_execution(path, ledger)
    logger.info("恢复状态：{}；操作 ID：{}；原因：{}", result.phase, result.proposal.id, result.reason)
    logger.info("当前模拟账本共 {} 笔", ledger.count())


if __name__ == "__main__":
    main()
