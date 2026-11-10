# keep-unlocked for Windows, no Python needed (Windows PowerShell 5.1+). Same commands and state files as keep-unlocked.py:
#   keep-unlocked.ps1 session | on | off | status | selftest
param([string]$Cmd = '', [int]$ClaudePid = 0, [string]$Kind = 'manual', [int]$Found = 1)
$ErrorActionPreference = 'Stop'
$State = Join-Path $HOME '.claude\keep-unlocked'
$TaskPath = '\keep-unlocked\'
$Shells = 'sh', 'bash', 'zsh', 'dash', 'fish', 'ksh', 'cmd', 'powershell', 'pwsh', 'python', 'python3', 'py', 'env'

function Get-Mode {
    $m = "$env:KEEP_UNLOCKED_MODE".Trim().ToLower()
    if ($m -eq 'auto' -or $m -eq 'manual') { $m } else { 'auto' }
}

# Executable name of a name or command line: '"C:\Program Files\x\claude.exe" -c' -> 'claude'
function Get-Base([string]$s) {
    $s = $s.Trim()
    if ($s.StartsWith('"')) { $s = $s.Substring(1).Split('"')[0] } else { $s = ($s -split '\s+')[0] }
    ([IO.Path]::GetFileName($s.Replace('/', '\'))).ToLower().TrimStart('-').Split('.')[0]
}

function Get-ProcTable {
    $t = @{}
    Get-CimInstance Win32_Process | ForEach-Object { $t[[int]$_.ProcessId] = $_ }
    $t
}

# (pid, found): first ancestor that is Claude Code, else the nearest non-shell one
function Find-Claude($t, [int]$id) {
    $fallback = 0; $seen = @{}
    while ($t.ContainsKey($id) -and -not $seen.ContainsKey($id) -and $id -gt 4) {
        $seen[$id] = 1
        $p = $t[$id]; $cl = "$($p.CommandLine)"; $n = Get-Base "$($p.Name)"
        if ($n -eq 'claude' -or (Get-Base $cl) -eq 'claude' -or "$($p.ExecutablePath) $cl" -match 'claude[\\/]versions[\\/]' -or
            ($n -eq 'node' -and $cl -match 'claude')) { return $id, $true }
        if (-not $fallback -and $Shells -notcontains $n) { $fallback = $id }
        $id = [int]$p.ParentProcessId
    }
    $fallback, $false
}

# The pid still runs a keeper of this plugin (a reused pid does not count). KeepUnlocked: keepers started by the .py
function Test-Keeper($rec, $t) {
    $id = 0
    if (-not [int]::TryParse("$($rec.pid)", [ref]$id)) { return $false }  # corrupt file: not running
    $p = $t[$id]
    [bool]($p -and (Get-Base "$($p.Name)") -eq 'powershell' -and
           ("$($p.CommandLine)" -match "keep-unlocked\.ps1[`"']? keeper|KeepUnlocked"))
}

# Running keepers; files of keepers that are gone are removed
function Get-Keepers($t) {
    if (-not (Test-Path $State)) { return }
    foreach ($f in Get-ChildItem $State -Filter *.json | Sort-Object Name) {
        $rec = $null
        try { $rec = Get-Content $f.FullName -Raw | ConvertFrom-Json } catch {}
        if ($rec -and (Test-Keeper $rec $t)) { $rec } else { Remove-Item $f.FullName -ErrorAction SilentlyContinue }
    }
}

function Format-Keeper($r) {
    if ($r.mode -eq 'manual') { $u = 'until off or reboot' } else {
        $u = "while Claude pid $($r.claude_pid) runs"
        if (-not $r.claude_found) { $u += ' (Claude process not identified, nearest parent process used)' }
    }
    "keeper pid $($r.pid) ($($r.cmd), $($r.mode)) $u, since $($r.started)"
}

# Each keeper is a scheduled task in \keep-unlocked\: outside Claude's process tree, in the user's session (needed for
# the F15 press), and windowless through conhost --headless (powershell -WindowStyle Hidden still flashes a window).
function Start-Keeper([string]$kind, [int]$claudePid, [bool]$found, [bool]$wait = $true) {
    $name = "$kind-$claudePid"
    # path in single quotes inside -Command: safe for spaces, apostrophes, $ and backticks
    $arg = "--headless powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass " +
           "-Command `"& '$($PSCommandPath.Replace("'", "''"))' keeper $claudePid $kind $([int]$found)`""
    $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\conhost.exe" -Argument $arg
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd `
                -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
    # a second try: another session's cleanup may remove the task between register and start
    foreach ($try in 1, 2) {
        $null = Register-ScheduledTask -TaskPath $TaskPath -TaskName $name -Action $action -Principal $principal -Settings $settings -Force
        try { Start-ScheduledTask -TaskPath $TaskPath -TaskName $name; break } catch { if ($try -eq 2) { throw } }
    }
    if (-not $wait) { return }
    $sw = [Diagnostics.Stopwatch]::StartNew()  # the keeper writes its own state file once it runs
    while ($sw.ElapsedMilliseconds -lt 10000 -and
           -not (Get-ChildItem $State -Filter *.json -ErrorAction SilentlyContinue |
                 Where-Object { (Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue) -match "`"mode`":`"$kind`"" })) { Start-Sleep -Milliseconds 200 }
    $r = @(Get-Keepers (Get-ProcTable) | Where-Object { $_.mode -eq $kind -and [int]$_.claude_pid -eq $claudePid })
    if ($r.Count) { 'started ' + (Format-Keeper $r[0]) } else { "started task $TaskPath$name, but its keeper did not report within 10 s" }
}

function Remove-KeeperTask([string]$name) {
    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
}

# Runs inside the task: record itself, keep awake, clean up when Claude ends
function Invoke-Keeper([int]$claudePid, [string]$kind, [bool]$found) {
    $rec = [ordered]@{ pid = $PID; mode = $kind; claude_pid = $(if ($claudePid) { $claudePid } else { $null })
                       claude_found = $found; cmd = 'powershell'; started = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') }
    New-Item -ItemType Directory -Force $State | Out-Null
    $file = Join-Path $State "$PID.json"
    [IO.File]::WriteAllText($file, ($rec | ConvertTo-Json -Compress))
    try { Invoke-KeeperLoop $claudePid } finally {
        Remove-Item $file -ErrorAction SilentlyContinue
        Remove-KeeperTask "$kind-$claudePid"
    }
}

# ES_CONTINUOUS|ES_SYSTEM_REQUIRED|ES_DISPLAY_REQUIRED and a harmless F15 press every 30 s,
# until the Claude process ends (auto) or forever (manual, ClaudePid 0)
function Invoke-KeeperLoop([int]$claudePid) {
    $k = Add-Type -Name P -Namespace KeepUnlocked -PassThru -MemberDefinition (
        '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f); ' +
        '[DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, System.UIntPtr e); ' +
        '[DllImport("kernel32.dll")] public static extern System.IntPtr OpenProcess(uint a, bool i, int pid); ' +
        '[DllImport("kernel32.dll")] public static extern uint WaitForSingleObject(System.IntPtr h, uint ms);')
    $h = [IntPtr]::Zero
    if ($claudePid) {
        # SYNCHRONIZE only, so it also works for an elevated Claude; the open handle keeps the pid from being reused
        $h = $k::OpenProcess(0x100000, $false, $claudePid)
        if ($h -eq [IntPtr]::Zero) { return }
    }
    while ($true) {
        [void]$k::SetThreadExecutionState([uint32]2147483651)
        $k::keybd_event(0x7E, 0, 0, [UIntPtr]::Zero); $k::keybd_event(0x7E, 0, 2, [UIntPtr]::Zero)
        if ($h -eq [IntPtr]::Zero) { Start-Sleep 30 }
        elseif ($k::WaitForSingleObject($h, 30000) -ne 0x102) { break }  # anything but WAIT_TIMEOUT: Claude ended
    }
}

function Invoke-Session {
    if ((Get-Mode) -ne 'auto') { return }
    $t = Get-ProcTable
    $c, $found = Find-Claude $t ([int]$t[$PID].ParentProcessId)
    if (-not $c) { [Console]::Error.WriteLine('keep-unlocked: Claude process not found, nothing started.'); return }
    # tasks that no longer run (logoff, reboot, crash) are left over; a running auto-<pid> means this Claude has a keeper
    $tasks = @(Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue)
    $tasks | Where-Object { $_.State -ne 'Running' } | ForEach-Object { Remove-KeeperTask $_.TaskName }
    if ($tasks | Where-Object { $_.State -eq 'Running' -and $_.TaskName -eq "auto-$c" }) { return }
    Start-Keeper 'auto' $c $found $false
}

function Invoke-SelfTest {
    function Assert($ok, $what) { if (-not $ok) { throw "selftest failed: $what" } }
    function P($id, $ppid, $name, $cl, $exe = '') {
        [pscustomobject]@{ ProcessId = $id; ParentProcessId = $ppid; Name = $name; CommandLine = $cl; ExecutablePath = $exe } }
    Assert ((Get-Base '"C:\Program Files\x\claude.exe" -c') -eq 'claude') 'Get-Base quoted path'
    Assert ((Get-Base '-bash') -eq 'bash') 'Get-Base login shell'
    Assert ((Get-Base 'C:/a/node.exe x') -eq 'node') 'Get-Base forward slashes'
    $t = @{}
    foreach ($p in (P 10 1 'explorer.exe' 'explorer'), (P 20 10 'claude.exe' 'claude -p x'), (P 30 20 'bash.exe' 'bash -c x'),
                   (P 40 30 'powershell.exe' 'powershell -File k.ps1 session'),
                   (P 50 10 'Code.exe' 'code'), (P 60 50 'bash.exe' 'bash'), (P 70 60 'pwsh.exe' 'pwsh'),
                   (P 80 999 'bash.exe' 'bash')) { $t[$p.ProcessId] = $p }
    $c, $f = Find-Claude $t 40; Assert ($c -eq 20 -and $f) 'Find-Claude through shells'
    $c, $f = Find-Claude $t 70; Assert ($c -eq 50 -and -not $f) 'Find-Claude fallback to nearest non-shell'
    $c, $f = Find-Claude $t 80; Assert ($c -eq 0 -and -not $f) 'Find-Claude broken chain'
    # command line as conhost passes it on: quotes stripped
    $k = @{ 1 = (P 1 0 'powershell.exe' "powershell.exe -NoLogo -Command & 'C:\x y''z\keep-unlocked.ps1' keeper 5 auto 1")
            2 = (P 2 0 'bash.exe' "bash -c powershell -File 'C:\x y''z\keep-unlocked.ps1' keeper 5 auto 1")
            3 = (P 3 0 'powershell.exe' 'powershell -File keep-unlocked.ps1 status') }
    Assert (Test-Keeper @{ pid = 1 } $k) 'Test-Keeper keeper with space and apostrophe'
    Assert (-not (Test-Keeper @{ pid = 2 } $k)) 'Test-Keeper ignores shells'
    Assert (-not (Test-Keeper @{ pid = 3 } $k)) 'Test-Keeper ignores other commands'
    Assert (-not (Test-Keeper @{ pid = 'x' } $k)) 'Test-Keeper corrupt pid'
    'ok'
}

switch ($Cmd) {
    'keeper' { Invoke-Keeper $ClaudePid $Kind ([bool]$Found) }
    'session' {
        # the hook must never block or fail the session
        try { Invoke-Session } catch { [Console]::Error.WriteLine("keep-unlocked: $_") }
        exit 0
    }
    'on' {
        $m = @(Get-Keepers (Get-ProcTable) | Where-Object { $_.mode -eq 'manual' })
        if ($m.Count) { 'already running: ' + (Format-Keeper $m[0]) } else { Start-Keeper 'manual' 0 $true }
    }
    'off' {
        $f = @(Get-Keepers (Get-ProcTable))
        foreach ($r in $f) {
            Stop-Process -Id $r.pid -Force -ErrorAction SilentlyContinue
            Remove-Item (Join-Path $State "$($r.pid).json") -ErrorAction SilentlyContinue
            'stopped ' + (Format-Keeper $r)
        }
        Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-ScheduledTask -InputObject $_ -ErrorAction SilentlyContinue; Remove-KeeperTask $_.TaskName }
        if (-not $f.Count) { 'no keeper running' }
    }
    'status' {
        "mode: $(Get-Mode)"
        $f = @(Get-Keepers (Get-ProcTable))
        $f | ForEach-Object { Format-Keeper $_ }
        if (-not $f.Count) { 'no keeper running' }
    }
    'selftest' { Invoke-SelfTest }
    default { 'usage: keep-unlocked.ps1 session | on | off | status | selftest'; exit 2 }
}
