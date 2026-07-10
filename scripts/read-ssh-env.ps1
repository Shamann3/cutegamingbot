# Read SSH settings from project .env (ASCII-safe)
param([string]$EnvFile = (Join-Path (Split-Path $PSScriptRoot -Parent) '.env'))

$vars = @{}
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $key = $Matches[1]
            $val = $Matches[2].Trim()
            if ($val.StartsWith('"') -and $val.EndsWith('"')) {
                $val = $val.Substring(1, $val.Length - 2)
            }
            $vars[$key] = $val
        }
    }
}

function Get-EnvVal([string]$Name, [string]$Default = '') {
    if ($vars.ContainsKey($Name) -and $vars[$Name]) { return $vars[$Name] }
    return $Default
}

[PSCustomObject]@{
    Host         = Get-EnvVal 'SSH_HOST' '207.154.219.208'
    User         = Get-EnvVal 'SSH_USER' 'root'
    Port         = [int](Get-EnvVal 'SSH_PORT' '22')
    LocalPort    = [int](Get-EnvVal 'SSH_TUNNEL_PORT' '15432')
    RemoteHost   = Get-EnvVal 'SSH_TUNNEL_REMOTE_HOST' '127.0.0.1'
    RemotePgPort = [int](Get-EnvVal 'SSH_REMOTE_PG_PORT' '5432')
    KeyPath      = Get-EnvVal 'SSH_KEY_PATH' ''
    PuttySession = Get-EnvVal 'SSH_PUTTY_SESSION' ''
    Password     = Get-EnvVal 'SSH_PASSWORD' ''
    UseKey       = (Get-EnvVal 'SSH_USE_KEY' 'false').ToLower() -eq 'true'
}
