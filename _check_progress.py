import reflex as rx

# 直接渲染 progress 不带 cond
c1 = rx.progress(value=10, max=100, width="220px")
print("progress direct OK")

# 用布尔 cond
c2 = rx.cond(True, rx.progress(value=10, max=100), rx.text("x"))
print("cond bool OK")

# 用 State bool 字段测试编译
print("has is_translating:", hasattr(rx.State, "is_translating"))
