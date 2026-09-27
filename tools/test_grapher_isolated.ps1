param([string]$OutputDir = ".phase13-grapher-native-suite")

$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root ".test-venv\Scripts\python.exe"
$nodes = @(& $python -m pytest --collect-only -q -m grapher |
    Where-Object { $_ -match '^tests/.+::' })
$base = Join-Path $root $OutputDir
New-Item -ItemType Directory -Path $base -Force | Out-Null
$failed = @()
$passed = 0
for ($i = 0; $i -lt $nodes.Count; $i++) {
    $number = $i + 1
    $before = @(Get-Process Grapher -ErrorAction SilentlyContinue | ForEach-Object Id)
    $log = Join-Path $base "$number.log"
    & $python -m pytest -q $nodes[$i] --basetemp (Join-Path $base "case-$number") *> $log
    $code = $LASTEXITCODE
    $after = @(Get-Process Grapher -ErrorAction SilentlyContinue | ForEach-Object Id)
    $leftover = @($after | Where-Object { $_ -notin $before })
    Write-Output "$number/$($nodes.Count) exit=$code leftover=$($leftover.Count) $($nodes[$i])"
    if ($code -ne 0 -or $leftover.Count -gt 0) {
        $failed += $nodes[$i]
        if ($leftover.Count -gt 0) {
            Write-Output "New Grapher PID remains: $($leftover -join ', '). Stopping without touching it."
            break
        }
    } else {
        $passed++
    }
}
Write-Output "passed=$passed failed=$($failed.Count) total=$($nodes.Count)"
if ($failed.Count -gt 0) { exit 1 }
