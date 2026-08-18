"""术语库页：术语库管理 + 术语导入向导 + 可编辑多语言术语表格。"""
from __future__ import annotations

import reflex as rx

from localization.components import (
    card,
    confirm_dialog,
    empty_state,
    layout,
    modal,
    page_heading,
    primary_button,
)
from localization.components.roles import term_role_select
from localization.state import State


def term_library_bar() -> rx.Component:
    """术语库管理栏：当前库选择 + 新建 + 删除。"""
    return card(
        rx.hstack(
            rx.vstack(
                rx.text("当前术语库", font_size="0.8rem", color="var(--app-muted)"),
                rx.select(
                    State.term_library_names,
                    value=State.selected_library_name,
                    on_change=State.select_library,
                    width="220px",
                    placeholder="选择术语库",
                    cursor="pointer",
                ),
                spacing="1",
            ),
            rx.spacer(),
            rx.hstack(
                rx.cond(
                    State.term_import_status != "",
                    rx.text(State.term_import_status, color="var(--app-muted)", font_size="0.85rem"),
                ),
                rx.button(
                    "＋ 新建术语库",
                    size="2",
                    variant="soft",
                    on_click=State.open_lib_dialog,
                    cursor="pointer",
                ),
                rx.button(
                    "删除当前库",
                    size="2",
                    variant="soft",
                    color_scheme="red",
                    on_click=State.confirm_delete_library,
                    cursor="pointer",
                ),
                spacing="3",
            ),
            width="100%",
            align_items="center",
        ),
        width="100%",
        margin_bottom="1rem",
    )


def lib_dialog() -> rx.Component:
    """新建术语库对话框。"""
    return modal(
        State.lib_dialog_open,
        on_close=State.close_lib_dialog,
        title="新建术语库",
        children=[
            rx.text("输入术语库名称与描述，术语将归入该库独立管理。", color="var(--app-muted)", font_size="0.85rem"),
            rx.input(
                placeholder="术语库名称（如：游戏技能库）",
                value=State.lib_new_name,
                on_change=State.set_lib_new_name,
                width="100%",
            ),
            rx.input(
                placeholder="描述（可选）",
                value=State.lib_new_desc,
                on_change=State.set_lib_new_desc,
                width="100%",
            ),
            rx.vstack(
                rx.text(
                    "术语源语言（触发词的语言，如 简体中文 / 英语；不限定则任何源语言都匹配）",
                    color="var(--app-muted)",
                    font_size="0.8rem",
                    width="100%",
                ),
                rx.select(
                    State.lib_new_source_lang_options,
                    value=State.lib_new_source_lang_display,
                    on_change=State.set_lib_new_source_lang,
                    width="100%",
                    cursor="pointer",
                ),
                spacing="1",
                width="100%",
            ),
            primary_button("创建", on_click=State.confirm_create_library, width="100%"),
        ],
    )


def lib_delete_dialog() -> rx.Component:
    """删除当前术语库的二次确认对话框。"""
    return confirm_dialog(
        State.lib_delete_confirm,
        title="确认删除术语库",
        message=f"确定要删除术语库「{State.selected_library_name}」吗？该库下的全部术语将一并删除，且不可恢复。",
        on_confirm=State.do_delete_library,
        on_cancel=State.cancel_delete_library,
    )


def term_import() -> rx.Component:
    """术语导入入口卡片：引导进入列映射导入向导。"""
    return card(
        rx.hstack(
            rx.vstack(
                rx.heading("导入术语", size="5", color="var(--app-fg)"),
                rx.text(
                    "支持本地文件（xlsx/csv/txt）、在线表格、纯文本直粘，导入前可预览并映射列",
                    color="var(--app-muted)",
                    font_size="0.85rem",
                ),
                align_items="flex-start",
                spacing="1",
            ),
            rx.spacer(),
            primary_button("导入术语", on_click=State.open_term_import, size="3", width="auto"),
            width="100%",
            align_items="center",
        ),
        width="100%",
    )


def term_auto_input(*children, **props) -> rx.Component:
    """术语表格内的高度自适应输入框：高度随内容，不出现滚动条。"""
    props["style"] = {
        "& textarea": {
            "field_sizing": "content",
            "min_height": "36px",
            "width": "100%",
            "box_sizing": "border-box",
            "word_break": "break-word",
            "overflow_wrap": "anywhere",
        },
    }
    props["resize"] = "none"
    props["width"] = "100%"
    props["min_height"] = "36px"
    return rx.text_area(*children, **props)


def term_filter_bar() -> rx.Component:
    """术语列表顶部的筛选/分页工具栏：搜索 + 分类筛选 + 每页条数。"""
    return rx.hstack(
        rx.input(
            placeholder="搜索术语 / 译法 / 备注…",
            value=State.term_search_keyword,
            on_change=State.set_term_search_keyword,
            width="220px",
        ),
        rx.hstack(
            rx.text("分类", font_size="0.8rem", color="var(--app-muted)"),
            rx.select(
                State.term_category_options,
                value=rx.cond(State.term_category == "", "全部", State.term_category),
                on_change=State.set_term_category_filter,
                width="150px",
                cursor="pointer",
            ),
            align_items="center",
            spacing="2",
        ),
        rx.spacer(),
        rx.text(
            f"共 {State.term_total} 条 · 第 {State.term_page}/{State.term_total_pages} 页",
            color="var(--app-muted)",
            font_size="0.85rem",
        ),
        rx.hstack(
            rx.text("每页", font_size="0.8rem", color="var(--app-muted)"),
            rx.select(
                ["10", "20", "50", "100"],
                value=rx.cond(State.term_page_size == 10, "10",
                              rx.cond(State.term_page_size == 20, "20",
                                      rx.cond(State.term_page_size == 50, "50", "100"))),
                on_change=State.set_term_page_size,
                width="80px",
                cursor="pointer",
            ),
            rx.text("条", font_size="0.8rem", color="var(--app-muted)"),
            align_items="center",
            spacing="1",
        ),
        width="100%",
        align_items="center",
        margin_bottom="1rem",
    )


def term_pagination() -> rx.Component:
    """分页导航：上一页 / 页码 / 下一页。"""
    return rx.hstack(
        rx.button(
            "上一页",
            size="2",
            variant="soft",
            on_click=State.goto_term_page(State.term_page - 1),
            disabled=State.term_page <= 1,
            cursor="pointer",
        ),
        rx.text(f"{State.term_page} / {State.term_total_pages}", color="var(--app-muted)", font_size="0.85rem"),
        rx.button(
            "下一页",
            size="2",
            variant="soft",
            on_click=State.goto_term_page(State.term_page + 1),
            disabled=State.term_page >= State.term_total_pages,
            cursor="pointer",
        ),
        spacing="3",
        align_items="center",
    )


def term_list_card() -> rx.Component:
    """术语列表卡片：可编辑的多语言术语表格 + 搜索/分类/分页。"""
    return card(
        rx.heading(f"术语列表（{State.term_total}）", size="5", color="var(--app-fg)", margin_bottom="1rem"),
        term_filter_bar(),
        rx.cond(
            State.term_rows.length() == 0,
            empty_state("该分类下暂无术语，请调整筛选或先导入"),
            rx.vstack(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("原文"),
                            rx.foreach(
                                State.term_table_langs,
                                lambda lang: rx.table.column_header_cell(lang),
                            ),
                            rx.table.column_header_cell("备注"),
                            rx.table.column_header_cell("操作"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            State.term_rows,
                            lambda t: rx.table.row(
                                rx.table.cell(
                                    term_auto_input(
                                        value=t.source_term,
                                        on_change=State.update_term_source(t.id),
                                    ),
                                    min_width="140px",
                                ),
                                rx.foreach(
                                    t.cells,
                                    lambda cell: rx.table.cell(
                                        term_auto_input(
                                            value=cell["text"],
                                            on_change=State.update_term_translation(t.id, cell["lang"]),
                                            placeholder="—",
                                        ),
                                        min_width="120px",
                                    ),
                                ),
                                rx.table.cell(
                                    term_auto_input(
                                        value=t.note,
                                        on_change=State.update_term_note(t.id),
                                        placeholder="备注",
                                    ),
                                    min_width="120px",
                                ),
                                rx.table.cell(
                                    rx.button(
                                        "删除",
                                        size="1",
                                        variant="ghost",
                                        color_scheme="red",
                                        on_click=State.delete_term(t.id),
                                        cursor="pointer",
                                    )
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                    variant="surface",
                ),
                rx.text(
                    "提示：表格单元格可直接编辑，输入后自动保存；清空译法即删除该语言的译法。",
                    color="var(--app-muted)",
                    font_size="0.8rem",
                    margin_top="0.5rem",
                ),
                width="100%",
            ),
        ),
        rx.center(term_pagination(), width="100%", margin_top="1rem"),
        width="100%",
    )


def term_source_step() -> rx.Component:
    """导入向导第 1 步：选择来源类型与输入。"""
    return rx.vstack(
        rx.hstack(
            rx.text("来源类型", font_size="0.8rem", color="var(--app-muted)"),
            rx.select(
                ["本地文件", "在线表格", "纯文本"],
                value=rx.cond(State.term_import_source_type == "file", "本地文件",
                              rx.cond(State.term_import_source_type == "url", "在线表格", "纯文本")),
                on_change=State.set_term_import_source_type,
                width="160px",
                cursor="pointer",
            ),
            spacing="3",
            align_items="center",
        ),
        rx.cond(
            State.term_import_source_type == "file",
            rx.upload(
                rx.vstack(
                    rx.text("上传术语文件（xlsx/csv/txt）", color="var(--app-muted)"),
                    rx.button("选择文件", size="2", variant="soft", cursor="pointer"),
                    spacing="2",
                    padding="1.5rem",
                    border="2px dashed var(--app-border)",
                    border_radius="0.8rem",
                ),
                on_drop=State.upload_term_file(rx.upload_files()),
                width="100%",
            ),
            rx.cond(
                State.term_import_source_type == "url",
                rx.hstack(
                    rx.input(
                        placeholder="https://docs.google.com/spreadsheets/d/...",
                        value=State.term_wizard_url,
                        on_change=State.set_term_wizard_url,
                        flex="1",
                    ),
                    rx.button("加载", size="2", variant="soft", on_click=State.load_term_url, cursor="pointer"),
                    width="100%",
                    align_items="center",
                ),
                rx.vstack(
                    rx.text_area(
                        placeholder="每行一条术语，可用逗号/Tab/等号分隔：源,目标,备注",
                        value=State.term_wizard_text,
                        on_change=State.set_term_wizard_text,
                        min_height="140px",
                        width="100%",
                    ),
                    rx.button("加载", size="2", variant="soft", on_click=State.load_term_text, cursor="pointer"),
                    width="100%",
                    align_items="flex-end",
                ),
            ),
        ),
        rx.hstack(
            rx.text("分类（可选）：", color="var(--app-muted)", font_size="0.85rem"),
            rx.input(
                placeholder="例如：技能、装备…",
                value=State.term_new_category,
                on_change=State.set_term_new_category,
                flex="1",
            ),
            width="100%",
            align_items="center",
        ),
        spacing="4",
        width="100%",
    )


def term_mapping_step() -> rx.Component:
    """导入向导第 2 步：列映射指认（每列一个角色下拉）。"""
    return rx.vstack(
        rx.hstack(
            rx.heading("列映射", size="5", color="var(--app-fg)"),
            rx.spacer(),
            rx.text("为每列指定语义角色（源术语/目标术语/备注）", color="var(--app-muted)", font_size="0.85rem"),
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("列名"),
                    rx.table.column_header_cell("语义角色"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    State.term_preview_headers,
                    lambda col: rx.table.row(
                        rx.table.cell(rx.text(col, font_weight="500")),
                        rx.table.cell(term_role_select(col)),
                    ),
                ),
            ),
            width="100%",
        ),
        rx.hstack(
            rx.button("上一步", size="2", variant="soft", on_click=State.set_term_import_step(1), cursor="pointer"),
            rx.spacer(),
            primary_button(
                "确认导入到当前术语库",
                on_click=State.confirm_term_import,
                loading=State.term_importing,
                width="auto",
            ),
            width="100%",
            align_items="center",
        ),
        spacing="3",
        width="100%",
    )


def term_import_wizard() -> rx.Component:
    """术语导入向导（模态，两步：来源 -> 列映射确认）。"""
    return modal(
        State.term_import_open,
        on_close=State.close_term_import,
        title="导入术语",
        width="720px",
        z_index="100",
        children=[
            rx.cond(
                State.term_import_step == 2,
                term_mapping_step(),
                term_source_step(),
            ),
        ],
    )


@rx.page(
    route="/terms",
    title="术语库",
    on_load=[State.load_languages, State.load_terms],
)
def terms_page() -> rx.Component:
    return layout(
        page_heading("术语库", "术语约束模式：翻译时优先采用指定译法，校对时高亮提醒"),
        rx.center(
            rx.vstack(
                term_library_bar(),
                term_import(),
                term_list_card(),
                spacing="5",
                width="100%",
                max_width="1400px",
            ),
            width="100%",
            align_items="center",
        ),
        term_import_wizard(),
        lib_dialog(),
        lib_delete_dialog(),
    )
