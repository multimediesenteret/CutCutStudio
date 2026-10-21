<#
.SYNOPSIS
  Kiosk-vakten (SO-6): holder touch-skjermen i gang i kiosk-brukerens økt.

.DESCRIPTION
  Startes av Oppgaveplanlegger når kiosk-brukeren logger inn (setup-kiosk.ps1). Hvert 5. sekund:
  * Kjører ikke Edge i kiosk-modus: start den.
  * Svarer CutCut, men touch-skjermen har ikke sendt hjerteslag på 30 s (svart side, hengt
    fane): lukk Edge og start den på nytt.
  * Svarer ikke CutCut: vent. Touch-siden kobler seg til igjen selv når CutCut er tilbake.
  Gjør aldri noe annet enn å starte og stoppe sin egen Edge.

.EXAMPLE
  .\kiosk-vakt.ps1 -Once -DryRun   # vis hva vakten ville gjort nå
#>
[CmdletBinding()]
param(
  [string]$Url = "http://127.0.0.1:8080/touch/",
  [string]$Api = "http://127.0.0.1:8080",
  [int]$StaleSeconds = 30,
  [int]$EverySeconds = 5,
  [string]$Edge = "",
  [switch]$Once,
  [switch]$DryRun
)

$ErrorActionPreference = "Continue"
Set-StrictMode -Version 3

if (-not $Edge) {
  $candidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
  )
  $Edge = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
$EdgeProfile = Join-Path $env:LOCALAPPDATA "CutCut\kiosk-edge"
$EdgeArgs = @(
  "--kiosk", $Url, "--edge-kiosk-type=fullscreen", "--no-first-run",
  "--user-data-dir=`"$EdgeProfile`"", "--disable-features=Translate",
  "--overscroll-history-navigation=0", "--disable-pinch"
)

function Write-Log([string]$text) {
  $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $text
  Write-Host $line
  $dir = Join-Path $env:LOCALAPPDATA "CutCut"
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Add-Content -Path (Join-Path $dir "kiosk-vakt.log") -Value $line -Encoding UTF8
}

function Get-KioskEdge {
  Get-CimInstance Win32_Process -Filter "Name = 'msedge.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*--kiosk*" -and $_.CommandLine -like "*kiosk-edge*" }
}

function Get-HeartbeatAge {
  # Returns: $null = CutCut does not answer; -1 = no touch screen yet; otherwise seconds.
  try {
    $r = Invoke-RestMethod -Uri "$Api/api/touch/heartbeat" -TimeoutSec 3
    if ($null -eq $r.age_ms) { return -1 }
    return [int]($r.age_ms / 1000)
  } catch { return $null }
}

function Start-Kiosk {
  if ($DryRun) { Write-Log "[tørrkjøring] ville startet Edge: $Edge $($EdgeArgs -join ' ')"; return }
  if (-not $Edge) { Write-Log "Fant ikke Microsoft Edge."; return }
  Start-Process -FilePath $Edge -ArgumentList $EdgeArgs | Out-Null
  Write-Log "Startet Edge i kiosk-modus ($Url)"
}

function Stop-Kiosk([string]$why) {
  if ($DryRun) { Write-Log "[tørrkjøring] ville lukket Edge: $why"; return }
  Get-KioskEdge | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Write-Log "Lukket Edge: $why"
}

$startedAt = Get-Date
$silentSince = $null
Write-Log "Kiosk-vakten startet ($Url)"
while ($true) {
  $running = @(Get-KioskEdge).Count -gt 0
  $age = Get-HeartbeatAge
  # CutCut answers, but the page has not said a word: hung or blank. (-1: core has not heard
  # any touch screen since it started; give it the same 30 s, e.g. after a core restart.)
  $quiet = ($null -ne $age) -and (($age -eq -1) -or ($age -gt $StaleSeconds))
  if (-not $quiet) { $silentSince = $null } elseif ($null -eq $silentSince) { $silentSince = Get-Date }
  if (-not $running) {
    Start-Kiosk
    $startedAt = Get-Date
    $silentSince = $null
  } elseif ($quiet -and ((Get-Date) - $startedAt).TotalSeconds -gt 60 -and
            ((Get-Date) - $silentSince).TotalSeconds -gt $StaleSeconds) {
    Stop-Kiosk "touch-skjermen har ikke sendt hjerteslag ($age s)"
    Start-Sleep -Seconds 2
    Start-Kiosk
    $startedAt = Get-Date
    $silentSince = $null
  }
  if ($Once) { break }
  Start-Sleep -Seconds $EverySeconds
}
