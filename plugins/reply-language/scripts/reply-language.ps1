# reply-language for Windows, no Python needed (Windows PowerShell 5.1+). Same behaviour as reply-language.py:
#   reply-language.ps1 prompt | stop    hook JSON on stdin
#   reply-language.ps1 selftest         the cases of tests/test_reply_language.py, prints ok
# Python's Unicode classes are spelled out: \w = [\p{L}\p{N}_], [^\W\d_] = [\p{L}\p{Nl}\p{No}], \s = [\s\x1c-\x1f].
# Strings are compared case-sensitively (-ceq, ordinal dictionaries) like in Python.
param([string]$Cmd = '')
$ErrorActionPreference = 'Stop'
# Windows PowerShell reads this file as UTF-8 only thanks to its BOM; without it every č/š/ž below is wrong
if ('č'.Length -ne 1) { [Console]::Error.WriteLine('reply-language.ps1 lost its UTF-8 BOM; save it as UTF-8 with BOM.'); exit 1 }
Add-Type -AssemblyName System.Web.Extensions
$Json = New-Object Web.Script.Serialization.JavaScriptSerializer
$Json.MaxJsonLength = [int]::MaxValue
$Json.RecursionLimit = 100000

$Codes = 'sl', 'en', 'cs', 'sk', 'hr', 'de'  # order of the .py dicts: ties go to the first
$Names = [Collections.Generic.Dictionary[string, string]]::new()
foreach ($kv in ('sl', 'Slovenian'), ('en', 'English'), ('cs', 'Czech'), ('sk', 'Slovak'), ('hr', 'Croatian'), ('de', 'German')) {
    $Names[$kv[0]] = $kv[1] }
# always allowed; besides them only the language of the user's prompt
$Allowed = @(foreach ($k in "$env:REPLY_LANGUAGE_ALLOWED".Replace(' ', '').Split(',')) { if ($Codes -ccontains $k) { $k } })
if (-not $Allowed.Count) { $Allowed = @('en') }
$Words = @{
    sl = 'je da se na ne ki za pa kaj ali bi sem mi kot tudi še že ker lahko naj kako samo bo tega tem ' +
         'ta te ti zdaj sedaj potem nato ampak vendar ko če kje zakaj moram moraš imam dela deluje treba prav dobro ' +
         'tu tukaj kar nekaj tole tisto vse dej daj sam pol rabim rabiš mora morajo dodaj naredi objavi poglej preveri ' +
         'nadaljuj popravi zakaj kje kateri katera mapo mapa datoteko verzijo novo ni lepo poravnano primerjaj ' +
         'sem si smo ste ga jo jih mu jim nekje desno levo zgoraj spodaj pa naredil dodal spremeni pogledam'
    en = 'the and is to of in that it for you this with be are not on have what how can was will would ' +
         'should there their which when then also just only but from about into does do'
    cs = 'jsem které který není jak co ale pro když také jako bude mít tak teď protože jestli tady'
    sk = 'sa som si ako čo ktorý ktorá nie alebo pre môže tiež keď teraz pretože len už ešte'
    hr = 'što će nije treba kad mogu ovo ovaj biti jer sada ovdje zašto trebam može'
    de = 'der die das und ist nicht ich ein eine mit auf für sie wir auch wenn dann aber noch'
}
$Lookup = [Collections.Generic.Dictionary[string, object]]::new()  # word -> languages that list it
foreach ($k in $Codes) {
    foreach ($w in $Words[$k] -split ' ') {
        if (-not $Lookup.ContainsKey($w)) { $Lookup[$w] = [Collections.Generic.List[string]]::new() }
        if (-not $Lookup[$w].Contains($k)) { $Lookup[$w].Add($k) }
    }
}
$SlChars = '[čšžČŠŽ]'  # also Czech/Croatian, so only when their letters are absent
$Chars = [ordered]@{ cs = '[ěřůĚŘŮ]'; sk = '[ľĺŕôĽĹŔÔ]'; hr = '[ćđĆĐ]'; de = '[öüßÖÜ]' }
$Shared = '[ťďňýáíéúŤĎŇÝÁÍÉÚ]'  # Czech and Slovak: Slovenian has none of them

function Strip-Code([string]$t) {
    $t = [regex]::Replace($t, '(?s)```.*?```', ' ')
    $t = [regex]::Replace($t, '`[^`\n]*`', ' ')
    # URLs and paths: a word with / or \ inside; the lookbehind anchors it to the word start, else time is quadratic
    [regex]::Replace($t, '(?<![^\s\x1c-\x1f])[^\s\x1c-\x1f]+[/\\][^\s\x1c-\x1f]+', ' ')
}

function Get-Scores([string]$text) {
    $stripped = Strip-Code $text
    $s = [Collections.Generic.Dictionary[string, int]]::new()
    foreach ($k in $Codes) { $s[$k] = 0 }
    foreach ($m in [regex]::Matches($stripped.ToLowerInvariant(), '[\p{L}\p{Nl}\p{No}]+')) {
        $l = $null
        if ($Lookup.TryGetValue($m.Value, [ref]$l)) { foreach ($k in $l) { $s[$k] += 1 } }
    }
    $any = $false
    foreach ($k in $Chars.Keys) {
        $n = [regex]::Matches($text, $Chars[$k]).Count
        $s[$k] += 3 * $n
        if ($n) { $any = $true }
    }
    if (-not $any) { $s['sl'] += [Math]::Min([regex]::Matches($stripped, $SlChars).Count, 3) }
    $s
}

# The user's own text without pasted output, notices and command output (<tag>...</tag>)
function Get-OwnWords([string]$t) {
    $t = [regex]::Replace($t, '(?s)<([A-Za-z][\p{L}\p{N}_-]*)[^>]*>.*?</\1>', ' ')
    [regex]::Replace($t, '<[^>]+>', ' ')
}

# Language of the user's text, or $null (too few words: keep the previous one).
# A non-English language wins: English is often just pasted command output or an error.
function Get-Language([string]$text) {
    $own = Get-OwnWords $text
    $s = Get-Scores $own
    $best = $null; $top = -1; $second = -1  # highest and second highest non-English score
    foreach ($k in $Codes) {
        if ($k -ceq 'en') { continue }
        if ($s[$k] -gt $top) { $second = $top; $top = $s[$k]; $best = $k } elseif ($s[$k] -gt $second) { $second = $s[$k] }
    }
    if ($top -ge 2 -and $top -gt $second) { return $best }
    # English only from a short message: longer text without native words is pasted output
    $lines = 0
    foreach ($l in [regex]::Split($own, '\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]')) { if ($l -match '[^\s\x1c-\x1f]') { $lines++ } }
    if ($s['en'] -ge 3 -and $top -eq 0 -and $lines -le 3) { 'en' } else { $null }
}

# Same directory as Python's tempfile.gettempdir(): the first existing of TMPDIR, TEMP, TMP
function Get-StateFile([string]$session) {
    $dir = $null
    foreach ($v in $env:TMPDIR, $env:TEMP, $env:TMP) {
        if ($v -and [IO.Directory]::Exists([IO.Path]::GetFullPath($v))) { $dir = [IO.Path]::GetFullPath($v); break } }
    if (-not $dir) { $dir = [IO.Path]::GetTempPath() }  # ponytail: Python also tries C:\TEMP, C:\TMP and the cwd here
    [IO.Path]::Combine($dir, 'claude-reply-language-' + [regex]::Replace($session, '[^A-Za-z0-9_-]', ''))
}

# Python truthiness: None, False, 0, '', empty list or dict are false
function Test-Truthy($v) {
    if ($null -eq $v) { return $false }
    if ($v -is [string]) { return $v.Length -gt 0 }
    if ($v -is [bool]) { return $v }
    if ($v -is [Collections.ICollection]) { return $v.Count -gt 0 }
    if ($v -is [ValueType]) { return $v -ne 0 }
    $true
}

function Get-Texts($content) {  # "text" of the {"type": "text"} blocks of a content list
    foreach ($b in $content) {
        if ($b -is [Collections.IDictionary] -and $b['type'] -ceq 'text') { if ($b.ContainsKey('text')) { $b['text'] } else { '' } } }
}

function Get-UserText($o) {
    $m = $o['message']
    if (-not (Test-Truthy $m)) { $m = @{} }
    $c = $m['content']
    if ($c -is [string]) { return $c }
    if ($c -isnot [Array]) { $c = @() }
    @(Get-Texts $c) -join "`n"
}

# Assistant text since the last real user message. Parsed from the end back to that message: same result as the
# .py's forward pass, but only the last turn is parsed (transcripts reach 100 MB)
function Get-LastTurn([IO.StreamReader]$r) {
    $lines = [Collections.Generic.List[string]]::new()
    try { while ($null -ne ($line = $r.ReadLine())) { $lines.Add($line) } } finally { $r.Dispose() }
    $texts = [Collections.Generic.List[string]]::new()
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        $o = $null
        try { $o = $Json.DeserializeObject($lines[$i]) } catch { continue }
        if ($o -isnot [Collections.IDictionary]) { continue }
        if ($o['type'] -ceq 'user' -and (Get-UserText $o) -match '[^\s\x1c-\x1f]' -and -not (Test-Truthy $o['isMeta'])) { break }
        if ($o['type'] -ceq 'assistant') {
            $m = $o['message']
            if (-not (Test-Truthy $m)) { $m = @{} }
            $c = $m['content']
            if ($c -is [Array]) { $texts.InsertRange(0, [string[]]@(Get-Texts $c)) }
        }
    }
    $texts -join "`n"
}

function Get-Field($data, [string]$key, [string]$default) {
    if (-not $data.ContainsKey($key)) { return $default }
    $v = $data[$key]
    if ($v -isnot [string]) { throw "$key is not a string" }  # Python fails on it too
    $v
}

function Invoke-Prompt($data) {
    $path = Get-StateFile (Get-Field $data 'session_id' 'default')
    $lang = Get-Language (Get-Field $data 'prompt' '')
    if ($lang) { [IO.File]::WriteAllText($path, $lang) }
    else { try { $lang = [IO.File]::ReadAllText($path).Trim() } catch { $lang = $null } }
    if ($lang) {
        if (-not $Names.ContainsKey($lang)) { throw "unknown language in ${path}: $lang" }
        $name = $Names[$lang]
        [Console]::Out.Write('{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ' +
            "`"The user writes in $name. Write every reply to the user in $name, and do your thinking in $name too. " +
            "Code, commands and quoted text stay as they are.`"}}`r`n")
    }
    0
}

function Invoke-Stop($data) {
    # one rewrite only: the hook's feedback is isMeta in the transcript, so the first foreign reply would count again
    if (Test-Truthy $data['stop_hook_active']) { return 0 }
    try { $lang = [IO.File]::ReadAllText((Get-StateFile (Get-Field $data 'session_id' 'default'))).Trim() } catch { $lang = $Allowed[0] }
    $text = $data['last_assistant_message']
    if (-not (Test-Truthy $text)) { $text = '' }
    if (Test-Truthy $data['transcript_path']) {
        $r = $null
        try {  # shared like Python's open(), so Claude Code can keep appending to the transcript
            $f = [IO.FileStream]::new([string]$data['transcript_path'], [IO.FileMode]::Open, [IO.FileAccess]::Read,
                                      [IO.FileShare]'ReadWrite, Delete')
            $r = [IO.StreamReader]::new($f, [Text.UTF8Encoding]::new($false, $true), $false)
        } catch {}
        if ($r) { $t = Get-LastTurn $r; if ($t) { $text = $t } }
    }
    $s = Get-Scores $text
    $n = [regex]::Matches((Strip-Code $text), $Shared).Count
    $s['cs'] += $n; $s['sk'] += $n
    $permitted = @($Allowed) + $lang
    $other = $null; $hits = 0
    foreach ($k in $Codes) {
        if ($permitted -cnotcontains $k -and ($null -eq $other -or $s[$k] -gt $hits)) { $other = $k; $hits = $s[$k] } }
    $ok = 0  # scores are never negative
    foreach ($k in $permitted) { if ($s.ContainsKey($k) -and $s[$k] -gt $ok) { $ok = $s[$k] } }
    # only a clear case: single foreign words or names in a reply are fine
    if ($other -and $hits -ge 4 -and $hits -gt $ok) {
        $want = if ($Names.ContainsKey($lang)) { $Names[$lang] } else { $Names[$Allowed[0]] }
        [Console]::Error.Write("The reply is in $($Names[$other]). Only $(@($Allowed | ForEach-Object { $Names[$_] }) -join ', ') " +
            "or the user's language ($want) are allowed. Write the last reply again in $want, without apologizing or explaining why.`r`n")
        return 2
    }
    0
}

function Invoke-SelfTest {
    function Assert($ok, $what) { if (-not $ok) { throw "selftest failed: $what" } }
    Assert ((Get-Language 'ok sedaj bi zelel nov repo s pluginom, ki to nastavi') -ceq 'sl') 'detect sl'
    Assert ((Get-Language 'can you check what this hook does') -ceq 'en') 'detect en'
    Assert ((Get-Language 'Proč to nefunguje, když je všechno správně?') -ceq 'cs') 'detect cs'
    Assert ($null -eq (Get-Language 'ok')) 'detect too short'
    Assert ((Get-Language '<pasted>the and is to of in that it for you</pasted> poglej kaj je to') -ceq 'sl') 'detect without <tag> blocks'
    function Run($mode, $data, $allowed = 'sl,en') {
        $psi = New-Object Diagnostics.ProcessStartInfo 'powershell.exe',
            "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$PSCommandPath`" $mode"
        $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
        $psi.RedirectStandardInput = $psi.RedirectStandardOutput = $psi.RedirectStandardError = $true
        $psi.EnvironmentVariables['REPLY_LANGUAGE_ALLOWED'] = $allowed
        $p = [Diagnostics.Process]::Start($psi)
        $b = [Text.UTF8Encoding]::new($false).GetBytes($Json.Serialize($data))
        $p.StandardInput.BaseStream.Write($b, 0, $b.Length); $p.StandardInput.Close()
        $r = @{ out = $p.StandardOutput.ReadToEnd(); err = $p.StandardError.ReadToEnd() }
        $p.WaitForExit(); $r.code = $p.ExitCode; $r
    }
    $session = "test-$PID"
    $p = Run 'prompt' @{ session_id = $session; prompt = 'kaj je to in zakaj ne deluje' }
    Assert ($p.out -match 'Slovenian') "prompt: $($p.out) $($p.err)"
    Assert ((Run 'stop' @{ session_id = $session; last_assistant_message = 'To je hook, ki preverja jezik in ga lahko nastaviš.' }).code -eq 0) 'stop sl'
    Assert ((Run 'stop' @{ session_id = $session; last_assistant_message = 'This is the hook that checks the reply.' }).code -eq 0) 'stop en'
    $bad = Run 'stop' @{ session_id = $session; last_assistant_message = 'Ovo je hook koji provjerava što će biti, jer sada treba ovdje.' }
    Assert ($bad.code -eq 2 -and $bad.err -match 'Croatian') "stop hr: $($bad.code) $($bad.err)"
    Assert ((Run 'stop' @{ session_id = $session; last_assistant_message = 'This is the hook that checks it.' } 'sl').code -eq 2) 'stop en not allowed'
    Assert ((Run 'stop' @{ session_id = $session; stop_hook_active = $true
                          last_assistant_message = 'Ovo je hook koji provjerava što će biti, jer sada treba ovdje.' }).code -eq 0) 'one rewrite only'
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Assert ((Strip-Code ('a/b ' + 'x' * 20000 + ' c')) -ceq ('  ' + 'x' * 20000 + ' c')) 'strip paths'
    Assert ($sw.ElapsedMilliseconds -lt 500) 'strip is linear'
    Remove-Item (Get-StateFile $session)
    'ok'
}

if ($Cmd -ceq 'selftest') { Invoke-SelfTest; exit 0 }
$data = $Json.DeserializeObject([IO.StreamReader]::new([Console]::OpenStandardInput(), [Text.UTF8Encoding]::new($false)).ReadToEnd())
if ($data -isnot [Collections.IDictionary]) { throw 'hook input is not a JSON object' }
exit $(if ($Cmd -ceq 'prompt') { Invoke-Prompt $data } else { Invoke-Stop $data })
