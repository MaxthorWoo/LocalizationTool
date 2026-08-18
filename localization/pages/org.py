"""组织页：创建 / 加入组织。"""
from __future__ import annotations

import reflex as rx

from localization.components import (
    card,
    confirm_dialog,
    empty_state,
    layout,
    page_heading,
    primary_button,
)
from localization.state import State


@rx.page(route="/org", title="组织", on_load=State.load_orgs)
def org_page() -> rx.Component:
    return layout(
        page_heading("组织", "创建或加入组织，共享组织的提示词模板与术语库"),
        rx.hstack(
            card(
                rx.heading("创建组织", size="5", color="var(--app-fg)", margin_bottom="1rem"),
                rx.vstack(
                    rx.input(placeholder="组织名称", value=State.org_new_name, on_change=State.set_org_new_name, width="100%"),
                    primary_button("创建组织", on_click=State.create_org, width="100%"),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            card(
                rx.heading("加入组织", size="5", color="var(--app-fg)", margin_bottom="1rem"),
                rx.vstack(
                    rx.text("输入组织邀请码即可加入该组织，获得共享模板与术语", color="var(--app-muted)", font_size="0.85rem"),
                    rx.input(placeholder="邀请码（如 RH62YY）", value=State.org_join_code, on_change=State.set_org_join_code, width="100%"),
                    rx.button("加入组织", on_click=State.join_org, variant="soft", width="100%", cursor="pointer"),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            spacing="5",
            width="100%",
            align_items="flex-start",
        ),
        rx.box(
            rx.heading("我的组织", size="5", color="var(--app-fg)", margin_bottom="1rem"),
            rx.text(
                "你已创建 / 加入的组织会一直保留，重启后自动加载，无需重复创建。",
                color="var(--app-muted)",
                font_size="0.8rem",
                margin_bottom="0.8rem",
            ),
            rx.cond(
                State.orgs.length() == 0,
                empty_state("还没有组织，请在上方创建或输入邀请码加入"),
                rx.vstack(
                    rx.foreach(
                        State.orgs,
                        lambda o: rx.hstack(
                            rx.vstack(
                                rx.hstack(
                                    rx.text(o["name"], font_weight="600", color="var(--app-fg)"),
                                    rx.cond(
                                        o["is_owner"],
                                        rx.badge("我创建的", color="#059669", background="#D1FAE5"),
                                    ),
                                    spacing="2",
                                    align_items="center",
                                ),
                                rx.text(f"创建于 {o['created_time']}", color="var(--app-muted)", font_size="0.75rem"),
                                spacing="1",
                                align_items="flex-start",
                            ),
                            rx.badge(f"邀请码：{o['join_code']}", color="#2563EB", background="#DBEAFE"),
                            rx.spacer(),
                            rx.cond(
                                o["is_owner"],
                                rx.button(
                                    "删除",
                                    size="2",
                                    variant="ghost",
                                    color_scheme="red",
                                    on_click=State.request_delete_org(o["id"]),
                                    cursor="pointer",
                                ),
                            ),
                            width="100%",
                            padding="0.8rem",
                            border="1px solid var(--app-border)",
                            border_radius="0.6rem",
                            align_items="center",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
            ),
            margin_top="1.5rem",
            width="100%",
        ),
        confirm_dialog(
            State.org_delete_confirm_id > 0,
            title="确认删除组织",
            message="确定要删除该组织吗？删除后不可恢复。仅创建者可删除。",
            on_confirm=State.do_delete_org,
            on_cancel=State.cancel_delete_org,
        ),
    )
