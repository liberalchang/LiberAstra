---
title: 作品与任务
---

# 作品与任务

资产、插件与任务中心：产物、来源和文件都在本地。

侧栏「资源」有两项：资产、插件。

## 资产

成功产物。生成中可切页，任务不停；同一浏览器标签会续挂进度，关标签后进度条不再自动挂上，任务仍在跑。画布上功能、语音、合成节点的产物默认不列出，在节点上「保存到资源库」后出现在这里。勾选「含画布中间结果」可查看这些未发布文件和蒙版。深度图生成的结果带深度图标记，文件名以 `_depth.png` 结尾。

## 插件

「资源 → 插件」只管理本机附加服务：Liber Speech（端口 5555）和 Liber Depth（端口 5556）。可以搜索。卡片上是图标、名称和说明；点开才看路径、启停和安装。

连接局域网里已经在跑的语音或深度服务时，不要在这里安装。到「服务提供方」填地址。

**安装。** 点「安装」后开关变成闪烁的「安装中」，卡片和详情里都有进度条。阶段依次是：准备 Python 环境、安装 PyTorch、安装该插件自己的依赖；深度插件还会下载默认模型。装完之前不能启用。失败时详情里有错误，进度条消失。

语音和深度共用一份带 PyTorch 的 Python 环境。已经检测到这份环境时，后装的插件只补自己缺的包，不会再装一遍 PyTorch。

| 启动方式 | 路径 |
|----------|------|
| 从 `backend` 开发启动 | 环境在 `%LOCALAPPDATA%\LiberAstra\plugin-runtime`。模型在 `backend/data/plugins/<speech 或 depth>/models` |
| Windows 安装包 | 数据目录是 `%LOCALAPPDATA%\LiberAstra\data`。环境在其中的 `plugins\runtime`。模型在 `plugins\<speech 或 depth>\models` |

已发布的 LiberSpeech 安装包如果自带 `docker-compose.yml` 和 `install.ps1`，启用时走 Docker，不再建上面这份 Python 环境。仓库里的 `services/speech` 没有 `install.ps1`，仍用 Python。

**启用和卸载。** 启用会拉起本机进程，并在服务提供方里放一份对应配置（Liber Speech API 或 Liber Depth 深度图）。禁用停进程并关掉这份本地配置。卸载同样停进程。Docker 方式的语音在禁用时执行 `docker compose stop`，不会 `down`。

语音权重不在安装时下载，第一次合成时落到语音模型目录。深度安装只下载 `dpt_swin2_large_384.pt`，其余权重见上文「深度图生成」。

---

## 任务

侧栏「任务」。看进度与状态。「重试」复用旧参数；改设置后请发新任务。画布上功能节点、语音节点、合成节点的执行也会出现在这里。

---
