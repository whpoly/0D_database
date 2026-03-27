param(
    [string]$CondaEnv = "web",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8050
)

$env:ZERO_DB_ENV = "development"
$env:ZERO_DB_DEBUG = "1"
$env:ZERO_DB_DEV_TOOLS_UI = "1"
$env:ZERO_DB_HOST = $Host
$env:ZERO_DB_PORT = "$Port"

conda run -n $CondaEnv python main.py
