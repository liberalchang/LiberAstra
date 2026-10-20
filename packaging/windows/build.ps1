# 打 LiberAstra 的 Windows 安装包。
# 构建机需要：Windows x64、Node.js 20+、可访问外网。目标机器不需要安装 Python。
# 产物：packaging/windows/output/LiberAstra-Setup.exe
$ErrorActionPreference = "Stop"
# robocopy 用 0–7 表示成功，不能当成失败。
$PSNativeCommandUseErrorActionPreference = $false

$Here = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $Here "..\..")).Path
$Stage = Join-Path $Here "stage"
$Cache = Join-Path $Here "cache"
$Output = Join-Path $Here "output"
$PyVersion = "3.12.10"
$EmbedZip = Join-Path $Cache "python-$PyVersion-embed-amd64.zip"
$EmbedUrl = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"

function Get-File($Url, $Dest) {
    if (Test-Path $Dest) { return }
    New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
    Write-Host "下载 $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Dest
}

Write-Host "构建前端"
Push-Location (Join-Path $Repo "frontend")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Pop-Location
if (-not (Test-Path (Join-Path $Repo "frontend\dist\index.html"))) {
    throw "frontend/dist 不存在"
}

if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage, $Cache, $Output | Out-Null

Write-Host "准备嵌入式 Python $PyVersion"
Get-File $EmbedUrl $EmbedZip
$Runtime = Join-Path $Stage "runtime"
Expand-Archive -Path $EmbedZip -DestinationPath $Runtime -Force
$Pth = Get-ChildItem $Runtime -Filter "python*._pth" | Select-Object -First 1
if (-not $Pth) { throw "未找到 python._pth" }
# 嵌入式 Python 的 ._pth 会忽略 PYTHONPATH。backend 必须写进这个文件，workflows 才能和包并列。
@"
python312.zip
.
Lib\site-packages
../backend
import site
"@ | Set-Content -Path $Pth.FullName -Encoding ascii

Get-File "https://bootstrap.pypa.io/get-pip.py" (Join-Path $Cache "get-pip.py")
Copy-Item (Join-Path $Cache "get-pip.py") (Join-Path $Runtime "get-pip.py")
$Python = Join-Path $Runtime "python.exe"
& $Python (Join-Path $Runtime "get-pip.py")
if ($LASTEXITCODE -ne 0) { throw "get-pip 失败" }
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "升级 pip 失败" }
# 嵌入式 Python 没有 venv，不能走本地包的构建隔离。只装依赖，源码用 PYTHONPATH 指向 backend。
& $Python -m pip install -r (Join-Path $Here "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "安装 Python 依赖失败" }
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $Stage "ms-playwright"
& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "安装 Chromium 失败" }
Remove-Item (Join-Path $Runtime "get-pip.py") -ErrorAction SilentlyContinue

Write-Host "拷贝程序与内置资源"
$BackendDest = Join-Path $Stage "backend"
New-Item -ItemType Directory -Force -Path $BackendDest | Out-Null
robocopy (Join-Path $Repo "backend\liberastra") (Join-Path $BackendDest "liberastra") /E /NFL /NDL /NJH /NJS /XD __pycache__ | Out-Null
robocopy (Join-Path $Repo "backend\workflows") (Join-Path $BackendDest "workflows") /E /NFL /NDL /NJH /NJS | Out-Null
robocopy (Join-Path $Repo "backend\prompts") (Join-Path $BackendDest "prompts") /E /NFL /NDL /NJH /NJS | Out-Null
robocopy (Join-Path $Repo "backend\templates") (Join-Path $BackendDest "templates") /E /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw "拷贝后端资源失败：robocopy $LASTEXITCODE" }
robocopy (Join-Path $Repo "frontend\dist") (Join-Path $Stage "frontend\dist") /E /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw "拷贝前端失败：robocopy $LASTEXITCODE" }
Copy-Item (Join-Path $Here "start.cmd") (Join-Path $Stage "start.cmd")

$env:LIBERASTRA_DATA_DIR = Join-Path $env:TEMP "la-build-check"
& $Python -c "import liberastra; from pathlib import Path; root = Path(liberastra.__file__).resolve().parents[1]; assert (root / 'workflows' / 'qwen_image_21' / 'manifest.yaml').exists(), root; from liberastra.core.config import Settings; static = Settings().resolved_static_dir; assert static and (static / 'index.html').exists(), static"
if ($LASTEXITCODE -ne 0) { throw "嵌入式 Python 无法导入 liberastra、工作流或前端页面" }

$Iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    Write-Host "未找到 Inno Setup，尝试用 winget 安装"
    winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
    $Iscc = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $Iscc) { throw "未找到 ISCC.exe。请安装 Inno Setup 6 后重跑本脚本。" }

Write-Host "编译安装包"
& $Iscc (Join-Path $Here "LiberAstra.iss")
Write-Host "完成：$(Join-Path $Output 'LiberAstra-Setup.exe')"
