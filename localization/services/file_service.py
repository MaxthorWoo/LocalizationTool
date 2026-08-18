"""文件服务：上传保存、解析调度、创建工程与条目、导出。

一个工程（Project）= 一个上传文件 或 一段纯文本。工程内含条目（Entry）。
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from sqlmodel import select

from .. import config
from ..db import session_scope
from ..models import (
    STATUS_PENDING,
    STATUS_TRANSLATED,
    Entry,
    Project,
    json_dumps,
)
from . import exporter, parser


# ---- 上传保存 ----

def save_upload(upload, filename: str) -> str:
    """将上传文件保存到 uploads 目录，返回保存路径。"""
    config.ensure_dirs()
    safe = _safe_name(filename)
    # 加时间戳前缀避免重名
    path = os.path.join(str(config.UPLOAD_DIR), f"{int(time.time())}_{uuid.uuid4().hex[:6]}_{safe}")
    content = upload.file.read()
    with open(path, "wb") as f:
        f.write(content)
    return path


# ---- 工程创建 ----

def create_project_from_table(
    name: str,
    file_path: str,
    file_type: str,
    role_by_column: dict[str, str],
    source_lang: str,
    target_langs: list[str],
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> Project:
    """从表格文件创建工程与条目。"""
    result = parser.parse_table_file(file_path, file_type, role_by_column)
    return _build_project(
        name=name,
        file_type=file_type,
        rows=result.rows,
        source_lang=source_lang,
        target_langs=target_langs,
        column_mapping=role_by_column,
        user_id=user_id,
        org_id=org_id,
    )


def create_project_from_text(
    name: str,
    text: str,
    mode: str,
    source_lang: str,
    target_langs: list[str],
    user_id: int = config.DEFAULT_USER_ID,
    org_id: int = config.DEFAULT_ORG_ID,
) -> Project:
    """从纯文本创建工程与条目。"""
    result = parser.parse_text(text, mode=mode)
    return _build_project(
        name=name,
        file_type="text",
        rows=result.rows,
        source_lang=source_lang,
        target_langs=target_langs,
        column_mapping={},
        user_id=user_id,
        org_id=org_id,
    )


def _build_project(
    *,
    name: str,
    file_type: str,
    rows: list[parser.ParsedRow],
    source_lang: str,
    target_langs: list[str],
    column_mapping: dict[str, str],
    user_id: int,
    org_id: int,
) -> Project:
    with session_scope() as s:
        proj = Project(
            user_id=user_id,
            org_id=org_id,
            name=name,
            file_type=file_type,
            source_lang=source_lang,
            target_langs=",".join(target_langs),
            column_mapping=json_dumps(column_mapping),
            total_count=len(rows),
        )
        s.add(proj)
        s.flush()
        s.refresh(proj)

        for idx, row in enumerate(rows):
            entry = Entry(
                user_id=user_id,
                project_id=proj.id,
                source_text=row.source,
                key_text=row.key,
                translations=json_dumps(row.existing),
                status=STATUS_TRANSLATED if _all_existing(row, target_langs) else "pending",
                sort_index=idx,
            )
            s.add(entry)
        proj.total_count = len(rows)
        s.add(proj)
        s.flush()
        s.refresh(proj)

    # 同步语言方案行（表格导入的目标语言 → 自动生成方案行；文本导入可空）
    from .project_lang_config_service import sync_from_project

    sync_from_project(proj.id, target_langs, user_id=user_id)
    return proj


def _all_existing(row: parser.ParsedRow, target_langs: list[str]) -> bool:
    """该行是否所有目标语言都已有译文。"""
    return bool(target_langs) and all(row.existing.get(lang) for lang in target_langs)


# ---- 查询 ----

def list_projects(user_id: int = config.DEFAULT_USER_ID) -> list[Project]:
    with session_scope() as s:
        stmt = select(Project).where(Project.user_id == user_id).order_by(Project.upload_time.desc())
        return list(s.exec(stmt).all())


def get_project(project_id: int) -> Project | None:
    with session_scope() as s:
        return s.get(Project, project_id)


def update_project_source_lang(project_id: int, source_lang: str) -> Project | None:
    """更新工程的源语言。返回更新后的工程，找不到返回 None。"""
    with session_scope() as s:
        proj = s.get(Project, project_id)
        if proj is None:
            return None
        proj.source_lang = (source_lang or "").strip()
        s.add(proj)
        s.refresh(proj)
        return proj


def list_entries(project_id: int, user_id: int = config.DEFAULT_USER_ID) -> list[Entry]:
    with session_scope() as s:
        stmt = (
            select(Entry)
            .where(Entry.project_id == project_id, Entry.user_id == user_id)
            .order_by(Entry.sort_index)
        )
        return list(s.exec(stmt).all())


def create_entry(
    project_id: int,
    source_text: str,
    key_text: str = "",
    sort_index: int = 0,
    user_id: int = config.DEFAULT_USER_ID,
) -> Entry | None:
    """新增一个条目（一行源文案）。"""
    with session_scope() as s:
        e = Entry(
            user_id=user_id,
            project_id=project_id,
            source_text=(source_text or "").strip(),
            key_text=(key_text or "").strip(),
            translations="{}",
            status=STATUS_PENDING,
            term_hits="[]",
            sort_index=sort_index,
        )
        s.add(e)
        s.flush()
        s.refresh(e)
        return e


def get_entry(entry_id: int) -> Entry | None:
    with session_scope() as s:
        return s.get(Entry, entry_id)


def update_entry_text(entry_id: int, lang: str, text: str) -> Entry | None:
    """人工编辑：更新某个条目某语言的译文。"""
    with session_scope() as s:
        e = s.get(Entry, entry_id)
        if e is None:
            return None
        e.set_translation(lang, text)
        s.add(e)
        s.flush()
        s.refresh(e)
        return e


def update_entry_status(entry_id: int, status: str) -> Entry | None:
    with session_scope() as s:
        e = s.get(Entry, entry_id)
        if e is None:
            return None
        e.status = status
        s.add(e)
        s.flush()
        s.refresh(e)
        return e


def update_entry_source(entry_id: int, source_text: str) -> Entry | None:
    """人工编辑：更新某个条目的源文案。"""
    with session_scope() as s:
        e = s.get(Entry, entry_id)
        if e is None:
            return None
        e.source_text = source_text
        s.add(e)
        s.flush()
        s.refresh(e)
        return e


def update_entry_term_hits(entry_id: int, hits: list[str]) -> Entry | None:
    """写回某条目命中的术语源词列表（用于 UI 高亮与统计）。"""
    with session_scope() as s:
        e = s.get(Entry, entry_id)
        if e is None:
            return None
        e.set_term_hits(hits)
        s.add(e)
        s.flush()
        s.refresh(e)
        return e


def clear_entry_translations(
    project_id: int,
    lang: str,
    user_id: int = config.DEFAULT_USER_ID,
) -> int:
    """清空某工程全部条目在指定语言的译文。

    若某条目清空后不再有任何译文，则将其状态重置为待译。
    返回受影响条目数。
    """
    with session_scope() as s:
        stmt = select(Entry).where(
            Entry.project_id == project_id, Entry.user_id == user_id
        )
        entries = s.exec(stmt).all()
        count = 0
        for e in entries:
            data = e.get_translations()
            if lang not in data:
                continue
            del data[lang]
            e.translations = json_dumps(data)
            if not data and e.status == STATUS_TRANSLATED:
                e.status = "pending"
            s.add(e)
            count += 1
        return count


def recompute_project_stats(project: Project, entries: list[Entry]) -> None:
    """根据条目状态重算工程统计。"""
    total = len(entries)
    translated = sum(1 for e in entries if e.status in (STATUS_TRANSLATED, "proofread", "review"))
    proofread = sum(1 for e in entries if e.status == "proofread")
    hits = sum(1 for e in entries if e.get_term_hits())
    with session_scope() as s:
        p = s.get(Project, project.id)
        if p is None:
            return
        p.total_count = total
        p.translated_count = translated
        p.proofread_count = proofread
        p.term_hit_count = hits
        s.add(p)


def delete_project(project_id: int, user_id: int = config.DEFAULT_USER_ID) -> bool:
    """删除工程及其全部条目，返回是否删除成功。"""
    with session_scope() as s:
        p = s.get(Project, project_id)
        if p is None:
            return False
        stmt = select(Entry).where(
            Entry.project_id == project_id, Entry.user_id == user_id
        )
        for e in s.exec(stmt).all():
            s.delete(e)
        s.delete(p)
        return True


# ---- 导出 ----

def export_project_xlsx(project_id: int, export_dir: str | None = None) -> str:
    """导出工程的条目结果为 xlsx，返回文件路径。

    列语言优先取工程的方案配置行；无方案行时回退 project.target_langs。
    """
    from .project_lang_config_service import list_configs

    proj = get_project(project_id)
    if proj is None:
        raise ValueError(f"工程不存在: {project_id}")
    entries = list_entries(project_id)
    lang_configs = list_configs(project_id)
    target_langs = [c.lang for c in lang_configs] if lang_configs else None
    return exporter.export_project(proj, entries, export_dir, target_langs)


def _safe_name(name: str) -> str:
    """生成安全文件名（去非法字符）。"""
    cleaned = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
    return cleaned or "upload"


# =========================================================
# API 引擎配置 CRUD
# =========================================================

def list_api_configs(user_id: int = config.DEFAULT_USER_ID) -> list["ApiConfig"]:
    from ..models import ApiConfig

    with session_scope() as s:
        stmt = select(ApiConfig).where(ApiConfig.user_id == user_id)
        return list(s.exec(stmt).all())


def get_api_config(cfg_id: int, user_id: int = config.DEFAULT_USER_ID):
    """按 id 取 API 配置。"""
    from ..models import ApiConfig

    with session_scope() as s:
        stmt = select(ApiConfig).where(
            ApiConfig.id == cfg_id, ApiConfig.user_id == user_id
        )
        return s.exec(stmt).first()


def get_default_api_config(user_id: int = config.DEFAULT_USER_ID):
    """返回默认 API 配置；无默认则返回第一个；都没有返回 None。"""
    from ..models import ApiConfig

    with session_scope() as s:
        stmt = (
            select(ApiConfig)
            .where(ApiConfig.user_id == user_id, ApiConfig.is_default == True)  # noqa: E712
        )
        cfg = s.exec(stmt).first()
        if cfg is not None:
            return cfg
        first = s.exec(select(ApiConfig).where(ApiConfig.user_id == user_id)).first()
        return first


def save_api_config(
    engine_name: str,
    base_url: str,
    api_key: str,
    model: str,
    is_default: bool,
    display_name: str = "",
    cfg_id: int = 0,
    max_concurrency: int = 0,
    user_id: int = config.DEFAULT_USER_ID,
):
    """新增或更新一条 API 配置。cfg_id > 0 时更新该条，否则新建。"""
    from ..models import ApiConfig

    with session_scope() as s:
        if is_default:
            # 取消其他默认
            for c in s.exec(select(ApiConfig).where(ApiConfig.user_id == user_id)).all():
                if c.is_default:
                    c.is_default = False
                    s.add(c)
        if cfg_id:
            cfg = s.get(ApiConfig, cfg_id)
            if cfg is None:
                return None
            cfg.engine_name = engine_name
            cfg.base_url = base_url
            cfg.api_key = api_key
            cfg.model = model
            cfg.is_default = is_default
            cfg.display_name = display_name
            cfg.max_concurrency = max(0, int(max_concurrency or 0))
            s.add(cfg)
            s.flush()
            return cfg
        cfg = ApiConfig(
            user_id=user_id,
            engine_name=engine_name,
            base_url=base_url,
            api_key=api_key,
            model=model,
            is_default=is_default,
            display_name=display_name,
            max_concurrency=max(0, int(max_concurrency or 0)),
        )
        s.add(cfg)
        s.flush()
        s.refresh(cfg)
        return cfg


def set_default_api_config(cfg_id: int, user_id: int = config.DEFAULT_USER_ID) -> None:
    from ..models import ApiConfig

    with session_scope() as s:
        for c in s.exec(select(ApiConfig).where(ApiConfig.user_id == user_id)).all():
            c.is_default = (c.id == cfg_id)
            s.add(c)


def delete_api_config(cfg_id: int) -> None:
    from ..models import ApiConfig

    with session_scope() as s:
        c = s.get(ApiConfig, cfg_id)
        if c:
            s.delete(c)


def update_tested_concurrency(
    cfg_id: int, tested_concurrency: int, user_id: int = config.DEFAULT_USER_ID
) -> None:
    """持久化某 API 配置的已探测并发缓存（跨重启保留）。"""
    from ..models import ApiConfig

    with session_scope() as s:
        cfg = s.get(ApiConfig, cfg_id)
        if cfg is None:
            return
        cfg.tested_concurrency = max(0, int(tested_concurrency or 0))
        s.add(cfg)
        s.flush()


def serialize_api_config(cfg) -> dict:
    return {
        "id": cfg.id,
        "engine_name": cfg.engine_name,
        "display_name": cfg.display_name,
        "base_url": cfg.base_url,
        "api_key": cfg.api_key,
        "model": cfg.model,
        "is_default": cfg.is_default,
        "max_concurrency": getattr(cfg, "max_concurrency", 0) or 0,
        "tested_concurrency": getattr(cfg, "tested_concurrency", 0) or 0,
    }


def test_api_config(
    engine_name: str,
    base_url: str,
    api_key: str,
    model: str,
) -> tuple[bool, str]:
    """测试一组引擎配置是否可用：发送一条简单 chat 请求。

    返回 (是否成功, 提示信息)。成功时返回模型回复摘要。
    """
    from ..models import ApiConfig
    from ..translators import create_translator

    cfg = ApiConfig(
        engine_name=engine_name,
        base_url=base_url,
        api_key=api_key,
        model=model,
        is_default=False,
    )
    try:
        translator = create_translator(engine_name, cfg)
        reply = translator.translate(
            [
                {"role": "system", "content": "你是一个翻译助手。只回复两个字：连接成功。不要多说。"},
                {"role": "user", "content": "请回复：连接成功"},
            ],
            target_lang="en",
        )
        return True, f"连接成功（模型回复：{reply[:80]}）"
    except Exception as exc:  # noqa: BLE001
        return False, f"连接失败：{exc}"
