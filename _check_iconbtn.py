import reflex as rx
import traceback

try:
    c = rx.icon_button(rx.icon("refresh-cw"), size="1", variant="soft")
    print("icon_button size=str OK")
except Exception as e:  # noqa: BLE001
    print("icon_button size=str ERR:", e)

try:
    c = rx.icon_button(rx.icon("refresh-cw"), size=1, variant="soft")
    print("icon_button size=int OK")
except Exception as e:  # noqa: BLE001
    print("icon_button size=int ERR:", e)
