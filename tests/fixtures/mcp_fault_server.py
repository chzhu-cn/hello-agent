"""测试专用子进程：参数校验通过后，在 add 内注入一次故障。"""

import argparse
import asyncio
import os

from hello_agent.sdk.e05_mcp import server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["raise", "disconnect"])
    mode = parser.parse_args().mode
    original_add = server.add

    def fail_once(a: float, b: float) -> float:
        server.add = original_add
        if mode == "disconnect":
            # 只终止当前测试子进程，不发送工具响应，模拟执行中服务崩溃。
            os._exit(7)
        raise RuntimeError("injected add execution failure")

    server.add = fail_once
    asyncio.run(server.main())


if __name__ == "__main__":
    main()
