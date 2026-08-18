"""首页：我的工程（文件上传 / 文本直粘 / 工程列表）。"""
from __future__ import annotations

import reflex as rx

from localization.components import (
    card,
    confirm_dialog,
    empty_state,
    import_wizard,
    layout,
    modal,
    page_heading,
    primary_button,
)
from localization.state import State


def upload_card() -> rx.Component:
    return card(
        rx.heading("上传文件作为工程", size="5", color="var(--app-fg)", margin_bottom="0.8rem"),
        rx.text("支持 xlsx / csv / txt，导入后进入列映射向导", color="var(--app-muted)", font_size="0.85rem", margin_bottom="1rem"),
        rx.upload(
            rx.vstack(
                rx.box("⬆", font_size="2.5rem", color="#2563EB"),
                rx.cond(
                    State.is_uploading,
                    rx.text(State.upload_feedback, color="#2563EB", font_size="0.9rem"),
                    rx.text("拖拽文件到此处，或点击选择文件", color="var(--app-muted)", font_size="0.9rem"),
                ),
                primary_button(
                    rx.cond(State.is_uploading, "解析中…", "选择文件"),
                    disabled=State.is_uploading,
                    size="3",
                    width="auto",
                ),
                spacing="3",
                padding="2.5rem",
                border="2px dashed var(--app-border)",
                border_radius="1rem",
                width="100%",
                align_items="center",
                justify_content="center",
            ),
            id="upload_file",
            on_drop=State.on_file_upload(rx.upload_files(upload_id="upload_file")),
            multiple=False,
            accept={
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
                "text/csv": [".csv"],
                "text/plain": [".txt"],
            },
            width="100%",
        ),
        flex="1",
        min_height="430px",
    )


def text_card() -> rx.Component:
    return card(
        rx.vstack(
            rx.heading("粘贴文本直接翻译", size="5", color="var(--app-fg)"),
            rx.text("无需文件，粘贴一段文字即可创建翻译工程", color="var(--app-muted)", font_size="0.85rem"),
            rx.input(
                placeholder="工程名称（可选）",
                value=State.text_project_name,
                on_change=State.set_text_project_name,
                width="100%",
            ),
            rx.text_area(
                placeholder="在这里粘贴要翻译的文本...",
                value=State.text_input,
                on_change=State.set_text_input,
                width="100%",
                min_height="160px",
                flex="1",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("切分方式", font_size="0.8rem", color="var(--app-muted)"),
                    rx.select(
                        ["逐行", "按段落", "整段"],
                        value=State.text_mode,
                        on_change=State.set_text_mode,
                        width="100%",
                    ),
                    spacing="1",
                    width="50%",
                ),
                rx.vstack(
                    rx.text("源语言", font_size="0.8rem", color="var(--app-muted)"),
                    rx.select(
                        State.lang_display_options,
                        value=State.text_source_lang_display,
                        on_change=State.set_text_source_lang,
                        width="100%",
                    ),
                    spacing="1",
                    width="50%",
                ),
                spacing="4",
                width="100%",
            ),
            primary_button("创建并翻译", on_click=State.confirm_text_project, width="100%"),
            width="100%",
            spacing="3",
            flex="1",
        ),
        flex="1",
        min_height="430px",
        display="flex",
        flex_direction="column",
    )


def project_list() -> rx.Component:
    return card(
        rx.heading("我的工程", size="5", color="var(--app-fg)", margin_bottom="1rem"),
        rx.cond(
            State.projects.length() == 0,
            empty_state("还没有工程，请从上方创建"),
            rx.vstack(
                rx.foreach(
                    State.projects,
                    lambda p: rx.hstack(
                        rx.box(
                            rx.heading(p["name"], size="4", color="var(--app-fg)"),
                            rx.text(
                                f"{p['file_type']} · 源语言 {p['source_lang_display']}",
                                color="var(--app-muted)",
                                font_size="0.8rem",
                            ),
                            spacing="1",
                            flex="1",
                            align_items="flex-start",
                        ),
                        rx.hstack(
                            rx.badge(f"{p['translated_count']}/{p['total_count']} 已译", color="#2563EB", background="#DBEAFE"),
                            rx.badge(f"{p['proofread_count']} 已校对", color="#059669", background="#D1FAE5"),
                            rx.badge(f"{p['term_hit_count']} 命中术语", color="#D97706", background="#FEF3C7"),
                            primary_button(
                                "进入校对",
                                on_click=State.open_project(p["id"]),
                                size="2",
                                width="auto",
                            ),
                            rx.button(
                                "删除",
                                size="2",
                                variant="ghost",
                                color_scheme="red",
                                on_click=State.request_delete_project(p["id"]),
                                cursor="pointer",
                            ),
                            spacing="3",
                            align_items="center",
                        ),
                        width="100%",
                        padding="0.9rem",
                        border="1px solid var(--app-border)",
                        border_radius="0.7rem",
                        align_items="center",
                        _hover={"background": "var(--app-hover)"},
                    ),
                ),
                spacing="3",
                width="100%",
            ),
        ),
        width="100%",
    )


def text_preview_dialog() -> rx.Component:
    """txt 上传后的文本预览弹窗：确认切分方式与工程名后创建。"""
    return modal(
        State.text_preview_open,
        on_close=State.close_text_preview,
        title="文本预览",
        width="720px",
        z_index="100",
        children=[
            rx.vstack(
                rx.hstack(
                    rx.vstack(
                        rx.text("工程名", font_size="0.8rem", color="var(--app-muted)"),
                        rx.input(
                            value=State.txt_preview_name,
                            on_change=State.set_txt_preview_name,
                            width="100%",
                        ),
                        spacing="1",
                        flex="1",
                    ),
                    rx.vstack(
                        rx.text("切分方式", font_size="0.8rem", color="var(--app-muted)"),
                        rx.select(
                            ["逐行", "按段落", "整段"],
                            value=State.text_mode,
                            on_change=State.set_text_mode,
                            width="100%",
                            cursor="pointer",
                        ),
                        spacing="1",
                        flex="1",
                    ),
                    rx.vstack(
                        rx.text("源语言", font_size="0.8rem", color="var(--app-muted)"),
                        rx.select(
                            State.lang_display_options,
                            value=State.text_source_lang_display,
                            on_change=State.set_text_source_lang,
                            width="100%",
                            cursor="pointer",
                        ),
                        spacing="1",
                        flex="1",
                    ),
                    spacing="4",
                    width="100%",
                    align_items="flex-start",
                    margin_bottom="1rem",
                ),
                rx.text_area(
                    value=State.txt_preview_content,
                    on_change=State.set_txt_preview_content,
                    width="100%",
                    min_height="240px",
                    placeholder="文本内容预览",
                ),
                primary_button("确认创建工程", on_click=State.confirm_txt_preview, width="100%"),
                rx.text(
                    "创建后可进入校对页添加目标语言并配置翻译方案",
                    color="var(--app-muted)",
                    font_size="0.8rem",
                    text_align="center",
                    width="100%",
                ),
                width="100%",
                spacing="3",
            ),
        ],
    )


@rx.page(route="/", title="我的工程", on_load=[State.load_languages, State.load_projects])
def index() -> rx.Component:
    return layout(
        page_heading("我的工程", "创建一个文件工程，或直接粘贴文本开始翻译"),
        rx.hstack(upload_card(), text_card(), spacing="5", width="100%", align_items="stretch"),
        rx.box(margin_top="1.5rem", width="100%"),
        project_list(),
        import_wizard(),
        text_preview_dialog(),
        confirm_dialog(
            State.project_delete_confirm_id > 0,
            title="确认删除工程",
            message="确定要删除该工程吗？其全部条目将一并删除，且不可恢复。",
            on_confirm=State.do_delete_project,
            on_cancel=State.cancel_delete_project,
        ),
    )
