# Runs a reply-language hook (prompt | stop): reply-language.py with Python 3, on Windows without an installed
# Python reply-language.ps1 (Windows PowerShell, about 1 s per hook instead of about 0.3 s).
d=${0%[/\\]*}  # script folder; on Windows the path may use backslashes
[ "$OS" = Windows_NT ] || exec python3 "$d/reply-language.py" "$@"

# Below this line only Windows (Git Bash's sh is bash): ${var//...} and -nt are bash-only, keep them under line 4.
# First python3.exe, then python.exe, then the py launcher on PATH. WindowsApps is skipped: its python.exe and
# python3.exe are the Microsoft Store stubs. No forks: the PATH walk is pure shell.
find_exe() {
  IFS=:; set -f
  for dir in $PATH; do
    case $dir in *WindowsApps*) continue ;; esac
    [ -x "$dir/$1" ] && { exe="$dir/$1"; unset IFS; return 0; }
  done
  unset IFS; return 1
}
# $exe (with args $@) runs Python 3.7+ (3.6 ignores -X utf8). A Python 2 or a py launcher without Python 3 would fail every
# hook, and exit 2 even blocks. Checked once per interpreter; only success is cached (a marker in temp, renewed when
# the interpreter changes), so later hooks pay one file test and a fixed install is used on the next hook.
usable() {
  ok="${TMP:-/tmp}/claude-reply-language.python-ok.${exe//[^A-Za-z0-9]/_}"
  [ -f "$ok" ] && [ ! "$exe" -nt "$ok" ] && return 0
  "$exe" "$@" -X utf8 -c 'import sys; sys.exit(sys.version_info < (3, 7))' </dev/null >/dev/null 2>&1 && : > "$ok"
}
# -X utf8: otherwise Windows Python reads the hook JSON on stdin as cp1252
if { find_exe python3.exe && usable; } || { find_exe python.exe && usable; }; then
  exec "$exe" -X utf8 "$d/reply-language.py" "$@"
fi
if find_exe py.exe && usable -3; then exec "$exe" -3 -X utf8 "$d/reply-language.py" "$@"; fi
exec powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$d/reply-language.ps1" "$@"
