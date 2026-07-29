param(
    [int]$Port = 8081,
    [string]$Project = "geoai-cloudrun",
    [string]$Region = "asia-northeast1",
    [string]$Service = "pipeline-demo-api",
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

Write-Host "Starting Cloud Run proxy on http://127.0.0.1:$Port"
Write-Host "Swagger UI: http://127.0.0.1:$Port/api/docs"
Write-Host "Close this terminal to stop the proxy."

gcloud run services proxy $Service --project $Project --region $Region --port $Port
