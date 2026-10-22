<#
.SYNOPSIS
  Installerer en ny versjon av CutCut Studio fra pakken, og ruller tilbake selv hvis den ikke
  kommer opp (SO-4, spesifikasjonen 12.3).

.DESCRIPTION
  Kjøres som administrator i servicevinduet, aldri under et opptak:

    1. Sjekker SHA-256 mot <pakke>.sha256 (eller -Sha256).
    2. Pakker ut ved siden av: C:\CutCut\versions\<versjon>\. Den gamle versjonen røres ikke.
    3. Prøver den nye versjonen mot studio-oppsettet (C:\CutCut\site) før noe byttes:
       oppsettet må kunne leses av den nye versjonen.
    4. Stopper tjenesten, bytter C:\CutCut\current til den nye versjonen og starter igjen.
    5. Venter til CutCut svarer på /api/health med den nye versjonen (standard 120 s).
       Gjør den ikke det: current tilbake til forrige versjon, tjenesten startes igjen, og
       skriptet avslutter med feil.
    6. Beholder de tre nyeste versjonene (aldri den som kjører, aldri den forrige).

  Opptak på Pearl påvirkes ikke (I7), men motoren klipper ikke mens tjenesten står (ca. 10 s).
  Alt skrives også til C:\CutCut\data\logs\install.log.

.EXAMPLE
  .\install.ps1 -Zip D:\cutcut-1.0.0-win64.zip
.EXAMPLE
  .\install.ps1 -Zip D:\cutcut-1.0.0-win64.zip -DryRun
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Zip,
  [string]$Root = "C:\CutCut",
  # Forventet SHA-256. Standard: første ord i <Zip>.sha256.
  [string]$Sha256 = "",
  [int]$Port = 8080,
  [int]$Keep = 3,
  [int]$HealthSeconds = 120,
  # Installer på nytt selv om versjonen allerede finnes.
  [switch]$Force,
  # Ikke installer tjenesten hvis den mangler (bare bytt versjon).
  [switch]$NoService,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3
Add-Type -AssemblyName System.IO.Compression.FileSystem

$Versions = Join-Path $Root "versions"
$Current = Join-Path $Root "current"
$Site = Join-Path $Root "site"
$LogDir = Join-Path $Root "data\logs"
$Service = "CutCut"

function Write-Log([string]$text) {
  $line = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $text
  Write-Host "  $text"
  if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    Add-Content -Path (Join-Path $LogDir "install.log") -Value $line -Encoding UTF8
  }
}

function Get-CurrentTarget {
  if (-not (Test-Path $Current)) { return $null }
  $item = Get-Item $Current -Force
  if ($item.LinkType -eq "Junction" -or $item.LinkType -eq "SymbolicLink") {
    return [string]($item.Target | Select-Object -First 1)
  }
  return $item.FullName  # an ordinary folder (git checkout): cannot switch back to it by link
}

function Set-Current([string]$target) {
  if (Test-Path $Current) {
    $item = Get-Item $Current -Force
    if (-not $item.LinkType) {
      throw "$Current er en vanlig mappe, ikke en lenke. Flytt den (f.eks. til $Versions\git) først."
    }
    $item.Delete()  # removes the junction, never what it points to
  }
  New-Item -ItemType Junction -Path $Current -Target $target | Out-Null
}

function Wait-Version([string]$want, [int]$seconds) {
  $deadline = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $h = Invoke-RestMethod -Uri "http://127.0.0.1:${Port}/api/health" -TimeoutSec 3
      if ($h.version -eq $want) { return $true }
    } catch { }
    Start-Sleep -Seconds 2
  }
  return $false
}

function Same-Path([string]$a, [string]$b) {
  if (-not $a -or -not $b) { return $false }
  return [IO.Path]::GetFullPath($a).TrimEnd("\") -ieq [IO.Path]::GetFullPath($b).TrimEnd("\")
}

function Start-Version([string]$dir) {
  # the service file may have changed between versions, so it is written again each time
  & (Join-Path $dir "installer\install-services.ps1") -Root $Root -Port $Port -NoStart
  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "install-services.ps1 feilet ($LASTEXITCODE)" }
  Start-Service $Service
}

function Stop-CutCut {
  if (Get-Service $Service -ErrorAction SilentlyContinue) {
    Stop-Service $Service -ErrorAction SilentlyContinue
    (Get-Service $Service).WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
  }
}

# every error also goes to install.log, so the technician (and CI) can see why
trap { Write-Log "FEIL: $_"; break }

Write-Host "CutCut Studio · installer pakke"

# 1. Checksum
if (-not (Test-Path $Zip)) { throw "Fant ikke pakken $Zip." }
if (-not $Sha256) {
  $sumFile = "$Zip.sha256"
  if (-not (Test-Path $sumFile)) { throw "Fant ikke $sumFile. Oppgi -Sha256." }
  $Sha256 = ((Get-Content $sumFile -Raw).Trim() -split "\s+")[0]
}
$actual = (Get-FileHash -Algorithm SHA256 -Path $Zip).Hash.ToLowerInvariant()
if ($actual -ne $Sha256.ToLowerInvariant()) {
  throw "Pakken har feil sjekksum ($actual). Forventet $Sha256. Ingenting er endret."
}
Write-Log "Sjekksum OK: $actual"

# 2. Version and extract next to the others
$archive = [System.IO.Compression.ZipFile]::OpenRead($Zip)
try {
  $top = ($archive.Entries | Select-Object -First 1).FullName.Split("/")[0]
} finally { $archive.Dispose() }
if ($top -notmatch "^cutcut-(.+)$") { throw "Ukjent pakke: toppmappen er «$top»." }
$Version = $Matches[1]
$Target = Join-Path $Versions $Version
Write-Log "Versjon $Version → $Target"

$Previous = Get-CurrentTarget
if ((Same-Path $Previous $Target) -and -not $Force) {
  throw "Versjon $Version kjører allerede. Bruk -Force for å installere den på nytt."
}
if ($DryRun) {
  Write-Log "[tørrkjøring] ville pakket ut, prøvd mot $Site, byttet current fra «$Previous» og startet $Service"
  exit 0
}
New-Item -ItemType Directory -Force -Path $Versions | Out-Null
if (Test-Path $Target) {
  if (-not $Force) { throw "$Target finnes allerede. Bruk -Force for å pakke ut på nytt." }
  if (Same-Path $Previous $Target) {
    throw "Kan ikke pakke ut over versjonen som kjører. Installer en annen versjon først."
  }
  Remove-Item -Recurse -Force $Target
}
$tmp = Join-Path $Versions ".tmp-$Version"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
[System.IO.Compression.ZipFile]::ExtractToDirectory($Zip, $tmp)
Move-Item (Join-Path $tmp $top) $Target
Remove-Item -Recurse -Force $tmp
Write-Log "Pakket ut"

# 3. Try the new version against the studio setup before anything changes
$py = Join-Path $Target "python\python.exe"
$probe = "import cutcut; from cutcut.common.config import load_site; s = load_site(r'$Site'); print(cutcut.__version__, s.devices.studio)"
$ErrorActionPreference = "Continue"  # Python's warnings on stderr are not failures
$out = (& $py -I -c $probe 2>&1 | Out-String).Trim()
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($code -ne 0) {
  Remove-Item -Recurse -Force $Target
  throw "Den nye versjonen kan ikke lese studio-oppsettet i ${Site}: $out. Ingenting er endret."
}
Write-Log "Studio-oppsettet leses av $Version ($out)"

# 4. Switch
if ($NoService -and -not (Get-Service $Service -ErrorAction SilentlyContinue)) {
  Set-Current $Target
  Write-Log "current → $Target. Tjenesten finnes ikke, og -NoService er satt: starter ikke."
  exit 0
}
Write-Log "Stopper $Service"
Stop-CutCut
if ((Test-Path $Current) -and -not (Get-Item $Current -Force).LinkType) {
  # first package on a PC set up from git (docs/studio/tjenester.md): keep it to go back to
  $moved = Join-Path $Versions ("git-{0:yyyyMMdd-HHmm}" -f (Get-Date))
  Move-Item $Current $moved
  $Previous = $moved
  Write-Log "Den gamle mappen $Current (git-utsjekk) er flyttet til $moved"
}
$ok = $false
try {
  Set-Current $Target
  Write-Log "current → $Target"
  Start-Version $Target
  # 5. Comes up, or goes back
  $ok = Wait-Version $Version $HealthSeconds
  if (-not $ok) { Write-Log "CutCut $Version svarte ikke innen $HealthSeconds s" }
} catch {
  Write-Log "Feil under bytte: $_"
}
if ($ok) {
  Write-Log "CutCut $Version svarer på /api/health"
} else {
  if (-not $Previous -or -not (Test-Path $Previous)) {
    Write-Log "Ingen forrige versjon å rulle tilbake til. Se $LogDir\service."
    exit 1
  }
  Write-Log "Ruller tilbake til $Previous"
  Stop-CutCut
  Set-Current $Previous
  Start-Version $Previous
  $prevVersion = try {
    (Get-Content (Join-Path $Previous "BUILD.json") -Raw | ConvertFrom-Json).version
  } catch { "" }
  if ($prevVersion -and (Wait-Version $prevVersion $HealthSeconds)) {
    Write-Log "Tilbake på $prevVersion, og den svarer. $Version er ikke tatt i bruk."
  } else {
    Write-Log "Tilbake på $Previous. Sjekk Helse i teknikervinduet."
  }
  exit 1
}

# 6. Keep the newest few
$keepPaths = @((Resolve-Path $Target).Path)
if ($Previous -and (Test-Path $Previous)) { $keepPaths += (Resolve-Path $Previous).Path }
$old = Get-ChildItem $Versions -Directory | Where-Object { $_.Name -notlike ".tmp-*" } |
  Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep
foreach ($dir in $old) {
  if ($keepPaths -contains $dir.FullName) { continue }
  Remove-Item -Recurse -Force $dir.FullName
  Write-Log "Fjernet gammel versjon $($dir.Name)"
}
Write-Log "Ferdig: CutCut $Version kjører."
exit 0
