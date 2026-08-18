"""通用 Reflex UI 组件。

集中放置可复用的基础组件与主题常量，避免在 app.py 中重复定义。
所有组件不直接依赖业务 State，事件处理器通过参数注入，保持解耦。
"""
from __future__ import annotations

import reflex as rx

# ---------- 主题常量 ----------
PRIMARY = "linear-gradient(135deg,#2563EB,#7C3AED)"
PRIMARY_HOVER = "linear-gradient(135deg,#1D4ED8,#6D28D9)"
DANGER = "#DC2626"
DANGER_HOVER = "#B91C1C"


def primary_button(
    text: str,
    on_click=None,
    size: str = "3",
    width: str = "100%",
    flex: str | None = None,
    loading: bool | None = None,
    disabled: bool | None = None,
    **kwargs,
) -> rx.Component:
    """渐变主题主按钮（统一白字 + 渐变背景 + 手型光标）。"""
    return rx.button(
        text,
        on_click=on_click,
        color="#FFFFFF",
        background=PRIMARY,
        _hover={"background": PRIMARY_HOVER},
        size=size,
        width=width,
        flex=flex,
        loading=loading,
        disabled=disabled,
        cursor="pointer",
        **kwargs,
    )


def soft_button(
    text: str,
    on_click,
    size: str = "2",
    variant: str = "soft",
    color_scheme: str = "gray",
    **kwargs,
) -> rx.Component:
    """柔和次级按钮。"""
    return rx.button(
        text,
        on_click=on_click,
        size=size,
        variant=variant,
        color_scheme=color_scheme,
        cursor="pointer",
        **kwargs,
    )


def select_field(
    label: str,
    options,
    value,
    on_change,
    width: str = "180px",
    placeholder: str = "",
) -> rx.Component:
    """带标签的下拉选择字段（label + select 垂直组合）。"""
    return rx.vstack(
        rx.text(label, font_size="0.8rem", color="var(--app-muted)"),
        rx.select(
            options,
            value=value,
            on_change=on_change,
            width=width,
            placeholder=placeholder,
            cursor="pointer",
        ),
        spacing="1",
        align_items="flex-start",
        width="100%",
    )


def input_field(
    label: str,
    value,
    on_change,
    placeholder: str = "",
    width: str = "100%",
) -> rx.Component:
    """带标签的输入字段（label + input 垂直组合）。"""
    return rx.vstack(
        rx.text(label, font_size="0.8rem", color="var(--app-muted)"),
        rx.input(
            value=value,
            on_change=on_change,
            placeholder=placeholder,
            width=width,
        ),
        spacing="1",
        align_items="flex-start",
        width="100%",
    )


def modal(
    open_cond,
    on_close,
    title: str,
    children,
    width: str = "420px",
    z_index: str = "100",
) -> rx.Component:
    """通用模态框：遮罩 + 居中卡片 + 标题 + ✕ 关闭。

    - open_cond：是否显示（Var）
    - on_close：关闭事件（点击遮罩/✕ 触发）
    - children：卡片内容（单个组件或组件列表）
    """
    return rx.cond(
        open_cond,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.heading(title, size="5", color="var(--app-fg)"),
                    rx.spacer(),
                    rx.button("✕", variant="ghost", on_click=on_close, cursor="pointer"),
                    width="100%",
                ),
                *([children] if not isinstance(children, (list, tuple)) else children),
                spacing="3",
                width=width,
                background="var(--app-card)",
                border_radius="1rem",
                padding="1.5rem",
                box_shadow="0 10px 30px rgba(0,0,0,0.15)",
            ),
            position="fixed",
            top="0",
            left="0",
            right="0",
            bottom="0",
            background="rgba(15,23,42,0.5)",
            display="flex",
            align_items="center",
            justify_content="center",
            z_index=z_index,
        ),
    )


def confirm_dialog(
    open_cond,
    title: str,
    message,
    on_confirm,
    on_cancel,
    confirm_text: str = "确认删除",
    cancel_text: str = "取消",
    danger: bool = True,
    z_index: str = "110",
) -> rx.Component:
    """通用确认对话框（删除等危险操作）。"""
    return modal(
        open_cond,
        on_close=on_cancel,
        title=title,
        width="420px",
        z_index=z_index,
        children=[
            rx.text(message, color="var(--app-muted)", font_size="0.9rem"),
            rx.hstack(
                soft_button(cancel_text, on_click=on_cancel, flex="1"),
                rx.button(
                    confirm_text,
                    on_click=on_confirm,
                    size="2",
                    color="#FFFFFF",
                    background=DANGER if danger else PRIMARY,
                    _hover={"background": DANGER_HOVER if danger else PRIMARY_HOVER},
                    flex="1",
                    cursor="pointer",
                ),
                width="100%",
                spacing="3",
            ),
        ],
    )


def badge(text, color_scheme: str = "gray", **kwargs) -> rx.Component:
    """统一徽章。"""
    return rx.badge(text, color_scheme=color_scheme, **kwargs)


def status_badge(label, fg: str, bg: str) -> rx.Component:
    """状态徽标（接收已序列化的标签与颜色）。"""
    return rx.badge(
        label,
        color=fg,
        background=bg,
        border_radius="full",
        variant="solid",
        font_size="0.75rem",
        padding="0.1rem 0.6rem",
    )


def card_heading(title: str, count: str = "") -> rx.Component:
    """卡片标题（可选计数徽章）。"""
    return rx.hstack(
        rx.heading(title, size="5", color="var(--app-fg)"),
        rx.cond(
            count != "",
            badge(count, color_scheme="blue", variant="soft"),
        ),
        align_items="center",
        spacing="2",
        margin_bottom="1rem",
        width="100%",
    )
