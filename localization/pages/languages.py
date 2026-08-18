"""语言管理页：添加自定义语言、查看/删除语言。"""
from __future__ import annotations

import reflex as rx

from localization.components import (
    card,
    empty_state,
    layout,
    page_heading,
    primary_button,
)
from localization.state import State


@rx.page(route="/languages", title="语言管理", on_load=State.load_languages_admin)
def languages_page() -> rx.Component:
    return layout(
        page_heading(
            "语言管理",
            "内置常用语言 + 手动添加自定义语言，添加后即可在源语言/目标语言/列映射中使用",
        ),
        rx.center(
            rx.vstack(
                card(
                    rx.heading("添加自定义语言", size="5", color="var(--app-fg)", margin_bottom="1rem"),
                    rx.text(
                        "语言代码用标准码（如 fil、hi、uk），后续选择该代码即代表对应语言",
                        color="var(--app-muted)",
                        font_size="0.85rem",
                    ),
                    rx.hstack(
                        rx.input(
                            placeholder="语言代码（如 fil）",
                            value=State.new_lang_code,
                            on_change=State.set_new_lang_code,
                            width="40%",
                            min_width="120px",
                            flex="0 0 40%",
                        ),
                        rx.input(
                            placeholder="语言名称（如 菲律宾语）",
                            value=State.new_lang_name,
                            on_change=State.set_new_lang_name,
                            flex="1",
                            min_width="140px",
                        ),
                        primary_button(
                            "添加",
                            on_click=State.add_language,
                            width="auto",
                            flex_shrink="0",
                        ),
                        width="100%",
                        align_items="center",
                    ),
                    rx.text(
                        "提示：内置语言（简体中文、英语等）无需重复添加，且不可删除。",
                        color="var(--app-muted)",
                        font_size="0.8rem",
                        margin_top="0.8rem",
                    ),
                    width="100%",
                ),
                card(
                    rx.heading(f"全部语言（{State.langs.length()}）", size="5", color="var(--app-fg)", margin_bottom="1rem"),
                    rx.cond(
                        State.langs.length() == 0,
                        empty_state("暂无语言"),
                        rx.vstack(
                            rx.foreach(
                                State.langs,
                                lambda l: rx.hstack(
                                    rx.badge(
                                        l["code"],
                                        color=rx.cond(
                                            rx.color_mode == "dark",
                                            "#93C5FD",
                                            "#1D4ED8",
                                        ),
                                        background=rx.cond(
                                            rx.color_mode == "dark",
                                            "#1E3A5F",
                                            "#DBEAFE",
                                        ),
                                    ),
                                    rx.text(l["name"], font_weight="600", color="var(--app-fg)"),
                                    rx.cond(
                                        l["is_preset"],
                                        rx.badge("内置", color="#059669", background="#D1FAE5"),
                                        rx.badge("自定义", color="#D97706", background="#FEF3C7"),
                                    ),
                                    rx.spacer(),
                                    rx.cond(
                                        l["is_preset"],
                                        rx.text("不可删除", color="var(--app-muted)", font_size="0.8rem"),
                                        rx.button(
                                            "删除",
                                            size="2",
                                            variant="ghost",
                                            color_scheme="red",
                                            on_click=State.delete_language(l["id"]),
                                            cursor="pointer",
                                        ),
                                    ),
                                    width="100%",
                                    padding="0.6rem",
                                    border="1px solid var(--app-border)",
                                    border_radius="0.6rem",
                                    align_items="center",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                    ),
                    width="100%",
                ),
                spacing="5",
                width="100%",
                max_width="800px",
            ),
            width="100%",
            align_items="center",
        ),
    )
