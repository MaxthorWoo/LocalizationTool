"""术语数据源适配器：从不同来源拉取表格数据并归一化为 DataFrame。

- LocalFileSource：本地文件（xlsx/csv/txt）
- OnlineSheetSource：在线表格直链（Google Sheets / Drive，requests 下载）

列映射由调用方（term_service）负责，本模块只负责"取到原始表格"。
"""
from __future__ import annotations

import abc
import os
import re

import pandas as pd

from .parser import _clean_cell


def clean_cell(value) -> str:
    """清洗单元格值为字符串（NaN/None 转空串）。"""
    return _clean_cell(value)


class BaseTermSource(abc.ABC):
    """术语数据源抽象基类。"""

    def __init__(self, source: str) -> None:
        self.source = source

    @abc.abstractmethod
    def fetch_dataframe(self) -> pd.DataFrame:
        """拉取并返回原始表格 DataFrame（未做列映射）。"""
        raise NotImplementedError


class LocalFileSource(BaseTermSource):
    """本地术语文件源：xlsx/csv/txt。"""

    def fetch_dataframe(self) -> pd.DataFrame:
        ext = os.path.splitext(self.source)[1].lower().lstrip(".")
        if ext in ("xlsx", "xls", "csv"):
            return self._read_table()
        if ext in ("txt",):
            return self._read_txt()
        raise ValueError(f"不支持的术语文件类型: {ext}")

    def _read_table(self) -> pd.DataFrame:
        if os.path.splitext(self.source)[1].lower() == ".csv":
            try:
                return pd.read_csv(self.source, dtype=str)
            except UnicodeDecodeError:
                return pd.read_csv(self.source, dtype=str, encoding="gbk")
        return pd.read_excel(self.source, dtype=str)

    def _read_txt(self) -> pd.DataFrame:
        """txt 术语文件：每行一个术语，分隔符支持 , TAB = :。读为单列。"""
        with open(self.source, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        rows: list[list[str]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = re.split(r"[\t,=:]", line, maxsplit=2)
            parts = [p.strip() for p in parts]
            rows.append(parts)
        # 统一为 DataFrame：有 ≥3 段则当成 源/目标/备注 三列
        if rows and any(len(r) >= 3 for r in rows):
            cols = ["源术语", "目标术语", "备注"]
        elif rows and any(len(r) == 2 for r in rows):
            cols = ["源术语", "目标术语"]
        else:
            cols = ["源术语"]
        return pd.DataFrame(rows, columns=cols)


class OnlineSheetSource(BaseTermSource):
    """在线表格直链源：Google Sheets / Drive，用 requests 下载为 CSV 后解析。"""

    def fetch_dataframe(self) -> pd.DataFrame:
        url = self._normalize_url(self.source)
        return self._download_csv(url)

    @staticmethod
    def _normalize_url(url: str) -> str:
        """将分享链接归一化为可直接下载 CSV 的导出链接。

        参考 Google Sheets 官方导出格式：
          https://docs.google.com/spreadsheets/d/<FILE_ID>/export?format=csv&gid=<GID>

        支持：
        - Google Sheets 分享链接（可带 #gid=<GID>，缺省用 gid=0）
        - 已是 Google 导出直链（export?format=csv）-> 原样返回，保留 gid
        - Drive 文件链接 -> Drive 下载入口
        - 其它直链 -> 原样返回
        """
        url = url.strip()
        if "docs.google.com/spreadsheets" in url and "/export" in url:
            return url
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
        if m:
            file_id = m.group(1)
            gid = ""
            gm = re.search(r"[#?&]gid=(\d+)", url)
            if gm:
                gid = f"&gid={gm.group(1)}"
            return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv{gid}"
        m2 = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
        if m2:
            file_id = m2.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        return url

    @staticmethod
    def _download_csv(url: str) -> pd.DataFrame:
        """用 requests 拉取 CSV 内容，utf-8-sig 解码后交给 pandas 解析。"""
        import io

        import requests

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(
                f"在线表格下载失败（HTTP {exc}），请检查链接是否已开启任何拥有链接的人可查看"
            ) from exc

        content = resp.content.decode("utf-8-sig", errors="replace")
        if content.lstrip().startswith("<!DOCTYPE") or "<html" in content[:2000].lower():
            raise ValueError("未获取到表格数据（可能链接无效或无权限），请确认分享权限为任何拥有链接的人可查看")

        df = pd.read_csv(io.StringIO(content), dtype=str)
        if df is None or df.empty:
            raise ValueError("在线表格内容为空或列缺失，请检查表格是否填写了数据")
        return df


def fetch_dataframe(source: str, is_online: bool) -> pd.DataFrame:
    """统一入口：根据来源类型创建对应数据源并返回原始 DataFrame。"""
    if is_online:
        return OnlineSheetSource(source).fetch_dataframe()
    return LocalFileSource(source).fetch_dataframe()
