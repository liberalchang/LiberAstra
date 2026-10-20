# 在本机安装 Liber Speech 插件（需要已安装并启动的 Docker，以及 NVIDIA 显卡）。
# 装在 LiberAstra 同一台电脑，或装到另一台 Windows 主机，步骤相同。
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "未找到 docker。请先安装 Docker Desktop：https://docs.docker.com/desktop/setup/install/windows-install/"
}

docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "语音插件启动失败" }

$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -ExpandProperty IPAddress
Write-Host ""
Write-Host "Liber Speech 已在本机监听 5555。"
Write-Host "本机 LiberAstra 的 Base URL：http://127.0.0.1:5555"
foreach ($ip in $ips) {
    Write-Host "其它主机上的 LiberAstra 填：http://${ip}:5555"
}
