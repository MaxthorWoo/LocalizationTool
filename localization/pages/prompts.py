"""提示词模板页：模板列表 + 多角色消息编辑器。"""
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


def prompt_editor() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading(
                rx.cond(
                    State.current_prompt_id == 0,
                    "新建提示词模板",
                    "编辑提示词模板",
                ),
                size="5",
                color="var(--app-fg)",
            ),
            rx.spacer(),
            rx.button("新建", variant="soft", on_click=State.new_prompt, cursor="pointer"),
        ),
        rx.hstack(
            rx.vstack(
                rx.text("模板名称", font_size="0.8rem", color="var(--app-muted)"),
                rx.input(value=State.current_prompt_name, on_change=State.set_prompt_name, width="100%"),
                spacing="1",
                width="48%",
            ),
            rx.vstack(
                rx.text("描述", font_size="0.8rem", color="var(--app-muted)"),
                rx.input(value=State.current_prompt_desc, on_change=State.set_prompt_desc, width="100%"),
                spacing="1",
                width="52%",
            ),
            spacing="4",
            width="100%",
        ),
        rx.box(
            rx.heading("可用内置变量", size="4", color="var(--app-fg)", margin_bottom="0.5rem"),
            rx.vstack(
                rx.foreach(
                    State.prompt_var_docs,
                    lambda v: rx.hstack(
                        rx.badge(v["name"], color="#2563EB", background="#DBEAFE"),
                        rx.text(v["desc"], color="var(--app-muted)", font_size="0.8rem"),
                        spacing="2",
                        width="100%",
                        align_items="center",
                    ),
                ),
                spacing="1",
                width="100%",
            ),
            width="100%",
            margin_bottom="1.2rem",
        ),
        rx.box(
            rx.heading("多角色消息", size="4", color="var(--app-fg)", margin_bottom="0.5rem"),
            rx.vstack(
                rx.foreach(
                    State.current_prompt_messages,
                    lambda msg, i: rx.box(
                        rx.hstack(
                            rx.select(
                                ["系统", "用户", "助手"],
                                on_change=State.set_prompt_message_role(i),
                                placeholder=rx.cond(
                                    msg["role"] == "system",
                                    "系统",
                                    rx.cond(msg["role"] == "user", "用户", "助手"),
                                ),
                                width="120px",
                                cursor="pointer",
                            ),
                            rx.spacer(),
                            rx.button("删除", variant="ghost", size="2", on_click=State.remove_prompt_message(i), cursor="pointer"),
                        ),
                        rx.text_area(
                            value=msg["content"],
                            on_change=State.set_prompt_message_content(i),
                            on_click=State.track_var_caret(i),
                            on_focus=State.track_var_caret(i),
                            on_key_up=State.track_var_caret(i),
                            width="100%",
                            min_height="100px",
                            margin_top="0.4rem",
                        ),
                        rx.hstack(
                            rx.button(
                                "＋ 插入变量",
                                size="1",
                                variant="soft",
                                on_click=State.toggle_var_picker(i),
                                cursor="pointer",
                            ),
                            rx.cond(
                                State.var_suggest_index == i,
                                rx.text("点击下方变量插入到当前光标位置", color="var(--app-muted)", font_size="0.7rem"),
                            ),
                            align_items="center",
                            spacing="2",
                            margin_top="0.3rem",
                        ),
                        rx.cond(
                            State.var_suggest_index == i,
                            rx.hstack(
                                rx.foreach(
                                    State.prompt_var_docs,
                                    lambda v: rx.button(
                                        rx.text("{", v["name"], "}", font_size="0.75rem"),
                                        on_click=State.insert_prompt_var(i, v["name"]),
                                        size="1",
                                        variant="soft",
                                        cursor="pointer",
                                    ),
                                ),
                                flex_wrap="wrap",
                                spacing="2",
                                margin_top="0.3rem",
                            ),
                        ),
                        border="1px solid var(--app-border)",
                        border_radius="0.7rem",
                        padding="0.8rem",
                        margin_bottom="0.6rem",
                        width="100%",
                    ),
                ),
                rx.button("+ 添加消息", variant="soft", on_click=State.add_prompt_message, width="100%", cursor="pointer"),
                spacing="1",
                width="100%",
            ),
            width="100%",
        ),
        primary_button("保存模板", on_click=State.save_prompt, width="100%", margin_top="1rem"),
        width="100%",
    )


@rx.page(
    route="/prompts",
    title="提示词模板",
    on_load=[State.load_languages, State.load_prompt_templates],
)
def prompts_page() -> rx.Component:
    return layout(
        page_heading("提示词模板", "大模型指令可配置化，支持多角色消息与组织内共享"),
        rx.hstack(
            card(prompt_editor(), width="72%"),
            card(
                rx.heading("模板列表", size="5", color="var(--app-fg)", margin_bottom="1rem"),
                rx.cond(
                    State.prompt_templates.length() == 0,
                    empty_state("还没有模板"),
                    rx.vstack(
                        rx.foreach(
                            State.prompt_templates,
                            lambda t: rx.hstack(
                                rx.vstack(
                                    rx.text(t["name"], font_weight="600", color="var(--app-fg)"),
                                    rx.text(
                                        rx.cond(
                                            t["description"] != "",
                                            t["description"],
                                            "无描述",
                                        ),
                                        color="var(--app-muted)",
                                        font_size="0.8rem",
                                    ),
                                    spacing="1",
                                    align_items="flex-start",
                                ),
                                rx.spacer(),
                                rx.button("编辑", size="2", variant="soft", on_click=State.open_prompt(t["id"]), cursor="pointer"),
                                rx.button("删除", size="2", variant="ghost", on_click=State.delete_prompt(t["id"]), cursor="pointer"),
                                width="100%",
                                padding="0.8rem",
                                border="1px solid var(--app-border)",
                                border_radius="0.6rem",
                                align_items="center",
                                _hover={"background": "var(--app-hover)"},
                            ),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),
                width="28%",
            ),
            spacing="5",
            width="100%",
            align_items="flex-start",
        ),
    )
