<#
.SYNOPSIS
  Gjør regi-PC-en klar som kiosk for touch-skjermen (SO-6, spesifikasjonen 8.2 og 9.2).

.DESCRIPTION
  Kjøres som administrator i servicevinduet. Kan kjøres på nytt, og endrer bare det som avviker.
  1. Lokal bruker «cutcut-kiosk» uten administratorrett (passord du velger, ikke i git).
  2. Automatisk innlogging for den brukeren etter omstart (-AutoLogon). Passordet lagres
     da i Windows-registeret; bruk heller Sysinternals Autologon hvis Multimediesenteret krever det (Q8).
  3. Oppgaven «CutCut kiosk-vakt» i Oppgaveplanlegger: starter kiosk-vakt.ps1 når brukeren
     logger inn, og på nytt hvis den stopper. Vakten starter Edge i kiosk-modus og laster
     touch-siden på nytt hvis den henger.
  Tjenesten CutCut (install-services.ps1) kjører uavhengig av dette, også uten innlogging.

.EXAMPLE
  .\installer\kiosk\setup-kiosk.ps1 -Password (Read-Host -AsSecureString) -AutoLogon
.EXAMPLE
  .\installer\kiosk\setup-kiosk.ps1 -DryRun
#>
[CmdletBinding()]
param(
  [string]$User = "cutcut-kiosk",
  [securestring]$Password,
  [string]$Url = "http://127.0.0.1:8080/touch/",
  [switch]$AutoLogon,
  [string]$GuardDir = "C:\CutCut\kiosk",
  [switch]$Remove,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3
$TaskName = "CutCut kiosk-vakt"
$Winlogon = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

function Say([string]$t) { Write-Host "  $t" }
function Invoke-Step([string]$what, [scriptblock]$action) {
  if ($DryRun) { Say "[tørrkjøring] $what"; return }
  Say $what
  & $action
}

Write-Host "CutCut Studio · kiosk for touch-skjermen"

if ($Remove) {
  Invoke-Step "Fjerner oppgaven $TaskName" {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  }
  Invoke-Step "Slår av automatisk innlogging" {
    Set-ItemProperty -Path $Winlogon -Name AutoAdminLogon -Value "0"
    Remove-ItemProperty -Path $Winlogon -Name DefaultPassword -ErrorAction SilentlyContinue
  }
  Say "Brukeren $User er beholdt (fjern med Remove-LocalUser hvis ønsket)."
  exit 0
}

# 1. The kiosk user
$existing = Get-LocalUser -Name $User -ErrorAction SilentlyContinue
if (-not $existing) {
  if (-not $Password -and -not $DryRun) { throw "Ny bruker: oppgi -Password." }
  Invoke-Step "Lager brukeren $User (vanlig bruker)" {
    New-LocalUser -Name $User -Password $Password -FullName "CutCut kiosk" `
      -Description "Touch-skjermen i podkaststudioet" -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    Add-LocalGroupMember -Group (Get-LocalGroup -SID "S-1-5-32-545") -Member $User
  }
} else {
  Say "Brukeren $User finnes."
  if ($Password) { Invoke-Step "Setter nytt passord" { Set-LocalUser -Name $User -Password $Password } }
}

# 2. Automatic login
if ($AutoLogon) {
  if (-not $Password -and -not $DryRun) { throw "-AutoLogon krever -Password." }
  Invoke-Step "Automatisk innlogging som $User" {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
      [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password))
    Set-ItemProperty -Path $Winlogon -Name AutoAdminLogon -Value "1"
    Set-ItemProperty -Path $Winlogon -Name DefaultUserName -Value $User
    Set-ItemProperty -Path $Winlogon -Name DefaultDomainName -Value $env:COMPUTERNAME
    Set-ItemProperty -Path $Winlogon -Name DefaultPassword -Value $plain
  }
}

# 3. The guard, started at the kiosk user's logon and restarted if it stops
Invoke-Step "Kopierer kiosk-vakt.ps1 til $GuardDir" {
  New-Item -ItemType Directory -Force -Path $GuardDir | Out-Null
  Copy-Item -Force (Join-Path $PSScriptRoot "kiosk-vakt.ps1") (Join-Path $GuardDir "kiosk-vakt.ps1")
}
Invoke-Step "Registrerer oppgaven «$TaskName»" {
  $script = Join-Path $GuardDir "kiosk-vakt.ps1"
  $action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" -Url `"$Url`""
  $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\$User"
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew
  $principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$User" -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null
}

Write-Host "Ferdig. Logg inn som $User (eller start PC-en på nytt med -AutoLogon) for å se touch-skjermen."
Write-Host "Vaktens logg: C:\Users\$User\AppData\Local\CutCut\kiosk-vakt.log"
