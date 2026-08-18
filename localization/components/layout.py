"""应用布局组件：侧边栏 + 内容区主框架。

包含：
- 侧边栏（Logo / 导航 / 底部日夜+收起按钮，支持展开/收起）
- 主布局 layout(*children)
- 页面基础组件：page_heading / card / empty_state

依赖：State（sidebar_collapsed、toggle_sidebar）、common（PRIMARY）。
"""
from __future__ import annotations

import reflex as rx

from localization.state import State

from .common import PRIMARY


def nav_item(
    title: str,
    route: str,
    icon: str,
    active: bool = False,
) -> rx.Component:
    """侧边栏菜单项：图标 + 文字（收起时仅图标）。"""
    return rx.link(
        rx.hstack(
            rx.icon(icon, size=18),
            rx.cond(
                State.sidebar_collapsed,
                rx.fragment(),
                rx.text(title, font_size="0.9rem", font_weight="500"),
            ),
            width="100%",
            align_items="center",
            justify_content="flex-start",
            spacing="3",
        ),
        href=route,
        padding="0.7rem",
        border_radius="0.6rem",
        width="100%",
        color="#FFFFFF" if active else "var(--sidebar-fg)",
        background=PRIMARY if active else "transparent",
        box_shadow="0 2px 8px rgba(0,0,0,0.08)" if active else "none",
        text_decoration="none",
        cursor="pointer",
        _hover={
            "background": "var(--sidebar-hover)" if not active else "var(--sidebar-active-hover)",
            "text_decoration": "none",
        },
    )


def nav_link(title: str, route: str, active: bool = False) -> rx.Component:
    """（兼容旧调用）简单的文字链接。"""
    return rx.link(
        title,
        href=route,
        padding="0.6rem 1rem",
        border_radius="0.5rem",
        font_size="0.9rem",
        font_weight="500",
        color="var(--sidebar-fg)",
        background=PRIMARY if active else "transparent",
        _hover={"background": "var(--sidebar-hover)"},
    )


def sidebar_brand() -> rx.Component:
    """侧边栏 Logo + 标题。"""
    return rx.hstack(
        rx.box(
            "L",
            background=PRIMARY,
            color="#FFFFFF",
            font_weight="700",
            font_size="1.1rem",
            width="2.2rem",
            height="2.2rem",
            display="flex",
            align_items="center",
            justify_content="center",
            border_radius="0.7rem",
            flex_shrink="0",
        ),
        rx.cond(
            State.sidebar_collapsed,
            rx.fragment(),
            rx.text("本地化翻译", font_weight="700", font_size="1rem", color="var(--app-fg)"),
        ),
        spacing="3",
        align_items="center",
        width="100%",
    )


def sidebar_footer() -> rx.Component:
    """侧边栏底部：日夜切换（Reflex 自带）+ 收起/展开按钮。

    - 日夜按钮：rx.color_mode.button()（Reflex 内置图标按钮）
    - 收起/展开：展开态显示左箭头（点击收起），收起态显示右箭头（点击展开）
    - 收起时仅保留收起按钮并居中；展开时两个按钮并排
    """
    return rx.hstack(
        rx.cond(
            State.sidebar_collapsed,
            rx.fragment(),
            rx.color_mode.button(),
        ),
        rx.button(
            rx.icon(
                rx.cond(State.sidebar_collapsed, "chevron-right", "chevron-left"),
                size=18,
            ),
            on_click=State.toggle_sidebar,
            variant="ghost",
            width="34px",
            height="34px",
            padding="0",
            color="var(--app-fg)",
            justify_content="center",
            cursor="pointer",
            _hover={"background": "var(--sidebar-hover)"},
        ),
        width="100%",
        justify_content=rx.cond(State.sidebar_collapsed, "center", "space-between"),
        align_items="center",
        spacing="2",
        padding_x="0.75rem",
        padding_y="0.5rem",
    )


def sidebar_nav() -> rx.Component:
    """侧边栏导航菜单（静态渲染，避免 foreach Var 问题）。"""
    return rx.vstack(
        nav_item("我的工程", "/", "folder-open"),
        nav_item("翻译校对", "/project", "languages"),
        nav_item("提示词模板", "/prompts", "file-text"),
        nav_item("术语库", "/terms", "book-open"),
        nav_item("语言", "/languages", "globe"),
        nav_item("引擎配置", "/settings", "settings"),
        nav_item("组织", "/org", "users"),
        spacing="2",
        width="100%",
    )


def layout(*children: rx.Component) -> rx.Component:
    """应用主布局：左侧可折叠侧边栏 + 内容区，支持日夜模式。"""
    theme_vars = rx.cond(
        rx.color_mode == "dark",
        {
            "--app-bg": "#0B1220",
            "--app-card": "#111B2E",
            "--app-fg": "#E2E8F0",
            "--app-muted": "#94A3B8",
            "--app-border": "#1E293B",
            "--app-hover": "#1E293B",
            "--sidebar-bg": "#0F172A",
            "--sidebar-fg": "#CBD5E1",
            "--sidebar-hover": "#1E293B",
            "--sidebar-active-hover": "#1D4ED8",
        },
        {
            "--app-bg": "#F4F6FB",
            "--app-card": "#FFFFFF",
            "--app-fg": "#0F172A",
            "--app-muted": "#64748B",
            "--app-border": "#E2E8F0",
            "--app-hover": "#F1F5F9",
            "--sidebar-bg": "#FFFFFF",
            "--sidebar-fg": "#334155",
            "--sidebar-hover": "#F1F5F9",
            "--sidebar-active-hover": "#1D4ED8",
        },
    )
    return rx.hstack(
        rx.vstack(
            rx.box(sidebar_brand(), width="100%", padding="1rem", flex_shrink="0"),
            rx.box(
                sidebar_nav(),
                width="100%",
                padding="0 0.75rem",
                flex="1",
                overflow_y="auto",
            ),
            rx.box(
                sidebar_footer(),
                width="100%",
                padding="0.75rem",
                border_top="1px solid var(--app-border)",
                flex_shrink="0",
            ),
            width=rx.cond(State.sidebar_collapsed, "64px", "230px"),
            height="100vh",
            background="var(--sidebar-bg)",
            border_right="1px solid var(--app-border)",
            spacing="0",
            transition="width 0.25s ease",
            flex_shrink="0",
            overflow="hidden",
        ),
        rx.box(
            *children,
            width="100%",
            padding="2rem",
            flex="1",
            height="100vh",
            overflow_y="auto",
        ),
        width="100%",
        height="100vh",
        background="var(--app-bg)",
        spacing="0",
        overflow="hidden",
        style=theme_vars,
    )


def page_heading(title: str, subtitle: str = "") -> rx.Component:
    return rx.vstack(
        rx.heading(title, size="6", color="var(--app-fg)"),
        rx.text(subtitle, color="var(--app-muted)", font_size="0.9rem") if subtitle else rx.fragment(),
        align_items="flex-start",
        width="100%",
        margin_bottom="1.2rem",
        spacing="1",
    )


def card(
    *children: rx.Component,
    width: str = "100%",
    margin_bottom: str = "",
    flex: str = "",
    height: str = "",
    min_height: str = "",
    min_width: str = "",
    display: str = "",
    flex_direction: str = "",
) -> rx.Component:
    return rx.box(
        *children,
        background="var(--app-card)",
        border="1px solid var(--app-border)",
        border_radius="1rem",
        padding="1.5rem",
        box_shadow="0 1px 3px rgba(0,0,0,0.05)",
        width=width,
        margin_bottom=margin_bottom,
        flex=flex,
        height=height,
        min_height=min_height,
        min_width=min_width,
        display=display,
        flex_direction=flex_direction,
    )


def empty_state(text: str) -> rx.Component:
    return rx.box(
        rx.text(text, color="var(--app-muted)", text_align="center", padding="3rem"),
        width="100%",
    )
