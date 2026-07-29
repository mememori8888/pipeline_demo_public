param(
    [string]$Project = "geoai-cloudrun",
    [string]$Region = "asia-northeast1",
    [string]$Service = "pipeline-demo-api",
    [string]$EnvFile = "D:\python\pipeline_demo\pipeline_demo\.env",
    [string]$CloudSdkConfig = ""
)

$ErrorActionPreference = "Stop"

if (-not $CloudSdkConfig) {
    $candidate = Join-Path $env:TEMP "codex-gcloud-pipeline-demo"
    if (Test-Path $candidate) {
        $CloudSdkConfig = $candidate
    }
}
if ($CloudSdkConfig) {
    $env:CLOUDSDK_CONFIG = $CloudSdkConfig
}

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

$url = gcloud run services describe $Service --project $Project --region $Region --format="value(status.url)"
$token = gcloud auth print-identity-token --audiences=$url

Invoke-RestMethod `
    -Uri "$url/api/v1/drive/status" `
    -Headers @{ Authorization = "Bearer $token"; "X-API-Key" = $apiKey } `
    -TimeoutSec 60
