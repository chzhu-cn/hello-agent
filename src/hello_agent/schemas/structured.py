"""E04：明确偏好提取结果，结构校验不代替事实验收。"""

from pydantic import BaseModel, ConfigDict, Field


class ColorPreference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    favorite_color: str | None = Field(
        description="用户明确说出的最喜欢颜色；未提供则为 null"
    )


COLOR_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "color_preference",
        "strict": True,
        "schema": ColorPreference.model_json_schema(),
    },
}
