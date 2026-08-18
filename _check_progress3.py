import reflex as rx
from reflex_base.compiler.compiler import compile_to_jsx

from localization.state import State


def dump(label: str, comps) -> None:
    js = compile_to_jsx(comps)
    text = str(js[0].to_string()) if js else ""
    print(f"=== {label} ===")
    print(text[:1500])
    print()


# 1) 直接 Progress 带 Var props（无 cond）
dump(
    "direct progress",
    rx.progress(value=State.progress_done, max=State.progress_total, width="220px"),
)

# 2) cond(True) 包裹
dump(
    "cond True wrap",
    rx.cond(True, rx.progress(value=State.progress_done, max=State.progress_total, width="220px")),
)

# 3) cond(is_translating) 包裹
dump(
    "cond is_translating wrap",
    rx.cond(State.is_translating, rx.progress(value=State.progress_done, max=State.progress_total, width="220px")),
)
