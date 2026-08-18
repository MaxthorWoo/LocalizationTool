"""Reflex 核心状态类。

承载所有业务状态与事件处理器：工程列表、条目管理、导入向导、
纯文本直粘、翻译调度、术语、提示词模板、引擎配置、组织。
所有数据交互通过 services 层完成，本模块只做状态编排与 UI 数据准备。
"""
from __future__ import annotations

import asyncio
import os
import threading
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Optional

import reflex as rx
from pydantic import BaseModel

from . import config
from . import models as m
from .services import (
    column_mapping as cm,
    concurrency_service,
    file_service,
    lang_profile_service,
    language_service,
    org_service,
    project_lang_config_service,
    prompt_service,
    term_service,
    term_sources,
    translation_service,
)
from .services.column_mapping import ROLE_IGNORE, ROLE_KEY, ROLE_SOURCE
from .translators import create_translator, get_registered_engines


# 状态徽标颜色（前景色, 背景色）
STATUS_COLORS = {
    "pending": ("#64748B", "#E2E8F0"),
    "translated": ("#2563EB", "#DBEAFE"),
    "proofread": ("#059669", "#D1FAE5"),
    "review": ("#D97706", "#FEF3C7"),
}

# 中文标签 -> 英文枚举值 反向映射（前端下拉显示中文，提交时还原枚举）
STATUS_LABEL_TO_CODE = {v: k for k, v in m.STATUS_LABELS.items()}
STRATEGY_LABEL_TO_CODE = {v: k for k, v in m.STRATEGY_LABELS.items()}
TEXT_MODE_LABEL_TO_CODE = {v: k for k, v in m.TEXT_MODE_LABELS.items()}
ROLE_LABEL_TO_CODE = {v: k for k, v in m.ROLE_LABELS.items()}


class EntryRow(BaseModel):
    """条目在 UI 中的 typed 表示（供 rx.foreach 使用）。"""

    id: int
    source_text: str
    key_text: str
    translations: dict[str, str]
    # 按 target_langs 顺序对齐的译文单元格列表（避免前端用 Var 索引 dict）
    cells: list[dict] = []
    status: str
    status_label: str
    status_fg: str
    status_bg: str
    term_hits_display: str


class TermRow(BaseModel):
    """术语在 UI 表格中的 typed 表示（供 rx.foreach 使用）。"""

    id: int
    source_term: str
    translations: dict[str, str]
    # 按 term_table_langs 顺序对齐的译文单元格列表（避免前端用 Var 索引 dict）
    cells: list[dict] = []
    note: str


class State(rx.State):
    """应用根状态。"""

    # ---- 通用 ----
    sidebar_collapsed: bool = False
    available_lang_codes: list[str] = config.AVAILABLE_LANG_CODES
    # 语言展示用（含名称），格式：["zh-CN 简体中文", ...] 或直接 code
    lang_display_options: list[str] = config.AVAILABLE_LANG_CODES
    # 列映射目标语言角色选项：显示语言名称（"目标·简体中文"），代码映射在 lang_label_to_code
    lang_role_options: list[str] = [f"目标·{code}" for code in config.AVAILABLE_LANG_CODES]
    # 语言名称 -> 代码 映射（供列映射 label 反查代码）
    lang_label_to_code: dict[str, str] = {
        name: code for code, name in language_service.PRESET_LANG_NAMES.items()
    }
    # 工程导入列映射下拉的完整 label 选项（静态角色 + 动态目标语言）
    column_role_labels: list[str] = (
        ["源文案", "键", "忽略"]
        + [f"目标·{code}" for code in config.AVAILABLE_LANG_CODES]
    )
    # 术语导入列映射下拉的完整 label 选项
    term_role_labels: list[str] = (
        ["源术语", "忽略", "备注"]
        + [f"目标·{code}" for code in config.AVAILABLE_LANG_CODES]
    )

    # ---- 语言管理 ----
    langs: list[dict] = []
    new_lang_code: str = ""
    new_lang_name: str = ""
    # 语言代码 <-> 中文显示名 映射（load_languages 填充）
    lang_code_to_display: dict[str, str] = {}
    lang_display_to_code: dict[str, str] = {}
    # 目标语言多选 checkbox 选项：[{"code": "zh-CN", "display": "zh-CN 简体中文"}, ...]
    lang_check_options: list[dict] = []
    # 下拉显示用（中文）
    text_source_lang_display: str = ""
    source_lang_display: str = ""
    target_lang_display_options: list[str] = []
    # 校对条目表 grid 布局的列宽字符串（随目标语言数动态生成，如 "36px 300px 260px ... 80px 150px 120px"）
    entry_grid_cols: str = ""
    # 语言方案配置（校对页方案表）行数据，含 display 字段
    lang_configs: list[dict] = []
    # 添加语言行用：可添加的语言下拉选项 + 选中值
    lang_config_add_options: list[str] = []
    lang_config_add_display: str = ""
    # 校对页工程源语言编辑
    project_source_lang_options: list[str] = []
    project_source_lang_display: str = ""
    # 翻译 API 选择：["自动匹配", "GLM glm-4-flash 默认"...]
    api_config_options: list[str] = []
    translate_api_choice: str = "自动匹配"
    translate_api_config_id: int = 0

    # ---- 工程列表 ----
    projects: list[dict] = []
    project_delete_confirm_id: int = 0

    # ---- 当前工程与条目 ----
    current_project: dict = {}
    has_project: bool = False
    entries: list[EntryRow] = []
    target_langs: list[str] = []
    translate_strategy: str = m.STRATEGY_LABELS[m.STRATEGY_SKIP]  # 中文标签，提交时转回枚举
    is_translating: bool = False
    progress_done: int = 0
    progress_total: int = 0
    new_entry_text: str = ""  # 校对表格底部"新增一行"的源文案输入框
    progress_text: str = ""
    progress_pct: str = "0%"  # 预计算进度百分比字符串（避免 UI 数值比较编译问题）
    clear_confirm_open: bool = False

    # ---- 导入向导（表格文件） ----
    wizard_open: bool = False
    wizard_step: int = 1
    wizard_file_path: str = ""
    wizard_file_name: str = ""
    preview_headers: list[str] = []
    preview_rows: list[list] = []
    role_by_column: dict = {}
    target_strategy: dict = {}
    source_lang: str = config.DEFAULT_SOURCE_LANG
    column_templates: list[dict] = []
    column_template_names: list[str] = []

    # ---- 纯文本直粘 ----
    text_input: str = ""
    text_project_name: str = ""
    text_mode: str = m.TEXT_MODE_LABELS[m.TEXT_MODE_PARAGRAPH]  # 中文标签，提交时转回枚举
    text_source_lang: str = config.DEFAULT_SOURCE_LANG
    # txt 上传预览弹窗（与粘贴文本隔离，避免内容串扰）
    text_preview_open: bool = False
    txt_preview_content: str = ""
    txt_preview_name: str = ""
    txt_preview_source_lang_display: str = ""

    # ---- 术语库 ----
    terms: list[dict] = []
    term_rows: list[TermRow] = []  # 术语表格 typed 行
    term_table_langs: list[str] = []  # 当前库术语实际用到的语言（表格表头）
    term_libraries: list[dict] = []
    term_library_names: list[str] = []
    selected_library_id: int = 0
    selected_library_name: str = ""
    # 翻译引用术语库
    translate_lib_options: list[str] = []
    translate_term_library_id: int = 0
    translate_lib_name: str = "不引用术语"
    # 翻译引用提示词模板
    translate_prompt_options: list[str] = []
    translate_prompt_template_id: int = 0
    translate_prompt_name: str = "默认模板"

    # ---- 语言翻译配置（LangProfile，设置页） ----
    lang_profiles: list[dict] = []
    profile_form_lang_display: str = ""
    profile_form_api: str = ""
    profile_form_template: str = ""
    profile_form_term: str = ""
    profile_form_strategy: str = ""
    profile_form_editing: int = 0  # 0=新增，>0=编辑该 profile id
    # 设置页表单下拉选项（load_lang_profiles 时填充）
    profile_lang_options: list[str] = []
    profile_api_options: list[str] = []
    profile_template_options: list[str] = []
    profile_term_options: list[str] = []
    profile_strategy_options: list[str] = ["（不指定）", "跳过已有译文", "覆盖重译"]
    term_importing: bool = False
    term_import_status: str = ""
    term_categories: list[str] = []
    term_category_options: list[str] = []
    term_category: str = ""
    term_new_category: str = ""
    term_page: int = 1
    term_page_size: int = 20
    term_total: int = 0
    term_total_pages: int = 1
    term_search_keyword: str = ""
    # 术语库管理对话框
    lib_dialog_open: bool = False
    lib_new_name: str = ""
    lib_new_desc: str = ""
    lib_new_source_lang_options: list[str] = []
    lib_new_source_lang_display: str = ""
    lib_delete_confirm: bool = False
    # 术语导入向导（列映射）
    term_import_open: bool = False
    term_import_step: int = 1
    term_import_source_type: str = "file"  # file / url / text
    term_wizard_file_path: str = ""
    term_wizard_url: str = ""
    term_wizard_text: str = ""
    term_preview_headers: list[str] = []
    term_preview_rows: list[list] = []
    term_column_map: dict = {}

    # ---- 提示词模板 ----
    prompt_templates: list[dict] = []
    current_prompt_id: int = 0
    current_prompt_name: str = ""
    current_prompt_desc: str = ""
    current_prompt_messages: list[dict] = []
    prompt_var_docs: list[dict] = []
    var_suggest_index: int = -1  # 当前弹出变量建议的消息索引（-1 = 不显示）
    var_caret_pos: dict[int, int] = {}  # 消息索引 -> 光标位置（供插入变量使用）

    # ---- 引擎配置 ----
    api_configs: list[dict] = []
    engine_names: list[str] = []
    engine_test_status: str = ""
    engine_test_loading: bool = False
    engine_test_passed: bool = False  # 当前表单是否已测试通过（通过后才允许保存）
    # 引擎配置表单（绑定到 State，供测试/保存读取）
    engine_form_engine: str = ""
    engine_form_display_name: str = ""
    engine_form_base_url: str = ""
    engine_form_api_key: str = ""
    engine_form_model: str = ""
    engine_form_is_default: bool = False
    engine_form_max_concurrency: str = ""  # 并发上限（0=自动，文本态便于留空）
    engine_form_editing_id: int = 0  # >0 表示正在编辑该配置

    # ---- 组织 ----
    orgs: list[dict] = []
    org_join_code: str = ""
    org_new_name: str = ""
    org_delete_confirm_id: int = 0

    # ---- 文件上传状态 ----
    is_uploading: bool = False
    upload_feedback: str = ""

    # =========================================================
    # 工具方法
    # =========================================================

    def _toast(self, msg: str) -> rx.EventSpec:
        """返回一个 Reflex 自带 toast 事件：页面顶部、短暂停留后自动关闭。"""
        return rx.toast(msg, position="top-center", duration=3000)

    @rx.event
    def toggle_sidebar(self) -> None:
        """展开/收起侧边栏。"""
        self.sidebar_collapsed = not self.sidebar_collapsed

    @rx.event
    def load_languages(self) -> None:
        """从数据库加载语言列表（内置 + 自定义），刷新全局语言选项。"""
        langs = language_service.list_languages()
        codes = [l["code"] for l in langs]
        self.available_lang_codes = codes
        # 展示选项：名称 + 代码，便于识别
        self.lang_display_options = [
            f"{l['code']} {l['name']}" if l["name"] and l["name"] != l["code"] else l["code"]
            for l in langs
        ]
        # 语言代码 <-> 中文显示名 双向映射（下拉显示中文，提交还原代码）
        self.lang_code_to_display = {
            l["code"]: (f"{l['code']} {l['name']}" if l["name"] and l["name"] != l["code"] else l["code"])
            for l in langs
        }
        self.lang_display_to_code = {v: k for k, v in self.lang_code_to_display.items()}
        self.lang_check_options = [
            {"code": l["code"], "display": self.lang_code_to_display[l["code"]]} for l in langs
        ]
        # 列映射目标语言角色选项：显示语言名称；名称 -> 代码 映射用于反查
        self.lang_label_to_code = {l["name"]: l["code"] for l in langs if l["name"]}
        self.lang_role_options = [f"目标·{l['name']}" for l in langs if l["name"]]
        self.column_role_labels = ["源文案", "键", "忽略"] + self.lang_role_options
        self.term_role_labels = ["源术语", "忽略", "备注"] + self.lang_role_options
        # 同步语言下拉显示值（默认语言）
        self.text_source_lang_display = self.lang_code_to_display.get(
            self.text_source_lang, self.text_source_lang
        )
        self.source_lang_display = self.lang_code_to_display.get(
            self.source_lang, self.source_lang
        )
        # 校对页工程源语言下拉：加"不修改"占位符
        self.project_source_lang_options = self.lang_display_options
        # 创建术语库源语言下拉：首项"不限定"
        self.lib_new_source_lang_options = ["不限定"] + list(self.lang_display_options)

    @rx.event
    def load_languages_admin(self) -> None:
        """加载语言管理页的语言列表。"""
        self.langs = language_service.list_languages()

    @rx.event
    def set_new_lang_code(self, value: str) -> None:
        self.new_lang_code = value

    @rx.event
    def set_new_lang_name(self, value: str) -> None:
        self.new_lang_name = value

    @rx.event
    def add_language(self) -> None:
        """添加自定义语言。"""
        lang, err = language_service.add_language(self.new_lang_code, self.new_lang_name)
        if lang is None:
            return self._toast(f"添加失败：{err}")
        self.new_lang_code = ""
        self.new_lang_name = ""
        self.load_languages_admin()
        self.load_languages()
        return self._toast(f"已添加语言：{lang.name}（{lang.code}）")

    @rx.event
    def delete_language(self, lang_id: int) -> None:
        """删除自定义语言（内置不可删）。"""
        ok, err = language_service.delete_language(int(lang_id))
        if not ok:
            return self._toast(f"删除失败：{err}")
        self.load_languages_admin()
        self.load_languages()
        return self._toast("已删除该语言")

    def _serialize_project(self, p: m.Project) -> dict:
        langs = p.get_target_lang_list()
        lang_disp = lambda c: self.lang_code_to_display.get(c, c)  # noqa: E731
        return {
            "id": p.id,
            "name": p.name,
            "file_type": p.file_type,
            "source_lang": p.source_lang,
            "source_lang_display": lang_disp(p.source_lang),
            "target_langs": langs,
            "target_langs_display": ", ".join(lang_disp(c) for c in langs),
            "total_count": p.total_count,
            "translated_count": p.translated_count,
            "proofread_count": p.proofread_count,
            "term_hit_count": p.term_hit_count,
        }

    def _serialize_entry(self, e: m.Entry) -> EntryRow:
        hits = e.get_term_hits()
        status_fg, status_bg = STATUS_COLORS.get(e.status, ("#64748B", "#E2E8F0"))
        translations = e.get_translations()
        cells = [
            {"lang": lang, "text": translations.get(lang, "")}
            for lang in self.target_langs
        ]
        return EntryRow(
            id=e.id,
            source_text=e.source_text,
            key_text=e.key_text,
            translations=translations,
            cells=cells,
            status=e.status,
            status_label=m.STATUS_LABELS.get(e.status, e.status),
            status_fg=status_fg,
            status_bg=status_bg,
            term_hits_display=", ".join(hits),
        )

    def _serialize_term(self, t: m.TermEntry) -> dict:
        tr = t.get_translations()
        return {
            "id": t.id,
            "source_term": t.source_term,
            "target_term": tr.get(config.DEFAULT_TARGET_LANG, "")
            or tr.get("", "")
            or t.target_term,
            "translations": tr,
            "note": t.note,
            "category": t.category or "",
        }

    # =========================================================
    # 通用加载
    # =========================================================

    @rx.event
    def load_home(self) -> None:
        """进入首页：加载工程列表与引擎。"""
        self.load_projects()
        self.load_api_configs()
        self.engine_names = get_registered_engines()

    @rx.event
    def load_projects(self) -> None:
        self.projects = [self._serialize_project(p) for p in file_service.list_projects()]

    # =========================================================
    # 导入向导：上传文件
    # =========================================================

    @rx.event
    async def on_file_upload(self, files: list[rx.UploadFile]) -> None:
        """上传文件：async 事件，耗时操作（文件保存、pandas 解析）全部放入
        后台线程执行，避免阻塞事件循环。

        真正根因：pd.read_excel 解析大表格需数秒，若在 async 事件里同步执行
        会阻塞 asyncio 事件循环 → WebSocket 心跳超时 → 前端「Socket is
        reconnected」断线重连 → State 重建 → 弹窗与 toast 一起消失。
        txt 解析毫秒级所以不触发。解法：await asyncio.to_thread(...) 让解析
        在线程中运行，事件循环保持响应、心跳不断。
        """
        if not files:
            return
        if self.is_uploading:
            return
        upload = files[0]
        ext = upload.filename.rsplit(".", 1)[-1].lower()
        self.is_uploading = True
        self.upload_feedback = f"正在解析 {upload.filename} …"
        try:
            # 文件保存 + 解析都放线程，避免阻塞事件循环
            saved_path = await asyncio.to_thread(
                file_service.save_upload, upload, upload.filename
            )
            if ext in ("txt", "text"):
                content = await asyncio.to_thread(_read_txt_content, saved_path)
                self.txt_preview_content = content
                self.txt_preview_name = os.path.splitext(upload.filename)[0] or "文本工程"
                self.txt_preview_source_lang_display = self.text_source_lang_display
                self.text_preview_open = True
                self.is_uploading = False
                self.upload_feedback = ""
                return self._toast("文本已读取，请选择切分方式并确认创建")

            df = await asyncio.to_thread(_read_preview_df, saved_path, ext)
            df = df.fillna("")
            headers = [str(c) for c in df.columns.tolist()]
            rows = [
                ["" if str(v) == "nan" else str(v) for v in df.iloc[i].tolist()]
                for i in range(min(config.PREVIEW_ROWS, len(df)))
            ]
            role_by_column = cm.guess_column_roles(headers, self.source_lang)
            target_strategy = cm.default_target_strategy(
                cm.extract_target_langs(role_by_column)
            )
            self.wizard_file_path = saved_path
            self.wizard_file_name = upload.filename
            self.preview_headers = headers
            self.preview_rows = rows
            self.role_by_column = role_by_column
            self.target_strategy = target_strategy
            self.load_column_templates()
            self.wizard_step = 2
            self.wizard_open = True
            return self._toast(f"文件已解析：{upload.filename}，请确认列映射")
        except Exception as exc:  # noqa: BLE001
            return self._toast(f"文件解析失败: {exc}")
        finally:
            self.is_uploading = False
            self.upload_feedback = ""

    @rx.event
    def set_wizard_step(self, step: int) -> None:
        self.wizard_step = int(step)

    @rx.event
    def close_wizard(self) -> None:
        self.wizard_open = False
        self.wizard_step = 1

    @rx.event
    def set_source_lang(self, value: str) -> None:
        # value 为中文显示（"zh-CN 简体中文"），映射回代码
        self.source_lang_display = value
        code = self.lang_display_to_code.get(value, value)
        self.source_lang = code
        # 重新猜测
        self.role_by_column = cm.guess_column_roles(self.preview_headers, code)
        self.target_strategy = cm.default_target_strategy(cm.extract_target_langs(self.role_by_column))

    @rx.event
    def set_column_role(self, column: str, label: str) -> None:
        """手动指认某列角色。label 如 源文案/键/忽略/目标·简体中文。"""
        if not label:
            return
        # label -> 内部角色值
        mapping = {"源文案": ROLE_SOURCE, "键": ROLE_KEY, "忽略": ROLE_IGNORE}
        role = mapping.get(label)
        if role is None and label.startswith("目标·"):
            name = label[len("目标·"):]
            code = self.lang_label_to_code.get(name)
            if code:
                role = f"target_{code}"
        if role is None:
            return
        self.role_by_column[column] = role
        self._recompute_strategy()

    def _recompute_strategy(self) -> None:
        langs = cm.extract_target_langs(self.role_by_column)
        new_strategy = {}
        for lang in langs:
            new_strategy[lang] = self.target_strategy.get(lang, m.STRATEGY_SKIP)
        self.target_strategy = new_strategy
        self.target_langs = langs

    @rx.event
    def set_target_strategy(self, lang: str, strategy: str) -> None:
        self.target_strategy[lang] = strategy

    # ---- 列模板 ----

    @rx.event
    def load_column_templates(self) -> None:
        self.column_templates = [cm.deserialize_template(t) for t in cm.list_templates()]
        self.column_template_names = [t["name"] for t in self.column_templates]

    @rx.event
    def apply_column_template_by_name(self, name: str) -> None:
        """根据模板名套用列映射。"""
        for t in self.column_templates:
            if t["name"] == name:
                self.role_by_column = dict(t["role_by_column"])
                self.target_strategy = dict(t["target_strategy"])
                self.target_langs = cm.extract_target_langs(self.role_by_column)
                return self._toast(f"已套用列映射模板：{name}")
        return self._toast("未找到该模板")

    @rx.event
    def save_column_template(self, form_data: dict) -> None:
        name = (form_data.get("tpl_name") or "").strip()
        if not name:
            return self._toast("请填写模板名称")
        cm.save_template(name, dict(self.role_by_column), dict(self.target_strategy), False)
        self.load_column_templates()
        return self._toast("列映射模板已保存")

    @rx.event
    def apply_column_template(self, tpl_id: int) -> None:
        tpl = cm.get_template(int(tpl_id))
        if tpl is None:
            return
        data = cm.deserialize_template(tpl)
        self.role_by_column = dict(data["role_by_column"])
        self.target_strategy = dict(data["target_strategy"])
        self.target_langs = cm.extract_target_langs(self.role_by_column)
        return self._toast("已套用列映射模板")

    @rx.event
    def delete_column_template(self, tpl_id: int) -> None:
        cm.delete_template(int(tpl_id))
        self.load_column_templates()

    # ---- 确认导入（表格文件建工程） ----

    @rx.event
    def confirm_table_import(self) -> None:
        source_col = cm.find_source_column(self.role_by_column)
        if source_col is None:
            return self._toast("请指定至少一列作为源文案列")
        langs = cm.extract_target_langs(self.role_by_column)
        if not langs:
            return self._toast("请指定至少一个目标语言列")
        ext = self.wizard_file_name.rsplit(".", 1)[-1].lower()
        try:
            proj = file_service.create_project_from_table(
                name=self.wizard_file_name,
                file_path=self.wizard_file_path,
                file_type=ext,
                role_by_column=dict(self.role_by_column),
                source_lang=self.source_lang,
                target_langs=langs,
            )
        except Exception as exc:  # noqa: BLE001
            return self._toast(f"导入失败: {exc}")
        self.wizard_open = False
        self.wizard_step = 1
        self.load_projects()
        return self._toast(f"工程已创建：{proj.name}（{proj.total_count} 条）")

    # =========================================================
    # 纯文本直粘
    # =========================================================

    @rx.event
    def set_text_input(self, value: str) -> None:
        self.text_input = value

    @rx.event
    def close_text_preview(self) -> None:
        self.text_preview_open = False

    @rx.event
    def set_txt_preview_name(self, value: str) -> None:
        self.txt_preview_name = value

    @rx.event
    def set_txt_preview_content(self, value: str) -> None:
        self.txt_preview_content = value

    @rx.event
    def confirm_txt_preview(self) -> None:
        """确认 txt 上传预览：用隔离字段创建工程，不影响粘贴文本框。"""
        text = self.txt_preview_content.strip()
        if not text:
            return self._toast("文本内容为空")
        name = self.txt_preview_name.strip() or "文本工程"
        mode = TEXT_MODE_LABEL_TO_CODE.get(self.text_mode, self.text_mode)
        proj = file_service.create_project_from_text(
            name=name,
            text=text,
            mode=mode,
            source_lang=self.text_source_lang,
            target_langs=[],
        )
        self.text_preview_open = False
        self.txt_preview_content = ""
        self.txt_preview_name = ""
        self.load_projects()
        return self._toast(f"工程已创建：{proj.name}（{proj.total_count} 条），请进入校对页添加目标语言")

    @rx.event
    def set_text_project_name(self, value: str) -> None:
        self.text_project_name = value

    @rx.event
    def set_text_mode(self, value: str) -> None:
        self.text_mode = value

    @rx.event
    def set_text_source_lang(self, value: str) -> None:
        self.text_source_lang_display = value
        self.text_source_lang = self.lang_display_to_code.get(value, value)

    @rx.event
    def confirm_text_project(self) -> None:
        text = self.text_input.strip()
        if not text:
            return self._toast("请粘贴要翻译的文本")
        name = self.text_project_name.strip() or "纯文本工程"
        # text_mode 为中文标签，转回枚举（line/paragraph/whole）
        mode = TEXT_MODE_LABEL_TO_CODE.get(self.text_mode, self.text_mode)
        proj = file_service.create_project_from_text(
            name=name,
            text=text,
            mode=mode,
            source_lang=self.text_source_lang,
            target_langs=[],  # 目标语言在校对页动态添加
        )
        self.text_input = ""
        self.text_project_name = ""
        self.text_preview_open = False
        self.load_projects()
        return self._toast(f"工程已创建：{proj.name}（{proj.total_count} 条），请进入校对页添加目标语言")

    # =========================================================
    # 工程操作与条目
    # =========================================================

    @rx.event
    def open_project(self, project_id: int):
        proj = file_service.get_project(int(project_id))
        if proj is None:
            return
        self.current_project = self._serialize_project(proj)
        self.has_project = True
        # 回填校对页工程源语言下拉显示值
        self.project_source_lang_display = self.lang_code_to_display.get(
            proj.source_lang, proj.source_lang
        )
        # 兼容旧数据：工程 target_langs 非空但无方案行时自动迁移
        if not project_lang_config_service.list_configs(int(project_id)):
            project_lang_config_service.sync_from_project(
                int(project_id), proj.get_target_lang_list()
            )
        self.load_lang_configs()
        self.load_entries()
        # 无论从首页还是本页触发，都确保停留在校对工作台
        return rx.redirect("/project")

    @rx.event
    def load_entries(self) -> None:
        pid = self.current_project.get("id")
        if not pid:
            return
        self.entries = [self._serialize_entry(e) for e in file_service.list_entries(pid)]

    # ---- 语言方案配置表 ----

    def _lib_display_name(self, lib: dict) -> str:
        """术语库展示名：库名（源语言名），未限定源语言时只显示库名。"""
        if not lib:
            return ""
        name = lib.get("name", "")
        sl = lib.get("source_lang") or ""
        if not sl:
            return name
        return f"{name}（{self.lang_code_to_display.get(sl, sl)}）"

    def _api_display_name(self, api) -> str:
        """API 配置展示名：有自定义名时用「名称 (engine model)」，否则「engine model」。

        兼容 dict（serialize_api_config 输出）与 ORM 对象两种形态。
        """
        if not api:
            return ""
        dname = ((api.get("display_name") if isinstance(api, dict) else api.display_name) or "").strip()
        engine = api.get("engine_name") if isinstance(api, dict) else api.engine_name
        model = api.get("model") if isinstance(api, dict) else api.model
        is_default = api.get("is_default") if isinstance(api, dict) else api.is_default
        base = f"{engine} {model}".strip()
        suffix = "（默认）" if is_default else ""
        if dname:
            return f"{dname} ({base}){suffix}"
        return f"{base}{suffix}"

    def _config_option_display(self, kind: str, row) -> str:
        """把方案行的 api/template/term/strategy 转成下拉的显示值。"""
        if kind == "api":
            if not row.api_config_id:
                return "自动匹配"
            api = file_service.get_api_config(row.api_config_id)
            return self._api_display_name(api) if api else "自动匹配"
        if kind == "template":
            if not row.prompt_template_id:
                return "默认模板"
            tpl = prompt_service.get_template(row.prompt_template_id)
            return tpl.name if tpl else "默认模板"
        if kind == "term":
            if not row.term_library_id:
                return "不引用术语"
            lib = next(
                (l for l in self.term_libraries if l["id"] == row.term_library_id), None
            )
            return self._lib_display_name(lib) if lib else "不引用术语"
        if kind == "strategy":
            return (
                m.STRATEGY_LABELS.get(row.strategy, "跳过已有译文")
                if row.strategy else "跳过已有译文"
            )
        return ""

    @rx.event
    def load_lang_configs(self) -> None:
        """加载当前工程的语言方案配置，并同步表格列语言。"""
        pid = self.current_project.get("id")
        if not pid:
            return
        rows = project_lang_config_service.list_configs(int(pid))
        self.lang_configs = []
        for r in rows:
            d = project_lang_config_service.serialize_config(r)
            d["lang_display"] = self.lang_code_to_display.get(r.lang, r.lang)
            d["api_display"] = self._config_option_display("api", r)
            d["template_display"] = self._config_option_display("template", r)
            d["term_display"] = self._config_option_display("term", r)
            d["strategy_display"] = self._config_option_display("strategy", r)
            self.lang_configs.append(d)
        # 表格列语言 = 所有已配置语言
        self.target_langs = [c["lang"] for c in self.lang_configs]
        self.target_lang_display_options = [c["lang_display"] for c in self.lang_configs]
        # 生成 grid 布局列宽字符串：36px(#) 300px(源文案) 260px×N(各语言) 80px(状态) 150px(命中术语) 160px(操作)
        n = len(self.target_lang_display_options)
        self.entry_grid_cols = "36px 300px" + " 260px" * n + " 80px 150px 160px"
        # 可添加的语言 = 全部语言 - 已配置语言
        existing = set(self.target_langs)
        self.lang_config_add_options = [
            d for d in self.lang_display_options
            if self.lang_display_to_code.get(d, d) not in existing
        ]
        self.lang_config_add_display = self.lang_config_add_options[0] if self.lang_config_add_options else ""

    @rx.event
    def set_lang_config_add_display(self, value: str) -> None:
        self.lang_config_add_display = value

    @rx.event
    def set_project_source_lang_display(self, value: str) -> None:
        """校对页修改工程源语言：value 为语言展示名（如 zh-TW 繁體中文）。"""
        pid = self.current_project.get("id")
        if not pid:
            return self._toast("请先打开一个工程")
        code = self.lang_display_to_code.get(value, value)
        if not code or code == self.current_project.get("source_lang"):
            return
        proj = file_service.update_project_source_lang(int(pid), code)
        if proj is None:
            return self._toast("工程不存在")
        # 同步前端展示
        self.project_source_lang_display = value
        self.current_project["source_lang"] = proj.source_lang
        self.current_project["source_lang_display"] = self.lang_code_to_display.get(
            proj.source_lang, proj.source_lang
        )
        return self._toast(f"工程源语言已更新为 {value}")

    @rx.event
    def add_lang_config(self) -> None:
        """添加一个语言方案行。若该语言在设置页有全局 LangProfile 配置，自动预填。"""
        pid = self.current_project.get("id")
        display = self.lang_config_add_display
        if not pid or not display:
            return self._toast("请先选择要添加的目标语言")
        lang = self.lang_display_to_code.get(display, display)
        prof = lang_profile_service.get_profile(lang)
        project_lang_config_service.upsert_config(
            int(pid),
            lang,
            api_config_id=prof.api_config_id if prof else None,
            prompt_template_id=prof.prompt_template_id if prof else None,
            term_library_id=prof.term_library_id if prof else None,
            strategy=prof.strategy if prof else "",
        )
        self.load_lang_configs()
        # 同步重新序列化条目，使新增语言的输入框列随之生成
        self.load_entries()
        return self._toast(f"已添加「{display}」")

    @rx.event
    def remove_lang_config(self, config_id: int) -> None:
        project_lang_config_service.delete_config(int(config_id))
        self.load_lang_configs()
        # 同步重新序列化条目，使删除语言的输入框列随之移除
        self.load_entries()

    @rx.event
    def toggle_lang_config_enabled(self, config_id: int, checked: bool) -> None:
        """勾选/取消勾选某语言方案行（仅决定是否参与翻译，不影响已存译文）。"""
        project_lang_config_service.set_enabled(int(config_id), checked)
        self.load_lang_configs()

    @rx.event
    def set_lang_config_api(self, config_id: int, choice: str) -> None:
        pid = self.current_project.get("id")
        if not pid:
            return
        api_id = None
        if choice != "自动匹配":
            api = next(
                (a for a in file_service.list_api_configs() if self._api_display_name(a) == choice),
                None,
            )
            api_id = api.id if api else None
        row = project_lang_config_service.get_config_by_id(int(config_id))
        if row:
            project_lang_config_service.upsert_config(
                int(pid), row.lang, api_config_id=api_id,
                prompt_template_id=row.prompt_template_id,
                term_library_id=row.term_library_id,
                strategy=row.strategy,
                enabled=row.enabled,
            )
        self.load_lang_configs()

    @rx.event
    def set_lang_config_template(self, config_id: int, choice: str) -> None:
        pid = self.current_project.get("id")
        if not pid:
            return
        tpl_id = None
        if choice != "默认模板":
            tpl = next((t for t in self.prompt_templates if t["name"] == choice), None)
            tpl_id = tpl["id"] if tpl else None
        row = project_lang_config_service.get_config_by_id(int(config_id))
        if row:
            project_lang_config_service.upsert_config(
                int(pid), row.lang, api_config_id=row.api_config_id,
                prompt_template_id=tpl_id,
                term_library_id=row.term_library_id,
                strategy=row.strategy,
                enabled=row.enabled,
            )
        self.load_lang_configs()

    @rx.event
    def set_lang_config_term(self, config_id: int, choice: str) -> None:
        pid = self.current_project.get("id")
        if not pid:
            return
        lib_id = None
        if choice != "不引用术语":
            lib = next(
                (l for l in self.term_libraries if self._lib_display_name(l) == choice), None
            )
            lib_id = lib["id"] if lib else None
        row = project_lang_config_service.get_config_by_id(int(config_id))
        if row:
            project_lang_config_service.upsert_config(
                int(pid), row.lang, api_config_id=row.api_config_id,
                prompt_template_id=row.prompt_template_id,
                term_library_id=lib_id,
                strategy=row.strategy,
                enabled=row.enabled,
            )
        self.load_lang_configs()

    @rx.event
    def set_lang_config_strategy(self, config_id: int, choice: str) -> None:
        pid = self.current_project.get("id")
        if not pid:
            return
        strategy = STRATEGY_LABEL_TO_CODE.get(choice, "")
        row = project_lang_config_service.get_config_by_id(int(config_id))
        if row:
            project_lang_config_service.upsert_config(
                int(pid), row.lang, api_config_id=row.api_config_id,
                prompt_template_id=row.prompt_template_id,
                term_library_id=row.term_library_id,
                strategy=strategy,
                enabled=row.enabled,
            )
        self.load_lang_configs()

    @rx.event
    def set_translate_strategy(self, value: str) -> None:
        # select 的 value 绑定此字段，需与中文 options 匹配，直接存中文标签
        self.translate_strategy = value

    @rx.event
    def edit_entry_text(self, entry_id: int, lang: str, value: str) -> None:
        file_service.update_entry_text(int(entry_id), lang, value)
        self.load_entries()

    @rx.event
    def edit_entry_source(self, entry_id: int, value: str) -> None:
        file_service.update_entry_source(int(entry_id), value)
        self.load_entries()

    @rx.event
    def set_new_entry_text(self, value: str) -> None:
        self.new_entry_text = value

    @rx.event
    def add_new_entry(self) -> None:
        """在校对表格末尾新增一行（仅源文案）。"""
        pid = self.current_project.get("id")
        if not pid:
            return
        text = (self.new_entry_text or "").strip()
        if not text:
            return
        entries = file_service.list_entries(pid)
        max_sort = max((e.sort_index for e in entries), default=0)
        file_service.create_entry(pid, text, sort_index=max_sort + 1)
        self.new_entry_text = ""
        self.load_entries()

    @rx.event
    def set_entry_status(self, entry_id: int, status: str) -> None:
        # status 为中文标签，映射回枚举存储
        code = STATUS_LABEL_TO_CODE.get(status, status)
        file_service.update_entry_status(int(entry_id), code)
        self.load_entries()

    @rx.event
    def request_delete_project(self, project_id: int) -> None:
        """请求删除工程：弹出二次确认。"""
        self.project_delete_confirm_id = int(project_id)

    @rx.event
    def cancel_delete_project(self) -> None:
        self.project_delete_confirm_id = 0

    @rx.event
    def do_delete_project(self) -> None:
        """确认后真正删除工程及其全部条目。"""
        pid = self.project_delete_confirm_id
        if not pid:
            return
        ok = file_service.delete_project(int(pid))
        self.project_delete_confirm_id = 0
        if ok:
            # 若删除的是当前打开的工程，退出工作台
            if self.current_project.get("id") == pid:
                self.has_project = False
                self.current_project = {}
                self.entries = []
                self.target_langs = []
                self.target_lang_display_options = []
                self.entry_grid_cols = ""
                self.lang_configs = []
                self.lang_config_add_options = []
                self.lang_config_add_display = ""
            self.load_projects()
            return self._toast("工程已删除")
        self.load_projects()
        return self._toast("删除失败：工程不存在")

    @rx.event
    def close_project(self) -> None:
        """关闭当前工程，返回工程选择列表。"""
        self.has_project = False
        self.current_project = {}
        self.entries = []
        self.target_langs = []
        self.target_lang_display_options = []
        self.entry_grid_cols = ""
        self.lang_configs = []
        self.lang_config_add_options = []
        self.lang_config_add_display = ""
        self.progress_done = 0
        self.progress_total = 0
        self.progress_text = ""
        self.is_translating = False

    # =========================================================
    # 翻译
    # =========================================================

    @rx.event
    def load_translate_apis(self) -> None:
        """加载翻译页可选的 API 列表（含"自动匹配"选项）。"""
        apis = file_service.list_api_configs()
        self.api_config_options = ["自动匹配"] + [
            self._api_display_name(a) for a in apis
        ]
        # 若之前手动选的 API 已不存在，回退自动匹配
        if self.translate_api_config_id and self.translate_api_choice != "自动匹配":
            cur = next((a for a in apis if a.id == self.translate_api_config_id), None)
            if cur is None:
                self.translate_api_choice = "自动匹配"
                self.translate_api_config_id = 0

    @rx.event
    def set_translate_api(self, choice: str) -> None:
        """选择翻译页的 API：自动匹配 或 手动指定某个 API。"""
        self.translate_api_choice = choice
        if choice == "自动匹配":
            self.translate_api_config_id = 0
            return
        apis = file_service.list_api_configs()
        # 选项格式为 _api_display_name，按展示名匹配
        cur = next(
            (a for a in apis if self._api_display_name(a) == choice), None
        )
        self.translate_api_config_id = cur.id if cur else 0

    @rx.event
    def load_translate_libraries(self) -> None:
        """加载翻译页面可引用的术语库列表（含"不引用"选项）。"""
        self.term_libraries = term_service.list_libraries()
        self.translate_lib_options = ["不引用术语"] + [
            self._lib_display_name(lib) for lib in self.term_libraries
        ]
        # 若当前选中的库已不存在，重置为不引用
        cur = next((l for l in self.term_libraries if l["id"] == self.translate_term_library_id), None)
        self.translate_lib_name = self._lib_display_name(cur) if cur else "不引用术语"
        if cur is None:
            self.translate_term_library_id = 0

    @rx.event
    def set_translate_library(self, name: str) -> None:
        """选择翻译时引用的术语库。"""
        self.translate_lib_name = name
        if name == "不引用术语":
            self.translate_term_library_id = 0
            return
        cur = next(
            (l for l in self.term_libraries if self._lib_display_name(l) == name), None
        )
        self.translate_term_library_id = cur["id"] if cur else 0

    @rx.event
    def load_translate_prompts(self) -> None:
        """加载翻译页面可选的提示词模板列表（含"默认模板"选项）。"""
        self.prompt_templates = [
            prompt_service.serialize_template(t) for t in prompt_service.list_templates()
        ]
        self.translate_prompt_options = ["默认模板"] + [
            t["name"] for t in self.prompt_templates
        ]
        # 若当前选中的模板已不存在，重置为默认
        cur = next(
            (t for t in self.prompt_templates if t["id"] == self.translate_prompt_template_id),
            None,
        )
        self.translate_prompt_name = cur["name"] if cur else "默认模板"
        if cur is None:
            self.translate_prompt_template_id = 0

    @rx.event
    def set_translate_prompt(self, name: str) -> None:
        """选择翻译时使用的提示词模板。"""
        self.translate_prompt_name = name
        if name == "默认模板":
            self.translate_prompt_template_id = 0
            return
        cur = next((t for t in self.prompt_templates if t["name"] == name), None)
        self.translate_prompt_template_id = cur["id"] if cur else 0

    @rx.event
    def start_translate(self):
        """同步事件：立即进入「翻译中」状态并 yield 后台 async 事件执行翻译，
        保证前端立刻有反馈（按钮 loading + 进度条），不会卡住页面。"""
        pid = self.current_project.get("id")
        if not pid:
            return self._toast("请先打开一个工程")
        rows = [c for c in self.lang_configs if c["enabled"]]
        if not rows:
            return self._toast("请至少勾选一个语言方案行")
        if self.is_translating:
            return
        entries = file_service.list_entries(pid)
        if not entries:
            return self._toast("该工程暂无条目")
        self.is_translating = True
        self._set_progress(0, len(entries) * len(rows), "正在准备翻译…")
        yield type(self).run_translate(pid, [c["id"] for c in rows])

    def _set_progress(self, done: int, total: int, text: str) -> None:
        """统一设置进度状态，并预计算百分比字符串。"""
        self.progress_done = int(done)
        self.progress_total = int(total)
        self.progress_text = text
        if int(total) > 0:
            pct = round(int(done) * 100 / int(total))
            self.progress_pct = f"{min(100, pct)}%"
        else:
            self.progress_pct = "0%"

    def _build_lang_ctx(self, proj, row) -> tuple[dict | None, str]:
        """由语言方案行构造翻译上下文（含 API / translator / prompt / 术语 / 策略）。

        Returns:
            (ctx_dict, "") 成功
            (None, 错误信息) 失败（无 API / 引擎创建失败等）
        """
        lang = row.lang
        lang_disp = self.lang_code_to_display.get(lang, lang)
        # API：行配置 > 默认 API
        api = None
        if row.api_config_id:
            api = file_service.get_api_config(row.api_config_id)
        if api is None:
            api = file_service.get_default_api_config()
        if api is None:
            return None, f"{lang_disp}：无可用 API，跳过"
        try:
            translator = create_translator(api.engine_name, api)
        except Exception as exc:  # noqa: BLE001
            return None, f"{lang_disp}：引擎创建失败：{exc}"
        # 提示词：行配置 > 默认模板 > 内置默认
        tpl = None
        if row.prompt_template_id:
            tpl = prompt_service.get_template(row.prompt_template_id)
        if tpl is None:
            tpl = prompt_service.get_default_template()
        prompt_msgs = (
            tpl.get_messages()
            if tpl is not None
            else prompt_service.build_default_translation_template()
        )
        if not prompt_msgs:
            prompt_msgs = prompt_service.build_default_translation_template()
        # 术语：行配置 > 不引用；仅引用与工程源语言匹配（或未限定）的术语库
        terms, _ = term_service.terms_for_prompt(
            row.term_library_id or 0,
            target_lang=lang,
            source_lang=proj.source_lang,
        )
        term_by_source = {t.source_term: t for t in terms if t.source_term}
        return (
            {
                "lang": lang,
                "lang_disp": lang_disp,
                "api": api,
                "translator": translator,
                "prompt_msgs": prompt_msgs,
                "terms": terms,
                "term_by_source": term_by_source,
                "strategy": row.strategy or m.STRATEGY_SKIP,
                # 语言级计数
                "translated": 0,
                "skipped": 0,
                "failed": 0,
            },
            "",
        )

    @rx.event(background=True)
    async def retranslate_cell(self, entry_id: int, lang: str) -> None:
        """重翻单个条目的单个语言（强制覆盖该语言已有译文）。"""
        pid = self.current_project.get("id")
        if not pid:
            return self._toast("请先打开一个工程")
        if self.is_translating:
            return self._toast("当前正在翻译中，请稍后再试")
        try:
            proj = file_service.get_project(pid)
            entry = file_service.get_entry(int(entry_id))
            if proj is None or entry is None:
                return self._toast("条目不存在")
            row = project_lang_config_service.get_config(pid, lang)
            if row is None:
                return self._toast(f"语言 {lang} 未配置方案，无法重翻")
            ctx, err = self._build_lang_ctx(proj, row)
            if err:
                return self._toast(err)
        except Exception as exc:  # noqa: BLE001
            return self._toast(f"准备重翻失败：{exc}")
        async with self:
            self.is_translating = True
            self._set_progress(0, 1, f"正在重翻 {lang}…")
        try:
            status = await asyncio.to_thread(
                translation_service.translate_single,
                entry,
                ctx["translator"],
                ctx["prompt_msgs"],
                source_lang=proj.source_lang,
                target_lang=lang,
                terms=ctx["terms"],
                term_by_source=ctx["term_by_source"],
                strategy=m.STRATEGY_OVERWRITE,
            )
        except Exception as exc:  # noqa: BLE001
            async with self:
                self.is_translating = False
                self.progress_text = ""
            return self._toast(f"重翻失败：{exc}")
        # 刷新统计与条目
        fresh_entries = file_service.list_entries(pid)
        file_service.recompute_project_stats(proj, fresh_entries)
        async with self:
            self.load_entries()
            self.load_projects()
            self.is_translating = False
            self.progress_text = ""
        if status == "translated":
            return self._toast(f"{lang} 重翻完成")
        return self._toast(f"{lang} 重翻无结果（可能返回空译文）")

    @rx.event(background=True)
    async def retranslate_row(self, entry_id: int) -> None:
        """重翻单个条目所有已启用语言（强制覆盖所有译文）。"""
        pid = self.current_project.get("id")
        if not pid:
            return self._toast("请先打开一个工程")
        if self.is_translating:
            return self._toast("当前正在翻译中，请稍后再试")
        rows = [c for c in self.lang_configs if c.get("enabled")]
        if not rows:
            return self._toast("请至少勾选一个语言方案行")
        try:
            proj = file_service.get_project(pid)
            entry = file_service.get_entry(int(entry_id))
            if proj is None or entry is None:
                return self._toast("条目不存在")
            ctxs: list[dict] = []
            errors: list[str] = []
            for row in rows:
                r = project_lang_config_service.get_config_by_id(int(row["id"]))
                if r is None:
                    continue
                ctx, err = self._build_lang_ctx(proj, r)
                if err:
                    errors.append(err)
                else:
                    ctxs.append(ctx)
            if not ctxs:
                return self._toast(
                    "；".join(errors) if errors else "无可重翻的语言方案"
                )
        except Exception as exc:  # noqa: BLE001
            return self._toast(f"准备重翻失败：{exc}")
        grand_total = len(ctxs)
        async with self:
            self.is_translating = True
            self._set_progress(0, grand_total, f"正在重翻 {grand_total} 个语言…")
        results = await asyncio.to_thread(
            self._retranslate_row_sync, proj, entry, ctxs
        )
        # 刷新统计与条目
        fresh_entries = file_service.list_entries(pid)
        file_service.recompute_project_stats(proj, fresh_entries)
        async with self:
            self.load_entries()
            self.load_projects()
            self.is_translating = False
            self.progress_text = ""
        ok = sum(1 for r in results if r == "translated")
        failed = sum(1 for r in results if r == "failed")
        skipped = grand_total - ok - failed
        msg = f"重翻完成：成功 {ok}，失败 {failed}，跳过 {skipped}"
        if errors:
            msg += "；" + "；".join(errors)
        return self._toast(msg)

    @staticmethod
    def _retranslate_row_sync(proj, entry, ctxs: list[dict]) -> list[str]:
        """同步重翻一行：所有语言并行（每 API 一个信号量），强制覆盖。"""
        stats_lock = threading.Lock()
        results: list[str] = ["pending"] * len(ctxs)

        # 按 API 分组，每组一个动态信号量
        api_groups: dict[int, dict] = {}
        for i, ctx in enumerate(ctxs):
            api_id = ctx["api"].id or 0
            group = api_groups.get(api_id)
            if group is None:
                try:
                    eff = concurrency_service.resolve_effective_concurrency(ctx["api"])
                except Exception:  # noqa: BLE001
                    eff = config.CONCURRENCY_DEFAULT_START
                group = {
                    "sem": concurrency_service.DynamicSemaphore(max(1, eff)),
                    "count": 0,
                }
                api_groups[api_id] = group
            ctx["_group"] = group

        def worker(i: int) -> None:
            ctx = ctxs[i]
            group = ctx["_group"]
            sem = group["sem"]
            sem.acquire()
            try:
                status = translation_service.translate_single(
                    entry,
                    ctx["translator"],
                    ctx["prompt_msgs"],
                    source_lang=proj.source_lang,
                    target_lang=ctx["lang"],
                    terms=ctx["terms"],
                    term_by_source=ctx["term_by_source"],
                    strategy=m.STRATEGY_OVERWRITE,
                )
            except Exception:  # noqa: BLE001
                status = "failed"
            finally:
                sem.release()
            with stats_lock:
                results[i] = status

        with ThreadPoolExecutor(
            max_workers=max(1, min(len(ctxs), config.CONCURRENCY_ABS_CAP))
        ) as ex:
            list(ex.map(worker, range(len(ctxs))))
        return results

    @rx.event(background=True)
    async def run_translate(self, pid: int, config_ids: list[int]) -> None:
        """后台 async 事件：全局并发并行翻译。

        所有目标语言（config_ids）与所有条目的翻译任务进入统一任务池，
        按「每 API 一个并发信号量」并行调度，不再按语言逐列串行。
        每个 API 的并发值优先取手动上限 / 已探测缓存，否则自动探测并持久化。
        运行中遇容量类错误自动降级并发、重测并覆盖缓存，重试该任务。
        """
        try:
            proj = file_service.get_project(int(pid))
            entries = file_service.list_entries(int(pid))
            if proj is None:
                async with self:
                    self.is_translating = False
                return self._toast("工程不存在")
        except Exception as exc:  # noqa: BLE001
            async with self:
                self.is_translating = False
            return self._toast(f"准备翻译失败: {exc}")

        loop = asyncio.get_running_loop()
        # 解析每个语言行 → 语言上下文（含 API / translator / prompt / 术语 / 策略）
        lang_ctxs: list[dict] = []
        summary: list[str] = []
        for cid in config_ids:
            row = project_lang_config_service.get_config_by_id(int(cid))
            if row is None:
                continue
            ctx, err = self._build_lang_ctx(proj, row)
            if err:
                summary.append(err)
                continue
            lang_ctxs.append(ctx)

        if not lang_ctxs:
            summary_text = "；".join(summary) if summary else "无可翻译的语言方案"
            async with self:
                self.is_translating = False
                self.progress_text = f"完成：{summary_text}"
            return self._toast(f"完成：{summary_text}")

        # 按 API 分组，每组一个可动态调整的并发信号量
        api_groups: dict[int, dict] = {}
        for ctx in lang_ctxs:
            api_id = ctx["api"].id or 0
            group = api_groups.get(api_id)
            if group is None:
                try:
                    effective = concurrency_service.get_or_probe_effective(ctx["api"])
                except Exception as exc:  # noqa: BLE001
                    effective = config.CONCURRENCY_DEFAULT_START
                    summary.append(f"{ctx['lang_disp']}：并发探测失败({exc})，用默认并发")
                group = {
                    "api": ctx["api"],
                    "sem": concurrency_service.DynamicSemaphore(effective),
                    "effective": effective,
                    "ctxs": [],
                }
                api_groups[api_id] = group
            group["ctxs"].append(ctx)
            ctx["group"] = group

        grand_total = len(entries) * len(lang_ctxs)
        done_count = 0
        done_lock = threading.Lock()
        futures: list = []
        futures_lock = threading.Lock()
        stats_lock = threading.Lock()

        def bump_progress(cur_text: str = "") -> None:
            with done_lock:
                done = done_count
            if done % 5 != 0 and done != grand_total:
                return

            async def _apply() -> None:
                async with self:
                    self._set_progress(
                        done,
                        grand_total,
                        f"正在翻译 {done}/{grand_total}",
                    )

            with futures_lock:
                futures.append(asyncio.run_coroutine_threadsafe(_apply(), loop))

        def run_parallel() -> None:
            """事件驱动并发调度（在后台线程执行，不阻塞事件循环）。

            所有语言×条目的任务进入统一任务池，按「每 API 一个信号量」限流。
            遇容量错误：降级该 API 组并发、重测持久化、重投递该任务重试。
            """
            nonlocal done_count
            entry_lock = threading.Lock()
            tasks: deque = deque()
            for li in range(len(lang_ctxs)):
                for ei in range(len(entries)):
                    tasks.append((li, ei))
            running: dict[Future, tuple[int, int]] = {}
            executor = ThreadPoolExecutor(max_workers=config.CONCURRENCY_ABS_CAP)
            degraded_api: set[int] = set()

            def worker(li: int, ei: int) -> str:
                nonlocal done_count
                ctx = lang_ctxs[li]
                entry = entries[ei]
                group = ctx["group"]
                sem = group["sem"]

                def finish(status: str, fail: bool = False) -> str:
                    if not fail:
                        if status == "translated":
                            with stats_lock:
                                ctx["translated"] += 1
                        elif status == "skipped":
                            with stats_lock:
                                ctx["skipped"] += 1
                        else:
                            with stats_lock:
                                ctx["failed"] += 1
                    with done_lock:
                        done_count += 1
                    bump_progress()
                    return status

                # 跳过不占用并发名额
                if not translation_service._should_translate(
                    entry, ctx["lang"], ctx["strategy"]
                ):
                    return finish("skipped")
                sem.acquire()
                try:
                    status = translation_service.translate_single(
                        entry,
                        ctx["translator"],
                        ctx["prompt_msgs"],
                        source_lang=proj.source_lang,
                        target_lang=ctx["lang"],
                        terms=ctx["terms"],
                        term_by_source=ctx["term_by_source"],
                        strategy=ctx["strategy"],
                        entry_lock=entry_lock,
                        capacity_error_raise=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    if concurrency_service.is_capacity_error(exc):
                        api_id = group["api"].id or 0
                        if api_id not in degraded_api:
                            degraded_api.add(api_id)
                            try:
                                new_eff = concurrency_service.downgrade_concurrency(
                                    group["api"], group["effective"]
                                )
                            except Exception:  # noqa: BLE001
                                new_eff = max(
                                    config.CONCURRENCY_PROBE_MIN,
                                    group["effective"] // 2,
                                )
                            group["effective"] = new_eff
                            sem.set_count(new_eff)
                        # retry：不计完成数，重新入队
                        return "retry"
                    return finish("failed")
                finally:
                    sem.release()
                return finish(status)

            def launch() -> None:
                while tasks and len(running) < config.CONCURRENCY_ABS_CAP:
                    li, ei = tasks.popleft()
                    fut = executor.submit(worker, li, ei)
                    running[fut] = (li, ei)

            launch()
            try:
                while running or tasks:
                    launch()
                    if not running:
                        break
                    done_set, still = wait(
                        list(running.keys()),
                        return_when=FIRST_COMPLETED,
                        timeout=1,
                    )
                    if not done_set:
                        continue
                    completed = [(running[f], f) for f in done_set]
                    running = {f: running[f] for f in still}
                    for (li, ei), fut in completed:
                        try:
                            status = fut.result()
                        except Exception:  # noqa: BLE001
                            status = "failed"
                            with stats_lock:
                                lang_ctxs[li]["failed"] += 1
                        if status == "retry":
                            tasks.appendleft((li, ei))
            finally:
                executor.shutdown(wait=True)

        await asyncio.to_thread(run_parallel)

        # 等待已排队的进度更新写完，避免最终结果被覆盖
        with futures_lock:
            pending = list(futures)
        for fut in pending:
            try:
                fut.result(timeout=1)
            except Exception:  # noqa: BLE001
                pass

        # 刷新统计与条目
        fresh_entries = file_service.list_entries(int(pid))
        file_service.recompute_project_stats(proj, fresh_entries)
        async with self:
            self.load_entries()
            self.load_projects()
            summary_text = "；".join(
                f"{ctx['lang_disp']}：翻译{ctx['translated']} "
                f"跳过{ctx['skipped']} 失败{ctx['failed']}"
                for ctx in lang_ctxs
            )
            if summary:
                summary_text = "；".join([*summary, summary_text]) if summary_text else "；".join(summary)
            self.progress_text = f"完成：{summary_text}"
            self.is_translating = False
        return self._toast(f"完成：{summary_text}")

    @rx.event
    def request_clear_translations(self) -> None:
        """请求清空所选语言方案行的全部译文：弹出二次确认。"""
        rows = [c for c in self.lang_configs if c["enabled"]]
        if not rows:
            return self._toast("请至少勾选一个语言方案行")
        self.clear_confirm_open = True

    @rx.event
    def cancel_clear_translations(self) -> None:
        self.clear_confirm_open = False

    @rx.event
    def do_clear_translations(self) -> None:
        """确认后清空勾选语言方案的译文，并将无译文的条目重置为待译。"""
        pid = self.current_project.get("id")
        rows = [c for c in self.lang_configs if c["enabled"]]
        self.clear_confirm_open = False
        if not pid or not rows:
            return
        langs = [c["lang"] for c in rows]
        total = 0
        for lang in langs:
            total += file_service.clear_entry_translations(int(pid), lang)
        proj = file_service.get_project(int(pid))
        if proj is not None:
            file_service.recompute_project_stats(proj, file_service.list_entries(int(pid)))
        self.load_entries()
        self.load_projects()
        lang_disp = "、".join(c["lang_display"] for c in rows)
        return self._toast(f"已清空 {total} 条译文（{lang_disp}）")

    # =========================================================
    # 导出
    # =========================================================

    @rx.event
    def export_project(self) -> None:
        pid = self.current_project.get("id")
        if not pid:
            return
        try:
            out = file_service.export_project_xlsx(pid)
            return self._toast(f"已导出: {out}")
        except Exception as exc:  # noqa: BLE001
            return self._toast(f"导出失败: {exc}")

    # =========================================================
    # 术语库
    # =========================================================

    def _refresh_libraries(self) -> None:
        """加载术语库列表；若无当前库则默认选中第一个。"""
        self.term_libraries = term_service.list_libraries()
        self.term_library_names = [self._lib_display_name(lib) for lib in self.term_libraries]
        ids = [lib["id"] for lib in self.term_libraries]
        if self.selected_library_id not in ids:
            self.selected_library_id = ids[0] if ids else 0
        cur = next((l for l in self.term_libraries if l["id"] == self.selected_library_id), None)
        self.selected_library_name = self._lib_display_name(cur) if cur else ""

    def _refresh_terms(self) -> None:
        """加载当前库当前页术语 + 分类列表（分页查询）+ 表格语言列。"""
        rows, total = term_service.query_terms(
            library_id=self.selected_library_id,
            page=self.term_page,
            page_size=self.term_page_size,
            category=self.term_category,
            keyword=self.term_search_keyword,
        )
        self.terms = [self._serialize_term(t) for t in rows]
        # 当前库实际用到的语言（表头），全库提取，避免翻页变化
        self.term_table_langs = term_service.get_library_langs(self.selected_library_id)
        # 术语表格 typed 行（cells 按 term_table_langs 顺序对齐）
        self.term_rows = [
            TermRow(
                id=t.id or 0,
                source_term=t.source_term,
                translations=tr,
                cells=[
                    {"lang": lang, "text": tr.get(lang, "")}
                    for lang in self.term_table_langs
                ],
                note=t.note,
            )
            for t in rows
            for tr in [t.get_translations()]
        ]
        self.term_total = total
        total_pages = max(1, -(-total // self.term_page_size))
        self.term_total_pages = total_pages
        if self.term_page > total_pages:
            self.term_page = total_pages
        self.term_categories = term_service.list_categories(library_id=self.selected_library_id)
        self.term_category_options = ["全部"] + self.term_categories

    @rx.event
    def load_terms(self) -> None:
        self._refresh_libraries()
        self._refresh_terms()

    @rx.event
    def select_library(self, name: str) -> None:
        cur = next(
            (l for l in self.term_libraries if self._lib_display_name(l) == name), None
        )
        if cur is None:
            return
        self.selected_library_id = cur["id"]
        self.selected_library_name = self._lib_display_name(cur)
        self.term_page = 1
        self.term_category = ""
        self._refresh_terms()

    @rx.event
    def set_term_new_category(self, value: str) -> None:
        self.term_new_category = value

    @rx.event
    def set_term_category_filter(self, category: str) -> None:
        self.term_category = "" if category == "全部" else category
        self.term_page = 1
        self._refresh_terms()

    @rx.event
    def set_term_search_keyword(self, value: str) -> None:
        """更新术语搜索关键词（实时过滤）。"""
        self.term_search_keyword = value
        self.term_page = 1
        self._refresh_terms()

    @rx.event
    def set_term_page_size(self, size: str) -> None:
        try:
            self.term_page_size = int(size)
        except ValueError:
            return
        self.term_page = 1
        self._refresh_terms()

    @rx.event
    def goto_term_page(self, page: int) -> None:
        total_pages = max(1, -(-self.term_total // self.term_page_size))
        page = max(1, min(int(page), total_pages))
        self.term_page = page
        self._refresh_terms()

    @rx.event
    def change_term_category(self, term_id: int, category: str) -> None:
        term_service.set_term_category(int(term_id), category)
        self._refresh_terms()

    # ---- 术语库管理对话框 ----

    @rx.event
    def open_lib_dialog(self) -> None:
        self.lib_dialog_open = True
        self.lib_new_name = ""
        self.lib_new_desc = ""
        self.lib_new_source_lang_display = "不限定"

    @rx.event
    def close_lib_dialog(self) -> None:
        self.lib_dialog_open = False

    @rx.event
    def set_lib_new_name(self, value: str) -> None:
        self.lib_new_name = value

    @rx.event
    def set_lib_new_desc(self, value: str) -> None:
        self.lib_new_desc = value

    @rx.event
    def set_lib_new_source_lang(self, value: str) -> None:
        self.lib_new_source_lang_display = value

    @rx.event
    def confirm_create_library(self) -> None:
        name = self.lib_new_name.strip()
        if not name:
            return self._toast("请输入术语库名称")
        display = self.lib_new_source_lang_display
        source_lang = (
            self.lang_display_to_code.get(display, display) if display != "不限定" else ""
        )
        lib = term_service.create_library(name, self.lib_new_desc.strip(), source_lang=source_lang)
        self.lib_dialog_open = False
        self.selected_library_id = lib.id
        self.selected_library_name = lib.name
        self._refresh_libraries()
        self.term_page = 1
        self.term_category = ""
        self._refresh_terms()
        return self._toast(f"已创建术语库：{lib.name}")

    @rx.event
    def confirm_delete_library(self) -> None:
        """请求删除当前库：弹出二次确认。"""
        if not self.selected_library_id:
            return self._toast("请先选择要删除的术语库")
        self.lib_delete_confirm = True

    @rx.event
    def cancel_delete_library(self) -> None:
        self.lib_delete_confirm = False

    @rx.event
    def do_delete_library(self) -> None:
        """确认后真正删除当前库及其全部术语。"""
        self.lib_delete_confirm = False
        if not self.selected_library_id:
            return self._toast("请先选择要删除的术语库")
        lib_id = self.selected_library_id
        ok = term_service.delete_library(lib_id)
        if ok:
            self.selected_library_id = 0
            self.selected_library_name = ""
            self._refresh_libraries()
            self.term_page = 1
            self._refresh_terms()
            return self._toast("已删除术语库及其全部术语")
        return self._toast("删除失败：无法删除该术语库")

    # ---- 术语导入向导（列映射） ----

    @rx.event
    def open_term_import(self) -> None:
        self.term_import_open = True
        self.term_import_step = 1
        self.term_import_source_type = "file"
        self.term_wizard_file_path = ""
        self.term_wizard_url = ""
        self.term_wizard_text = ""
        self.term_preview_headers = []
        self.term_preview_rows = []
        self.term_column_map = {}

    @rx.event
    def close_term_import(self) -> None:
        self.term_import_open = False

    @rx.event
    def set_term_import_source_type(self, value: str) -> None:
        mapping = {"本地文件": "file", "在线表格": "url", "纯文本": "text"}
        self.term_import_source_type = mapping.get(value, value)

    @rx.event
    def set_term_import_step(self, step: int) -> None:
        self.term_import_step = int(step)

    @rx.event
    def set_term_wizard_url(self, value: str) -> None:
        self.term_wizard_url = value

    @rx.event
    def set_term_wizard_text(self, value: str) -> None:
        self.term_wizard_text = value

    def _load_term_preview(self, source: str, is_online: bool) -> str | None:
        """从来源读取 DataFrame 并填充预览 + 自动猜测列映射。

        返回 None 表示成功，否则返回错误消息（由调用方触发 toast）。
        """
        try:
            df = term_sources.fetch_dataframe(source, is_online)
        except Exception as exc:  # noqa: BLE001
            return f"读取表格失败: {exc}"
        headers = [str(c) for c in df.columns]
        self.term_preview_headers = headers
        self.term_preview_rows = [
            df.iloc[i].astype(str).tolist()
            for i in range(min(config.PREVIEW_ROWS, len(df)))
        ]
        self.term_column_map = self._guess_term_column_map(headers)
        self.term_import_step = 2
        return None

    @staticmethod
    def _guess_term_column_map(headers: list[str]) -> dict[str, str]:
        src_hints = ("源术语", "原文", "source", "term", "source_term")
        note_hints = ("备注", "说明", "note", "remark", "comment")
        roles: dict[str, str] = {}
        # 识别多语言目标列
        lang_roles: dict[str, str] = {}
        for c in headers:
            cl = str(c).strip().lower()
            if any(h in cl for h in note_hints):
                roles[c] = "note"
                continue
            lang = term_service.guess_lang_from_header(c)
            if lang:
                lang_roles[c] = f"target_lang:{lang}"
        # 源术语列：优先列名提示；否则若有中文语言列（典型源语言是中文）用中文列；
        # 再否则用第1个非语言列
        src = next((c for c in headers if any(h in str(c).strip().lower() for h in src_hints)), None)
        if src is None:
            src = next((c for c, _lang in lang_roles.items() if c in lang_roles and "zh-CN" in lang_roles[c]), None)
        if src is None:
            src = next((c for c in headers if c not in lang_roles), None)
        if src:
            roles.pop(src, None)  # 若源列是某语言列，先从目标角色移除
            roles[src] = "source_term"
        roles.update(lang_roles)
        # 兜底：若没有任何目标语言列，用第2个非源列
        if not lang_roles:
            non_src = [c for c in headers if c != src]
            if non_src:
                roles[non_src[0]] = f"target_lang:{config.DEFAULT_TARGET_LANG}"
        return roles

    @rx.event
    async def upload_term_file(self, files: list[rx.UploadFile]) -> None:
        if not files:
            return
        upload = files[0]
        path = file_service.save_upload(upload, upload.filename)
        self.term_wizard_file_path = path
        err = await asyncio.to_thread(self._load_term_preview, path, False)
        if err is not None:
            return self._toast(err)

    @rx.event
    async def load_term_url(self) -> None:
        url = self.term_wizard_url.strip()
        if not url:
            return self._toast("请输入在线表格链接")
        err = await asyncio.to_thread(self._load_term_preview, url, True)
        if err is not None:
            return self._toast(err)

    @rx.event
    async def load_term_text(self) -> None:
        text = self.term_wizard_text.strip()
        if not text:
            return self._toast("请粘贴术语文本（每行一条，可用逗号/Tab/等号分隔）")
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".txt", prefix="terms_")
        import os

        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        self.term_wizard_file_path = path
        err = await asyncio.to_thread(self._load_term_preview, path, False)
        if err is not None:
            return self._toast(err)

    @rx.event
    def set_term_column_role(self, col: str, label: str) -> None:
        # 下拉返回 label，映射回内部角色值（source_term / target_lang:<code> / note / ignore）
        role = label
        mapping = {"源术语": "source_term", "备注": "note", "忽略": "ignore"}
        if label in mapping:
            role = mapping[label]
        elif label.startswith("目标·"):
            name = label[len("目标·"):]
            code = self.lang_label_to_code.get(name)
            if not code:
                return
            role = f"target_lang:{code}"
        self.term_column_map = dict(self.term_column_map)
        self.term_column_map[col] = role

    @rx.event
    async def confirm_term_import(self) -> None:
        """按当前列映射导入术语到当前术语库。"""
        if not self.selected_library_id:
            return self._toast("请先创建或选择术语库")
        source = (
            self.term_wizard_file_path
            or self.term_wizard_url.strip()
            or self.term_wizard_text.strip()
        )
        if not source:
            return self._toast("请先上传文件、填入链接或粘贴文本")
        is_online = bool(self.term_wizard_url.strip()) and not self.term_wizard_file_path
        self.term_importing = True
        self.term_import_status = "正在导入术语…"
        try:
            n = await asyncio.to_thread(
                term_service.import_terms,
                source,
                is_online,
                self.selected_library_id,
                self.term_new_category,
                dict(self.term_column_map),
            )
            self.term_import_status = f"已导入 {n} 条术语"
            self.term_import_open = False
            self._refresh_terms()
            return self._toast(f"导入成功：{n} 条术语")
        except Exception as exc:  # noqa: BLE001
            self.term_import_status = f"导入失败：{exc}"
            return self._toast(f"导入失败: {exc}")
        finally:
            self.term_importing = False

    @rx.event
    def delete_term(self, term_id: int) -> None:
        term_service.delete_term(int(term_id))
        self._refresh_terms()

    @rx.event
    def update_term_source(self, term_id: int, value: str) -> None:
        term_service.update_term_source(int(term_id), value)
        # 更新当前行内存状态，避免整表刷新
        self.term_rows = [
            TermRow(**{**row.model_dump(), "source_term": value}) if row.id == term_id else row
            for row in self.term_rows
        ]

    @rx.event
    def update_term_translation(self, term_id: int, lang: str, value: str) -> None:
        term_service.update_term_translation(int(term_id), lang, value)
        new_rows = []
        for row in self.term_rows:
            if row.id != term_id:
                new_rows.append(row)
                continue
            tr = dict(row.translations)
            if value.strip():
                tr[lang] = value
            else:
                tr.pop(lang, None)
            new_rows.append(
                TermRow(
                    id=row.id,
                    source_term=row.source_term,
                    translations=tr,
                    cells=[{"lang": l, "text": tr.get(l, "")} for l in self.term_table_langs],
                    note=row.note,
                )
            )
        self.term_rows = new_rows

    @rx.event
    def update_term_note(self, term_id: int, value: str) -> None:
        term_service.update_term_note(int(term_id), value)
        self.term_rows = [
            TermRow(**{**row.model_dump(), "note": value}) if row.id == term_id else row
            for row in self.term_rows
        ]

    # =========================================================
    # 提示词模板
    # =========================================================

    @rx.event
    def load_prompt_templates(self) -> None:
        self.prompt_templates = [prompt_service.serialize_template(t) for t in prompt_service.list_templates()]
        self.prompt_var_docs = prompt_service.prompt_var_docs()

    @rx.event
    def new_prompt(self) -> None:
        self.current_prompt_id = 0
        self.current_prompt_name = ""
        self.current_prompt_desc = ""
        self.current_prompt_messages = [
            {"role": "system", "content": "你是专业的本地化翻译专家。"},
            {"role": "user", "content": "请翻译：{source_text}"},
        ]

    @rx.event
    def open_prompt(self, tpl_id: int) -> None:
        tpl = prompt_service.get_template(int(tpl_id))
        if tpl is None:
            return
        self.current_prompt_id = tpl.id
        self.current_prompt_name = tpl.name
        self.current_prompt_desc = tpl.description
        self.current_prompt_messages = tpl.get_messages()

    @rx.event
    def set_prompt_name(self, value: str) -> None:
        self.current_prompt_name = value

    @rx.event
    def set_prompt_desc(self, value: str) -> None:
        self.current_prompt_desc = value

    @rx.event
    def set_prompt_message_content(self, index: int, value: str) -> None:
        idx = int(index)
        if 0 <= idx < len(self.current_prompt_messages):
            self.current_prompt_messages[idx]["content"] = value

    @rx.event
    def toggle_var_picker(self, index: int) -> None:
        """展开/收起指定消息的变量插入栏。"""
        self.var_suggest_index = index if self.var_suggest_index != index else -1

    @rx.event
    def track_var_caret(self, index: int):
        """记录指定消息 textarea 的当前光标位置（前端 JS 读取 selectionStart 回传）。"""
        return rx.call_script(
            "document.activeElement ? (document.activeElement.selectionStart ?? 0) : 0",
            callback=State.set_var_caret(int(index)),
        )

    @rx.event
    def set_var_caret(self, index: int, pos: int) -> None:
        """保存指定消息 textarea 的光标位置。"""
        try:
            self.var_caret_pos[int(index)] = max(0, int(pos or 0))
        except (TypeError, ValueError):
            pass

    @rx.event
    def insert_prompt_var(self, index: int, var_name: str) -> None:
        """把变量插入到指定消息内容的光标位置（无记录则追加到末尾）。"""
        idx = int(index)
        if 0 <= idx < len(self.current_prompt_messages):
            content = self.current_prompt_messages[idx]["content"] or ""
            pos = self.var_caret_pos.get(idx, len(content))
            pos = max(0, min(pos, len(content)))
            var_text = "{" + var_name + "}"
            self.current_prompt_messages[idx]["content"] = (
                content[:pos] + var_text + content[pos:]
            )
            # 插入后光标移到变量之后
            self.var_caret_pos[idx] = pos + len(var_text)
        self.var_suggest_index = -1

    @rx.event
    def hide_var_suggest(self) -> None:
        self.var_suggest_index = -1

    @rx.event
    def set_prompt_message_role(self, index: int, role: str) -> None:
        # role 为中文标签，映射回英文枚举（system/user/assistant）
        idx = int(index)
        if 0 <= idx < len(self.current_prompt_messages):
            self.current_prompt_messages[idx]["role"] = ROLE_LABEL_TO_CODE.get(role, role)

    @rx.event
    def add_prompt_message(self) -> None:
        self.current_prompt_messages.append({"role": "user", "content": ""})

    @rx.event
    def remove_prompt_message(self, index: int) -> None:
        idx = int(index)
        if 0 <= idx < len(self.current_prompt_messages):
            self.current_prompt_messages.pop(idx)

    @rx.event
    def save_prompt(self) -> None:
        name = self.current_prompt_name.strip()
        if not name:
            return self._toast("请填写模板名称")
        messages = [dict(x) for x in self.current_prompt_messages if x.get("content", "").strip()]
        if not messages:
            return self._toast("模板至少需要一条消息")
        if self.current_prompt_id:
            prompt_service.update_template(self.current_prompt_id, name=name, description=self.current_prompt_desc, messages=messages)
        else:
            prompt_service.create_template(name, messages, self.current_prompt_desc)
        self.load_prompt_templates()
        return self._toast("提示词模板已保存")

    @rx.event
    def delete_prompt(self, tpl_id: int) -> None:
        prompt_service.delete_template(int(tpl_id))
        self.load_prompt_templates()

    # =========================================================
    # 引擎配置
    # =========================================================

    @rx.event
    def load_api_configs(self) -> None:
        self.api_configs = [
            file_service.serialize_api_config(a)
            for a in file_service.list_api_configs()
        ]
        for cfg in self.api_configs:
            mc = cfg.get("max_concurrency", 0) or 0
            tc = cfg.get("tested_concurrency", 0) or 0
            cfg["max_concurrency_disp"] = f"并发上限：{mc}" if mc > 0 else ""
            cfg["tested_concurrency_disp"] = f"已探测并发：{tc}" if tc > 0 else ""
        self.engine_names = get_registered_engines()

    # ---- 语言翻译配置（LangProfile） ----

    @rx.event
    def load_lang_profiles(self) -> None:
        """加载语言翻译配置列表，并刷新表单下拉选项。"""
        self.lang_profiles = []
        api_by_id = {a.id: a for a in file_service.list_api_configs()}
        for p in lang_profile_service.list_profiles():
            d = lang_profile_service.serialize_profile(p)
            d["lang_display"] = self.lang_code_to_display.get(p.lang, p.lang)
            api = api_by_id.get(p.api_config_id) if p.api_config_id else None
            d["api_display"] = f"{api.engine_name} {api.model}" if api else "（默认）"
            tpl = (
                prompt_service.get_template(p.prompt_template_id)
                if p.prompt_template_id else None
            )
            d["template_display"] = tpl.name if tpl else "（默认）"
            lib = next(
                (l for l in self.term_libraries if l["id"] == p.term_library_id),
                None,
            ) if p.term_library_id else None
            d["term_display"] = self._lib_display_name(lib) if lib else "（不引用）"
            d["strategy_display"] = (
                m.STRATEGY_LABELS.get(p.strategy, "（跟随翻译页）")
                if p.strategy else "（跟随翻译页）"
            )
            self.lang_profiles.append(d)
        self.profile_lang_options = list(self.lang_display_options)
        self.profile_api_options = ["（不指定）"] + [
            self._api_display_name(a) for a in self.api_configs
        ]
        self.profile_template_options = ["（不指定）"] + [
            t["name"] for t in self.prompt_templates
        ]
        self.profile_term_options = ["（不指定）"] + [
            self._lib_display_name(lib) for lib in self.term_libraries
        ]

    @rx.event
    def set_profile_form_lang(self, value: str) -> None:
        self.profile_form_lang_display = value

    @rx.event
    def set_profile_form_api(self, value: str) -> None:
        self.profile_form_api = value

    @rx.event
    def set_profile_form_template(self, value: str) -> None:
        self.profile_form_template = value

    @rx.event
    def set_profile_form_term(self, value: str) -> None:
        self.profile_form_term = value

    @rx.event
    def set_profile_form_strategy(self, value: str) -> None:
        self.profile_form_strategy = value

    @rx.event
    def reset_lang_profile_form(self) -> None:
        """清空语言配置表单（取消编辑/新增）。"""
        self.profile_form_editing = 0
        self.profile_form_lang_display = ""
        self.profile_form_api = ""
        self.profile_form_template = ""
        self.profile_form_term = ""
        self.profile_form_strategy = ""

    @rx.event
    def edit_lang_profile(self, profile_id: int) -> None:
        """编辑某语言配置：回填表单。"""
        prof = next((p for p in self.lang_profiles if p["id"] == int(profile_id)), None)
        if prof is None:
            return
        self.profile_form_editing = int(profile_id)
        self.profile_form_lang_display = self.lang_code_to_display.get(
            prof["lang"], prof["lang"]
        )
        # 回填各下拉显示值
        if prof["api_config_id"]:
            api = file_service.get_api_config(prof["api_config_id"])
            self.profile_form_api = self._api_display_name(api) if api else ""
        else:
            self.profile_form_api = ""
        if prof["prompt_template_id"]:
            tpl = prompt_service.get_template(prof["prompt_template_id"])
            self.profile_form_template = tpl.name if tpl else ""
        else:
            self.profile_form_template = ""
        if prof["term_library_id"]:
            lib = next(
                (l for l in self.term_libraries if l["id"] == prof["term_library_id"]), None
            )
            self.profile_form_term = self._lib_display_name(lib) if lib else ""
        else:
            self.profile_form_term = ""
        self.profile_form_strategy = m.STRATEGY_LABELS.get(prof["strategy"], "") if prof["strategy"] else ""

    @rx.event
    def save_lang_profile(self) -> None:
        """保存语言配置（新增或更新）。"""
        lang_display = self.profile_form_lang_display
        if not lang_display:
            return self._toast("请选择目标语言")
        lang = self.lang_display_to_code.get(lang_display, lang_display)
        # 解析各下拉为 id / 枚举
        api_config_id = None
        if self.profile_form_api:
            api = next(
                (a for a in file_service.list_api_configs() if self._api_display_name(a) == self.profile_form_api),
                None,
            )
            api_config_id = api.id if api else None
        prompt_template_id = None
        if self.profile_form_template:
            tpl = next(
                (t for t in self.prompt_templates if t["name"] == self.profile_form_template), None
            )
            prompt_template_id = tpl["id"] if tpl else None
        term_library_id = None
        if self.profile_form_term:
            lib = next(
                (l for l in self.term_libraries if self._lib_display_name(l) == self.profile_form_term), None
            )
            term_library_id = lib["id"] if lib else None
        strategy = STRATEGY_LABEL_TO_CODE.get(self.profile_form_strategy, "") if self.profile_form_strategy else ""
        lang_profile_service.upsert_profile(
            lang,
            api_config_id=api_config_id,
            prompt_template_id=prompt_template_id,
            term_library_id=term_library_id,
            strategy=strategy,
        )
        self.profile_form_editing = 0
        self.profile_form_lang_display = ""
        self.profile_form_api = ""
        self.profile_form_template = ""
        self.profile_form_term = ""
        self.profile_form_strategy = ""
        self.load_lang_profiles()
        return self._toast(f"已保存「{lang_display}」的翻译配置")

    @rx.event
    def delete_lang_profile(self, profile_id: int) -> None:
        ok = lang_profile_service.delete_profile(int(profile_id))
        if ok:
            self.load_lang_profiles()
            return self._toast("配置已删除")
        return self._toast("删除失败")

    @rx.event
    def set_engine_form_engine(self, value: str) -> None:
        self.engine_form_engine = value
        self._reset_engine_test_passed()

    @rx.event
    def set_engine_form_display_name(self, value: str) -> None:
        self.engine_form_display_name = value
        self._reset_engine_test_passed()

    @rx.event
    def set_engine_form_base_url(self, value: str) -> None:
        self.engine_form_base_url = value
        self._reset_engine_test_passed()

    @rx.event
    def set_engine_form_api_key(self, value: str) -> None:
        self.engine_form_api_key = value
        self._reset_engine_test_passed()

    @rx.event
    def set_engine_form_model(self, value: str) -> None:
        self.engine_form_model = value
        self._reset_engine_test_passed()

    @rx.event
    def set_engine_form_max_concurrency(self, value: str) -> None:
        self.engine_form_max_concurrency = value
        self._reset_engine_test_passed()

    @rx.event
    def set_engine_form_is_default(self, value: bool) -> None:
        self.engine_form_is_default = bool(value)

    @rx.event
    def edit_api_config(self, cfg_id: int) -> None:
        """将已有配置回填到表单，进入编辑模式。"""
        cfg = next((a for a in self.api_configs if a["id"] == cfg_id), None)
        if cfg is None:
            return self._toast("配置不存在")
        self.engine_form_editing_id = int(cfg_id)
        self.engine_form_engine = cfg["engine_name"]
        self.engine_form_display_name = cfg.get("display_name", "")
        self.engine_form_base_url = cfg["base_url"]
        self.engine_form_api_key = cfg["api_key"]
        self.engine_form_model = cfg["model"]
        self.engine_form_is_default = bool(cfg["is_default"])
        mc = cfg.get("max_concurrency", 0) or 0
        self.engine_form_max_concurrency = str(mc) if mc > 0 else ""
        self.engine_test_passed = False
        self.engine_test_status = ""
        return self._toast("已载入配置，可修改后重新测试并保存")

    @rx.event
    def reset_engine_form(self) -> None:
        """退出编辑模式，清空表单。"""
        self.engine_form_editing_id = 0
        self.engine_form_engine = ""
        self.engine_form_display_name = ""
        self.engine_form_base_url = ""
        self.engine_form_api_key = ""
        self.engine_form_model = ""
        self.engine_form_is_default = False
        self.engine_form_max_concurrency = ""
        self.engine_test_passed = False
        self.engine_test_status = ""

    def _reset_engine_test_passed(self) -> None:
        """表单字段变更后，之前的测试通过状态失效。"""
        self.engine_test_passed = False
        self.engine_test_status = ""

    @rx.event
    def test_api_connection(self):
        """同步事件：立即设置 loading + status（前端立刻收到反馈），
        然后 yield 一个后台 async 事件跑实际测试。
        """
        engine = self.engine_form_engine.strip()
        base_url = self.engine_form_base_url.strip()
        api_key = self.engine_form_api_key.strip()
        model = self.engine_form_model.strip()
        if not engine or not api_key:
            self.engine_test_status = "请先填写引擎名称与 API Key"
            self.engine_test_passed = False
            return
        if self.engine_test_loading:
            return
        self.engine_test_loading = True
        self.engine_test_status = "正在测试连接…"
        yield type(self).run_api_test(engine, base_url, api_key, model)

    @rx.event(background=True)
    async def run_api_test(self, engine: str, base_url: str, api_key: str, model: str) -> None:
        """后台 async 事件：执行实际测试，结果写回 state。

        连接成功后自动探测并发上限：将探测结果回填到表单的并发上限
        输入框（作为建议值），并在状态区展示「已探测并发 N」。
        探测失败不阻塞保存（连接已通过）。
        """
        async with self:
            try:
                ok, msg = await asyncio.to_thread(
                    file_service.test_api_config, engine, base_url, api_key, model
                )
                self.engine_test_status = msg
                self.engine_test_passed = bool(ok)
                toast_msg = msg
            except Exception as exc:  # noqa: BLE001
                self.engine_test_status = f"连接失败：{exc}"
                self.engine_test_passed = False
                toast_msg = f"连接失败：{exc}"
                self.engine_test_loading = False
                return self._toast(toast_msg)
            # 连接成功 → 探测并发上限（临时对象，id=0，不持久化）
            probed = 0
            try:
                probed = await asyncio.to_thread(
                    self._probe_form_concurrency, engine, base_url, api_key, model
                )
            except Exception:  # noqa: BLE001
                probed = 0
            finally:
                self.engine_test_loading = False
            manual = (self.engine_form_max_concurrency or "").strip()
            manual_val = 0
            try:
                manual_val = int(manual) if manual else 0
            except ValueError:
                manual_val = -1
            if probed > 0:
                if manual_val > 0:
                    self.engine_test_status = (
                        f"{msg}；已探测并发上限：{probed}（保留手动配置：{manual_val}）"
                    )
                else:
                    self.engine_form_max_concurrency = str(probed)
                    self.engine_test_status = (
                        f"{msg}；已探测并发上限：{probed}（已填入并发上限，可修改后保存）"
                    )
            else:
                self.engine_test_status = f"{msg}；并发探测失败，将使用自动模式"
        return self._toast(self.engine_test_status)

    @staticmethod
    def _probe_form_concurrency(
        engine: str, base_url: str, api_key: str, model: str
    ) -> int:
        """用表单参数探测并发上限（构造临时 ApiConfig，id=None 不落库）。"""
        tmp = m.ApiConfig(
            engine_name=engine,
            base_url=base_url,
            api_key=api_key,
            model=model,
            is_default=False,
        )
        return concurrency_service.probe_max_concurrency(tmp)

    @rx.event
    def save_api_config(self, form_data: dict) -> None:
        """保存配置（读取表单 State 字段，表单仅用于 submit 触发）。

        处于编辑模式（engine_form_editing_id > 0）时更新该条配置，否则新建。
        """
        engine = self.engine_form_engine.strip()
        display_name = self.engine_form_display_name.strip()
        base_url = self.engine_form_base_url.strip()
        api_key = self.engine_form_api_key.strip()
        model = self.engine_form_model.strip()
        is_default = self.engine_form_is_default
        max_conc_str = (self.engine_form_max_concurrency or "").strip()
        try:
            max_concurrency = int(max_conc_str) if max_conc_str else 0
        except ValueError:
            return self._toast("并发上限必须是整数（0 表示自动）")
        if max_concurrency < 0:
            return self._toast("并发上限不能为负数")
        if not engine or not api_key:
            return self._toast("请填写引擎名称与 API Key")
        cfg_id = int(self.engine_form_editing_id or 0)
        saved = file_service.save_api_config(
            engine, base_url, api_key, model, is_default,
            display_name=display_name,
            cfg_id=cfg_id,
            max_concurrency=max_concurrency,
        )
        if saved is None:
            return self._toast("要更新的配置不存在")
        self.engine_form_editing_id = 0
        self.load_api_configs()
        verb = "更新" if cfg_id else "保存"
        return self._toast(f"API 配置已{verb}")

    @rx.event
    def set_default_api(self, cfg_id: int) -> None:
        file_service.set_default_api_config(int(cfg_id))
        self.load_api_configs()

    @rx.event
    def delete_api_config(self, cfg_id: int) -> None:
        file_service.delete_api_config(int(cfg_id))
        self.load_api_configs()

    # =========================================================
    # 组织
    # =========================================================

    @rx.event
    def load_orgs(self) -> None:
        me = config.DEFAULT_USER_ID
        self.orgs = [
            {
                "id": o.id,
                "name": o.name,
                "join_code": o.join_code,
                "created_time": o.created_time.strftime("%Y-%m-%d %H:%M"),
                "created_by": o.created_by,
                "is_owner": o.created_by == me,
            }
            for o in org_service.list_orgs()
        ]

    @rx.event
    def set_org_new_name(self, value: str) -> None:
        self.org_new_name = value

    @rx.event
    def set_org_join_code(self, value: str) -> None:
        self.org_join_code = value

    @rx.event
    def create_org(self) -> None:
        org, msg = org_service.create_org(self.org_new_name)
        if org is None:
            return self._toast(f"创建失败：{msg}")
        self.org_new_name = ""
        self.load_orgs()
        if msg:
            return self._toast(f"{msg}（邀请码：{org.join_code}）")
        return self._toast(f"组织已创建，邀请码：{org.join_code}")

    @rx.event
    def join_org(self) -> None:
        code = self.org_join_code.strip()
        if not code:
            return self._toast("请输入组织邀请码")
        org = org_service.join_by_code(code)
        if org is None:
            return self._toast("邀请码无效")
        self.org_join_code = ""
        self.load_orgs()
        return self._toast(f"已加入组织：{org.name}")

    @rx.event
    def request_delete_org(self, org_id: int) -> None:
        """请求删除组织：弹出二次确认。"""
        self.org_delete_confirm_id = int(org_id)

    @rx.event
    def cancel_delete_org(self) -> None:
        self.org_delete_confirm_id = 0

    @rx.event
    def do_delete_org(self) -> None:
        """确认后真正删除组织（仅创建者可删）。"""
        org_id = self.org_delete_confirm_id
        if not org_id:
            return
        ok, msg = org_service.delete_org(int(org_id))
        self.org_delete_confirm_id = 0
        if ok:
            self.load_orgs()
            return self._toast("组织已删除")
        self.load_orgs()
        return self._toast(f"删除失败：{msg}")


def _read_txt_content(path: str) -> str:
    """读取 txt 文本内容（供后台线程调用）。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_preview_df(path: str, ext: str):
    """读取预览 DataFrame（供向导展示前几行）。

    - xlsx/xls: 工作表
    - csv: 分隔符文本
    - txt: 按行解析为单列「source」，无列映射向导，走文本工程流程
    """
    import pandas as pd

    if ext == "csv":
        try:
            return pd.read_csv(path, dtype=str)
        except UnicodeDecodeError:
            return pd.read_csv(path, dtype=str, encoding="gbk")
    if ext in ("txt", "text"):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        return pd.DataFrame({"source": lines}, dtype=str)
    return pd.read_excel(path, dtype=str)
