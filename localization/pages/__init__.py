"""页面模块包。

导入所有页面模块以注册 Reflex 路由（@rx.page 在导入时生效）。
app.py 只需导入本包即可完成全部路由注册。
"""
from . import index, languages, org, project, prompts, settings, terms  # noqa: F401

__all__ = ["index", "project", "prompts", "terms", "settings", "org", "languages"]
