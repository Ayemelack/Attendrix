param(
    [switch]$InstallCA
)

$ErrorActionPreference = "Stop"
$toolsDir = Split-Path -Parent $PSCommandPath
$projectDir = Split-Path -Parent $toolsDir
$certFile = Join-Path $toolsDir "cert.pem"
$keyFile  = Join-Path $toolsDir "key.pem"
$mkcertData = Join-Path $env:LOCALAPPDATA "mkcert"
$caPem = Join-Path $mkcertData "rootCA.pem"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Attendrix - HTTPS Certificate Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Ensure mkcert is installed
$mkcertPath = $null
$mkcert = Get-Command "mkcert" -ErrorAction SilentlyContinue
if ($mkcert) {
    $mkcertPath = $mkcert.Source
} else {
    # Common WinGet install location (not on PATH)
    $wingetPattern = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\FiloSottile.mkcert*\mkcert.exe"
    $matches = Get-ChildItem -Path $wingetPattern -ErrorAction SilentlyContinue
    if ($matches) {
        $mkcertPath = $matches[0].FullName
    }
}

if (-not $mkcertPath) {
    Write-Host "mkcert not found. Install via: winget install FiloSottile.mkcert" -ForegroundColor Yellow
    Write-Host "Or download from: https://github.com/FiloSottile/mkcert/releases" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] mkcert found: $mkcertPath" -ForegroundColor Green

# 2. Install local CA into system trust store (LocalMachine\Root)
if (-not $InstallCA) {
    $isAdmin = [Security.Principal.WindowsPrincipal]::new(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Host "NOTICE: CA installation requires Administrator privileges." -ForegroundColor Yellow
        Write-Host "Run this script with -InstallCA in an elevated prompt." -ForegroundColor Yellow
    }
}

# Check if CA is already trusted (LocalMachine\Root)
$caTrusted = $false
if (Test-Path $caPem) {
    $caThumbprint = (Get-PfxCertificate -FilePath $caPem).Thumbprint
    $found = Get-ChildItem -Path Cert:\LocalMachine\Root -Recurse |
        Where-Object { $_.Thumbprint -eq $caThumbprint }
    if ($found) { $caTrusted = $true }
}

if ($InstallCA) {
    Write-Host "Installing mkcert local Certificate Authority..." -ForegroundColor Cyan
    # Step 1: mkcert -install (creates/updates rootCA.pem if needed)
    & $mkcertPath -install *>$null
    # Step 2: manually add to LocalMachine\Root (mkcert -install without admin
    # only installs to CurrentUser\Root — insufficient for LAN access)
    if (Test-Path $caPem) {
        & certutil -addstore Root $caPem 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] CA installed to LocalMachine\Root" -ForegroundColor Green
        } else {
            Write-Host "[WARN] certutil failed. Try: Run 'certutil -addstore Root \"$caPem\"' manually as Admin" -ForegroundColor Yellow
        }
    }
    # Verify
    $caThumbprint = (Get-PfxCertificate -FilePath $caPem).Thumbprint
    $found = Get-ChildItem -Path Cert:\LocalMachine\Root -Recurse |
        Where-Object { $_.Thumbprint -eq $caThumbprint }
    if ($found) {
        Write-Host "[OK] CA is TRUSTED by system" -ForegroundColor Green
        $caTrusted = $true
    } else {
        Write-Host "[WARN] CA still not in LocalMachine\Root. Check admin rights." -ForegroundColor Yellow
    }
} else {
    if ($caTrusted) {
        Write-Host "[OK] CA is TRUSTED by system" -ForegroundColor Green
    } else {
        Write-Host "[WARN] CA not in LocalMachine\Root. Certificate will show browser warning." -ForegroundColor Yellow
    }
}

# 3. Detect LAN IPs (match gen_cert.py filtering — only interfaces with default gateway)
$lanIps = & powershell -NoProfile -Command @'
Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null } |
    Select-Object -ExpandProperty IPv4Address |
    Select-Object -ExpandProperty IPAddress
'@
$ipList = @("localhost")
$lanIps | ForEach-Object {
    $ip = $_.Trim()
    if ($ip -and ($ip -notmatch ':') -and ($ip -ne '127.0.0.1')) {
        $ipList += $ip
    }
}
# Fallback if PowerShell method returns nothing
if ($ipList.Count -le 1) {
    $lanIps = & py -c @"
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.1)
    s.connect(('10.255.255.255', 1))
    print(s.getsockname()[0])
    s.close()
except: pass
"@
    foreach ($ip in ($lanIps -split '\s+')) {
        if ($ip -and ($ip -notmatch ':') -and ($ip -ne '127.0.0.1')) {
            $ipList += $ip
        }
    }
}

Write-Host "[OK] Detected IPs:" -ForegroundColor Green
foreach ($ip in $ipList) {
    if ($ip -ne 'localhost') { Write-Host "     $ip" }
}

# 4. Generate certificates (only if missing)
$needRegen = $false
if (-not (Test-Path $certFile -PathType Leaf) -or -not (Test-Path $keyFile -PathType Leaf)) {
    $needRegen = $true
} else {
    # Check cert subjects include current IPs
    try {
        $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($certFile)
        $sanList = ($cert.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.17' }).Format($false)
        foreach ($ip in $ipList) {
            if ($ip -ne 'localhost' -and $sanList -notlike "*$ip*") {
                Write-Host "[INFO] New IP $ip not in existing cert - regenerating" -ForegroundColor Yellow
                $needRegen = $true
                break
            }
        }
    } catch {
        Write-Host "[WARN] Cannot validate existing cert - regenerating" -ForegroundColor Yellow
        $needRegen = $true
    }
}

if ($needRegen) {
    Write-Host "Generating certificate for: $($ipList -join ', ')" -ForegroundColor Cyan
    & $mkcertPath -cert-file "$certFile" -key-file "$keyFile" $ipList 2>$null
    if (-not $?) { Write-Host "Failed to generate certificate" -ForegroundColor Red; exit 1 }
    Write-Host "[OK] Certificate generated" -ForegroundColor Green
} else {
    Write-Host "[OK] Certificates are current (no regeneration needed)" -ForegroundColor Green
}

if ($caTrusted) {
    Write-Host "[OK] Certificate is TRUSTED by the system" -ForegroundColor Green
} else {
    Write-Host "[WARN] Certificate is NOT TRUSTED by the system" -ForegroundColor Yellow
    Write-Host "       Run this script as Administrator with -InstallCA flag" -ForegroundColor Yellow
}

# 5. Success info
Write-Host "" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  HTTPS Setup Complete!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start Attendrix with HTTPS:" -ForegroundColor White
Write-Host "  .\start-mobile.bat" -ForegroundColor Yellow
Write-Host ""
Write-Host "Access from mobile:" -ForegroundColor White
foreach ($ip in $ipList) {
    if ($ip -ne 'localhost') {
        Write-Host "  https://$($ip):5443" -ForegroundColor Yellow
    }
}
Write-Host ""
Write-Host "Mobile setup:" -ForegroundColor White
Write-Host "  1. Open the URL above on your phone" -ForegroundColor White
Write-Host "  2. Certificate is trusted (no warning) on" -ForegroundColor White
Write-Host "     Android Chrome + iOS Safari 13+" -ForegroundColor White
Write-Host ""
Write-Host "NOTE: For iOS Safari, you must also install" -ForegroundColor Yellow
Write-Host "the Root CA on your iPhone/iPad:" -ForegroundColor Yellow
Write-Host "  1. Share $caPem to your phone" -ForegroundColor Yellow
Write-Host "     (AirDrop, email, or host it at https://$($ipList[1]):5443/ca.crt)" -ForegroundColor Yellow
Write-Host "  2. Open Settings > General > About > Certificate Trust Settings" -ForegroundColor Yellow
Write-Host "  3. Enable the 'mkcert' root certificate" -ForegroundColor Yellow
Write-Host "  4. Camera (getUserMedia) will work" -ForegroundColor Yellow
Write-Host ""
