---
name: LiberAstra
description: 自托管 AIGC 聚合编排平台——导演监视台式创作台
colors:
  primary: "#6d28d9"
  primary-dark: "#7c3aed"
  primary-foreground: "#fafafa"
  accent: "#e11d48"
  background: "#f3f4f6"
  background-dark: "#0d0c10"
  card: "#ffffff"
  card-dark: "#18171d"
  field-dark: "#2d2b35"
  foreground: "#18181b"
  foreground-dark: "#f4f4f5"
  muted-foreground: "#52525b"
  muted-foreground-dark: "#b4b4bc"
  success: "#15803d"
  success-dark: "#4ade80"
  danger: "#dc2626"
  danger-dark: "#f87171"
  warning: "#b45309"
  warning-dark: "#fbbf24"
  info: "#2563eb"
  info-dark: "#60a5fa"
typography:
  display:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "2.25rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    letterSpacing: "-0.025em"
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
rounded:
  sm: "8px"
  md: "10px"
  lg: "12px"
  xl: "16px"
  hero: "24px"
  auth: "28px"
spacing:
  group: "8px"
  section: "16px"
  page: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.lg}"
    height: "44px"
    padding: "0 16px"
  button-outline:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.lg}"
    height: "44px"
  nav-item-active:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    height: "40px"
---

# Design System: LiberAstra

## Overview

**Creative North Star: "导演监视台 (Director's Console)"**

LiberAstra 的界面是一间导播间：用户面对的不是营销页，而是一排仪器——ComfyUI、Ollama、语音服务、云端 API 都是被编排的设备。设计语言因此克制、密集、以状态为先：颜色是信号灯（运行蓝、成功绿、失败红、告警琥珀），主色星云紫只出现在动作与定位上。明暗双主题与中英双语是一等公民，任何视觉决策必须在四套组合里同时成立。

**Key Characteristics:**
- 工具密度优先于视觉表现欲；可扫读性高于一切
- 颜色承载状态与导航，不承载装饰
- 轻盈、安静、精密的组件性格：淡色底、细边框、无重阴影
- 品牌签名元素是「主色光斑」——页头与登录页的大半径柔光斑，随主题色变化

## Colors

调色板是一组角色而不是一袋色板：画布、卡片、控件底、动作、状态，各司其职。

### Primary
- **星云紫 (Nebula Violet)**(#6d28d9，暗色 #7c3aed):唯一动作色——主按钮、聚焦环、选中态、侧栏当前项淡底。暗色版加深到 violet-600 以保证 5.2:1 的文字对比度。

### Secondary
- **信号玫红**(#e11d48):仅用于顶部公告 banner 与少量强调点缀，两主题同值。

### Neutral
- **纸灰**(#f3f4f6):亮色画布。
- **墨紫黑**(#0d0c10):暗色画布——中性色带极轻的紫 hue，与星云紫呼应，暗色不是纯灰。
- **卡片白/暗卡**(#ffffff / #18171d):内容承载面。
- **控件底**（暗色 #2d2b35):刻意比卡片亮，避免控件融入底。
- **次级文字**(#52525b / #b4b4bc):提示与元信息。

### Status
- **成功**(#15803d / #4ade80)、**失败**(#dc2626 / #f87171)、**告警**(#b45309 / #fbbf24)、**运行/信息**(#2563eb / #60a5fa):监视台的信号灯，正文对比度均 ≥4.5:1。

### Named Rules
**The One Voice Rule.** 星云紫在任一屏幕的占比 ≤10%。它的稀有就是它的力量——动作、聚焦、当前位置，除此之外不花它。
**The Signal Rule.** 状态色只表达状态（任务、校验、服务健康），永不用于装饰或品牌。

## Typography

**Display / Body / Label 全部为同一系统字栈**(system-ui + PingFang SC + Microsoft YaHei):自托管 LAN 工具不加载 webfont,零 FOUT、离线可用、中文原生渲染。层级靠字重、字号、字距与颜色的组合，不依赖第二字体。

**Character:** 务实的技术感——14px 正文密度服务扫读，标题用负字距收紧，数字用 tabular-nums。

### Hierarchy
- **Display**(600, 2.25rem, 行高 1.15, -0.025em):仅首页 hero 标题。一个应用只配一个 display 位。
- **Title**(600, 1.5rem, tracking-tight):页头 h1。
- **Body**(400, 0.875rem, 行高 1.5):控件、正文、表格的默认密度。
- **Label**(500, 0.75rem):提示、元信息、徽章；行高放宽(relaxed)补偿小字号。

### Named Rules
**The Balance Rule.** 标题 `text-wrap: balance`，正文 `text-wrap: pretty`——不允许孤词末行出现在任何标题里。

## Layout

侧栏(展开 240px / 收起 64px)+ 单列任务页。页面容器统一 `max-w-5xl`，首页工作台 `max-w-6xl`。纵向节奏三级：组内 8px、区间 16px、页面 24px(gap-2/4/6)。工具页左右分栏(参数 | 结果),窄屏堆叠;侧栏在 md 以下收为抽屉。相关项靠近优先于加容器;卡片只装真正的内容组,不做排版填充物。

## Elevation & Depth

以色调分层为主，阴影只在两处出现：弹窗/登录卡的 `shadow-2xl`(层级声明)与 hover 的 `shadow-md`(状态反馈)。品牌光斑(页头 `bg-primary/15`、磨砂浮卡上可到 `/20`,大圆 `blur-3xl`)是唯一的氛围元素，也是签名。

### Named Rules
**The Flat-By-Default Rule.** 静止的表面是平的。阴影只响应状态(hover、弹层),不做装饰性深度。

## Shapes

圆角梯度即层级：徽章/芯片 8px，输入框 10px，按钮与小卡 12px，卡片 16px，页头/hero 24px，登录卡为登记的例外 28px(磨砂浮层独享),头像与图标钮全圆。边框一律 1px `--border`;不允许彩色粗边条。

## Components

### Buttons
- **性格:** 轻盈、安静、精密——半粗字、12px 圆角、按压时 scale 0.98 的物理确认。
- **Primary:** 星云紫底 + #fafafa 字(44px 高);hover 降 10% 不透明度。
- **Outline:** 控件底 + 细边框;**Ghost:** 无框,hover 淡底。图标钮 40px。
- **Focus:** 全体统一 2px `--ring` 光环,仅 `:focus-visible`。

### Inputs / Fields
- **Style:** 控件底色 + 1px 边框 + 10px 圆角(下拉 44px 高,文本域 12px 圆角)。
- **Focus:** 主色光环 + 主色光标;浏览器自动填充底色跟随主题。
- 标签与控件程序化关联(`<label htmlFor>`),提示文字在控件下方。

### Cards / Containers
- 16px 圆角 + 1px 边框 + 卡片底色;不嵌套卡片;内边距 16–24px。

### Navigation
- 侧栏分组导航,当前项 = 星云紫淡底 + 主色字(The One Voice Rule 的合法支出);折叠态纯图标 + tooltip;md 以下为遮罩抽屉。

### Dialogs(LightboxShell)
- 遮罩 70% 黑 + 轻模糊,弹层 16px 圆角 + shadow-2xl,Esc 关闭、焦点圈在弹窗内、关闭归还焦点。

### Signature: 页头(PageHeader)
- 24px 圆角横卡:主色淡底图标砖(带 1px 主色描边)+ Title + 一行说明,右上两片主色光斑。全站每页一张,是监视台的"工位铭牌"。

## Do's and Don'ts

### Do:
- **Do** 状态一律用 success/danger/warning/info token,明暗两主题自动正确。
- **Do** 新弹窗复用 LightboxShell,模式切换复用 Segmented,表单字段复用 Field。
- **Do** 每个视觉决策同时在明暗 × 中英四套组合里验证。

### Don't:
- **Don't** 引入硬编码色板类(text-red-500 等)——2026-10 已全部清除,补丁式 `.dark` 覆写一并删除,不许回流。
- **Don't** 嵌套卡片、用彩色粗边条、或把星云紫花在装饰上。
- **Don't** 新增第二字体或 webfont;层级用字重/字号/字距/颜色解决。
- **Don't** 给静态表面加阴影;阴影只响应状态。
