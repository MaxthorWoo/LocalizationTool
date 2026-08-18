"""Reflex 项目配置。"""

import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="app",
    app_module_import="app",
    frontend_port=3100,
    backend_port=8100,
    telemetry_enabled=False,
    show_built_with_reflex=False,
    default_color_mode="light",
    disable_plugins=[SitemapPlugin],
    plugins=[rx.plugins.RadixThemesPlugin(theme=rx.theme(appearance="light", accent_color="blue", radius="medium"))],
)
