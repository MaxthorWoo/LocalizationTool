"""SQLite 数据库初始化与会话管理。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from . import config
from . import models as models_module  # noqa: F401  # 确保模型注册

_engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)


def _ensure_column(table: str, column: str, ddl: str) -> None:
    """给已存在的表安全补充列（SQLite ALTER TABLE ADD COLUMN）。"""
    from sqlalchemy import inspect, text

    insp = inspect(_engine)
    cols = {c["name"] for c in insp.get_columns(table)} if insp.has_table(table) else set()
    if column not in cols:
        with _engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def init_db() -> None:
    """创建所有表（如不存在），并对旧表做必要的轻量迁移。"""
    config.ensure_dirs()
    SQLModel.metadata.create_all(_engine)
    # 旧版术语表补充字段
    _ensure_column("termentry", "category", "category VARCHAR NOT NULL DEFAULT ''")
    _ensure_column("termentry", "library_id", "library_id INTEGER NOT NULL DEFAULT 0")
    _ensure_column("termentry", "translations", "translations VARCHAR NOT NULL DEFAULT '{}'")
    # 术语库补充源语言字段（兼容旧数据）
    _ensure_column("termlibrary", "source_lang", "source_lang VARCHAR NOT NULL DEFAULT ''")
    # API 配置补充自定义名称字段（兼容旧数据）
    _ensure_column("apiconfig", "display_name", "display_name VARCHAR NOT NULL DEFAULT ''")
    # API 配置补充并发上限与已探测并发缓存字段（兼容旧数据）
    _ensure_column(
        "apiconfig", "max_concurrency", "max_concurrency INTEGER NOT NULL DEFAULT 0"
    )
    _ensure_column(
        "apiconfig", "tested_concurrency", "tested_concurrency INTEGER NOT NULL DEFAULT 0"
    )
    _ensure_default_library()
    _migrate_target_term_to_translations()
    # 组织表补充归属字段（兼容旧数据）
    _ensure_column("org", "user_id", "user_id INTEGER NOT NULL DEFAULT 0")
    _ensure_column("org", "org_id", "org_id INTEGER NOT NULL DEFAULT 0")
    _ensure_column("org", "created_by", "created_by INTEGER NOT NULL DEFAULT 0")
    # 初始化内置常用语言（语言表为空时）
    from .services.language_service import init_preset_languages

    init_preset_languages()


def _migrate_target_term_to_translations() -> None:
    """将旧版单一 target_term 迁移到 translations JSON（仅当 translations 为空且 target_term 非空）。"""
    import json

    from sqlalchemy import text

    with _engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, target_term, translations FROM termentry "
                 "WHERE (translations IS NULL OR translations = '' OR translations = '{}') "
                 "AND target_term IS NOT NULL AND target_term != ''")
        ).fetchall()
        for rid, tgt, _tr in rows:
            conn.execute(
                text("UPDATE termentry SET translations = :tr WHERE id = :rid"),
                {"tr": json.dumps({"": tgt}, ensure_ascii=False), "rid": rid},
            )


def _ensure_default_library() -> None:
    """确保存在一个默认术语库，并将旧版无归属的术语归入该库。"""
    from sqlalchemy import text

    with _engine.begin() as conn:
        # 创建默认库（如无任何库）
        row = conn.execute(text("SELECT id FROM termlibrary LIMIT 1")).fetchone()
        if row is None:
            res = conn.execute(
                text(
                    "INSERT INTO termlibrary (user_id, org_id, name, description, created_time) "
                    "VALUES (0, 0, '默认术语库', '自动创建的默认术语库', "
                    "(SELECT strftime('%Y-%m-%d %H:%M:%S','now')))"
                )
            )
            lib_id = res.lastrowid
        else:
            lib_id = row[0]
        # 将 library_id 为 0 的旧术语归入默认库
        conn.execute(
            text("UPDATE termentry SET library_id = :lid WHERE library_id = 0"),
            {"lid": lib_id},
        )


def get_session() -> type[Session]:
    """返回 SQLModel 会话类（使用方式：Session(engine) 或直接实例化）。"""
    return Session


@contextmanager
def session_scope() -> Iterator[Session]:
    """提供带事务提交与异常回滚的 SQLModel 会话上下文。

    该会话支持 SQLModel 的 .exec() 查询方法。
    expire_on_commit=False：commit 后属性不过期，允许在 session 关闭后
    安全读取已加载的实例属性（用于在 service 中返回 ORM 对象）。
    """
    session = Session(_engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
