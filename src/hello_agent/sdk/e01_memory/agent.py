"""E01-A：保留已完成的对话轮次，体验进程内会话。"""

import argparse
from time import perf_counter

from logly import logger
from openai import APIError, OpenAI

from hello_agent.config.settings import llm_config
from hello_agent.schemas.memory import Conversation, ConversationMessage
from hello_agent.tools.llm import request_text

SYSTEM_PROMPT = "根据当前会话回答。用户未提供的信息请明确说不知道，不猜测其偏好。用简短中文回答。"


def chat(client: OpenAI, session: Conversation, prompt: str) -> str:
    user_message = ConversationMessage(role="user", content=prompt.strip())
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *[message.model_dump() for message in session.messages],
        user_message.model_dump(),
    ]
    logger.info("发送历史 {} 条，加上系统说明与本轮输入；模型请求 1 次。", len(session.messages))
    started = perf_counter()
    answer = request_text(client, messages)
    assistant_message = ConversationMessage(role="assistant", content=answer)
    session.messages.extend([user_message, assistant_message])
    logger.success("回复：{}", answer)
    logger.info("本轮耗时 {:.2f} 秒；会话已保存 {} 条消息。", perf_counter() - started, len(session.messages))
    return answer


def demo(client: OpenAI) -> None:
    session_a = Conversation()
    logger.info("会话 A：提供虚构偏好，再追问。")
    chat(client, session_a, "本次虚构角色扮演中，我最喜欢的颜色是青绿色。")
    chat(client, session_a, "我最喜欢什么颜色？")
    logger.info("会话 B：新建会话，询问同样的问题。")
    chat(client, Conversation(), "我最喜欢什么颜色？")


def main() -> None:
    parser = argparse.ArgumentParser(description="E01-A 进程内会话；默认固定演示")
    parser.add_argument("--interactive", action="store_true", help="连续输入；/new 新会话，/exit 退出")
    args = parser.parse_args()
    if llm_config.base_url is None:
        logger.error("请配置 LLM_BASE_URL。")
        raise SystemExit(1)
    try:
        with OpenAI(
            api_key=llm_config.api_key.get_secret_value(), base_url=str(llm_config.base_url),
            timeout=llm_config.timeout, max_retries=0,
        ) as client:
            if not args.interactive:
                demo(client)
                return
            session = Conversation()
            logger.info("输入内容后回车；/new 新建会话，/exit 退出。历史仅保存在本次进程中。")
            while True:
                logger.info("请输入：")
                prompt = input().strip()
                if prompt == "/exit":
                    return
                if prompt == "/new":
                    session = Conversation()
                    logger.info("已新建空会话。")
                    continue
                if not prompt:
                    continue
                try:
                    chat(client, session, prompt)
                except (APIError, ValueError) as exc:
                    logger.error("本轮失败（{}），未保存该轮，不自动重试。", type(exc).__name__)
    except (EOFError, KeyboardInterrupt):
        logger.info("会话结束，进程内历史不保存到磁盘。")
    except (APIError, ValueError) as exc:
        logger.error("演示失败：{}。", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
