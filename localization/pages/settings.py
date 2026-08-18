"""引擎配置页：添加 / 管理翻译 API 引擎。"""
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


@rx.page(
    route="/settings",
    title="引擎配置",
    on_load=[
        State.load_languages,
        State.load_api_configs,
        State.load_translate_libraries,
        State.load_translate_prompts,
        State.load_lang_profiles,
    ],
)
def settings_page() -> rx.Component:
    return layout(
        page_heading("引擎配置", "配置翻译 API（首期支持 GLM 及 OpenAI 兼容接口）"),
        rx.hstack(
            card(
                rx.heading("添加引擎", size="5", color="var(--app-fg)", margin_bottom="1rem"),
                rx.form(
                    rx.vstack(
                        rx.hstack(
                            rx.text(
                                rx.cond(
                                    State.engine_form_editing_id > 0,
                                    "编辑引擎配置",
                                    "新增引擎配置",
                                ),
                                font_size="0.85rem",
                                color="var(--app-muted)",
                            ),
                            rx.spacer(),
                            rx.cond(
                                State.engine_form_editing_id > 0,
                                rx.button(
                                    "取消编辑",
                                    size="1",
                                    variant="ghost",
                                    on_click=State.reset_engine_form,
                                    cursor="pointer",
                                ),
                            ),
                            width="100%",
                        ),
                        rx.input(
                            placeholder="配置名称（可选，用于区分用途，如 韩语专属API）",
                            value=State.engine_form_display_name,
                            on_change=State.set_engine_form_display_name,
                            width="100%",
                        ),
                        rx.select(
                            State.engine_names,
                            value=State.engine_form_engine,
                            on_change=State.set_engine_form_engine,
                            placeholder="选择引擎",
                            width="100%",
                            cursor="pointer",
                        ),
                        rx.input(
                            placeholder="Base URL（如 https://open.bigmodel.cn/api/paas/v4/）",
                            value=State.engine_form_base_url,
                            on_change=State.set_engine_form_base_url,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="API Key",
                            value=State.engine_form_api_key,
                            on_change=State.set_engine_form_api_key,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="模型名（如 glm-4-flash）",
                            value=State.engine_form_model,
                            on_change=State.set_engine_form_model,
                            width="100%",
                        ),
                        rx.input(
                            placeholder="并发上限（0=自动探测，留空表示自动）",
                            value=State.engine_form_max_concurrency,
                            on_change=State.set_engine_form_max_concurrency,
                            type="number",
                            width="100%",
                        ),
                        rx.checkbox(
                            "设为默认引擎",
                            checked=State.engine_form_is_default,
                            on_change=State.set_engine_form_is_default,
                        ),
                        rx.hstack(
                            rx.button(
                                rx.cond(
                                    State.engine_test_loading,
                                    rx.hstack(
                                        rx.spinner(size="2"),
                                        rx.text("测试中…", font_size="0.85rem"),
                                        spacing="2",
                                        align_items="center",
                                        justify_content="center",
                                    ),
                                    rx.text("测试连接"),
                                ),
                                type="button",
                                on_click=State.test_api_connection,
                                variant="soft",
                                flex="1",
                                disabled=State.engine_test_loading,
                                cursor="pointer",
                                _disabled={"opacity": "0.6", "cursor": "wait"},
                            ),
                            primary_button(
                                rx.cond(
                                    State.engine_form_editing_id > 0,
                                    "保存修改",
                                    "保存配置",
                                ),
                                type="submit",
                                flex="1",
                                disabled=State.engine_test_passed == False,  # noqa: E712
                            ),
                            spacing="3",
                            width="100%",
                            flex_wrap="wrap",
                        ),
                        rx.cond(
                            State.engine_test_passed == False,  # noqa: E712
                            rx.text(
                                "提示：请先点击「测试连接」并确认成功，才能保存配置。",
                                color="var(--app-muted)",
                                font_size="0.75rem",
                            ),
                        ),
                        rx.cond(
                            State.engine_test_status != "",
                            rx.box(
                                rx.text(
                                    State.engine_test_status,
                                    color=rx.cond(
                                        State.engine_test_status.startswith("连接成功"),
                                        "#059669",
                                        "#DC2626",
                                    ),
                                    font_size="0.85rem",
                                    padding="0.6rem",
                                    background="var(--app-hover)",
                                    border_radius="0.5rem",
                                    width="100%",
                                ),
                                width="100%",
                            ),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=State.save_api_config,
                    width="100%",
                ),
                width="100%",
                min_width="320px",
                flex="1",
            ),
            card(
                rx.heading("已配置引擎", size="5", color="var(--app-fg)", margin_bottom="1rem"),
                rx.cond(
                    State.api_configs.length() == 0,
                    empty_state("还没有配置引擎"),
                    rx.vstack(
                        rx.foreach(
                            State.api_configs,
                            lambda c: rx.box(
                                rx.hstack(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.cond(
                                                c["display_name"] != "",
                                                rx.text(c["display_name"], font_weight="600", color="var(--app-fg)"),
                                                rx.text(c["engine_name"], font_weight="600", color="var(--app-fg)"),
                                            ),
                                            rx.cond(c["is_default"], rx.badge("默认", color="#059669", background="#D1FAE5")),
                                            spacing="2",
                                        ),
                                        rx.text(
                                            f"{c['engine_name']} · model: {c['model']} · {c['base_url']}",
                                            color="var(--app-muted)",
                                            font_size="0.8rem",
                                        ),
                                        rx.hstack(
                                            rx.cond(
                                                c["max_concurrency_disp"] != "",
                                                rx.badge(
                                                    c["max_concurrency_disp"],
                                                    color="#7C3AED",
                                                    background="#EDE9FE",
                                                ),
                                            ),
                                            rx.cond(
                                                c["tested_concurrency_disp"] != "",
                                                rx.badge(
                                                    c["tested_concurrency_disp"],
                                                    color="#0F766E",
                                                    background="#CCFBF1",
                                                ),
                                            ),
                                            spacing="2",
                                        ),
                                        spacing="1",
                                        align_items="flex-start",
                                    ),
                                    rx.spacer(),
                                    rx.button("编辑", size="2", variant="soft", on_click=State.edit_api_config(c["id"]), cursor="pointer"),
                                    rx.cond(
                                        c["is_default"],
                                        rx.fragment(),
                                        rx.button("设为默认", size="2", variant="ghost", on_click=State.set_default_api(c["id"]), cursor="pointer"),
                                    ),
                                    rx.button("删除", size="2", variant="ghost", color_scheme="red", on_click=State.delete_api_config(c["id"]), cursor="pointer"),
                                    flex="1",
                                    align_items="center",
                                    flex_wrap="wrap",
                                ),
                                width="100%",
                                border="1px solid var(--app-border)",
                                border_radius="0.6rem",
                                padding="0.8rem",
                                margin_bottom="0.6rem",
                            ),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),
                width="100%",
                min_width="320px",
                flex="1",
            ),
            spacing="5",
            width="100%",
            align_items="flex-start",
            flex_wrap="wrap",
            margin_bottom="1.5rem",
        ),
        card(
            rx.heading("语言翻译配置", size="5", color="var(--app-fg)", margin_bottom="0.3rem"),
            rx.text(
                "为每个目标语言独立指定 API / 提示词模板 / 术语库 / 翻译策略。"
                "未指定的项跟随翻译页的当前选择或默认值。",
                color="var(--app-muted)",
                font_size="0.8rem",
                margin_bottom="1rem",
            ),
            rx.hstack(
                rx.select(
                    State.profile_lang_options,
                    value=State.profile_form_lang_display,
                    on_change=State.set_profile_form_lang,
                    placeholder="目标语言",
                    width="130px",
                    cursor="pointer",
                ),
                rx.select(
                    State.profile_api_options,
                    value=State.profile_form_api,
                    on_change=State.set_profile_form_api,
                    placeholder="API（不指定=默认）",
                    width="200px",
                    cursor="pointer",
                ),
                rx.select(
                    State.profile_template_options,
                    value=State.profile_form_template,
                    on_change=State.set_profile_form_template,
                    placeholder="提示词模板",
                    width="170px",
                    cursor="pointer",
                ),
                rx.select(
                    State.profile_term_options,
                    value=State.profile_form_term,
                    on_change=State.set_profile_form_term,
                    placeholder="术语库",
                    width="150px",
                    cursor="pointer",
                ),
                rx.select(
                    State.profile_strategy_options,
                    value=State.profile_form_strategy,
                    on_change=State.set_profile_form_strategy,
                    placeholder="策略",
                    width="160px",
                    cursor="pointer",
                ),
                primary_button(
                    rx.cond(
                        State.profile_form_editing > 0,
                        "更新配置",
                        "新增配置",
                    ),
                    on_click=State.save_lang_profile,
                    size="2",
                    width="auto",
                ),
                rx.cond(
                    State.profile_form_editing > 0,
                    rx.button(
                        "取消",
                        size="2",
                        variant="ghost",
                        on_click=State.reset_lang_profile_form,
                        cursor="pointer",
                    ),
                ),
                spacing="3",
                width="100%",
                align_items="center",
                flex_wrap="wrap",
            ),
            rx.divider(margin_y="1rem"),
            rx.cond(
                State.lang_profiles.length() == 0,
                empty_state("还没有配置任何语言"),
                rx.vstack(
                    rx.foreach(
                        State.lang_profiles,
                        lambda p: rx.box(
                            rx.hstack(
                                rx.badge(p["lang_display"], color="#1D4ED8", background="#DBEAFE"),
                                rx.text(
                                    f"API：{p['api_display']} · 模板：{p['template_display']} · 术语库：{p['term_display']} · 策略：{p['strategy_display']}",
                                    color="var(--app-fg)",
                                    font_size="0.85rem",
                                ),
                                rx.spacer(),
                                rx.button("编辑", size="2", variant="soft", on_click=State.edit_lang_profile(p["id"]), cursor="pointer"),
                                rx.button("删除", size="2", variant="ghost", color_scheme="red", on_click=State.delete_lang_profile(p["id"]), cursor="pointer"),
                                width="100%",
                                align_items="center",
                            ),
                            width="100%",
                            border="1px solid var(--app-border)",
                            border_radius="0.6rem",
                            padding="0.8rem",
                            margin_bottom="0.6rem",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
            ),
            width="100%",
        ),
    )
