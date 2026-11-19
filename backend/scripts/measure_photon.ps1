param(
    [switch]$ImportIndex,
    [ValidateRange(1, 30)][int]$Samples = 5
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$reportPath = Join-Path $repoRoot 'data/geocoding/qa/photon-resources.json'
Get-Command docker -ErrorAction Stop | Out-Null
$report = [ordered]@{
    measured_at_utc = [DateTime]::UtcNow.ToString('o')
    import_succeeded = $null
    initial_import_seconds = $null
    samples = @()
    index_size_kib = $null
    search_latency_ms = @()
}
Push-Location -LiteralPath $repoRoot
try {
    if ($ImportIndex) {
        # The import script refuses to overwrite an existing index.
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $importPath = Join-Path $repoRoot 'docker/photon/import.sh'
        & docker compose --profile geocoding run --rm --no-deps --entrypoint /bin/sh -v "${importPath}:/opt/import.sh:ro" photon /opt/import.sh
        $timer.Stop()
        if ($LASTEXITCODE -ne 0) { throw 'Photon import failed; no successful import duration recorded.' }
        $report.import_succeeded = $true
        $report.initial_import_seconds = $timer.Elapsed.TotalSeconds
    }
    & docker compose --profile geocoding up -d photon
    if ($LASTEXITCODE -ne 0) { throw 'Photon startup failed.' }
    $ready = $false
    $deadline = [DateTime]::UtcNow.AddMinutes(5)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $health = Invoke-WebRequest 'http://127.0.0.1:2322/status' -TimeoutSec 3
            if ($health.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'Photon did not become healthy within five minutes.' }
    $containerId = (& docker compose --profile geocoding ps -q photon).Trim()
    if (-not $containerId) { throw 'Photon container was not found.' }
    for ($sample = 0; $sample -lt $Samples; $sample++) {
        $stats = & docker stats --no-stream --format '{{json .}}' $containerId
        if ($LASTEXITCODE -ne 0) { throw 'Docker resource sampling failed.' }
        $report.samples += [ordered]@{ captured_at_utc = [DateTime]::UtcNow.ToString('o'); docker_stats = ($stats | ConvertFrom-Json) }
    }
    $size = & docker compose --profile geocoding exec -T photon du -sk /data/photon_data
    if ($LASTEXITCODE -ne 0) { throw 'Index storage measurement failed.' }
    $report.index_size_kib = [long](($size -split '\s+')[0])
    foreach ($query in @('PES University', 'Murugeshpalya', 'Devanahalli')) {
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $response = Invoke-WebRequest ("http://127.0.0.1:2322/api?q=" + [Uri]::EscapeDataString($query) + '&bbox=77.15,12.6,78,13.5&limit=3') -TimeoutSec 10
        $timer.Stop()
        $report.search_latency_ms += [ordered]@{ query = $query; status_code = $response.StatusCode; elapsed_ms = $timer.Elapsed.TotalMilliseconds }
    }
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding utf8
    Write-Output "Recorded measured Photon resources at $reportPath"
} finally { Pop-Location }
