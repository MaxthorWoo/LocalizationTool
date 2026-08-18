"""工程的"语言方案配置"服务（ProjectLangConfig）。

每个工程维护一组语言方案行，每行 = 一个目标语言 + 该语言专用的
API / 提示词模板 / 术语库 / 翻译策略。校对页上方按此渲染方案表，
条目表格的列也由这些语言决定。
"""
from __future__ import annotations

from sqlmodel import select

from localization import config
from localization.db import session_scope
from localization.models import ProjectLangConfig


def list_configs(project_id: int, user_id: int = config.DEFAULT_USER_ID) -> list[ProjectLangConfig]:
    with session_scope() as s:
        stmt = (
            select(ProjectLangConfig)
            .where(
                ProjectLangConfig.project_id == project_id,
                ProjectLangConfig.user_id == user_id,
            )
            .order_by(ProjectLangConfig.id)
        )
        return list(s.exec(stmt).all())


def get_config(project_id: int, lang: str, user_id: int = config.DEFAULT_USER_ID) -> ProjectLangConfig | None:
    with session_scope() as s:
        stmt = select(ProjectLangConfig).where(
            ProjectLangConfig.project_id == project_id,
            ProjectLangConfig.user_id == user_id,
            ProjectLangConfig.lang == lang,
        )
        return s.exec(stmt).first()


def upsert_config(
    project_id: int,
    lang: str,
    *,
    api_config_id: int | None = None,
    prompt_template_id: int | None = None,
    term_library_id: int | None = None,
    strategy: str = "",
    enabled: bool = True,
    user_id: int = config.DEFAULT_USER_ID,
) -> ProjectLangConfig:
    """按 (project, lang) 创建或更新一行方案配置。"""
    with session_scope() as s:
        stmt = select(ProjectLangConfig).where(
            ProjectLangConfig.project_id == project_id,
            ProjectLangConfig.user_id == user_id,
            ProjectLangConfig.lang == lang,
        )
        row = s.exec(stmt).first()
        if row is None:
            row = ProjectLangConfig(project_id=project_id, user_id=user_id, lang=lang)
            s.add(row)
        row.api_config_id = api_config_id
        row.prompt_template_id = prompt_template_id
        row.term_library_id = term_library_id
        row.strategy = strategy
        row.enabled = enabled
        s.flush()
        s.refresh(row)
        return row


def get_config_by_id(config_id: int, user_id: int = config.DEFAULT_USER_ID) -> ProjectLangConfig | None:
    with session_scope() as s:
        stmt = select(ProjectLangConfig).where(
            ProjectLangConfig.id == config_id,
            ProjectLangConfig.user_id == user_id,
        )
        return s.exec(stmt).first()


def delete_config(config_id: int) -> bool:
    with session_scope() as s:
        row = s.get(ProjectLangConfig, config_id)
        if row is None:
            return False
        s.delete(row)
        return True


def set_enabled(config_id: int, enabled: bool) -> bool:
    with session_scope() as s:
        row = s.get(ProjectLangConfig, config_id)
        if row is None:
            return False
        row.enabled = enabled
        s.add(row)
        return True


def sync_from_project(
    project_id: int,
    langs: list[str],
    user_id: int = config.DEFAULT_USER_ID,
) -> None:
    """把工程的目标语言列表同步为方案行（幂等）：
    旧数据 / 表格导入列映射产生的语言 → 自动生成方案行（默认配置）。
    """
    for lang in langs:
        if get_config(project_id, lang, user_id) is None:
            upsert_config(project_id, lang, user_id=user_id)


def serialize_config(row: ProjectLangConfig) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "lang": row.lang,
        "api_config_id": row.api_config_id,
        "prompt_template_id": row.prompt_template_id,
        "term_library_id": row.term_library_id,
        "strategy": row.strategy,
        "enabled": row.enabled,
    }
