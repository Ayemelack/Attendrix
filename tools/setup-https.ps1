param(
    [switch]$InstallCA
)

$ErrorActionPreference = "Stop"
$toolsDir = Split-Path -Parent $PSCommandPath
$projectDir = Split-Path -Parent $toolsDir
$certFile = Join-Path $toolsDir "cert.pem"
$keyFile  = Join-Path $toolsDir "key.pem"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Attendrix - HTTPS Certificate Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Ensure mkcert is installed
$mkcert = Get-Command "mkcert" -ErrorAction SilentlyContinue
if (-not $mkcert) {
    Write-Host "mkcert not found. Install via: winget install FiloSottile.mkcert" -ForegroundColor Yellow
    Write-Host "Or download from: https://github.com/FiloSottile/mkcert/releases" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] mkcert found: $($mkcert.Source)" -ForegroundColor Green

# 2. Install local CA (system trust)
if ($InstallCA -or -not (Test-Path "$env:USERPROFILE\.local-share\mkcert\rootCA.pem")) {
    Write-Host "Installing mkcert local Certificate Authority..." -ForegroundColor Cyan
    & mkcert -install
    if (-not $?) { Write-Host "Failed to install CA" -ForegroundColor Red; exit 1 }
    Write-Host "[OK] Local CA installed" -ForegroundColor Green
} else {
    Write-Host "[OK] Local CA already installed" -ForegroundColor Green
}

# 3. Detect LAN IPs
$lanIps = & py -c @"
import socket
ips = ['127.0.0.1']
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.1)
    s.connect(('10.255.255.255', 1))
    ips.append(s.getsockname()[0])
    s.close()
except: pass
try:
    hostname = socket.gethostname()
    for info in socket.getaddrinfo(hostname, None):
        ip = info[4][0]
        if ':' not in ip and not ip.startswith('127.') and not ip.startswith('169.254.') and ip not in ips:
            ips.append(ip)
except: pass
print(' '.join(ips))
"@

$ipList = $lanIps -split ' '
Write-Host "[OK] Detected IPs:" -ForegroundColor Green
foreach ($ip in $ipList) { Write-Host "     $ip" }

# 4. Generate certificates
$hostnames = @("localhost") + $ipList
Write-Host ""Generating certificate for: $($hostnames -join ', ')..."" -ForegroundColor Cyan
& mkcert -cert-file "$certFile" -key-file "$keyFile" $hostnames
if (-not $?) { Write-Host "Failed to generate certificate" -ForegroundColor Red; exit 1 }

Write-Host "" -ForegroundColor Green
Write-Host "[OK] Certificate: $certFile" -ForegroundColor Green
Write-Host "[OK] Private key:  $keyFile" -ForegroundColor Green

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
    if ($ip -ne '127.0.0.1') {
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
Write-Host "  1. Share rootCA.pem to your phone (AirDrop, email, etc.)" -ForegroundColor Yellow
Write-Host "     Root CA location:" -ForegroundColor Yellow
Write-Host "     $env:USERPROFILE\.local-share\mkcert\rootCA.pem" -ForegroundColor Yellow
Write-Host "  2. Open Settings > General > About > Certificate Trust Settings" -ForegroundColor Yellow
Write-Host "  3. Enable the 'mkcert' root certificate" -ForegroundColor Yellow
Write-Host "  4. Camera (getUserMedia) will work" -ForegroundColor Yellow
Write-Host ""
