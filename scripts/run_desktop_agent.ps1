<#
.SYNOPSIS
    ContextIQ Desktop Behavioral Activity Collector PowerShell Runner
.DESCRIPTION
    Launches, manages, and checks status of the ContextIQ Desktop Agent.
.EXAMPLE
    .\scripts\run_desktop_agent.ps1 status
    .\scripts\run_desktop_agent.ps1 run --grant-consent
    .\scripts\run_desktop_agent.ps1 start
    .\scripts\run_desktop_agent.ps1 stop
#>

[CmdletBinding()]
param (
    [Parameter(Position = 0)]
    [ValidateSet("run", "start", "stop", "status", "autostart")]
    [string]$Command = "status",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$RootDir = Split-Path -Parent $PSScriptRoot
$AgentDir = Join-Path $RootDir "desktop-agent"
$VenvPython = Join-Path $RootDir "backend\.venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
} else {
    $PythonExe = "python"
}

Write-Host "ContextIQ Desktop Agent CLI" -ForegroundColor Cyan
Write-Host "Python Path: $PythonExe" -ForegroundColor Gray
Write-Host "Agent Path : $AgentDir" -ForegroundColor Gray
Write-Host ""

$MainScript = Join-Path $AgentDir "app\main.py"
& $PythonExe $MainScript $Command @RemainingArgs
