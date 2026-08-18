"""列映射模块：列语义角色、语言自动猜测、映射模板序列化与 CRUD。

不写死列名。表格的每一列在导入时被指认为一种"语义角色"：
- source                源文案列（待翻译内容）
- key                   键列（唯一标识，不翻译）
- ignore                忽略列（不参与翻译）
- target_<lang_code>    目标语言列（译文写入，lang_code 为语言代码，如 en、zh-TW）

用户可手动指认，也可将映射保存为模板复用。
"""
from __future__ import annotations

import re
from typing import Any

from sqlmodel import Session, select

from .. import config
from ..db import session_scope
from ..models import ColumnTemplate, json_dumps, json_loads

# ---- 列语义角色 ----
ROLE_SOURCE = "source"
ROLE_KEY = "key"
ROLE_IGNORE = "ignore"

# 语言代码 -> 匹配关键词（列名中出现的标记）
# 顺序即优先级：先匹配到的语言优先。
# 注意：避免使用过于泛的单词（如单独的中文"文"、单字母代码 en/ja/ko/id 等），
# 以防误判。明确语言词汇与带连字符的代码优先。
LANG_DETECT: dict[str, list[str]] = {
    "zh-TW": ["繁體中文", "繁體", "繁体", "繁中", "正體", "正体", "zh-tw", "zh_tw", "zh-TW", "zht"],
    "zh-CN": ["简体中文", "簡體中文", "简体", "简中", "汉语", "zh-cn", "zh_cn", "zh-CN", "zhs"],
    "en": ["美式英語", "美式英语", "英語", "英语", "英文", "en-us", "en_us", "en-US", "english"],
    "ja": ["日本語", "日语", "日文", "jpn", "ja-jp", "ja_jp", "ja-JP", "japanese"],
    "ko": ["韓語", "韩语", "韓文", "韩文", "korean", "ko-kr", "ko_kr", "ko-KR"],
    "th": ["泰語", "泰语", "thai", "th-th", "th_th", "th-TH"],
    "id": ["印尼語", "印尼语", "印尼", "indonesian", "id-id", "id_id", "id-ID"],
    "vi": ["越南語", "越南语", "越南", "vietnamese", "vi-vn", "vi_vn", "vi-VN"],
    "fr": ["法語", "法语", "法文", "french", "fr-fr", "fr_fr", "fr-FR"],
    "de": ["德語", "德语", "德文", "german", "de-de", "de_de", "de-DE"],
    "es": ["西班牙語", "西班牙语", "西語", "西语", "spanish", "es-es", "es_es", "es-ES"],
    "pt": ["葡萄牙語", "葡萄牙语", "葡語", "葡语", "portuguese", "pt-br", "pt_br", "pt-BR"],
    "ru": ["俄語", "俄语", "俄文", "russian", "ru-ru", "ru_ru", "ru-RU"],
    "ar": ["阿拉伯語", "阿拉伯语", "阿拉伯", "arabic", "ar-sa", "ar_sa", "ar-SA"],
}

# 键列识别关键词
KEY_HINTS = ["id", "编号", "編號", "键", "鍵", "key", "code", "代码", "代碼", "序号", "序號"]

# 忽略列识别关键词
IGNORE_HINTS = ["备注", "備註", "note", "注释", "註釋", "说明", "說明", "remark", "comment"]


def detect_lang_in_column(column_name: str) -> str | None:
    """从列名中识别语言代码。未识别返回 None。"""
    name = column_name.strip().lower()
    for lang, hints in LANG_DETECT.items():
        for hint in hints:
            if hint.lower() in name:
                return lang
    return None


def _looks_like_key(column_name: str) -> bool:
    name = column_name.strip().lower()
    return any(h.lower() in name for h in KEY_HINTS)


def _looks_like_ignore(column_name: str) -> bool:
    name = column_name.strip().lower()
    return any(h.lower() in name for h in IGNORE_HINTS)


def guess_column_roles(
    headers: list[str], source_lang: str = config.DEFAULT_SOURCE_LANG
) -> dict[str, str]:
    """自动猜测每列的语义角色。

    返回 {列名: 角色}。规则：
    1. 命中源语言标记的列 -> source
    2. 命中其他语言标记的列 -> target_<lang>
    3. 命中键/忽略标记的列 -> key / ignore
    4. 其余 -> ignore（保守处理，避免误当源文案）
    """
    roles: dict[str, str] = {}
    source_lower = source_lang.strip().lower()

    for col in headers:
        cname = str(col)
        lang = detect_lang_in_column(cname)
        if lang is not None:
            if lang.lower() == source_lower:
                roles[cname] = ROLE_SOURCE
            else:
                roles[cname] = f"target_{lang}"
            continue
        if _looks_like_key(cname):
            roles[cname] = ROLE_KEY
            continue
        if _looks_like_ignore(cname):
            roles[cname] = ROLE_IGNORE
            continue
        # 无标记的列，默认忽略（用户可手动指认为 source）
        roles[cname] = ROLE_IGNORE
    return roles


def default_target_strategy(target_langs: list[str]) -> dict[str, str]:
    """默认已有译文策略：跳过已有译文。"""
    from ..models import STRATEGY_SKIP

    return {lang: STRATEGY_SKIP for lang in target_langs}


def extract_target_langs(role_by_column: dict[str, str]) -> list[str]:
    """从角色映射中提取目标语言代码列表（去重保序）。"""
    langs: list[str] = []
    seen: set[str] = set()
    for role in role_by_column.values():
        if role.startswith("target_"):
            lang = role[len("target_") :]
            if lang not in seen:
                seen.add(lang)
                langs.append(lang)
    return langs


def find_source_column(role_by_column: dict[str, str]) -> str | None:
    """返回源文案列名（无则 None）。"""
    for col, role in role_by_column.items():
        if role == ROLE_SOURCE:
            return col
    return None


# ---- 模板持久化 CRUD ----

def save_template(
    name: str,
    role_by_column: dict[str, str],
    target_strategy: dict[str, str],
    auto_detected: bool,
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> ColumnTemplate:
    """保存列映射模板。"""
    tpl = ColumnTemplate(
        user_id=user_id,
        org_id=org_id,
        name=name,
        role_by_column=json_dumps(role_by_column),
        target_strategy=json_dumps(target_strategy),
        auto_detected=auto_detected,
    )
    with session_scope() as s:
        s.add(tpl)
        s.flush()
        s.refresh(tpl)
        return tpl


def list_templates(user_id: int = config.DEFAULT_USER_ID) -> list[ColumnTemplate]:
    with session_scope() as s:
        stmt = select(ColumnTemplate).where(ColumnTemplate.user_id == user_id)
        return list(s.exec(stmt).all())


def get_template(tpl_id: int) -> ColumnTemplate | None:
    with session_scope() as s:
        return s.get(ColumnTemplate, tpl_id)


def delete_template(tpl_id: int) -> None:
    with session_scope() as s:
        tpl = s.get(ColumnTemplate, tpl_id)
        if tpl:
            s.delete(tpl)


def deserialize_template(tpl: ColumnTemplate) -> dict[str, Any]:
    """将模板对象转为便于 UI 使用的字典。"""
    return {
        "id": tpl.id,
        "name": tpl.name,
        "role_by_column": json_loads(tpl.role_by_column, {}),
        "target_strategy": json_loads(tpl.target_strategy, {}),
        "auto_detected": tpl.auto_detected,
    }
