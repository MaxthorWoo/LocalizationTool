"""翻译校对页：工具栏 + 条目表格 + 导入向导。"""
from __future__ import annotations

import reflex as rx

from localization.components import (
    card,
    confirm_dialog,
    empty_state,
    import_wizard,
    layout,
    page_heading,
    primary_button,
    status_badge,
)
from localization.state import State


def lang_config_table() -> rx.Component:
    """语言方案配置表：每行一个目标语言 + 该语言的整套翻译方案。"""
    return card(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("语言方案配置", size="5", color="var(--app-fg)"),
                    rx.text(
                        "为每个目标语言独立配置 API / 提示词 / 术语库 / 策略；"
                        "勾选的行参与翻译，取消勾选不影响已保存的译文。",
                        color="var(--app-muted)",
                        font_size="0.8rem",
                    ),
                    spacing="1",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.vstack(
                        rx.text("工程源语言", font_size="0.8rem", color="var(--app-muted)"),
                        rx.select(
                            State.project_source_lang_options,
                            value=State.project_source_lang_display,
                            on_change=State.set_project_source_lang_display,
                            placeholder="选择源语言",
                            width="190px",
                            cursor="pointer",
                        ),
                        spacing="1",
                        align_items="flex-start",
                    ),
                    rx.vstack(
                        rx.text("添加目标语言", font_size="0.8rem", color="var(--app-muted)"),
                        rx.hstack(
                            rx.select(
                                State.lang_config_add_options,
                                value=State.lang_config_add_display,
                                on_change=State.set_lang_config_add_display,
                                placeholder="选择目标语言",
                                width="190px",
                                cursor="pointer",
                            ),
                            primary_button(
                                "添加",
                                on_click=State.add_lang_config,
                                size="2",
                                width="auto",
                            ),
                            spacing="2",
                        ),
                        spacing="1",
                        align_items="flex-start",
                    ),
                    spacing="4",
                ),
                width="100%",
                align_items="flex-start",
            ),
            rx.divider(width="100%"),
            rx.cond(
                State.lang_configs.length() == 0,
                rx.text(
                    "尚未配置目标语言。请在上方选择语言后点击「添加目标语言」。",
                    color="var(--app-muted)",
                    font_size="0.85rem",
                    padding="0.6rem 0",
                ),
                rx.vstack(
                    # 表头（平铺自适应，各列居中）
                    rx.hstack(
                        rx.box(width="36px", flex="0 0 36px"),
                        rx.box("目标语言", flex="1", text_align="center", color="var(--app-muted)", font_size="0.8rem"),
                        rx.box("翻译 API", flex="1", text_align="center", color="var(--app-muted)", font_size="0.8rem"),
                        rx.box("提示词模板", flex="1", text_align="center", color="var(--app-muted)", font_size="0.8rem"),
                        rx.box("术语库", flex="1", text_align="center", color="var(--app-muted)", font_size="0.8rem"),
                        rx.box("翻译策略", flex="1", text_align="center", color="var(--app-muted)", font_size="0.8rem"),
                        rx.box("操作", flex="1", text_align="center", color="var(--app-muted)", font_size="0.8rem"),
                        width="100%",
                        spacing="3",
                    ),
                    rx.foreach(
                        State.lang_configs,
                        lambda row: rx.hstack(
                            rx.box(
                                rx.checkbox(
                                    checked=row["enabled"],
                                    on_change=State.toggle_lang_config_enabled(row["id"]),
                                    cursor="pointer",
                                ),
                                width="36px",
                                flex="0 0 36px",
                                display="flex",
                                justify_content="center",
                            ),
                            rx.box(
                                rx.badge(
                                    row["lang_display"],
                                    color="#1D4ED8",
                                    background="#DBEAFE",
                                    width="100%",
                                    justify_content="center",
                                ),
                                flex="1",
                                display="flex",
                                justify_content="center",
                            ),
                            rx.box(
                                rx.select(
                                    State.api_config_options,
                                    value=row["api_display"],
                                    on_change=State.set_lang_config_api(row["id"]),
                                    width="100%",
                                    cursor="pointer",
                                ),
                                flex="1",
                                min_width="0",
                            ),
                            rx.box(
                                rx.select(
                                    State.translate_prompt_options,
                                    value=row["template_display"],
                                    on_change=State.set_lang_config_template(row["id"]),
                                    width="100%",
                                    cursor="pointer",
                                ),
                                flex="1",
                                min_width="0",
                            ),
                            rx.box(
                                rx.select(
                                    State.translate_lib_options,
                                    value=row["term_display"],
                                    on_change=State.set_lang_config_term(row["id"]),
                                    width="100%",
                                    cursor="pointer",
                                ),
                                flex="1",
                                min_width="0",
                            ),
                            rx.box(
                                rx.select(
                                    ["跳过已有译文", "覆盖重译"],
                                    value=row["strategy_display"],
                                    on_change=State.set_lang_config_strategy(row["id"]),
                                    width="100%",
                                    cursor="pointer",
                                ),
                                flex="1",
                                min_width="0",
                            ),
                            rx.box(
                                rx.button(
                                    "删除",
                                    size="1",
                                    variant="ghost",
                                    color_scheme="red",
                                    on_click=State.remove_lang_config(row["id"]),
                                    cursor="pointer",
                                ),
                                flex="1",
                                display="flex",
                                justify_content="center",
                            ),
                            width="100%",
                            align_items="center",
                            spacing="3",
                        ),
                    ),
                    width="100%",
                    spacing="2",
                ),
            ),
            spacing="2",
            width="100%",
        ),
        width="100%",
    )


def translate_toolbar() -> rx.Component:
    """操作行：开始翻译 / 清空 / 导出 / 切换工程 + 进度。"""
    return card(
        rx.hstack(
            primary_button(
                "开始翻译",
                on_click=State.start_translate,
                disabled=State.is_translating,
                loading=State.is_translating,
                size="3",
                width="auto",
            ),
            rx.button(
                "清空译文",
                on_click=State.request_clear_translations,
                variant="soft",
                color_scheme="red",
                size="3",
                cursor="pointer",
            ),
            rx.button(
                "导出 xlsx",
                on_click=State.export_project,
                variant="soft",
                size="3",
                cursor="pointer",
            ),
            rx.button(
                "切换工程",
                on_click=State.close_project,
                variant="ghost",
                size="3",
                cursor="pointer",
            ),
            rx.spacer(),
            rx.vstack(
                rx.text(
                    State.progress_text,
                    color="var(--app-muted)",
                    font_size="0.85rem",
                ),
                rx.box(
                    rx.box(
                        height="8px",
                        border_radius="4px",
                        background="#6366F1",
                        width=State.progress_pct,
                    ),
                    width="220px",
                    height="8px",
                    border_radius="4px",
                    background="var(--app-hover)",
                    overflow="hidden",
                ),
                spacing="1",
                align_items="flex-start",
                style={"display": rx.cond(State.is_translating, "flex", "none")},
            ),
            width="100%",
            align_items="center",
            justify_content="flex-start",
            spacing="4",
        ),
        width="100%",
    )


def auto_text_area(*children, text_align: str = "left", **props) -> rx.Component:
    """高度随内容自适应、宽度固定的 textarea。

    field-sizing: content 会同时影响宽度与高度，因此必须在内层 <textarea>
    上显式固定 width: 100% + box-sizing: border-box，使 field-sizing 只作用于高度。
    不设 max_height，高度完全跟随内容，无滚动条。
    text_align: 文本框内文字对齐方式（left/center/right）。
    """
    props["style"] = {
        "& textarea": {
            "field_sizing": "content",
            "min_height": "70px",
            "width": "100%",
            "box_sizing": "border-box",
            "word_break": "break-word",
            "overflow_wrap": "anywhere",
            "text_align": text_align,
        },
    }
    props["resize"] = "none"
    props["width"] = "100%"
    return rx.text_area(*children, **props)


def entry_table() -> rx.Component:
    """翻译校对条目表。

    用 CSS Grid 布局替代 <table>：每行一个 grid，列宽由 State.entry_grid_cols
    统一控制（表头与数据行完全对齐）。命中术语列设为 height:100% + min_height:0
    + overflow-y:auto——行高由文本输入框决定，术语内容超出时在本列内滚动，
    文本较长时术语列跟随延伸且不出滚动条。
    """
    grid_style = {
        "display": "grid",
        "grid_template_columns": State.entry_grid_cols,
        "gap": "0.6rem",
        "padding": "0.55rem 0.7rem",
        "border_bottom": "1px solid var(--app-border)",
        "align_items": "stretch",
        "justify_items": "stretch",
    }
    header_cell_style = {
        "color": "var(--app-muted)",
        "font_size": "0.75rem",
        "font_weight": "600",
        "text_align": "center",
    }
    return card(
        rx.cond(
            State.entries.length() == 0,
            empty_state("该工程暂无条目"),
            rx.vstack(
                rx.box(
                    # 表头行
                    rx.box(
                        rx.text("#", **header_cell_style),
                        rx.text("源文案", **header_cell_style),
                        rx.foreach(
                            State.target_lang_display_options,
                            lambda lang: rx.text(lang, **header_cell_style),
                        ),
                        rx.text("状态", **header_cell_style),
                        rx.text("命中术语", **header_cell_style),
                        rx.text("操作", **header_cell_style),
                        style=grid_style,
                        background="var(--app-hover)",
                        border_top="1px solid var(--app-border)",
                        align_items="center",
                    ),
                    # 数据行
                    rx.foreach(
                        State.entries,
                        lambda e: rx.box(
                            rx.box(
                                rx.cond(
                                    e.key_text != "",
                                    rx.text(e.key_text, color="var(--app-muted)", font_size="0.8rem"),
                                    rx.text("-", color="var(--app-muted)", font_size="0.8rem"),
                                ),
                                align_self="center",
                                text_align="center",
                                width="100%",
                            ),
                            rx.box(
                                rx.cond(
                                    e.term_hits_display != "",
                                    auto_text_area(
                                        value=e.source_text,
                                        on_change=State.edit_entry_source(e.id),
                                        text_align="center",
                                        background=rx.cond(
                                            rx.color_mode == "dark",
                                            "#064E3B",
                                            "#D1FAE5",
                                        ),
                                        color=rx.cond(
                                            rx.color_mode == "dark",
                                            "#A7F3D0",
                                            "#065F46",
                                        ),
                                    ),
                                    auto_text_area(
                                        value=e.source_text,
                                        on_change=State.edit_entry_source(e.id),
                                        text_align="center",
                                    ),
                                ),
                            ),
                            rx.foreach(
                                e.cells,
                                lambda cell: rx.box(
                                    auto_text_area(
                                        value=cell["text"],
                                        on_change=State.edit_entry_text(e.id, cell["lang"]),
                                        text_align="center",
                                    ),
                                    rx.icon_button(
                                        rx.icon("refresh-cw"),
                                        size="1",
                                        variant="soft",
                                        color_scheme="blue",
                                        on_click=State.retranslate_cell(e.id, cell["lang"]),
                                        cursor="pointer",
                                        title="重翻此语言",
                                        aria_label="重翻此语言",
                                        style={"position": "absolute", "bottom": "4px", "right": "4px", "z_index": "1"},
                                        disabled=State.is_translating,
                                    ),
                                    position="relative",
                                    width="100%",
                                ),
                            ),
                            rx.box(
                                rx.hstack(
                                    status_badge(e.status_label, e.status_fg, e.status_bg),
                                    justify_content="center",
                                    width="100%",
                                ),
                                align_self="center",
                            ),
                            rx.box(
                                # 术语列：内容绝对定位，不参与 grid 行高计算，
                                # 行高由文本输入框决定；术语过多时在自身高度内滚动。
                                rx.box(
                                    rx.cond(
                                        e.term_hits_display != "",
                                        rx.text(e.term_hits_display, color="#D97706", font_size="0.8rem", text_align="center"),
                                        rx.text("—", color="var(--app-muted)", font_size="0.8rem", text_align="center"),
                                    ),
                                    position="absolute",
                                    top="0",
                                    left="0",
                                    right="0",
                                    bottom="0",
                                    overflow_y="auto",
                                    overflow_x="hidden",
                                    word_break="break-word",
                                ),
                                position="relative",
                                min_height="0",
                                width="100%",
                            ),
                            rx.box(
                                rx.vstack(
                                    rx.select(
                                        ["待译", "已译", "已校对", "需复核"],
                                        on_change=State.set_entry_status(e.id),
                                        placeholder="修改状态",
                                        width="150px",
                                        cursor="pointer",
                                    ),
                                    rx.button(
                                        rx.hstack(
                                            rx.icon("refresh-cw", size=1),
                                            rx.text("重翻整行", font_size="0.75rem"),
                                            spacing="2",
                                            align_items="center",
                                            justify_content="center",
                                        ),
                                        on_click=State.retranslate_row(e.id),
                                        size="1",
                                        variant="soft",
                                        color_scheme="blue",
                                        width="150px",
                                        cursor="pointer",
                                        disabled=State.is_translating,
                                        _disabled={"opacity": "0.5", "cursor": "wait"},
                                    ),
                                    spacing="2",
                                    justify_content="center",
                                    width="100%",
                                    align_items="center",
                                ),
                                align_self="center",
                            ),
                            style=grid_style,
                        ),
                    ),
                    width="100%",
                    overflow_x="auto",
                ),
                # 新增一行：底部输入源文案，点击添加
                rx.hstack(
                    rx.input(
                        placeholder="输入源文案，为工程新增一行（可选填 key 见注释）",
                        value=State.new_entry_text,
                        on_change=State.set_new_entry_text,
                        width="100%",
                        flex="1",
                    ),
                    primary_button(
                        "新增一行",
                        on_click=State.add_new_entry,
                        width="auto",
                        flex_shrink="0",
                    ),
                    spacing="3",
                    width="100%",
                    margin_top="0.8rem",
                ),
                width="100%",
            ),
        ),
        width="100%",
    )


@rx.page(
    route="/project",
    title="翻译校对",
    on_load=[
        State.load_languages,
        State.load_translate_libraries,
        State.load_translate_prompts,
        State.load_translate_apis,
        State.load_projects,
    ],
)
def project_page() -> rx.Component:
    return layout(
        rx.cond(
            State.has_project,
            rx.vstack(
                page_heading(State.current_project.name, "对照翻译与校对工作台"),
                lang_config_table(),
                translate_toolbar(),
                entry_table(),
                width="100%",
            ),
            rx.vstack(
                page_heading("翻译校对", "选择一个工程进行对照翻译与校对"),
                card(
                    rx.foreach(
                        State.projects,
                        lambda p: rx.button(
                            rx.hstack(
                                rx.text(p["name"], font_weight="500"),
                                rx.text(f"{p['translated_count']}/{p['total_count']} 已译", color="var(--app-muted)"),
                            ),
                            on_click=State.open_project(p["id"]),
                            variant="soft",
                            width="100%",
                            margin_bottom="0.5rem",
                            cursor="pointer",
                        ),
                    ),
                ),
                width="100%",
            ),
        ),
        import_wizard(),
        confirm_dialog(
            State.clear_confirm_open,
            title="清空译文",
            message="确定要清空所有已勾选语言的译文吗？清空后可重新翻译。",
            on_confirm=State.do_clear_translations,
            on_cancel=State.cancel_clear_translations,
            confirm_text="清空",
        ),
    )
