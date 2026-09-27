$ErrorActionPreference = 'SilentlyContinue'
$report = 'C:\Users\Asus\PycharmProjects\support-bot-main\CuteUpdate1\_cursor_state_clean.txt'
$protId = '25a8ca7a-24b7-4c9a-a98e-db91399d4800'
$prot = "C:\Users\Asus\.cursor\projects\c-Users-Asus-PycharmProjects-support-bot-main-CuteUpdate1\agent-transcripts\$protId\$protId.jsonl"
$gs = Join-Path $env:APPDATA 'Cursor\User\globalStorage'
$before = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 2)
$lines = @("BEFORE=$before", "PROT_BEFORE=$(Test-Path -LiteralPath $prot)")

# Only the ~11GB chat DB and its backup — not settings, not protected transcript
$targets = @(
  (Join-Path $gs 'state.vscdb'),
  (Join-Path $gs 'state.vscdb.backup'),
  (Join-Path $gs 'state.vscdb-shm'),
  (Join-Path $gs 'state.vscdb-wal')
)

foreach ($t in $targets) {
  if (Test-Path -LiteralPath $t) {
    $gb = [math]::Round((Get-Item -LiteralPath $t).Length / 1GB, 2)
    Remove-Item -LiteralPath $t -Force
    $still = Test-Path -LiteralPath $t
    $lines += "target $t was=${gb}GB removed=$(-not $still)"
  } else {
    $lines += "missing $t"
  }
}

# If locked by Cursor, try rename then delete
$state = Join-Path $gs 'state.vscdb'
if (Test-Path -LiteralPath $state) {
  $ren = Join-Path $gs ("state.vscdb.to_delete_" + (Get-Date -Format 'yyyyMMddHHmmss'))
  Rename-Item -LiteralPath $state -NewName (Split-Path $ren -Leaf) -Force
  if (Test-Path -LiteralPath $ren) {
    Remove-Item -LiteralPath $ren -Force
    $lines += "retry_rename_delete still=$(Test-Path -LiteralPath $ren)"
  } else {
    $lines += "retry_rename failed - Cursor may be locking the file. Close Cursor and rerun."
  }
}

$after = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 2)
$lines += "AFTER=$after"
$lines += "FREED=$([math]::Round($after - $before, 2))"
$lines += "PROT_AFTER=$(Test-Path -LiteralPath $prot)"
$lines += "STATE_AFTER=$(Test-Path -LiteralPath $state)"
$lines += 'DONE'
$lines | Set-Content -Path $report -Encoding UTF8
