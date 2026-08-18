"""本地化可视化翻译平台 - 应用入口。

仅负责：
1. 数据库初始化
2. 创建 Reflex App 实例（全局样式）
3. 导入页面包以注册全部路由

页面代码拆分在 localization/pages/ 各文件中。
"""
import reflex as rx

# 导入全部页面以注册路由（side-effect import）
from localization import pages as _pages  # noqa: F401

_ = _pages

# =========================================================
# App 实例
# =========================================================

app = rx.App(
    style={
        "body": {"background": "#F8FAFC"},
        # 所有可交互元素统一手型光标
        "button": {"cursor": "pointer"},
        "a": {"cursor": "pointer"},
        "select": {"cursor": "pointer"},
        "label": {"cursor": "pointer"},
    },
)


def _ensure_initialized() -> None:
    """应用启动时初始化数据库。"""
    from localization.db import init_db

    init_db()


_ensure_initialized()
