"""工程导入列映射向导（首页 / 校对页共用）。

依赖：State、modal、select_field、primary_button、column_role_select。
"""
from __future__ import annotations

import reflex as rx

from localization.components.common import modal, primary_button, select_field
from localization.components.roles import column_role_select
from localization.state import State


def import_wizard() -> rx.Component:
    """导入向导（多步模态）：上传表格文件后确认列映射。"""
    return modal(
        State.wizard_open,
        on_close=State.close_wizard,
        title="列映射",
        width="760px",
        z_index="100",
        children=[
            rx.cond(
                State.wizard_step == 2,
                rx.vstack(
                    rx.text(
                        "自动识别列的语义角色，如需修正请在每列下拉中选择。",
                        color="var(--app-muted)",
                        font_size="0.85rem",
                        margin_bottom="1rem",
                    ),
                    rx.hstack(
                        select_field(
                            "源语言",
                            State.lang_display_options,
                            value=State.source_lang_display,
                            on_change=State.set_source_lang,
                        ),
                        select_field(
                            "套用列模板",
                            State.column_template_names,
                            value="",
                            on_change=State.apply_column_template_by_name,
                            placeholder="选择模板",
                        ),
                        rx.vstack(
                            rx.text("保存为模板", font_size="0.8rem", color="var(--app-muted)"),
                            rx.form(
                                rx.hstack(
                                    rx.input(name="tpl_name", placeholder="模板名", width="120px"),
                                    rx.button("保存", size="2", variant="soft", type="submit", cursor="pointer"),
                                    spacing="2",
                                ),
                                on_submit=State.save_column_template,
                            ),
                            spacing="1",
                            align_items="flex-start",
                            width="100%",
                        ),
                        spacing="6",
                        width="100%",
                        align_items="flex-start",
                        margin_bottom="1rem",
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
                                State.preview_headers,
                                lambda col: rx.table.row(
                                    rx.table.cell(rx.text(col, font_weight="500")),
                                    rx.table.cell(column_role_select(col)),
                                ),
                            ),
                        ),
                        width="100%",
                        margin_bottom="1rem",
                    ),
                    primary_button("确认导入", on_click=State.confirm_table_import, width="100%"),
                    width="100%",
                ),
                rx.fragment(),
            ),
        ],
    )
