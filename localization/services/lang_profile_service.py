"""目标语言翻译配置（LangProfile）服务。

实现「按目标语言独立配置 API / 提示词模板 / 术语库 / 策略」：
- 每个目标语言一行配置；
- 翻译时若某语言存在配置，优先使用其专用配置；
- 未配置的项跟随翻译页工具栏的当前选择或默认值。
"""
from __future__ import annotations

from sqlmodel import select

from localization import config
from localization.db import session_scope
from localization.models import LangProfile


def get_profile(lang: str, user_id: int = config.DEFAULT_USER_ID) -> LangProfile | None:
    """按目标语言代码取配置。"""
    with session_scope() as s:
        stmt = select(LangProfile).where(
            LangProfile.user_id == user_id, LangProfile.lang == lang
        )
        return s.exec(stmt).first()


def list_profiles(user_id: int = config.DEFAULT_USER_ID) -> list[LangProfile]:
    """列出全部语言配置。"""
    with session_scope() as s:
        stmt = select(LangProfile).where(LangProfile.user_id == user_id).order_by(LangProfile.lang)
        return list(s.exec(stmt).all())


def upsert_profile(
    lang: str,
    api_config_id: int | None = None,
    prompt_template_id: int | None = None,
    term_library_id: int | None = None,
    strategy: str = "",
    user_id: int = config.DEFAULT_USER_ID,
) -> LangProfile:
    """按语言 upsert：已存在则更新，否则新建。"""
    with session_scope() as s:
        stmt = select(LangProfile).where(
            LangProfile.user_id == user_id, LangProfile.lang == lang
        )
        prof = s.exec(stmt).first()
        if prof is None:
            prof = LangProfile(user_id=user_id, lang=lang)
            s.add(prof)
        prof.api_config_id = api_config_id or None
        prof.prompt_template_id = prompt_template_id or None
        prof.term_library_id = term_library_id or None
        prof.strategy = strategy or ""
        s.flush()
        s.refresh(prof)
        return prof


def delete_profile(profile_id: int) -> bool:
    with session_scope() as s:
        p = s.get(LangProfile, profile_id)
        if p is None:
            return False
        s.delete(p)
        return True


def resolve_lang_config(
    lang: str,
    *,
    manual_api_config_id: int = 0,
    manual_template_id: int = 0,
    manual_term_library_id: int = 0,
    manual_strategy: str = "",
    user_id: int = config.DEFAULT_USER_ID,
) -> dict:
    """解析某目标语言的实际翻译配置（优先级从高到低）。

    - API：翻译页手动指定 > 语言 profile > 默认 API（用户明确要求翻译页可覆盖 API）
    - 提示词 / 术语库 / 策略：语言 profile > 翻译页当前选择（profile 更专用，优先）
    """
    prof = get_profile(lang, user_id=user_id)
    return {
        "lang": lang,
        "api_config_id": manual_api_config_id
        or (prof.api_config_id if prof else None),
        "prompt_template_id": (prof.prompt_template_id if prof else None)
        or manual_template_id,
        "term_library_id": (prof.term_library_id if prof else None)
        or manual_term_library_id,
        "strategy": (prof.strategy if prof else "") or manual_strategy,
    }


def serialize_profile(p: LangProfile) -> dict:
    return {
        "id": p.id,
        "lang": p.lang,
        "api_config_id": p.api_config_id,
        "prompt_template_id": p.prompt_template_id,
        "term_library_id": p.term_library_id,
        "strategy": p.strategy,
    }
