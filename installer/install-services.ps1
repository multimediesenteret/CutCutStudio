<#
.SYNOPSIS
  Installerer (eller fjerner) Windows-tjenestene for CutCut Studio med WinSW (SO-2).

.DESCRIPTION
  Tjenesten «CutCut» starter supervisor (cutcut supervisor), som starter og passer på core,
  atem-bridge og audio-capture. Windows starter tjenesten ved oppstart og på nytt etter krasj
  (5, 10, 30 s). Kjøres som administrator i servicevinduet. Kan kjøres på nytt: en tjeneste
  som finnes, stoppes, oppdateres og startes igjen.

  Med -Companion installeres også «CutCut-Companion» (Companion uten skjerm). Stien til
  Companions start og argumentene bekreftes på test-PC-en (Q35).

.EXAMPLE
  .\installer\install-services.ps1 -Root C:\CutCut
.EXAMPLE
  .\installer\install-services.ps1 -Root C:\CutCut -Uninstall
#>
[CmdletBinding()]
param(
  [string]$Root = "C:\CutCut",
  # Mappen med CutCut: en pakke (python\) eller en git-utsjekk (.venv). Standard: Root\current.
  [string]$App = "",
  [string]$Site = "",
  [string]$Data = "",
  [int]$Port = 8080,
  [string]$UiDir = "",
  # WinSW-x64.exe 2.12.0. Mangler filen, lastes den ned fra GitHub og sjekkes mot SHA-256.
  [string]$WinSW = "",
  [switch]$Companion,
  [string]$CompanionExe = "",
  [string]$CompanionArgs = "",
  [switch]$NoStart,
  [switch]$Uninstall,
  # Vis hva som ville blitt gjort, uten å endre noe.
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3

$WinSWVersion = "2.12.0"
$WinSWSha256 = "05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da"
$WinSWUrl = "https://github.com/winsw/winsw/releases/download/v$WinSWVersion/WinSW-x64.exe"

if (-not $App) { $App = Join-Path $Root "current" }
if (-not $Site) { $Site = Join-Path $Root "site" }
if (-not $Data) { $Data = Join-Path $Root "data" }
$ServiceDir = Join-Path $Root "services"
$Templates = Join-Path $PSScriptRoot "winsw"

function Say([string]$text) { Write-Host "  $text" }

function Invoke-Step([string]$what, [scriptblock]$action) {
  if ($DryRun) { Say "[tørrkjøring] $what"; return }
  Say $what
  & $action
}

function Get-WinSW {
  $target = Join-Path $ServiceDir "WinSW-x64.exe"
  $source = if ($WinSW) { $WinSW } elseif (Test-Path $target) { $target } else { "" }
  if (-not $source) {
    Invoke-Step "Laster ned WinSW $WinSWVersion" {
      New-Item -ItemType Directory -Force -Path $ServiceDir | Out-Null
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      Invoke-WebRequest -Uri $WinSWUrl -OutFile $target -UseBasicParsing
    }
    $source = $target
  }
  if (-not $DryRun) {
    $hash = (Get-FileHash -Algorithm SHA256 -Path $source).Hash.ToLowerInvariant()
    if ($hash -ne $WinSWSha256) {
      throw "WinSW har feil sjekksum ($hash). Forventet $WinSWSha256. Avbryter."
    }
  }
  return $source
}

function Install-Service([string]$id, [string]$xml, [string]$winsw) {
  $exe = Join-Path $ServiceDir "$id.exe"
  $cfg = Join-Path $ServiceDir "$id.xml"
  $existing = Get-Service -Name $id -ErrorAction SilentlyContinue
  if ($existing) {
    Invoke-Step "Stopper og fjerner gammel $id" {
      if ($existing.Status -ne "Stopped") { & $exe stop | Out-Host }
      & $exe uninstall | Out-Host
    }
  }
  Invoke-Step "Skriver $cfg" {
    New-Item -ItemType Directory -Force -Path $ServiceDir | Out-Null
    if ((Resolve-Path $winsw).Path -ne $exe) { Copy-Item -Force $winsw $exe }
    Set-Content -Path $cfg -Value $xml -Encoding UTF8
  }
  Invoke-Step "Installerer tjenesten $id" { & $exe install | Out-Host }
  if (-not $NoStart) {
    Invoke-Step "Starter $id" { & $exe start | Out-Host }
  }
}

function Remove-Service([string]$id) {
  $exe = Join-Path $ServiceDir "$id.exe"
  if (-not (Get-Service -Name $id -ErrorAction SilentlyContinue)) {
    Say "$id er ikke installert."
    return
  }
  Invoke-Step "Stopper $id" { & $exe stop | Out-Host }
  Invoke-Step "Fjerner $id" { & $exe uninstall | Out-Host }
}

function Expand-Template([string]$name, [hashtable]$values) {
  $text = Get-Content -Raw -Encoding UTF8 (Join-Path $Templates $name)
  foreach ($key in $values.Keys) {
    $value = [Security.SecurityElement]::Escape([string]$values[$key])
    $text = $text.Replace("{{$key}}", $value)
  }
  if ($text -match "\{\{[A-Z_]+\}\}") { throw "Mal $name har verdier som ikke er fylt inn: $($Matches[0])" }
  return $text
}

Write-Host "CutCut Studio · Windows-tjenester (WinSW $WinSWVersion)"

if ($Uninstall) {
  Remove-Service "CutCut"
  Remove-Service "CutCut-Companion"
  exit 0
}

# Pakken fra install.ps1 har sin egen Python (python\python.exe); en git-utsjekk har .venv.
$python = Join-Path $App "python\python.exe"
if (-not (Test-Path $python)) { $python = Join-Path $App ".venv\Scripts\python.exe" }
if (-not $DryRun -and -not (Test-Path $python)) {
  throw "Fant ikke Python i $App. Bruk install.ps1 med en pakke, eller kjør «uv sync --locked --extra silero» i $App først."
}
if (-not $DryRun -and -not (Test-Path (Join-Path $Site "devices.yaml"))) {
  throw "Fant ikke studio-oppsettet i $Site (devices.yaml)."
}
Invoke-Step "Lager $Data" {
  New-Item -ItemType Directory -Force -Path (Join-Path $Data "logs") | Out-Null
}

$winsw = Get-WinSW
if (-not $UiDir -and (Test-Path (Join-Path $App "ui\dist\tech\index.html"))) {
  $UiDir = Join-Path $App "ui\dist"  # pakken har skjermene med seg
}
$uiArg = if ($UiDir) { " --ui-dir `"$UiDir`"" } else { "" }
$xml = Expand-Template "CutCut.xml.tmpl" @{
  PYTHON = $python; SITE = $Site; DATA = $Data; PORT = $Port; WORKDIR = $App; UI_ARG = $uiArg
}
Install-Service "CutCut" $xml $winsw

if ($Companion) {
  if (-not $CompanionExe) { throw "-Companion krever -CompanionExe (stien bekreftes på test-PC-en, Q35)." }
  $xml = Expand-Template "Companion.xml.tmpl" @{
    COMPANION_EXE = $CompanionExe
    COMPANION_ARGS = $CompanionArgs
    COMPANION_DIR = (Split-Path -Parent $CompanionExe)
    DATA = $Data
  }
  Install-Service "CutCut-Companion" $xml $winsw
}

Write-Host "Ferdig. Status: Get-Service CutCut; logg: $Data\logs\service"
