# 打 Liber Speech 插件安装包。
# Windows：packaging/speech/output/LiberSpeech-Setup.exe
# Linux 显卡主机：packaging/speech/output/LiberSpeech-plugin.zip（解压后执行 install.sh）
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$Here = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $Here "..\..")).Path
$Stage = Join-Path $Here "stage"
$Output = Join-Path $Here "output"
$Speech = Join-Path $Repo "services\speech"

if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage, $Output | Out-Null

robocopy $Speech $Stage /E /NFL /NDL /NJH /NJS /XD __pycache__ | Out-Null
if ($LASTEXITCODE -ge 8) { throw "拷贝语音插件失败：robocopy $LASTEXITCODE" }
Copy-Item (Join-Path $Here "install.ps1") (Join-Path $Stage "install.ps1")
Copy-Item (Join-Path $Here "install.sh") (Join-Path $Stage "install.sh")

$Zip = Join-Path $Output "LiberSpeech-plugin.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip
Write-Host "Linux / 通用插件包：$Zip"

$Iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    Write-Host "未找到 Inno Setup。已生成 zip。安装 Inno Setup 6 后重跑可得到 LiberSpeech-Setup.exe"
    exit 0
}

& $Iscc (Join-Path $Here "LiberSpeech.iss")
Write-Host "完成：$(Join-Path $Output 'LiberSpeech-Setup.exe')"
