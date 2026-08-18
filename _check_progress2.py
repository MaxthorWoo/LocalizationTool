import reflex as rx
from localization.state import State

# 模拟 project.py 的进度条写法
c = rx.cond(
    State.progress_total > 0,
    rx.vstack(
        rx.text(State.progress_text, color="var(--app-muted)", font_size="0.85rem"),
        rx.progress(
            value=State.progress_done,
            max=State.progress_total,
            width="220px",
        ),
        spacing="1",
        align_items="flex-start",
    ),
)
# 输出编译后的 JSX 查看 Progress props
import reflex_base.compiler.compiler as comp

jsx = comp.compile_to_jsx([c])
text = str(jsx[0].to_string()) if jsx else ""
import re

for m in re.finditer(r"Progress[^,]*,{", text):
    print("PROGRESS JSX:", m.group(0)[:200])
for m in re.finditer(r"value[^}]*}", text):
    print("VALUE:", m.group(0)[:150])
