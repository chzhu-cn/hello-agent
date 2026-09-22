"""E01-B：按会话读取 JSON，通过同目录临时文件替换旧历史。"""

from pathlib import Path
from tempfile import NamedTemporaryFile

from hello_agent.schemas.memory import Conversation, SessionKey


def session_path(directory: Path, name: str) -> Path:
    key = SessionKey(name=name)
    return directory / f"session-{key.name}.json"


def load_session(directory: Path, name: str) -> Conversation:
    path = session_path(directory, name)
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Conversation()
    return Conversation.model_validate_json(content)


def save_session(directory: Path, name: str, session: Conversation) -> None:
    path = session_path(directory, name)
    content = Conversation.model_validate(session.model_dump()).model_dump_json(
        indent=2
    )
    write_memory_json(path, content)


def write_memory_json(path: Path, content: str) -> None:
    """完整写入临时文件后替换目标；失败时清理临时文件。"""
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
