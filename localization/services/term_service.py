"""术语服务：命名术语库管理、术语导入（双数据源 + 列映射）、分页查询、翻译引用。"""
from __future__ import annotations

import json

from sqlmodel import select

from .. import config
from ..db import session_scope
from ..models import TermEntry, TermLibrary
from . import term_sources

# 术语导入的列语义角色（供列映射指认 / 自动识别）
TERM_ROLE_SOURCE = "source_term"
TERM_ROLE_TARGET = "target_term"  # 旧角色，兼容旧模板；新模板用 target_lang:<code>
TERM_ROLE_NOTE = "note"

# 目标语言列角色的前缀：target_lang:zh-CN
TERM_ROLE_TARGET_LANG_PREFIX = "target_lang:"

# 列名自动识别提示（中英文）
TERM_SOURCE_HINTS = ("源术语", "原文", "source", "term", "source_term")
TERM_NOTE_HINTS = ("备注", "说明", "note", "remark", "comment")
# 语言列名 -> 语言代码 的识别提示（用于多语言目标列的自动猜测）
LANG_HEADER_MAP = [
    ("简体中文", "zh-CN"),
    ("中文_CN", "zh-CN"),
    ("中文cn", "zh-CN"),
    ("zh-cn", "zh-CN"),
    ("简体", "zh-CN"),
    ("繁體中文", "zh-TW"),
    ("繁體", "zh-TW"),
    ("中文_TW", "zh-TW"),
    ("zhtw", "zh-TW"),
    ("zh-tw", "zh-TW"),
    ("美式英語", "en"),
    ("美式英语", "en"),
    ("英语_EN", "en"),
    ("english", "en"),
    ("英文", "en"),
    ("en-us", "en"),
    ("日语", "ja"),
    ("日本語", "ja"),
    ("日本语", "ja"),
    ("japanese", "ja"),
    ("日文", "ja"),
    ("韓語", "ko"),
    ("韩语", "ko"),
    ("korean", "ko"),
    ("泰語", "th"),
    ("泰语", "th"),
    ("thai", "th"),
    ("印尼語", "id"),
    ("印尼语", "id"),
    ("indonesian", "id"),
    ("越南語", "vi"),
    ("越南语", "vi"),
    ("vietnamese", "vi"),
    ("法语", "fr"),
    ("德語", "de"),
    ("德语", "de"),
    ("西班牙語", "es"),
    ("西班牙语", "es"),
    ("葡萄牙語", "pt"),
    ("葡萄牙语", "pt"),
    ("俄語", "ru"),
    ("俄语", "ru"),
    ("阿拉伯語", "ar"),
    ("阿拉伯语", "ar"),
]


# 常见 ISO 语言代码 -> 标准代码（用于从列名后缀提取，如 日本語_JA -> ja）
ISO_CODE_MAP = {
    "zh-cn": "zh-CN", "zh-hans": "zh-CN", "cn": "zh-CN", "chinese": "zh-CN",
    "zh-tw": "zh-TW", "zh-hant": "zh-TW",
    "en": "en", "en-us": "en", "en-gb": "en", "eng": "en",
    "ja": "ja", "jp": "ja", "jpn": "ja",
    "ko": "ko", "kr": "ko", "kor": "ko",
    "th": "th", "tha": "th",
    "id": "id", "ind": "id", "id-id": "id",
    "vi": "vi", "vie": "vi", "vn": "vi",
    "fr": "fr", "fre": "fr", "fra": "fr",
    "de": "de", "ger": "de", "deu": "de",
    "es": "es", "spa": "es",
    "pt": "pt", "por": "pt",
    "ru": "ru", "rus": "ru",
    "ar": "ar", "ara": "ar",
}


def guess_lang_from_header(header: str) -> str | None:
    """根据列名猜测语言代码，如"简体中文_CN" -> zh-CN。猜不到返回 None。"""
    h = str(header).strip().lower().replace("（", "").replace("）", "").replace(" ", "")
    # 1. 名称匹配
    for key, code in LANG_HEADER_MAP:
        if key in h:
            return code
    # 2. 提取代码后缀（如 日本語_JA / 英文_En / 日語(JPN)）
    for sep in ("_", "-", "（", "(", "/", "｜", "|"):
        if sep in h:
            tail = h.rsplit(sep, 1)[-1].strip().rstrip(")）")
            code = ISO_CODE_MAP.get(tail.lower())
            if code:
                return code
    # 3. 整个列名就是代码
    if h.lower() in ISO_CODE_MAP:
        return ISO_CODE_MAP[h.lower()]
    return None


# =========================================================
# 命名术语库 CRUD
# =========================================================
def create_library(
    name: str,
    description: str = "",
    source_lang: str = "",
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> TermLibrary:
    """创建命名术语库。source_lang：术语源语言代码，空=不限定。"""
    lib = TermLibrary(
        user_id=user_id,
        org_id=org_id,
        name=(name or "").strip() or "未命名术语库",
        description=(description or "").strip(),
        source_lang=(source_lang or "").strip(),
    )
    with session_scope() as s:
        s.add(lib)
        s.flush()
        s.refresh(lib)
        return lib


def get_library(library_id: int) -> TermLibrary | None:
    with session_scope() as s:
        return s.get(TermLibrary, library_id)


def list_libraries(
    user_id: int = config.DEFAULT_USER_ID, org_id: int = config.DEFAULT_ORG_ID
) -> list[dict]:
    """列出个人 + 组织可见的术语库，附各库术语条数。"""
    from sqlalchemy import func

    with session_scope() as s:
        libs = s.exec(
            select(TermLibrary).where(
                (TermLibrary.user_id == user_id) | (TermLibrary.org_id == org_id)
            )
        ).all()
        # 各库术语计数
        counts: dict[int, int] = {}
        for (lid, c) in s.exec(
            select(TermEntry.library_id, func.count())
            .where(
                (TermEntry.user_id == user_id) | (TermEntry.org_id == org_id)
            )
            .group_by(TermEntry.library_id)
        ).all():
            counts[lid] = int(c)
        return [
            {
                "id": lib.id,
                "name": lib.name,
                "description": lib.description,
                "source_lang": lib.source_lang,
                "term_count": counts.get(lib.id, 0),
                "created_time": lib.created_time.isoformat() if lib.created_time else "",
            }
            for lib in libs
        ]


def delete_library(
    library_id: int, user_id: int = config.DEFAULT_USER_ID, org_id: int = config.DEFAULT_ORG_ID
) -> bool:
    """删除术语库及其全部术语。返回是否删除成功。"""
    with session_scope() as s:
        lib = s.get(TermLibrary, library_id)
        if lib is None:
            return False
        # 只允许删除自己/组织的库
        if lib.user_id != user_id and lib.org_id != org_id:
            return False
        # 级联删除库内术语
        entries = s.exec(
            select(TermEntry).where(TermEntry.library_id == library_id)
        ).all()
        for e in entries:
            s.delete(e)
        s.delete(lib)
        return True


# =========================================================
# 术语导入
# =========================================================
def _guess_column_map(headers: list[str]) -> dict[str, str]:
    """根据列名自动猜测术语列映射，返回 {列名: 角色}。

    角色：
      - source_term：源术语（一个）
      - target_lang:<code>：某语言列（可多个），如 target_lang:zh-CN
      - note：备注
    优先识别语言列；若一个语言列都没识别到，才退化用目标术语列名/第2列兜底。
    """
    roles: dict[str, str] = {}
    lang_cols: list[tuple[str, str]] = []
    for c in headers:
        cl = str(c).strip().lower()
        # 跳过已被识别为源/备注的列
        if any(h in cl for h in TERM_SOURCE_HINTS) and any(h in cl for h in TERM_NOTE_HINTS):
            continue
        lang = guess_lang_from_header(c)
        if lang:
            lang_cols.append((c, lang))
            roles[c] = f"{TERM_ROLE_TARGET_LANG_PREFIX}{lang}"

    # 源术语列：优先列名提示；否则若有中文语言列（典型源语言是中文）用中文列；
    # 再否则用第1个非语言列
    src = next((c for c in headers if any(h in str(c).strip().lower() for h in TERM_SOURCE_HINTS)), None)
    if src is None:
        zh_col = next((c for c, lang in lang_cols if lang == "zh-CN"), None)
        src = zh_col
    if src is None:
        src = next((c for c in headers if c not in roles), None)
    if src:
        # 若源列是某个语言列，把它从目标角色中移除
        roles.pop(src, None)
        roles[src] = TERM_ROLE_SOURCE

    # 备注列
    note = next((c for c in headers if any(h in str(c).strip().lower() for h in TERM_NOTE_HINTS)), None)
    if note and note != src:
        roles[note] = TERM_ROLE_NOTE

    # 若没有任何语言列，退化：用目标术语列名提示或第2列作为单一目标
    if not lang_cols and len(headers) >= 2:
        tgt = next((c for c in headers if any(h in str(c).strip().lower() for h in ("目标术语", "译文", "target", "translation"))), None)
        if tgt is None:
            tgt = headers[1] if headers[1] != src else (headers[2] if len(headers) > 2 else None)
        if tgt:
            roles[tgt] = f"{TERM_ROLE_TARGET_LANG_PREFIX}{config.DEFAULT_TARGET_LANG}"
    return roles


def _target_cols_from_map(cmap: dict[str, str]) -> list[tuple[str, str]]:
    """从列映射提取目标语言列，返回 [(列名, 语言代码)]。"""
    target_cols: list[tuple[str, str]] = []
    for col, role in cmap.items():
        if role.startswith(TERM_ROLE_TARGET_LANG_PREFIX):
            lang = role[len(TERM_ROLE_TARGET_LANG_PREFIX):]
            target_cols.append((col, lang))
        elif role == TERM_ROLE_TARGET:
            target_cols.append((col, config.DEFAULT_TARGET_LANG))
    return target_cols


def import_terms(
    source: str,
    is_online: bool,
    library_id: int = 0,
    category: str = "",
    column_map: dict[str, str] | None = None,
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> int:
    """从数据源拉取术语并入库到指定术语库，返回导入条数。

    column_map: {列名: 角色}。
      角色可为 source_term / note / target_lang:<code>（多语言列）。
      为空则自动猜测。
    """
    df = term_sources.fetch_dataframe(source, is_online)
    headers = [str(c) for c in df.columns]
    cmap = column_map or _guess_column_map(headers)
    src_col = next((c for c, r in cmap.items() if r == TERM_ROLE_SOURCE), None)
    note_col = next((c for c, r in cmap.items() if r == TERM_ROLE_NOTE), None)
    target_cols = _target_cols_from_map(cmap)
    if src_col is None:
        raise ValueError("未指定源术语列")
    if not target_cols:
        raise ValueError("未指定任何目标语言列")

    imported = 0
    cat = (category or "").strip()
    with session_scope() as s:
        for _, row in df.iterrows():
            src = term_sources.clean_cell(row.get(src_col, "") if src_col else "")
            if not src:
                continue
            note = term_sources.clean_cell(row.get(note_col, "") if note_col else "")
            # 构建多语言译法
            translations: dict[str, str] = {}
            for col, lang in target_cols:
                val = term_sources.clean_cell(row.get(col, "") if col else "")
                if val:
                    translations[lang] = val
            # 兼容旧字段：若只有一个目标语言，仍写回 target_term
            tgt = next(iter(translations.values()), "")
            exists = s.exec(
                select(TermEntry).where(
                    TermEntry.library_id == library_id,
                    TermEntry.source_term == src,
                )
            ).first()
            if exists:
                exists.note = note
                merged = exists.get_translations()
                merged.update(translations)
                exists.set_translations(merged)
                exists.target_term = merged.get(config.DEFAULT_TARGET_LANG, tgt)
                if cat:
                    exists.category = cat
                s.add(exists)
            else:
                s.add(
                    TermEntry(
                        user_id=user_id,
                        org_id=org_id,
                        library_id=library_id,
                        source_term=src,
                        target_term=tgt,
                        translations=json.dumps(translations, ensure_ascii=False),
                        note=note,
                        category=cat,
                    )
                )
            imported += 1
    return imported


# =========================================================
# 术语查询（按库 + 分页 + 分类）
# =========================================================
def _user_scope(user_id: int, org_id: int):
    return (TermEntry.user_id == user_id) | (TermEntry.org_id == org_id)


def query_terms(
    library_id: int = 0,
    page: int = 1,
    page_size: int = 20,
    category: str = "",
    keyword: str = "",
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> tuple[list[TermEntry], int]:
    """分页查询某库内的术语，返回 (当前页数据, 总条数)。

    library_id 为 0 时查全部；category 为空不过滤，否则精确过滤；
    keyword 非空时模糊匹配源术语 / 备注 / 译法（含 JSON 内的译法文本）。
    """
    from sqlalchemy import func

    with session_scope() as s:
        base = _user_scope(user_id, org_id)
        if library_id:
            base = base & (TermEntry.library_id == library_id)
        if category:
            base = base & (TermEntry.category == category)
        if keyword:
            kw = f"%{keyword}%"
            base = base & (
                (TermEntry.source_term.like(kw))
                | (TermEntry.note.like(kw))
                | (TermEntry.translations.like(kw))
            )
        total = s.exec(select(func.count()).select_from(TermEntry).where(base)).one()
        offset = (max(page, 1) - 1) * page_size
        stmt = (
            select(TermEntry)
            .where(base)
            .order_by(TermEntry.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = list(s.exec(stmt).all())
        return rows, int(total)


def list_categories(
    library_id: int = 0,
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> list[str]:
    """返回某库内已使用的术语分类（去重，排除空串）。"""
    from sqlalchemy import distinct

    with session_scope() as s:
        base = _user_scope(user_id, org_id)
        if library_id:
            base = base & (TermEntry.library_id == library_id)
        stmt = (
            select(distinct(TermEntry.category))
            .where(base & (TermEntry.category != ""))
        )
        return sorted(str(c) for c in s.exec(stmt).all() if c)


def set_term_category(term_id: int, category: str) -> None:
    """设置单个术语的分类。"""
    with session_scope() as s:
        t = s.get(TermEntry, term_id)
        if t:
            t.category = (category or "").strip()
            s.add(t)


def get_library_langs(
    library_id: int = 0,
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> list[str]:
    """返回某库内所有术语实际用到的语言代码并集（作为术语表格的表头）。"""
    terms = list_terms_by_library(library_id, user_id=user_id, org_id=org_id)
    lang_set: set[str] = set()
    for t in terms:
        lang_set.update(k for k in t.get_translations() if k)
    # 用全局语言顺序排序（内置在前）
    order = {code: i for i, code in enumerate(config.AVAILABLE_LANG_CODES)}
    return sorted(lang_set, key=lambda c: order.get(c, 999))


def delete_term(term_id: int) -> None:
    with session_scope() as s:
        t = s.get(TermEntry, term_id)
        if t:
            s.delete(t)


def update_term_translation(term_id: int, lang: str, value: str) -> None:
    """更新某术语指定语言的译法。value 为空则移除该语言。"""
    with session_scope() as s:
        t = s.get(TermEntry, term_id)
        if t is None:
            return
        tr = t.get_translations()
        value = (value or "").strip()
        if value:
            tr[lang] = value
        else:
            tr.pop(lang, None)
        t.set_translations(tr)
        # 同步兼容字段 target_term
        t.target_term = tr.get(config.DEFAULT_TARGET_LANG, "") or tr.get("", "") or t.target_term
        s.add(t)


def update_term_source(term_id: int, source: str) -> None:
    """更新某术语的源术语（原文）。"""
    with session_scope() as s:
        t = s.get(TermEntry, term_id)
        if t is None:
            return
        t.source_term = (source or "").strip()
        s.add(t)


def update_term_note(term_id: int, note: str) -> None:
    """更新某术语的备注。"""
    with session_scope() as s:
        t = s.get(TermEntry, term_id)
        if t is None:
            return
        t.note = (note or "").strip()
        s.add(t)


def list_terms_by_library(
    library_id: int, user_id: int = config.DEFAULT_USER_ID, org_id: int = config.DEFAULT_ORG_ID
) -> list[TermEntry]:
    """返回某库的全部术语（用于翻译引用 / 术语上下文）。"""
    with session_scope() as s:
        stmt = select(TermEntry).where(
            (TermEntry.library_id == library_id) & _user_scope(user_id, org_id)
        )
        return list(s.exec(stmt).all())


# =========================================================
# 术语约束上下文（翻译引用）
# =========================================================
try:
    from zhconv import convert as _zh_convert  # 繁简归一化（纯 Python，无重依赖）
except Exception:  # noqa: BLE001

    def _zh_convert(text: str, _conv: str = "zh-cn") -> str:
        return text


def _norm_cn(text: str) -> str:
    """把中文统一转成简体，用于术语匹配时的繁简归一化比较。"""
    if not text:
        return text
    try:
        return _zh_convert(text, "zh-cn")
    except Exception:  # noqa: BLE001
        return text


def match_terms(text: str, terms: list[TermEntry]) -> list[str]:
    """对文本做子串命中检测，返回命中的术语源词列表（按出现顺序）。

    匹配时做繁简归一化：术语源词与原文统一转简体后比较，
    因此简体术语可命中繁体原文（含异体字），反之亦然。
    返回值保持原始 source_term（不归一化），便于下游按源词索引。
    """
    hits: list[str] = []
    if not text:
        return hits
    text_norm = _norm_cn(text)
    for t in terms:
        st = t.source_term
        if st and _norm_cn(st) in text_norm:
            hits.append(st)
    return hits


def build_term_context(terms: list[TermEntry], target_lang: str = "") -> str:
    """构造术语约束说明（注入提示词 system 消息）。

    按 target_lang 从每条术语的多语言译法中选取对应译法；
    未指定语言时优先默认语言译法。
    """
    if not terms:
        return "（无特殊术语约束）"
    lines = []
    for t in terms:
        tr = t.get_translations()
        tgt = tr.get(target_lang, "") or tr.get("", "") or t.target_term
        if not tgt:
            continue
        lines.append(f"{t.source_term} -> {tgt}" + (f"（{t.note}）" if t.note else ""))
    if not lines:
        return "（无特殊术语约束）"
    return (
        "术语库中的指定译法具有最高优先级，必须原样使用，禁止增删改任何字词"
        "（包括冠词、助词、敬语体、时态等修饰变化）。\n"
        "若原文出现以下术语，对应部分必须逐字采用指定译法：\n"
        + "\n".join(lines)
    )


def _library_ids_by_source_lang(
    source_lang: str, user_id: int = config.DEFAULT_USER_ID, org_id: int = config.DEFAULT_ORG_ID
) -> list[int]:
    """返回可用于当前源语言的术语库 id 列表：
    未限定源语言（空）的库 + 与 source_lang 一致的库；source_lang 为空时返回全部。
    """
    with session_scope() as s:
        libs = s.exec(
            select(TermLibrary).where(
                (TermLibrary.user_id == user_id) | (TermLibrary.org_id == org_id)
            )
        ).all()
    if not source_lang:
        return [lib.id for lib in libs if lib.id is not None]
    return [lib.id for lib in libs if lib.id is not None and (not lib.source_lang or lib.source_lang == source_lang)]


def terms_for_prompt(
    library_id: int = 0,
    target_lang: str = "",
    source_lang: str = "",
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> tuple[list[TermEntry], str]:
    """返回翻译时所需的术语列表与约束上下文。

    library_id > 0 时引用该库的术语；为 0 时引用全部可见库（兼容旧行为）。
    source_lang：工程源语言；非空时只引用未限定源语言或与之匹配的术语库，
    target_lang：目标语言，用于从多语言译法中选取对应译法。
    """
    if library_id:
        # 指定库：若库限定了源语言且与工程源语言不符，则不引用
        lib = get_library(library_id)
        if lib is not None and source_lang and lib.source_lang and lib.source_lang != source_lang:
            return [], build_term_context([], target_lang)
        all_terms = list_terms_by_library(library_id, user_id=user_id, org_id=org_id)
    else:
        lib_ids = _library_ids_by_source_lang(source_lang, user_id=user_id, org_id=org_id)
        if not lib_ids:
            return [], build_term_context([], target_lang)
        with session_scope() as s:
            all_terms = list(
                s.exec(
                    select(TermEntry).where(
                        _user_scope(user_id, org_id) & TermEntry.library_id.in_(lib_ids)
                    )
                ).all()
            )
    return all_terms, build_term_context(all_terms, target_lang)
