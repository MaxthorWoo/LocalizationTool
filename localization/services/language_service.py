"""语言服务：语言配置的查询与增删（常用预置 + 手动添加双轨制）。"""
from __future__ import annotations

from sqlmodel import select

from .. import config
from ..db import session_scope
from ..models import Language

# 内置语言的中文名称（code -> 名称），用于初始化预置语言
PRESET_LANG_NAMES = {
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "th": "泰语",
    "id": "印尼语",
    "vi": "越南语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
    "pt": "葡萄牙语",
    "ru": "俄语",
    "ar": "阿拉伯语",
}


def init_preset_languages(
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> None:
    """初始化内置常用语言（仅当语言表为空时执行，避免重复）。"""
    with session_scope() as s:
        existing = s.exec(select(Language)).first()
        if existing is not None:
            return
        for code in config.AVAILABLE_LANG_CODES:
            s.add(
                Language(
                    user_id=user_id,
                    org_id=org_id,
                    code=code,
                    name=PRESET_LANG_NAMES.get(code, code),
                    is_preset=True,
                )
            )


def _all_langs(
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> list[Language]:
    with session_scope() as s:
        stmt = select(Language).where(
            (Language.user_id == user_id) | (Language.org_id == org_id)
        ).order_by(Language.is_preset.desc(), Language.id.asc())
        return list(s.exec(stmt).all())


def list_languages(
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> list[dict]:
    """返回语言列表（内置在前，自定义在后）。"""
    return [
        {
            "id": l.id,
            "code": l.code,
            "name": l.name,
            "is_preset": l.is_preset,
        }
        for l in _all_langs(user_id, org_id)
    ]


def get_lang_codes(
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> list[str]:
    """返回全部可用语言代码（供前端下拉、语言猜测）。"""
    return [l.code for l in _all_langs(user_id, org_id)]


def add_language(
    code: str,
    name: str,
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> tuple[Language | None, str]:
    """添加自定义语言。返回 (语言对象或 None, 错误信息)。"""
    code = (code or "").strip()
    name = (name or "").strip()
    if not code or not name:
        return None, "语言代码与名称不能为空"
    # 代码统一转小写，便于唯一性判断
    code_lower = code.lower()
    with session_scope() as s:
        exists = s.exec(
            select(Language).where(
                (Language.code == code_lower)
                | (Language.code == code)
            )
        ).first()
        if exists is not None:
            if exists.is_preset:
                return None, f"该语言代码「{code}」已是内置语言，无需重复添加"
            return None, f"语言代码「{code}」已存在"
        lang = Language(
            user_id=user_id,
            org_id=org_id,
            code=code,
            name=name,
            is_preset=False,
        )
        s.add(lang)
        return lang, ""


def delete_language(
    lang_id: int,
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> tuple[bool, str]:
    """删除自定义语言。内置语言不可删除。"""
    with session_scope() as s:
        lang = s.get(Language, lang_id)
        if lang is None:
            return False, "语言不存在"
        if lang.is_preset:
            return False, "内置语言不可删除"
        s.delete(lang)
        return True, ""
