param(
    [Parameter(Mandatory = $true)]
    [string]$GuardUrl,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [string]$Client = $(if ($env:COMPUTERNAME) { $env:COMPUTERNAME } else { [System.Net.Dns]::GetHostName() }),
    [int]$Duration = 360,
    [int]$RefreshIntervalMinutes = 180,
    [string[]]$GameProcessName = @(),
    [string[]]$GameProcessPath = @(),
    [string]$TaskPath = "\SRC Guard\",
    [string]$ScriptPath = $(Join-Path $PSScriptRoot "SRCGuardClient.ps1"),
    [string]$ConfigFile = $(Join-Path (Join-Path $env:LOCALAPPDATA "SRCGuardClient") "config.json"),
    [string]$XmlOutputDir = $(Join-Path $PSScriptRoot "generated"),
    [switch]$EnableProcessAudit,
    [switch]$GenerateOnly,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Escape-Xml([string]$Value) {
    return [System.Security.SecurityElement]::Escape($Value)
}

function Ensure-TaskPath([string]$Value) {
    if (-not $Value.StartsWith("\")) {
        $Value = "\$Value"
    }
    if (-not $Value.EndsWith("\")) {
        $Value = "$Value\"
    }
    return $Value
}

function New-XPathString([string]$Value) {
    if ($Value.Contains("'") -and $Value.Contains('"')) {
        throw "Process path contains both single and double quotes, which is not supported in Task Scheduler XPath."
    }
    if ($Value.Contains("'")) {
        return '"' + $Value + '"'
    }
    return "'" + $Value + "'"
}

function New-ProcessPathFilter([string]$DataName) {
    if ($GameProcessPath.Count -eq 0) {
        return ""
    }

    $conditions = @()
    foreach ($path in $GameProcessPath) {
        if (-not [string]::IsNullOrWhiteSpace($path)) {
            $conditions += "Data[@Name='$DataName']=" + (New-XPathString $path.Trim())
        }
    }

    if ($conditions.Count -eq 0) {
        return ""
    }

    return " and *[EventData[" + ($conditions -join " or ") + "]]"
}

function New-ProcessEventSubscription([int]$EventId, [string]$DataName) {
    $pathFilter = New-ProcessPathFilter $DataName
    return @"
<QueryList>
  <Query Id="0" Path="Security">
    <Select Path="Security">*[System[Provider[@Name='Microsoft-Windows-Security-Auditing'] and EventID=$EventId]]$pathFilter</Select>
  </Query>
</QueryList>
"@
}

function New-ActionXml([string]$Action, [bool]$IncludeEventProcessPath) {
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$ScriptPath`"",
        "-Action", $Action,
        "-ConfigFile", "`"$ConfigFile`""
    )
    if ($IncludeEventProcessPath) {
        $arguments += @("-EventProcessPath", "`"`$(ProcessPath)`"")
    }
    $argumentText = $arguments -join " "

    return @"
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>$(Escape-Xml $argumentText)</Arguments>
    </Exec>
  </Actions>
"@
}

function New-EventTriggerXml([int]$EventId, [string]$DataName) {
    $subscription = New-ProcessEventSubscription $EventId $DataName
    return @"
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription><![CDATA[$subscription]]></Subscription>
      <ValueQueries>
        <Value name="ProcessPath">Event/EventData/Data[@Name='$DataName']</Value>
      </ValueQueries>
    </EventTrigger>
  </Triggers>
"@
}

function New-TriggersXml([string]$TriggerType) {
    if ($TriggerType -eq "None") {
        return "  <Triggers />"
    }

    if ($TriggerType -eq "ProcessStart") {
        return New-EventTriggerXml 4688 "NewProcessName"
    }

    if ($TriggerType -eq "ProcessStop") {
        return New-EventTriggerXml 4689 "ProcessName"
    }

    $startBoundary = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
    return @"
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
      <Repetition>
        <Interval>PT${RefreshIntervalMinutes}M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
    </CalendarTrigger>
  </Triggers>
"@
}

function New-TaskXml(
    [string]$Name,
    [string]$Description,
    [string]$Action,
    [string]$TriggerType,
    [string]$MultipleInstancesPolicy,
    [string]$ExecutionTimeLimit,
    [bool]$IncludeEventProcessPath
) {
    $author = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $triggers = New-TriggersXml $TriggerType
    $actions = New-ActionXml $Action $IncludeEventProcessPath

    return @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>$(Escape-Xml $author)</Author>
    <Description>$(Escape-Xml $Description)</Description>
  </RegistrationInfo>
$triggers
  <Principals>
    <Principal id="Author">
      <UserId>$(Escape-Xml $sid)</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>$MultipleInstancesPolicy</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>$ExecutionTimeLimit</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
$actions
</Task>
"@
}

function Write-TaskXml([hashtable]$Task) {
    $xml = New-TaskXml `
        -Name $Task.Name `
        -Description $Task.Description `
        -Action $Task.Action `
        -TriggerType $Task.TriggerType `
        -MultipleInstancesPolicy $Task.MultipleInstancesPolicy `
        -ExecutionTimeLimit $Task.ExecutionTimeLimit `
        -IncludeEventProcessPath $Task.IncludeEventProcessPath
    $path = Join-Path $XmlOutputDir "$($Task.Name).xml"
    Set-Content -Path $path -Value $xml -Encoding Unicode
    return $path
}

function Write-RunCommand([string]$Name, [string]$TaskName) {
    $taskFullName = "$TaskPath$TaskName"
    $path = Join-Path $XmlOutputDir "$Name.cmd"
    Set-Content -Path $path -Value "@echo off`r`nschtasks /run /tn `"$taskFullName`"`r`n" -Encoding ASCII
}

$TaskPath = Ensure-TaskPath $TaskPath
$ScriptPath = (Resolve-Path $ScriptPath).Path

if (($GameProcessName.Count -eq 0) -and ($GameProcessPath.Count -eq 0)) {
    throw "Specify -GameProcessPath for an exact Task Scheduler event trigger, or -GameProcessName for script-side filtering."
}

if (($GameProcessPath.Count -eq 0) -and ($GameProcessName.Count -gt 0)) {
    Write-Warning "Only GameProcessName was provided. Task Scheduler will wake on process events and SRCGuardClient.ps1 will filter by exe name. Use -GameProcessPath for exact event filtering."
}

if ($EnableProcessAudit) {
    auditpol /set /subcategory:"{0CCE922B-69AE-11D9-BED3-505054503030}" /success:enable | Out-Null
    auditpol /set /subcategory:"{0CCE922C-69AE-11D9-BED3-505054503030}" /success:enable | Out-Null
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ConfigFile) | Out-Null
New-Item -ItemType Directory -Force -Path $XmlOutputDir | Out-Null

$config = [ordered]@{
    GuardUrl = $GuardUrl.TrimEnd("/")
    Token = $Token
    Client = $Client
    Duration = $Duration
    GameProcessNames = $GameProcessName
    GameProcessPaths = $GameProcessPath
    StateDir = Join-Path $env:LOCALAPPDATA "SRCGuardClient"
}
$config | ConvertTo-Json | Set-Content -Path $ConfigFile -Encoding UTF8

$tasks = @(
    @{
        Name = "SRC Guard Game Start"
        Action = "event-start"
        TriggerType = "ProcessStart"
        MultipleInstancesPolicy = "IgnoreNew"
        ExecutionTimeLimit = "PT10M"
        IncludeEventProcessPath = $true
        Description = "Tell SRC Guard when the configured game process starts."
    },
    @{
        Name = "SRC Guard Game Stop"
        Action = "event-stop"
        TriggerType = "ProcessStop"
        MultipleInstancesPolicy = "IgnoreNew"
        ExecutionTimeLimit = "PT10M"
        IncludeEventProcessPath = $true
        Description = "Tell SRC Guard when the configured game process exits."
    },
    @{
        Name = "SRC Guard Start"
        Action = "start"
        TriggerType = "None"
        MultipleInstancesPolicy = "Parallel"
        ExecutionTimeLimit = "PT10M"
        IncludeEventProcessPath = $false
        Description = "Tell SRC Guard that this Windows client started playing."
    },
    @{
        Name = "SRC Guard Refresh"
        Action = "refresh-if-active"
        TriggerType = "Refresh"
        MultipleInstancesPolicy = "IgnoreNew"
        ExecutionTimeLimit = "PT10M"
        IncludeEventProcessPath = $false
        Description = "Renew SRC Guard while this Windows client is playing."
    },
    @{
        Name = "SRC Guard Stop"
        Action = "stop"
        TriggerType = "None"
        MultipleInstancesPolicy = "Parallel"
        ExecutionTimeLimit = "PT10M"
        IncludeEventProcessPath = $false
        Description = "Tell SRC Guard that this Windows client stopped playing."
    }
)

foreach ($task in $tasks) {
    $xmlPath = Write-TaskXml $task
    Write-RunCommand $task.Name $task.Name

    if (-not $GenerateOnly) {
        $xml = Get-Content -Raw -Path $xmlPath
        Register-ScheduledTask `
            -TaskName $task.Name `
            -TaskPath $TaskPath `
            -Xml $xml `
            -Force:$Force | Out-Null
    }
}

Write-Output "Config written to: $ConfigFile"
Write-Output "Task XML files written to: $XmlOutputDir"
if ($GenerateOnly) {
    Write-Output "GenerateOnly was set; import the XML files from Task Scheduler when ready."
} else {
    Write-Output "Scheduled tasks registered under: $TaskPath"
}
