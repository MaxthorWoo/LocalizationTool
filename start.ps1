# 本地化翻译平台 - 一键启动（PowerShell）
# 用法：右键"使用 PowerShell 运行"，或 PowerShell 中执行  .\start.ps1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  本地化可视化翻译平台 - 一键启动" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ---- 1. 激活虚拟环境 ----
$Activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $Activate)) {
    Write-Host "[错误] 未找到虚拟环境 .venv，请先执行:" -ForegroundColor Red
    Write-Host "       python -m venv .venv"
    Write-Host "       .venv\Scripts\pip install -r requirements.txt"
    Read-Host "按回车退出"
    exit 1
}
. $Activate
Write-Host "[OK] 虚拟环境已激活: $env:VIRTUAL_ENV" -ForegroundColor Green

# ---- 2. 校验 Reflex ----
if (-not (Test-Path (Join-Path $Root ".venv\Scripts\reflex.exe"))) {
    Write-Host "[错误] 未检测到 reflex，请先安装依赖:" -ForegroundColor Red
    Write-Host "       .venv\Scripts\pip install -r requirements.txt"
    Read-Host "按回车退出"
    exit 1
}

# ---- 3. 检查端口占用 ----
$FrontendPort = 3100
$BackendPort = 8100
$occupied = @()
foreach ($port in @($FrontendPort, $BackendPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        $occupied += $port
    }
}
if ($occupied.Count -gt 0) {
    Write-Host "[警告] 端口被占用: $($occupied -join ', ')" -ForegroundColor Yellow
    Write-Host "       可能已有实例在运行，或与其他服务冲突。" -ForegroundColor Yellow
    Write-Host "       如需改端口，请编辑 rxconfig.py 的 frontend_port / backend_port。" -ForegroundColor Yellow
}

# ---- 4. 打开浏览器 ----
Start-Sleep -Seconds 1
Start-Process "http://localhost:3100"

Write-Host ""
Write-Host "[启动中] Reflex 正在启动，请稍候..." -ForegroundColor Cyan
Write-Host "         前端: http://localhost:3100" -ForegroundColor White
Write-Host "         后端: http://localhost:8100" -ForegroundColor White
Write-Host "         [提示] 按 Ctrl+C 停止服务。" -ForegroundColor DarkGray
Write-Host ""

# ---- 5. 启动 Reflex ----
reflex run

Write-Host ""
Write-Host "Reflex 已停止。" -ForegroundColor Cyan
