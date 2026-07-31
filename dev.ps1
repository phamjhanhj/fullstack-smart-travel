$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$backendDirectory = Join-Path $projectRoot 'backend'
$frontendDirectory = Join-Path $projectRoot 'frontend'
$venvPython = Join-Path $backendDirectory 'venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Không tìm thấy Python virtual environment: $venvPython"
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendDirectory 'node_modules'))) {
    throw "Frontend chưa cài dependencies. Hãy chạy: cd frontend; npm install"
}

$occupiedPorts = @(4200, 8000) | Where-Object {
    Get-NetTCPConnection -State Listen -LocalPort $_ -ErrorAction SilentlyContinue
}
if ($occupiedPorts.Count -gt 0) {
    throw "Không thể khởi động trùng dịch vụ. Cổng đang được sử dụng: $($occupiedPorts -join ', '). Hãy dừng phiên cũ trước."
}
Write-Host 'Đang khởi động Smart Travel Planner...' -ForegroundColor Cyan
Write-Host 'Backend : http://localhost:8000' -ForegroundColor Green
Write-Host 'Swagger : http://localhost:8000/docs' -ForegroundColor Green
Write-Host 'Frontend: http://localhost:4200' -ForegroundColor Green
Write-Host 'Nhấn Ctrl+C để dừng cả frontend và backend.' -ForegroundColor Yellow

$backendProcess = $null
$frontendProcess = $null

try {
    $backendProcess = Start-Process `
        -FilePath $venvPython `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000' `
        -WorkingDirectory $backendDirectory `
        -NoNewWindow `
        -PassThru

    $frontendProcess = Start-Process `
        -FilePath 'npm.cmd' `
        -ArgumentList 'start' `
        -WorkingDirectory $frontendDirectory `
        -NoNewWindow `
        -PassThru

    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
        Start-Sleep -Milliseconds 500
        $backendProcess.Refresh()
        $frontendProcess.Refresh()
    }

    if ($backendProcess.HasExited) {
        throw "Backend đã dừng với exit code $($backendProcess.ExitCode)."
    }

    if ($frontendProcess.HasExited) {
        throw "Frontend đã dừng với exit code $($frontendProcess.ExitCode)."
    }
}
finally {
    foreach ($process in @($frontendProcess, $backendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Host 'Đã dừng Smart Travel Planner.' -ForegroundColor Yellow
}
