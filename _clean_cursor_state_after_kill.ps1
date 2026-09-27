$ErrorActionPreference = 'SilentlyContinue'
$log = 'C:\Users\Asus\PycharmProjects\support-bot-main\CuteUpdate1\_cursor_state_done.txt'
$before = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 2)
$gs = Join-Path $env:APPDATA 'Cursor\User\globalStorage'
$prot = 'C:\Users\Asus\.cursor\projects\c-Users-Asus-PycharmProjects-support-bot-main-CuteUpdate1\agent-transcripts\25a8ca7a-24b7-4c9a-a98e-db91399d4800\25a8ca7a-24b7-4c9a-a98e-db91399d4800.jsonl'
$lines = @("BEFORE=$before", "PROT_BEFORE=$(Test-Path -LiteralPath $prot)")

foreach ($n in @('state.vscdb', 'state.vscdb.backup', 'state.vscdb-shm', 'state.vscdb-wal')) {
  $p = Join-Path $gs $n
  if (Test-Path -LiteralPath $p) {
    $gb = [math]::Round((Get-Item -LiteralPath $p).Length / 1GB, 2)
    Remove-Item -LiteralPath $p -Force
    # retry rename if still locked
    if (Test-Path -LiteralPath $p) {
      $ren = Join-Path $gs ($n + '.to_delete')
      Rename-Item -LiteralPath $p -NewName (Split-Path $ren -Leaf) -Force
      Remove-Item -LiteralPath $ren -Force
    }
    $lines += "removed $n was=${gb}GB still=$(Test-Path -LiteralPath $p)"
  } else {
    $lines += "missing $n"
  }
}

$after = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 2)
$lines += "AFTER=$after"
$lines += "FREED=$([math]::Round($after - $before, 2))"
$lines += "PROT_AFTER=$(Test-Path -LiteralPath $prot)"
$lines += "STATE_AFTER=$(Test-Path -LiteralPath (Join-Path $gs 'state.vscdb'))"
$lines += 'DONE'
$lines | Set-Content -Path $log -Encoding UTF8
