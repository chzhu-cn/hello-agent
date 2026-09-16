"""E01-C：只保存用户明确设置的偏好，不从聊天自动提取。"""

from pathlib import Path

from hello_agent.schemas.memory import PreferenceChange, Preferences, SessionKey
from hello_agent.tools.memory import write_memory_json


def preference_path(directory: Path, profile: str) -> Path:
    key = SessionKey(name=profile)
    return directory / f"preferences-{key.name}.json"


def load_preferences(directory: Path, profile: str) -> Preferences:
    path = preference_path(directory, profile)
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Preferences()
    return Preferences.model_validate_json(content)


def update_preference(directory: Path, profile: str, key: str, value: str | None) -> Preferences:
    current = load_preferences(directory, profile)
    # None 表示删除，空字符串不代表删除。
    change = PreferenceChange(key=key, value=value)
    values = current.values.copy()
    if value is None:
        values.pop(change.key, None)
    else:
        values[change.key] = change.value
    updated = Preferences(values=values)
    write_memory_json(preference_path(directory, profile), updated.model_dump_json(indent=2))
    return updated
