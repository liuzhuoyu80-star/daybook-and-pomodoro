# 日程簿与浮动番茄钟

两款可以独立运行的小工具。**日程簿**用浏览器安排每日精力、任务、思考和交付；**浮动番茄钟**是在桌面一角运行的工作与休息计时器。

在仓库首页选择 **Code → Download ZIP**，解压整个文件夹，再按下面对应的步骤启动。使用 Git 也可克隆仓库。运行工具无需 GitHub 账号。

## 日程簿

1. 在准备存放数据的电脑上安装 [Node.js](https://nodejs.org/)（推荐 LTS，最低 18）。重新打开终端，输入 `node --version` 检查。
2. 打开 `daybook` 文件夹。Windows 双击 **start-windows.cmd**；macOS 双击 **start-mac.command**。也可在该文件夹的终端执行 `node server.cjs`，Linux 同样适用。无需运行 npm install。
3. 把终端显示的完整地址复制到浏览器。使用期间保持服务窗口打开，按 Ctrl+C 停止。首次使用从空白日程开始，右上角可选择用户、添加用户。
4. 要在另一台设备接着写，让它连接同一局域网，在浏览器打开**同一个地址**并选择同一用户。若有防火墙提示，仅在信任的专用网络允许访问。用户切换不需要密码；能访问该服务的人都可以切换用户、读取和编辑记录。

**数据保存在哪里**

| 操作 | 保存位置 |
| --- | --- |
| 在页面填写 | 当前浏览器自动保存本地草稿 |
| 点击「保存草稿」 | 服务电脑的 `DaybookData/drafts`，按用户和日期建文件 |
| 点击「归档整日工作台」 | 服务电脑的 `DaybookData/history`，在「历史看板」打开 |
| 添加、改名或移除用户 | 服务电脑的 `DaybookData/users.json` |

Windows 可在资源管理器地址栏输入 `%LOCALAPPDATA%\DaybookData`；macOS、Linux 在当前用户主目录的 `~/DaybookData`。首次保存相应内容时才建目录。换服务电脑时，先保存重要的浏览器草稿，再把整个 `DaybookData` 文件夹复制到新电脑的对应位置。数据由运行服务的人保管，不会发送到 GitHub。

服务默认选择本机的私有 IPv4 地址和端口 8768；没有符合条件的地址时使用 `127.0.0.1`。有多张网卡时，可通过 `DAYBOOK_HOST` 指定本机地址；端口已占用时，可设置 `DAYBOOK_PORT`。只在自己电脑上使用时，在 Windows PowerShell 输入：

```powershell
$env:DAYBOOK_HOST = "127.0.0.1"
node server.cjs
```

在 macOS 或 Linux 的终端中，对应命令是 `DAYBOOK_HOST=127.0.0.1 node server.cjs`。页面源码位于 [daybook/dist/index.html](daybook/dist/index.html)，服务入口是 [daybook/server.cjs](daybook/server.cjs)。

## 浮动番茄钟

| 版本 | 表盘 |
| --- | --- |
| v0.1 | 初代表盘，工作与休息倒计时 |
| v0.2 | 七段液晶显示，按钮点击反馈、到点三阵震动、休息夜光 |
| v0.3 | 机械旋钮，滚动调整单次倒计时 |
| v0.4 | 方形数字手表，四个侧键 |

**Windows 运行**：安装带有 py 启动器的 [Python 3.12](https://www.python.org/downloads/)，进入解压后的 `pomodoro` 文件夹，在 PowerShell 或命令提示符执行：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe v0.2\main.py
```

以后直接运行最后一行即可。试其他表盘时，把最后一行中的版本号换为 `v0.1`、`v0.3` 或 `v0.4`。v0.4 的 `watch.png` 要与 `main.py` 放在同一目录。

**Mac 运行 v0.2**：支持 macOS 12 或更新版本，进入 `pomodoro/v0.2`，双击 **start-mac.command**。也可在该目录打开终端执行 `sh start-mac.command`。首次启动需要联网下载并校验 Python 和 Qt 环境（约 160 MB），完成后可离线启动。启动脚本覆盖 Apple 芯片与 Intel；桌面置顶、触控板和系统权限体验仍待实机验收。

v0.2 中，点三角形开始，点双竖线暂停。点选时、分、秒后可滚轮调整，拖动数字移动窗口。右键表盘可退出。
