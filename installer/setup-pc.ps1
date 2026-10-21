<#
.SYNOPSIS
  Sjekker (og med -Fix retter) Windows-oppsettet på regi-PC-en (SO-5, spesifikasjonen 9.2).

.DESCRIPTION
  Hvert punkt får grønt, gult eller rødt, med hva som er funnet. Uten -Fix endres ingenting.
  Med -Fix rettes det som trygt kan rettes lokalt: strøm, USB-strømsparing, rask oppstart,
  skjermsparer, Windows Update-tider, tidstjeneste og brannmur. Nettverk (fast IP), drivere,
  BIOS og UPS sjekkes bare: de settes opp for hånd. Kan kjøres så ofte man vil.
  Om NTNU tillater lokale endringer på en administrert PC, avgjøres av Q8.

  Rapporten skrives som Markdown og JSON (samme format som maskintestene) og kan limes inn i
  GitHub-issuet SO-5.

.EXAMPLE
  .\installer\setup-pc.ps1                       # bare sjekk
.EXAMPLE
  .\installer\setup-pc.ps1 -Fix -NtpServer ntp.ntnu.no -AllowFrom 10.10.10.0/24
#>
[CmdletBinding()]
param(
  [switch]$Fix,
  [string]$NtpServer = "",
  [string]$AllowFrom = "LocalSubnet",
  [int]$Port = 8080,
  [int]$ActiveFrom = 6,
  [int]$ActiveTo = 23,
  [string]$Out = "C:\CutCut\data\hwtest",
  [string]$VersionsYaml = ""
)

# Continue, not Stop: Windows PowerShell 5.1 turns a native tool's stderr (powercfg, w32tm)
# into a terminating error under Stop. Every check reads back what it set instead.
$ErrorActionPreference = "Continue"
Set-StrictMode -Version 3
$results = New-Object System.Collections.Generic.List[object]
$icon = @{ ok = "✅"; advarsel = "⚠️"; feil = "❌"; manuelt = "📝" }

function Add-Result([string]$id, [string]$title, [string]$result, [string]$text, $details = $null) {
  $results.Add([pscustomobject]@{ id = $id; title = $title; result = $result; summary = $text; details = $details })
  Write-Host ("  {0} {1} {2}: {3}" -f $icon[$result], $id, $title, $text)
}

function Get-PowerValue([string]$sub, [string]$setting) {
  $out = powercfg /query SCHEME_CURRENT $sub $setting 2>$null | Out-String
  if ($out -match "Current AC Power Setting Index:\s+0x([0-9a-fA-F]+)") { return [Convert]::ToInt32($Matches[1], 16) }
  if ($out -match "Gjeldende indeks for innstilling for vekselstr\S*:\s+0x([0-9a-fA-F]+)") { return [Convert]::ToInt32($Matches[1], 16) }
  return $null
}

function Get-Reg([string]$path, [string]$name) {
  try { return (Get-ItemProperty -Path $path -Name $name -ErrorAction Stop).$name } catch { return $null }
}

function Set-Reg([string]$path, [string]$name, $value, [string]$type = "DWord") {
  if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
  New-ItemProperty -Path $path -Name $name -Value $value -PropertyType $type -Force | Out-Null
}

Write-Host ("CutCut Studio · Windows-oppsett (9.2) · {0}" -f $(if ($Fix) { "sjekk og rett" } else { "bare sjekk" }))

# P1 Power: never sleep, never hibernate, screen always on, high performance
$sleep = Get-PowerValue "SUB_SLEEP" "STANDBYIDLE"
$hib = Get-PowerValue "SUB_SLEEP" "HIBERNATEIDLE"
$screen = Get-PowerValue "SUB_VIDEO" "VIDEOIDLE"
if ($Fix -and (($sleep -ne 0) -or ($hib -ne 0) -or ($screen -ne 0))) {
  powercfg /change standby-timeout-ac 0 | Out-Null
  powercfg /change hibernate-timeout-ac 0 | Out-Null
  powercfg /change monitor-timeout-ac 0 | Out-Null
  powercfg /hibernate off 2>$null | Out-Null
  $sleep = Get-PowerValue "SUB_SLEEP" "STANDBYIDLE"; $hib = Get-PowerValue "SUB_SLEEP" "HIBERNATEIDLE"; $screen = Get-PowerValue "SUB_VIDEO" "VIDEOIDLE"
}
$d = @{ sleep_s = $sleep; hibernate_s = $hib; screen_off_s = $screen }
if ($sleep -eq 0 -and $hib -eq 0 -and $screen -eq 0) { Add-Result "P1" "Strøm" "ok" "Aldri hvile, dvale eller skjerm av" $d }
else { Add-Result "P1" "Strøm" "feil" "PC-en kan gå i hvile eller slå av skjermen (kjør med -Fix)" $d }

# P2 USB selective suspend off (RØDECaster, card reader, touch)
$usbSub = "2a737441-1930-4402-8d77-b2bebba308a3"; $usbSet = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"
$usb = Get-PowerValue $usbSub $usbSet
if ($Fix -and $usb -ne 0 -and $null -ne $usb) {
  powercfg /setacvalueindex SCHEME_CURRENT $usbSub $usbSet 0 | Out-Null
  powercfg /setactive SCHEME_CURRENT | Out-Null
  $usb = Get-PowerValue $usbSub $usbSet
}
if ($usb -eq 0) { Add-Result "P2" "USB-strømsparing" "ok" "Av" }
elseif ($null -eq $usb) { Add-Result "P2" "USB-strømsparing" "advarsel" "Innstillingen finnes ikke i strømplanen" }
else { Add-Result "P2" "USB-strømsparing" "feil" "På: RØDECaster kan bli slått av (kjør med -Fix)" }

# P3 Fast startup off (a real restart after power loss and updates)
$hiberboot = Get-Reg "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power" "HiberbootEnabled"
if ($Fix -and $hiberboot -ne 0) {
  Set-Reg "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power" "HiberbootEnabled" 0
  $hiberboot = 0
}
if ($hiberboot -eq 0) { Add-Result "P3" "Rask oppstart" "ok" "Av" }
else { Add-Result "P3" "Rask oppstart" "advarsel" "På: kan gi halvveis oppstart etter strømbrudd (kjør med -Fix)" }

# P4 Screen saver off for every user (policy)
$ssPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Control Panel\Desktop"
$ss = Get-Reg $ssPath "ScreenSaveActive"
if ($Fix -and $ss -ne "0") { Set-Reg $ssPath "ScreenSaveActive" "0" "String"; $ss = "0" }
if ($ss -eq "0") { Add-Result "P4" "Skjermsparer" "ok" "Av for alle brukere" }
else { Add-Result "P4" "Skjermsparer" "advarsel" "Ikke låst av (kjør med -Fix)" }

# P5 Windows Update: active hours, no automatic restart while someone is logged in
$ux = "HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
$au = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
if ($Fix) {
  Set-Reg $ux "ActiveHoursStart" $ActiveFrom
  Set-Reg $ux "ActiveHoursEnd" $ActiveTo
  Set-Reg $au "NoAutoRebootWithLoggedOnUsers" 1
}
$s1 = Get-Reg $ux "ActiveHoursStart"; $s2 = Get-Reg $ux "ActiveHoursEnd"; $nr = Get-Reg $au "NoAutoRebootWithLoggedOnUsers"
$d = @{ active_from = $s1; active_to = $s2; no_auto_reboot = $nr }
if ($s1 -eq $ActiveFrom -and $s2 -eq $ActiveTo -and $nr -eq 1) {
  Add-Result "P5" "Windows Update" "ok" "Aktive timer $ActiveFrom–$ActiveTo, ingen automatisk omstart med innlogget bruker" $d
} else { Add-Result "P5" "Windows Update" "advarsel" "Kan starte PC-en på nytt i åpningstiden (kjør med -Fix; Q8, Q30)" $d }

# P6 Time: the time service runs and syncs
$svc = Get-Service w32time -ErrorAction SilentlyContinue
if ($Fix -and $svc) {
  Set-Service w32time -StartupType Automatic
  if ($svc.Status -ne "Running") { Start-Service w32time }
  if ($NtpServer) {
    w32tm /config /manualpeerlist:$NtpServer /syncfromflags:manual /update | Out-Null
    w32tm /resync /nowait | Out-Null
  }
  $svc = Get-Service w32time
}
$status = (w32tm /query /status 2>$null | Out-String)
$source = if ($status -match "Source:\s*(.+)") { $Matches[1].Trim() } else { "ukjent" }
$d = @{ service = if ($svc) { [string]$svc.Status } else { "mangler" }; source = $source }
if ($svc -and $svc.Status -eq "Running" -and $source -notmatch "Local CMOS|Free-running") {
  Add-Result "P6" "Klokke (NTP)" "ok" "Tidstjenesten kjører, kilde $source" $d
} else { Add-Result "P6" "Klokke (NTP)" "advarsel" "Klokka synkroniseres ikke (kilde $source). Kjør med -Fix -NtpServer …" $d }

# P7 Firewall: the screens and monitoring reach port 8080 from the studio network only
$ruleName = "CutCut Studio $Port"
$rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($Fix -and -not $rule) {
  New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port `
    -RemoteAddress $AllowFrom -Action Allow -Profile Any | Out-Null
  $rule = Get-NetFirewallRule -DisplayName $ruleName
}
if ($rule) { Add-Result "P7" "Brannmur" "ok" "Port $Port åpen fra $AllowFrom (Companion bare på 127.0.0.1)" }
else { Add-Result "P7" "Brannmur" "advarsel" "Ingen regel for port ${Port}: teknikervinduet nås bare fra PC-en selv (kjør med -Fix)" }

# P8 Network: fixed IP (checked, never changed here)
$ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" })
$dhcp = @($ips | Where-Object { $_.PrefixOrigin -eq "Dhcp" })
$d = @{ addresses = @($ips | ForEach-Object { "{0} ({1}, {2})" -f $_.IPAddress, $_.InterfaceAlias, $_.PrefixOrigin }) }
if ($ips.Count -eq 0) { Add-Result "P8" "Nett" "feil" "Ingen IPv4-adresse" $d }
elseif ($dhcp.Count -gt 0) { Add-Result "P8" "Nett" "advarsel" "DHCP på $($dhcp[0].InterfaceAlias): studio-nettet bør ha fast IP (settes for hånd, 2.6)" $d }
else { Add-Result "P8" "Nett" "ok" ("Fast IP: " + (($ips | ForEach-Object { $_.IPAddress }) -join ", ")) $d }

# P9 Services and kiosk (SO-2, SO-6)
$cut = Get-Service CutCut -ErrorAction SilentlyContinue
$task = Get-ScheduledTask -TaskName "CutCut kiosk-vakt" -ErrorAction SilentlyContinue
$d = @{ service = if ($cut) { "$($cut.Status), $($cut.StartType)" } else { "mangler" }; kiosk_task = [bool]$task }
if ($cut -and $cut.StartType -eq "Automatic" -and $task) { Add-Result "P9" "Tjenester og kiosk" "ok" "CutCut starter automatisk ($($cut.Status)), kiosk-vakten er registrert" $d }
else { Add-Result "P9" "Tjenester og kiosk" "advarsel" "Kjør installer\install-services.ps1 og installer\kiosk\setup-kiosk.ps1" $d }

# P10 Drivers (noted, never changed)
$gpu = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | ForEach-Object { "{0} {1}" -f $_.Name, $_.DriverVersion })
$apps = @(Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
  Where-Object { $_.PSObject.Properties["DisplayName"] -and $_.DisplayName -match "R(Ø|O)DE|Companion|Edge|ASIO" } |
  ForEach-Object { "{0} {1}" -f $_.DisplayName, $(if ($_.PSObject.Properties["DisplayVersion"]) { $_.DisplayVersion } else { "" }) })
$rode = @($apps | Where-Object { $_ -match "R(Ø|O)DE" })
$d = @{ gpu = $gpu; software = $apps }
if ($rode.Count -gt 0) { Add-Result "P10" "Drivere" "ok" ("Notert: " + (($rode + $gpu) -join "; ")) $d }
else { Add-Result "P10" "Drivere" "advarsel" "Fant ikke RØDE-driveren (RØDE Central/ASIO)" $d }
if ($VersionsYaml) {
  $lines = @("# Drivere og programvare på regi-PC-en, notert av setup-pc.ps1 $(Get-Date -Format 'yyyy-MM-dd') (9.2).", "schema_version: 1", "gpu:")
  $lines += $gpu | ForEach-Object { "  - `"$_`"" }
  $lines += "software:"
  $lines += $apps | ForEach-Object { "  - `"$_`"" }
  Set-Content -Path $VersionsYaml -Value $lines -Encoding UTF8
  Write-Host "  Skrev $VersionsYaml"
}

# P11 UPS
$ups = @(Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue)
if ($ups.Count -gt 0) { Add-Result "P11" "UPS" "ok" "UPS/batteri sett av Windows: $($ups[0].Name)" }
else { Add-Result "P11" "UPS" "advarsel" "Ingen UPS koblet til med USB: ved strømbrudd stopper PC-en brått (Q31)" }

# P12 BIOS (cannot be read from Windows)
Add-Result "P12" "BIOS" "manuelt" "Sjekk for hånd: «Power on after AC loss» = på, så PC-en starter selv etter strømbrudd"

# Report
$worst = if ($results | Where-Object { $_.result -eq "feil" }) { "feil" } elseif ($results | Where-Object { $_.result -eq "advarsel" }) { "advarsel" } else { "ok" }
$stamp = Get-Date
$os = Get-CimInstance Win32_OperatingSystem
$md = @("## Windows-oppsett (9.2) $($icon[$worst])", "", ("Kjørt {0:yyyy-MM-dd HH:mm} · {1} {2} · {3} · {4}" -f $stamp, $os.Caption, $os.Version, $env:COMPUTERNAME, $(if ($Fix) { "med -Fix" } else { "bare sjekk" })), "", "| Punkt | Resultat | Hva vi fant |", "| --- | --- | --- |")
foreach ($r in $results) { $md += "| {0} {1} | {2} {3} | {4} |" -f $r.id, $r.title, $icon[$r.result], $r.result, ($r.summary -replace "\|", "\|") }
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$base = Join-Path $Out ("{0:yyyyMMdd-HHmm}-windows" -f $stamp)
Set-Content -Path "$base.md" -Value $md -Encoding UTF8
@{ name = "windows"; started = $stamp.ToString("s"); result = $worst; fix = [bool]$Fix; steps = $results } |
  ConvertTo-Json -Depth 6 | Set-Content -Path "$base.json" -Encoding UTF8
Write-Host ""
Write-Host "Rapport: $base.md (lim inn i GitHub-issue SO-5) og $base.json"
if ($worst -eq "feil") { exit 1 } else { exit 0 }
