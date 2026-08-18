"""文件解析器：将不同来源（xlsx/csv/txt/纯文本）解析为可导入的条目结构。

表格类文件先读为 pandas DataFrame，再依据列映射（role_by_column）提取：
- source：源文案
- key：键列内容
- target_<lang>：目标语言列的已有译文（用于"跳过已有"策略）

txt / 纯文本按行/分段/整段切分为条目。
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

from . import column_mapping as cm
from .column_mapping import ROLE_IGNORE, ROLE_KEY, ROLE_SOURCE

SUPPORTED_TABLE_TYPES = ("xlsx", "xls", "csv")
SUPPORTED_TEXT_TYPES = ("txt",)


@dataclass
class ParsedRow:
    """解析出的一条待导入数据。"""

    source: str
    key: str = ""
    existing: dict[str, str] = field(default_factory=dict)  # {lang: 已有译文}


@dataclass
class ParseResult:
    """解析结果。"""

    headers: list[str] = field(default_factory=list)  # 表格列名（txt 为空）
    rows: list[ParsedRow] = field(default_factory=list)


def _clean_cell(value) -> str:
    """将单元格值清洗为字符串，NaN/None 转空串。"""
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    s = str(value).strip()
    if s.lower() in ("nan", "none", "nat"):
        return ""
    return s


def read_table_df(path: str, file_type: str) -> pd.DataFrame:
    """读取表格类文件为 DataFrame（列名保持字符串）。"""
    if file_type == "csv":
        # csv 可能是 utf-8 或 gbk 编码
        try:
            return pd.read_csv(path, dtype=str)
        except UnicodeDecodeError:
            return pd.read_csv(path, dtype=str, encoding="gbk")
    # xlsx / xls
    return pd.read_excel(path, dtype=str)


def parse_table_file(path: str, file_type: str, role_by_column: dict[str, str]) -> ParseResult:
    """按列映射解析表格文件。

    role_by_column: {列名: 角色}。target_<lang> 角色提供 {lang: 列名} 映射。
    """
    df = read_table_df(path, file_type)
    headers = [str(c) for c in df.columns.tolist()]

    # 构建语言 -> 列名 的映射，以及源列/键列名
    lang_to_col: dict[str, str] = {}
    source_col = None
    key_col = None
    for col, role in role_by_column.items():
        if role == ROLE_SOURCE:
            source_col = col
        elif role == ROLE_KEY:
            key_col = col
        elif role.startswith("target_"):
            lang = role[len("target_") :]
            lang_to_col[lang] = col

    result = ParseResult(headers=headers)
    if source_col is None:
        # 没有源列，无法提取
        return result

    for _, row in df.iterrows():
        source_text = _clean_cell(row.get(source_col, ""))
        if not source_text:
            continue  # 跳过空源文案行
        key_text = _clean_cell(row.get(key_col, "")) if key_col else ""
        existing: dict[str, str] = {}
        for lang, col in lang_to_col.items():
            val = _clean_cell(row.get(col, ""))
            if val:
                existing[lang] = val
        result.rows.append(ParsedRow(source=source_text, key=key_text, existing=existing))

    return result


def parse_txt_file(path: str) -> ParseResult:
    """解析 txt 文件：按空行分段，每段作为一个条目。"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return parse_text(content, mode="paragraph")


def parse_text(content: str, mode: str = "line") -> ParseResult:
    """解析纯文本，按指定模式切分为条目。

    mode: line=逐行 / paragraph=按空行分段 / whole=整段
    """
    result = ParseResult()
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    if mode == "line":
        segments = [ln.strip() for ln in text.split("\n") if ln.strip()]
    elif mode == "paragraph":
        segments = [p.strip() for p in text.split("\n\n") if p.strip()]
    else:  # whole
        segments = [text.strip()] if text.strip() else []
    for seg in segments:
        result.rows.append(ParsedRow(source=seg))
    return result


def parse_file(path: str, file_type: str, role_by_column: dict[str, str] | None = None) -> ParseResult:
    """按文件类型调度解析。

    - 表格类：需要 role_by_column
    - txt/text：按段落切分
    """
    ft = (file_type or "").lower().lstrip(".")
    if ft in SUPPORTED_TABLE_TYPES:
        if not role_by_column:
            raise ValueError("表格类文件解析需要列映射 role_by_column")
        return parse_table_file(path, ft, role_by_column)
    if ft in SUPPORTED_TEXT_TYPES or ft == "text":
        return parse_txt_file(path)
    raise ValueError(f"不支持的文件类型: {file_type}")
