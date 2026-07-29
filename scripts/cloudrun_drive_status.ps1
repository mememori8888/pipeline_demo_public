param(
    [string]$BaseUrl = "https://pipeline-demo-api-xebbfpgofa-an.a.run.app",
    [string]$EnvFile = "D:\python\pipeline_demo\pipeline_demo\.env"
)

$ErrorActionPreference = "Stop"

function Read-DotEnvValue {
    param([string]$Path, [string]$Name)
    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $idx = $trimmed.IndexOf("=")
        $key = $trimmed.Substring(0, $idx).Trim()
        if ($key -ne $Name) {
            continue
        }
        $value = $trimmed.Substring($idx + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        return $value
    }
    return $null
}

$apiKey = Read-DotEnvValue -Path $EnvFile -Name "APP_API_KEY"
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "APP_API_KEY was not found in $EnvFile"
}

$baseUrl = $BaseUrl.TrimEnd("/")

Invoke-RestMethod `
    -Uri "$baseUrl/api/v1/drive/status" `
    -Headers @{ "X-API-Key" = $apiKey } `
    -TimeoutSec 60
