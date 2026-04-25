param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("start", "refresh", "refresh-if-active", "event-start", "event-stop", "stop", "status")]
    [string]$Action,

    [string]$GuardUrl = $env:SRC_GUARD_URL,
    [string]$Token = $env:SRC_GUARD_TOKEN,
    [string]$Client = $(if ($env:SRC_GUARD_CLIENT) { $env:SRC_GUARD_CLIENT } elseif ($env:COMPUTERNAME) { $env:COMPUTERNAME } else { [System.Net.Dns]::GetHostName() }),
    [int]$Duration = $(if ($env:SRC_GUARD_DURATION) { [int]$env:SRC_GUARD_DURATION } else { 360 }),
    [string]$StateDir = $(if ($env:SRC_GUARD_STATE_DIR) { $env:SRC_GUARD_STATE_DIR } else { Join-Path $env:LOCALAPPDATA "SRCGuardClient" }),
    [string]$ConfigFile = $(if ($env:SRC_GUARD_CONFIG) { $env:SRC_GUARD_CONFIG } else { Join-Path (Join-Path $env:LOCALAPPDATA "SRCGuardClient") "config.json" }),
    [string[]]$GameProcessName = @(),
    [string[]]$GameProcessPath = @(),
    [string]$EventProcessPath = ""
)

$ErrorActionPreference = "Stop"

if (Test-Path $ConfigFile) {
    $Config = Get-Content -Raw -Path $ConfigFile | ConvertFrom-Json
    if (-not $PSBoundParameters.ContainsKey("GuardUrl") -and $Config.GuardUrl) {
        $GuardUrl = $Config.GuardUrl
    }
    if (-not $PSBoundParameters.ContainsKey("Token") -and $Config.Token) {
        $Token = $Config.Token
    }
    if (-not $PSBoundParameters.ContainsKey("Client") -and $Config.Client) {
        $Client = $Config.Client
    }
    if (-not $PSBoundParameters.ContainsKey("Duration") -and $Config.Duration) {
        $Duration = [int]$Config.Duration
    }
    if (-not $PSBoundParameters.ContainsKey("StateDir") -and $Config.StateDir) {
        $StateDir = $Config.StateDir
    }
    if (-not $PSBoundParameters.ContainsKey("GameProcessName") -and $Config.GameProcessNames) {
        $GameProcessName = @($Config.GameProcessNames)
    }
    if (-not $PSBoundParameters.ContainsKey("GameProcessPath") -and $Config.GameProcessPaths) {
        $GameProcessPath = @($Config.GameProcessPaths)
    }
}

if (-not $PSBoundParameters.ContainsKey("GameProcessName") -and $env:SRC_GUARD_GAME_PROCESS_NAMES) {
    $GameProcessName = $env:SRC_GUARD_GAME_PROCESS_NAMES -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}
if (-not $PSBoundParameters.ContainsKey("GameProcessPath") -and $env:SRC_GUARD_GAME_PROCESS_PATHS) {
    $GameProcessPath = $env:SRC_GUARD_GAME_PROCESS_PATHS -split ";" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}

function Require-Config {
    if ([string]::IsNullOrWhiteSpace($GuardUrl)) {
        throw "GuardUrl is required. Pass -GuardUrl or set SRC_GUARD_URL."
    }
    if ([string]::IsNullOrWhiteSpace($Token)) {
        throw "Token is required. Pass -Token or set SRC_GUARD_TOKEN."
    }
    if ($Client -notmatch '^[A-Za-z0-9_.:-]+$') {
        throw "Client may only contain A-Z, a-z, 0-9, dot, underscore, colon, or dash."
    }
}

function Require-ProcessConfig {
    if (($GameProcessName.Count -eq 0) -and ($GameProcessPath.Count -eq 0)) {
        throw "GameProcessName or GameProcessPath is required for process event actions."
    }
}

function Ensure-StateDir {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
}

function Get-GenerationPath {
    Join-Path $StateDir "generation"
}

function Get-ModePath {
    Join-Path $StateDir "mode"
}

function New-Generation {
    "$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())-$PID"
}

function Write-ClientState([string]$Generation, [string]$Mode) {
    Ensure-StateDir
    Set-Content -Path (Get-GenerationPath) -Value $Generation -NoNewline
    Set-Content -Path (Get-ModePath) -Value $Mode -NoNewline
}

function Clear-ClientState {
    Remove-Item -Force -ErrorAction SilentlyContinue -Path (Get-GenerationPath), (Get-ModePath)
}

function Read-StateFile([string]$Path) {
    if (Test-Path $Path) {
        return (Get-Content -Raw -Path $Path).Trim()
    }
    return ""
}

function Read-Generation {
    Read-StateFile (Get-GenerationPath)
}

function Read-Mode {
    Read-StateFile (Get-ModePath)
}

function Normalize-ProcessName([string]$Value) {
    $name = $Value.Trim()
    if ($name -and -not $name.EndsWith(".exe", [System.StringComparison]::OrdinalIgnoreCase)) {
        $name = "$name.exe"
    }
    return $name.ToLowerInvariant()
}

function Normalize-ProcessPath([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }
    return $Value.Trim().ToLowerInvariant()
}

function Invoke-GuardPost([string]$Endpoint, [hashtable]$Body) {
    Require-Config
    $headers = @{ Authorization = "Bearer $Token" }
    Invoke-RestMethod `
        -Uri "$GuardUrl$Endpoint" `
        -Method Post `
        -Headers $headers `
        -ContentType "application/json" `
        -Body ($Body | ConvertTo-Json)
}

function Invoke-GuardGet([string]$Endpoint) {
    Require-Config
    $headers = @{ Authorization = "Bearer $Token" }
    Invoke-RestMethod -Uri "$GuardUrl$Endpoint" -Headers $headers
}

function Start-Playing {
    Write-ClientState (New-Generation) "playing"
    Invoke-GuardPost "/webhook/play/start" @{ client = $Client; duration = $Duration }
}

function Refresh-Playing {
    Invoke-GuardPost "/webhook/play/start" @{ client = $Client; duration = $Duration }
}

function Refresh-IfActive {
    if ((Read-Mode) -eq "playing") {
        Refresh-Playing
    } else {
        Write-Output "SRC Guard client is not in playing mode; renewal skipped."
    }
}

function Stop-Now {
    Invoke-GuardPost "/webhook/play/stop" @{ client = $Client }
    Clear-ClientState
}

function Test-ConfiguredProcessPath([string]$ProcessPath) {
    Require-ProcessConfig
    $normalizedPath = Normalize-ProcessPath $ProcessPath
    if (-not $normalizedPath) {
        return $false
    }

    $nameSet = @{}
    foreach ($name in $GameProcessName) {
        $normalized = Normalize-ProcessName $name
        if ($normalized) {
            $nameSet[$normalized] = $true
        }
    }

    $pathSet = @{}
    foreach ($path in $GameProcessPath) {
        $normalized = Normalize-ProcessPath $path
        if ($normalized) {
            $pathSet[$normalized] = $true
        }
    }

    if ($pathSet.ContainsKey($normalizedPath)) {
        return $true
    }

    $leafName = Normalize-ProcessName ([System.IO.Path]::GetFileName($ProcessPath))
    return $nameSet.ContainsKey($leafName)
}

function Test-GameProcessRunning {
    Require-ProcessConfig
    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    foreach ($process in $processes) {
        if ($process.ExecutablePath -and (Test-ConfiguredProcessPath $process.ExecutablePath)) {
            return $true
        }
        if ($process.Name -and (Test-ConfiguredProcessPath $process.Name)) {
            return $true
        }
    }
    return $false
}

function Handle-ProcessStartEvent {
    Require-Config
    if ((Test-ConfiguredProcessPath $EventProcessPath) -and (Read-Mode) -ne "playing") {
        Start-Playing
    }
}

function Handle-ProcessStopEvent {
    Require-Config
    if ((Test-ConfiguredProcessPath $EventProcessPath) -and (Read-Mode) -eq "playing") {
        if (-not (Test-GameProcessRunning)) {
            Stop-Now
        }
    }
}

switch ($Action) {
    "start" { Start-Playing }
    "refresh" { Refresh-Playing }
    "refresh-if-active" { Refresh-IfActive }
    "event-start" { Handle-ProcessStartEvent }
    "event-stop" { Handle-ProcessStopEvent }
    "stop" { Stop-Now }
    "status" { Invoke-GuardGet "/status" }
}
