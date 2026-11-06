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
$Pyproject = Join-Path $Repo "backend\pyproject.toml"
$Icon = Join-Path $Here "assets\liberastra.ico"
$Launcher = Join-Path $Here "launcher\Launcher.cs"

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

# backend/pyproject.toml 是依赖和版本号的唯一来源，避免打包清单漂移。
$Version = (& $Python -c "import sys,tomllib;print(tomllib.load(open(sys.argv[1],'rb'))['project']['version'])" $Pyproject).Trim()
if ($LASTEXITCODE -ne 0 -or -not $Version) { throw "读取 backend/pyproject.toml 版本失败" }
$DepsFile = Join-Path $Stage "requirements.build.txt"
& $Python -c "import sys,tomllib;data=tomllib.load(open(sys.argv[1],'rb'));open(sys.argv[2],'w',encoding='utf-8').write('\n'.join(data['project']['dependencies'])+'\n')" $Pyproject $DepsFile
if ($LASTEXITCODE -ne 0) { throw "生成依赖清单失败" }
& $Python -m pip install -r $DepsFile
if ($LASTEXITCODE -ne 0) { throw "安装 Python 依赖失败" }
Remove-Item $DepsFile -ErrorAction SilentlyContinue
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

Write-Host "编译启动器"
$Csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $Csc)) { throw "未找到 csc.exe，需要 .NET Framework 4.x" }
$Version4 = if ($Version -match '^\d+\.\d+\.\d+$') { "$Version.0" } elseif ($Version -match '^\d+\.\d+\.\d+\.\d+$') { $Version } else { throw "不支持的版本号：$Version" }
$VersionInfo = Join-Path $Stage "launcher-version.cs"
@"
using System.Reflection;
[assembly: AssemblyTitle("LiberAstra")]
[assembly: AssemblyDescription("LiberAstra desktop launcher")]
[assembly: AssemblyCompany("LiberAstra")]
[assembly: AssemblyProduct("LiberAstra")]
[assembly: AssemblyCopyright("MIT License")]
[assembly: AssemblyVersion("$Version4")]
[assembly: AssemblyFileVersion("$Version4")]
"@ | Set-Content -Path $VersionInfo -Encoding utf8
& $Csc /nologo /target:winexe /platform:x64 /optimize+ /win32icon:"$Icon" /out:"$(Join-Path $Stage 'LiberAstra.exe')" /r:System.dll /r:System.Core.dll /r:System.Windows.Forms.dll /r:System.Drawing.dll "$Launcher" "$VersionInfo"
if ($LASTEXITCODE -ne 0) { throw "编译启动器失败" }
Remove-Item $VersionInfo -ErrorAction SilentlyContinue

$env:LIBERASTRA_DATA_DIR = Join-Path $env:TEMP "la-build-check"
& $Python -c "import liberastra.main; from pathlib import Path; import liberastra; root = Path(liberastra.__file__).resolve().parents[1]; assert (root / 'workflows' / 'qwen_image_21' / 'manifest.yaml').exists(), root; from liberastra.core.config import Settings; static = Settings().resolved_static_dir; assert static and (static / 'index.html').exists(), static"
if ($LASTEXITCODE -ne 0) { throw "嵌入式 Python 无法导入 liberastra.main、工作流或前端页面" }

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

Write-Host "编译安装包 $Version"
& $Iscc "/DMyAppVersion=$Version" (Join-Path $Here "LiberAstra.iss")
Write-Host "完成：$(Join-Path $Output 'LiberAstra-Setup.exe')"
