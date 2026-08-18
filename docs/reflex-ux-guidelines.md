# Reflex 交互细节统一修改指南（给 AI 的流程文档）

> 目的：当你需要在任意 Reflex 项目中修改"光标样式（cursor）、按钮禁用、下拉框交互"等
> 细节时，按本文档流程执行，避免踩坑。
> 适用版本：Reflex 0.9.x（0.9.8 验证通过）。

---

## 0. 背景与核心结论

Reflex 的组件（`rx.button`、`rx.select` 等）大多不是原生 HTML 元素，
而是 Radix Themes 封装的自定义组件。因此：

| 组件 | 底层真实 DOM | `cursor` 属性是否生效 | 备注 |
| --- | --- | --- | --- |
| `rx.button` | `<button>` | ✅ 生效 | 但全局 style 只认 `button` 选择器 |
| `rx.select` | `<button>`（点击弹出列表） | ✅ 生效 | **不是**原生 `<select>`！全局 `select` 选择器对它无效 |
| `rx.input` | `<input>` | 通常无需设置 | 文本输入本身就该是文本光标 |
| `rx.link` / `rx.text(...as_="a")` | `<a>` | ✅ 生效 | |
| `rx.checkbox` | `<button>` + 内部 `input[type=checkbox]` | ✅ 生效 | |
| 原生 `html.select` | `<select>` | ✅ 生效 | 一般不会直接用到 |

**两条铁律：**

1. `rx.select` 底层是 `<button>`，不是 `<select>`。
   → 全局样式里写 `"select": {"cursor": "pointer"}` 只对**原生** select 生效，
   `rx.select` 必须单独设置 `cursor="pointer"`（局部）或加全局 `button` 规则。
2. 禁用属性在 Reflex 0.9.8 中只认 **`disabled`**，`is_disabled` 不生效。

---

## 1. 修改前检查清单

1. 确认 Reflex 版本：`reflex --version`（本文档适用于 0.9.x）。
2. 定位"全局样式"位置：通常在 `app.py` 的 `rx.App(style={...})` 里。
3. 定位"组件样式"位置：项目里封装的公共组件文件（如 `components/common.py`）。
4. 用文本搜索找出所有受影响的关键词：
   - `rx.button(`、`rx.select(`、`is_disabled`、`cursor`
5. **搜索时注意**：`is_disabled` 可能是某个组件的 props 传参，也可能是
   RxConfig/其他框架的参数，务必逐个确认来源，不要盲改。

---

## 2. 全局手型光标（推荐方式）

在 `app.py` 的 `rx.App(style={...})` 中一次性统一设置：

```python
app = rx.App(
    style={
        # 所有可交互元素统一手型光标
        "button": {"cursor": "pointer"},
        "a": {"cursor": "pointer"},
        "select": {"cursor": "pointer"},   # 仅对原生 <select> 生效
        "label": {"cursor": "pointer"},
    },
)
```

> 注意：这是全局兜底。`rx.select` 不在此列，需要单独处理（见第 4 节）。

---

## 3. 局部设置（组件级）

在封装组件内部给每个组件显式加 `cursor="pointer"`，优点是**不依赖全局选择器**，
即使后续全局样式被覆盖也不受影响：

```python
def primary_button(text, on_click=None, disabled=None, **kwargs) -> rx.Component:
    return rx.button(
        text,
        on_click=on_click,
        disabled=disabled,   # 注意：不是 is_disabled
        cursor="pointer",    # 局部显式声明
        **kwargs,
    )
```

---

## 4. 下拉框（rx.select）——最容易踩坑

### 4.1 现象

全局写了 `"select": {"cursor": "pointer"}`，但 `rx.select` 鼠标移上去**没有手型**。

### 4.2 原因

`rx.select` 底层渲染成 `<button>`（Radix Themes 的下拉触发按钮），
CSS 全局选择器 `select` 匹配不到它。

### 4.3 正确做法

给每个 `rx.select` 显式传 `cursor="pointer"`：

```python
rx.select(
    options,
    value=value,
    on_change=on_change,
    width=width,
    placeholder=placeholder,
    cursor="pointer",   # ← 必须局部设置
)
```

### 4.4 自查方法

- 用浏览器开发者工具（F12）选中下拉框，看 DOM 元素标签名。
  若显示 `<button>`，则说明是 Radix 封装，必须走局部 `cursor`。
- 如果项目中 `rx.select` 很多，可以在公共封装组件里统一加，只改一处。

---

## 5. 禁用按钮：is_disabled 不生效

### 5.1 现象

```python
rx.button("保存", is_disabled=not_state)
```
点击仍然可触发，或组件没有进入禁用视觉状态。

### 5.2 原因

Reflex 0.9.8 的 `rx.button` 只识别 **`disabled`** 属性，
`is_disabled` 是旧版本/其他组件的命名，此处被静默忽略。

### 5.3 正确做法

```python
rx.button(
    "保存",
    on_click=save,
    disabled=not_state,   # ← 改成 disabled
)
```

### 5.4 全项目排查

```text
搜索关键词：is_disabled
逐个替换为 disabled（确认该处确实是 Reflex 组件 prop）。
```

---

## 6. 验证流程（每次修改后必须执行）

1. 重新编译 / 热重载：
   ```bash
   reflex run          # 观察编译输出有无报错
   ```
   （或按项目 `start.bat` / `start.ps1` 启动）
2. 浏览器打开对应页面：
   - 鼠标悬停在按钮上 → 应为手型。
   - 鼠标悬停在 `rx.select` 下拉框上 → 应为手型（需按第 4 节设置过）。
   - 点击禁用按钮 → 无反应、有禁用样式。
3. 切到"夜间/日间"主题再验证一次（若项目支持日夜模式，CSS 变量可能影响观感，
   但不影响 cursor 属性）。
4. 检查运行日志无新的异常。

---

## 7. 常见坑速查（源自真实项目经验）

| 坑 | 现象 | 解法 |
| --- | --- | --- |
| `is_disabled` | 禁用不生效 | 改成 `disabled` |
| `rx.select` 无手型 | 全局 `select` 选择器无效 | 局部加 `cursor="pointer"` |
| 中文引号进 Python 字符串 | `SyntaxError` | 用英文引号或无引号文案 |
| `rx.foreach` 里拼接 Var | 报错/渲染异常 | 用 `rx.text("{", v["name"], "}")` 多子节点 |
| async 事件无转圈反馈 | 点击后 UI 无 loading | 拆成同步事件立即设状态 + `yield` 后台 async 事件 |
| background task 改 state | `ImmutableStateError` | 必须 `async with self:` |
| 卡片宽度百分比堆叠 | 布局超宽 | 检查同层多个 `width` 百分比是否超 100% |

---

## 8. 给其他 AI 的执行模板

> 当接到"把 X 组件改成手型/禁用"这类需求时，按此模板执行：

1. **先搜后改**：`search_content` 找 `rx.button(`、`rx.select(`、`is_disabled`。
2. **先全局后局部**：全局 style 里加 `button/a/select/label` 的 cursor 规则；
   公共组件文件里给 `rx.select` 单独加 `cursor="pointer"`。
3. **disabled 代替 is_disabled**：所有禁用逻辑统一用 `disabled=`。
4. **改完必须编译验证**：跑一次 `reflex run` 确认无报错，再让用户浏览器确认。
5. **不要顺手重构**：只改目标细节，别动无关代码（尤其是用户已调好的布局）。

---

*本文件基于本仓库实际项目（Reflex 0.9.8）验证经验整理，可直接复制到其他 Reflex 项目复用。*
