"""数据模型定义。

使用 SQLModel + SQLite。所有业务模型均预留 user_id / org_id 字段：
- user_id 默认 0（首期单用户），后期多用户只需加登录与过滤。
- org_id 默认 0 表示"个人/本地"，加入组织后可通过组织共享模板与术语。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Field, SQLModel

# ---- 常量 ----

# 条目状态
STATUS_PENDING = "pending"        # 待译
STATUS_TRANSLATED = "translated"  # 已译
STATUS_PROOFREAD = "proofread"    # 已校对
STATUS_REVIEW = "review"          # 需复核
STATUS_LABELS = {
    STATUS_PENDING: "待译",
    STATUS_TRANSLATED: "已译",
    STATUS_PROOFREAD: "已校对",
    STATUS_REVIEW: "需复核",
}

# 已有译文策略
STRATEGY_SKIP = "skip_existing"   # 跳过已有译文
STRATEGY_OVERWRITE = "overwrite"  # 覆盖重译
STRATEGY_LABELS = {
    STRATEGY_SKIP: "跳过已有译文",
    STRATEGY_OVERWRITE: "覆盖重译",
}

# 文本切分方式
TEXT_MODE_LINE = "line"            # 逐行
TEXT_MODE_PARAGRAPH = "paragraph"  # 按段落
TEXT_MODE_WHOLE = "whole"          # 整段
TEXT_MODE_LABELS = {
    TEXT_MODE_LINE: "逐行",
    TEXT_MODE_PARAGRAPH: "按段落",
    TEXT_MODE_WHOLE: "整段",
}

# 提示词角色
ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_LABELS = {
    ROLE_SYSTEM: "系统",
    ROLE_USER: "用户",
    ROLE_ASSISTANT: "助手",
}


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


def json_dumps(obj: Any) -> str:
    """对象序列化为 JSON 字符串。"""
    return json.dumps(obj, ensure_ascii=False)


def json_loads(text: str | None, default: Any) -> Any:
    """JSON 字符串反序列化，失败返回默认值。"""
    if not text:
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


class Project(SQLModel, table=True):
    """文件工程：一个上传文件 / 一段纯文本 = 一个工程。

    以该工程为单位围绕其进行解析、翻译、校对、产出。
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)

    name: str = Field(default="", description="工程名称（文件名或文本标题）")
    file_type: str = Field(default="text", description="来源类型：xlsx/csv/txt/text")
    source_lang: str = Field(default="zh-CN")
    target_langs: str = Field(default="", description="逗号分隔的目标语言代码列表")

    # 导入时的列映射（JSON），保留以便重新导出时还原列结构
    column_mapping: str = Field(default="", description="列映射 JSON")

    upload_time: datetime = Field(default_factory=utc_now)
    total_count: int = Field(default=0)
    translated_count: int = Field(default=0)
    proofread_count: int = Field(default=0)
    term_hit_count: int = Field(default=0)

    def get_target_lang_list(self) -> list[str]:
        """返回目标语言代码列表。"""
        return [x.strip() for x in self.target_langs.split(",") if x.strip()]

    def set_target_langs(self, langs: list[str]) -> None:
        self.target_langs = ",".join(langs)


class Entry(SQLModel, table=True):
    """条目：一行 = 一个源文案，含多个目标语言译文。

    translations 存 JSON：{"en": "...", "zh-TW": "...", ...}
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    project_id: int = Field(default=0, index=True, foreign_key="project.id")

    source_text: str = Field(default="")
    # 可选键列内容（如 ID），不翻译，导出时保留
    key_text: str = Field(default="")
    translations: str = Field(default="{}", description="JSON: {lang: text}")
    status: str = Field(default=STATUS_PENDING, index=True)
    term_hits: str = Field(default="[]", description="JSON: 命中的术语源词列表")
    sort_index: int = Field(default=0)

    def get_translations(self) -> dict[str, str]:
        return json_loads(self.translations, {})

    def set_translation(self, lang: str, text: str) -> None:
        data = self.get_translations()
        data[lang] = text
        self.translations = json_dumps(data)

    def get_translation(self, lang: str) -> str:
        return self.get_translations().get(lang, "")

    def get_term_hits(self) -> list[str]:
        return json_loads(self.term_hits, [])

    def set_term_hits(self, hits: list[str]) -> None:
        self.term_hits = json_dumps(hits)


class Language(SQLModel, table=True):
    """语言配置：可用的源语言 / 目标语言。

    采用"常用预置 + 手动添加"双轨制：
    - is_preset=True：内置常用语言，不可删除
    - is_preset=False：用户手动添加的语言，可删除
    code 全局唯一（如 zh-CN / en / ko）。
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)

    code: str = Field(default="", index=True, description="语言代码，如 zh-CN")
    name: str = Field(default="", description="语言名称，如 简体中文")
    is_preset: bool = Field(default=False, description="是否内置语言")


class TermLibrary(SQLModel, table=True):
    """命名术语库：术语的组织单元。

    一个术语库 = 一组相关术语（如"游戏技能库""装备库"）。
    导入、删除、引用都以库为单位；翻译时可选择引用某个库的术语作为约束。
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)

    name: str = Field(default="")
    description: str = Field(default="")
    # 术语源语言（触发词所属语言，如 zh-CN / zh-TW / en / ja）；空串=不限定
    source_lang: str = Field(default="", index=True, description="术语源语言代码，空=不限定")
    created_time: datetime = Field(default_factory=utc_now)


class TermEntry(SQLModel, table=True):
    """术语库条目：术语约束模式，归属于某个命名术语库。

    - source_term: 源术语（触发词）
    - translations: 多语言译法，JSON 字典 {语言代码: 译文}
    - target_term: 兼容旧数据保留的单一目标译法（默认语言，可迁移到 translations）
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)
    library_id: int = Field(default=0, index=True, description="所属术语库 id")

    source_term: str = Field(default="", index=True)
    target_term: str = Field(default="")
    translations: str = Field(default="{}", description="多语言译法 JSON")
    note: str = Field(default="")
    category: str = Field(default="", index=True)

    def get_translations(self) -> dict[str, str]:
        """返回多语言译法字典。"""
        return json_loads(self.translations, {})

    def set_translations(self, translations: dict[str, str]) -> None:
        self.translations = json_dumps(translations)


class ApiConfig(SQLModel, table=True):
    """翻译引擎 API 配置（用户可自行配置）。"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)

    engine_name: str = Field(default="", description="引擎显示名，如 GLM")
    display_name: str = Field(default="", description="自定义配置名，如 韩语专属API")
    base_url: str = Field(default="")
    api_key: str = Field(default="")
    model: str = Field(default="")
    is_default: bool = Field(default=False)
    max_concurrency: int = Field(
        default=0, description="手动并发上限，0=自动探测/不限制"
    )
    tested_concurrency: int = Field(
        default=0, description="自动探测并持久化的最优并发缓存，0=未探测"
    )


class ProjectLangConfig(SQLModel, table=True):
    """工程的"语言方案配置"行。

    一个工程 = 多行，每行一个目标语言，独立指定：
    - api_config_id      该语言用的 API（None=跟随翻译页/默认）
    - prompt_template_id 该语言用的提示词模板（None=跟随翻译页/默认）
    - term_library_id    该语言引用的术语库（None=跟随翻译页/不引用）
    - strategy           该语言翻译策略枚举（空串=跟随翻译页）
    - enabled            是否勾选参与本次翻译（默认 True，取消勾选不影响已存译文）
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)
    project_id: int = Field(default=0, index=True)

    lang: str = Field(default="", index=True)
    api_config_id: int | None = Field(default=None)
    prompt_template_id: int | None = Field(default=None)
    term_library_id: int | None = Field(default=None)
    strategy: str = Field(default="")
    enabled: bool = Field(default=True)


class LangProfile(SQLModel, table=True):
    """目标语言翻译配置：一个目标语言可独立指定 API / 提示词 / 术语库 / 策略。

    用于满足「韩语用韩语专用 API 与提示词、英语用英语专用配置」等场景。
    各字段为 None / 空串 表示「未配置，跟随翻译页或默认值」。
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)

    lang: str = Field(default="", index=True, description="目标语言代码，如 en")
    api_config_id: int | None = Field(default=None, description="该语言使用的 API 配置 id；None=跟随默认/翻译页")
    prompt_template_id: int | None = Field(default=None, description="该语言使用的提示词模板 id；None=跟随默认/翻译页")
    term_library_id: int | None = Field(default=None, description="该语言引用的术语库 id；None=跟随翻译页")
    strategy: str = Field(default="", description="该语言翻译策略枚举；空串=跟随翻译页")
    updated_time: datetime = Field(default_factory=utc_now)


class ColumnTemplate(SQLModel, table=True):
    """列映射模板：保存常用列结构，下次导入一键套用。"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)

    name: str = Field(default="")
    role_by_column: str = Field(default="{}", description="JSON: {列名: 角色}")
    target_strategy: str = Field(default="{}", description="JSON: {语言: 策略}")
    auto_detected: bool = Field(default=False)


class Org(SQLModel, table=True):
    """组织：用于模板 / 术语库的组织内共享。

    通过 join_code 邀请码加入组织，加入后即可使用该组织的共享资源。
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)
    created_by: int = Field(default=0, index=True, description="创建者 user_id")
    name: str = Field(default="")
    join_code: str = Field(default="", index=True, description="组织邀请码")
    created_time: datetime = Field(default_factory=utc_now)


class PromptTemplate(SQLModel, table=True):
    """提示词模板：多角色消息序列。

    messages 存 JSON：
        [{"role": "system", "content": "...{变量}..."},
         {"role": "user", "content": "...{source_text}..."}]
    翻译时将 {变量} 替换为实际值后提交给 /chat/completions。
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=0, index=True)
    org_id: int = Field(default=0, index=True)

    name: str = Field(default="")
    description: str = Field(default="")
    messages: str = Field(default="[]", description="JSON 多角色消息序列")
    is_default: bool = Field(default=False)

    def get_messages(self) -> list[dict[str, str]]:
        msgs = json_loads(self.messages, [])
        # 保证每条消息含 role 与 content 字段
        return [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in msgs
            if isinstance(m, dict)
        ]

    def set_messages(self, messages: list[dict[str, str]]) -> None:
        self.messages = json_dumps(messages)
