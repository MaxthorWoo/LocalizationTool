import inspect
import reflex as rx

print("rx version:", getattr(rx, "__version__", "unknown"))
p = rx.progress
try:
    print("rx.progress params:", list(inspect.signature(p).parameters))
except Exception as e:  # noqa: BLE001
    print("rx.progress err:", e)

# 测试 cond 数值比较
try:
    c = rx.cond(rx.State.progress_total > 0, rx.text("yes"), rx.text("no"))
    print("cond > 0 OK")
except Exception as e:  # noqa: BLE001
    print("cond > 0 ERR:", e)
