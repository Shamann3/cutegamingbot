# Run a Python script with live console output and a clean UTF-8 log file.
# Uses cmd.exe so Python stderr (warnings) is not wrapped as NativeCommandError.
param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$PythonExe,
    [Parameter(Mandatory = $true)][string]$PythonArgs,
    [Parameter(Mandatory = $true)][string]$Script,
    [Parameter(Mandatory = $true)][string]$LogPath
)

$Host.UI.RawUI.WindowTitle = $Title
Set-Location -LiteralPath $WorkingDirectory

# Make the console and pipes UTF-8 so Cyrillic from Python/cmd is not mojibaked.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { chcp 65001 > $null } catch { }

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONWARNINGS = 'ignore::UserWarning'
$ErrorActionPreference = 'Continue'

Write-Host "===== $Title =====" -ForegroundColor Cyan
Write-Host "Log: $LogPath" -ForegroundColor DarkGray
Write-Host ''

if (Test-Path $LogPath) {
    try {
        Remove-Item $LogPath -Force -ErrorAction Stop
    } catch {
        Write-Host "[launcher] log file busy, will append/share: $LogPath" -ForegroundColor DarkYellow
    }
}

$argList = @()
foreach ($part in ($PythonArgs -split '\s+')) {
    if ($part) { $argList += $part }
}
$argList += $Script

function Quote-CmdArg([string]$s) {
    if ($s -match '[\s"]') { return '"' + $s.Replace('"', '\"') + '"' }
    return $s
}

$py = Quote-CmdArg $PythonExe
$argsJoined = ($argList | ForEach-Object { Quote-CmdArg $_ }) -join ' '
$cmdLine = "$py $argsJoined 2>&1"

# Один постоянный UTF-8 поток на весь запуск: без открытия/закрытия файла на
# каждую строку (это устраняло ошибку "Поток был недоступен для чтения" и
# заметно ускоряет логирование при частом выводе бота).
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$writer = $null
try {
    $fs = New-Object System.IO.FileStream(
        $LogPath,
        [System.IO.FileMode]::Create,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::ReadWrite
    )
    $writer = New-Object System.IO.StreamWriter($fs, $utf8NoBom)
    $writer.AutoFlush = $false
} catch {
    $fallback = [System.IO.Path]::Combine(
        [System.IO.Path]::GetDirectoryName($LogPath),
        ([System.IO.Path]::GetFileNameWithoutExtension($LogPath) + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + [System.IO.Path]::GetExtension($LogPath))
    )
    Write-Host "[launcher] cannot open log '$LogPath': $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "[launcher] using fallback log: $fallback" -ForegroundColor Yellow
    try {
        $fs = New-Object System.IO.FileStream(
            $fallback,
            [System.IO.FileMode]::Create,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::ReadWrite
        )
        $writer = New-Object System.IO.StreamWriter($fs, $utf8NoBom)
        $writer.AutoFlush = $false
        $LogPath = $fallback
    } catch {
        Write-Host "[launcher] fallback log also failed, console only." -ForegroundColor Red
        $writer = $null
    }
}

$exitCode = 0
try {
    & cmd.exe /c $cmdLine 2>&1 | ForEach-Object {
        $line = "$_"
        if ($line) {
            if ($null -ne $writer) {
                try {
                    $writer.WriteLine($line)
                    $writer.Flush()
                } catch {
                    # Логирование не должно ронять процесс — просто продолжаем вывод в консоль.
                }
            }
            Write-Host $line
        }
    }
    if ($null -ne $LASTEXITCODE) { $exitCode = $LASTEXITCODE }
} catch {
    $msg = "[launcher] $($_.Exception.Message)"
    if ($null -ne $writer) { try { $writer.WriteLine($msg) } catch { } }
    Write-Host $msg -ForegroundColor Red
    $exitCode = 1
} finally {
    if ($null -ne $writer) {
        try { $writer.Flush() } catch { }
        try { $writer.Dispose() } catch { }
    }
}

Write-Host ''
if ($exitCode -eq 0) {
    Write-Host "[$Title] process ended." -ForegroundColor Green
} else {
    Write-Host "[$Title] exited with code $exitCode. See log above." -ForegroundColor Yellow
}
