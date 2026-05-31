import os
import sys
import subprocess
import datetime
import ipaddress
import socket

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


def _find_mkcert():
    """Locate mkcert executable on PATH or common Windows locations."""
    try:
        result = subprocess.run(['where', 'mkcert'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            path = result.stdout.strip().split('\n')[0].strip()
            if path and os.path.isfile(path):
                return path
    except Exception:
        pass
    user_profile = os.environ.get('USERPROFILE', '')
    pattern = os.path.join(user_profile,
        'AppData', 'Local', 'Microsoft', 'WinGet', 'Packages',
        'FiloSottile.mkcert*', 'mkcert*.exe')
    import glob
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return None


def _mkcert_ca_thumbprint():
    """Read the mkcert root CA thumbprint."""
    caroot = os.environ.get('CAROOT',
        os.path.join(os.environ.get('APPDATA', ''), 'mkcert'))
    ca_path = os.path.join(caroot, 'rootCA.pem')
    mkcert_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'mkcert')
    alt_ca = os.path.join(mkcert_dir, 'rootCA.pem')
    for path in [ca_path, alt_ca]:
        if os.path.exists(path):
            try:
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.backends import default_backend
                with open(path, 'rb') as f:
                    ca = x509.load_pem_x509_certificate(f.read(), default_backend())
                ca_bytes = ca.public_bytes(serialization.Encoding.DER)
                import hashlib
                return hashlib.sha1(ca_bytes).hexdigest().upper()
            except Exception:
                pass
    return None


def _is_mkcert_ca_trusted():
    """Check if mkcert root CA is installed in Windows trust store."""
    thumbprint = _mkcert_ca_thumbprint()
    if not thumbprint:
        return False
    try:
        # Use single quotes around thumbprint to avoid cmd-line quote stripping
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             f'Get-ChildItem -Path Cert:\\LocalMachine\\Root, Cert:\\CurrentUser\\Root -Recurse | '
             f'Where-Object {{ $_.Thumbprint -eq \'{thumbprint}\' }} | '
             f'Measure-Object | Select-Object -ExpandProperty Count'],
            capture_output=True, text=True, timeout=10
        )
        count = result.stdout.strip()
        return count.isdigit() and int(count) > 0
    except Exception:
        return False


def _install_mkcert_ca():
    """Install mkcert CA into Windows trust store via admin elevation."""
    mkcert = _find_mkcert()
    if not mkcert:
        return False
    # Try without elevation first (may work on some systems)
    try:
        subprocess.run([mkcert, '-install'], capture_output=True, timeout=30)
    except Exception:
        pass
    if _is_mkcert_ca_trusted():
        return True
    # If not trusted, attempt with admin elevation via certutil
    caroot = os.environ.get('CAROOT',
        os.path.join(os.environ.get('APPDATA', ''), 'mkcert'))
    alt_caroot = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'mkcert')
    for dr in [caroot, alt_caroot]:
        ca_pem = os.path.join(dr, 'rootCA.pem')
        if os.path.exists(ca_pem):
            try:
                subprocess.run(
                    ['certutil', '-addstore', 'Root', ca_pem],
                    capture_output=True, timeout=30
                )
            except Exception:
                pass
            break
    return _is_mkcert_ca_trusted()


def generate_mkcert_certs(cert_path, key_path):
    """Generate locally-trusted certs using mkcert.

    Returns (success: bool, trusted: bool) where trusted indicates
    whether the CA is installed in the Windows trust store.
    """
    mkcert = _find_mkcert()
    if not mkcert:
        return (False, False)
    # Ensure CA is installed (best effort — may need admin)
    subprocess.run([mkcert, '-install'], capture_output=True, timeout=30)
    trusted = _is_mkcert_ca_trusted()
    lan_ips = get_lan_ips()
    hosts = ['localhost'] + lan_ips
    try:
        result = subprocess.run(
            [mkcert, '-cert-file', cert_path, '-key-file', key_path] + hosts,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f'  mkcert certificate generated for: {", ".join(hosts)}')
            if trusted:
                print(f'  Certificate source: mkcert')
                print(f'  Status: TRUSTED')
            else:
                print(f'  Certificate source: mkcert')
                print(f'  Status: NOT TRUSTED — CA not in Windows trust store')
                print(f'  Run: start-mobile.bat as Administrator to install the CA')
            return (True, trusted)
    except Exception:
        pass
    return (False, False)


def get_lan_ips():
    """Detect LAN IP addresses reachable from other devices (Wi-Fi/Ethernet only).

    Filters out virtual adapters (VMware, Docker, WSL, VPN) by only returning
    IPs from interfaces that have a default gateway.
    """
    ips = set()
    # Method 1 (preferred): use PowerShell to find interfaces with a default gateway.
    # This automatically excludes VMware, Docker, WSL, VPN virtual adapters.
    try:
        ps_cmd = (
            'Get-NetIPConfiguration | '
            'Where-Object { $_.IPv4DefaultGateway -ne $null } | '
            'Select-Object -ExpandProperty IPv4Address | '
            'Select-Object -ExpandProperty IPAddress'
        )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                ip = line.strip()
                if ip and ':' not in ip:
                    ips.add(ip)
    except Exception:
        pass
    # Method 2: fallback — connect to a dummy UDP address to find the default interface IP
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
            s.close()
        except Exception:
            pass
    # Method 3: resolve hostname and filter out virtual ranges
    if not ips:
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                ip = info[4][0]
                if ':' not in ip and not ip.startswith('127.') and not ip.startswith('169.254.'):
                    ips.add(ip)
        except Exception:
            pass
    return sorted(ips)


def generate_self_signed_cert(cert_path, key_path):
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Attendrix Dev"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    sans = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]

    lan_ips = get_lan_ips()
    for ip_str in lan_ips:
        sans.append(x509.IPAddress(ipaddress.IPv4Address(ip_str)))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(sans),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256(), backend=default_backend())
    )

    os.makedirs(os.path.dirname(cert_path), exist_ok=True)

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"  SSL certificate: {cert_path}")
    print(f"  Private key:     {key_path}")
    if lan_ips:
        print(f"  LAN IPs included in cert: {', '.join(lan_ips)}")


def cert_has_current_lan_ips(cert_path):
    """Check if existing cert includes all current LAN IPs."""
    try:
        with open(cert_path, 'rb') as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        current_lan_ips = set(get_lan_ips())
        if not current_lan_ips:
            return True
        try:
            san_ext = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            cert_ips = set()
            for san in san_ext.value:
                if isinstance(san, x509.IPAddress):
                    ip_str = str(san.value)
                    if not ip_str.startswith('127.'):
                        cert_ips.add(ip_str)
            return current_lan_ips.issubset(cert_ips)
        except x509.ExtensionNotFound:
            return False
    except Exception:
        return False


def ensure_cert_files(cert_path, key_path):
    """Ensure valid mkcert certificate exists. Returns True if ready.

    Uses mkcert ONLY — self-signed fallback is removed to prevent
    certificate ambiguity and browser trust errors.
    If mkcert is not available or the CA is not trusted, prints
    a clear error and returns False (server startup should abort).
    """
    if not _find_mkcert():
        print("  ERROR: mkcert not found. Install it: winget install FiloSottile.mkcert")
        print("  Then run: start-mobile.bat as Administrator")
        return False

    # Generate certs if missing or IPs changed
    if not (os.path.exists(cert_path) and os.path.exists(key_path)):
        print("  Generating mkcert certificate...")
        success, trusted = generate_mkcert_certs(cert_path, key_path)
        if not success:
            print("  ERROR: Failed to generate mkcert certificate")
            return False
        if not trusted:
            print("  ERROR: mkcert CA not installed in Windows trust store.")
            print("  Run this script as Administrator once: start-mobile.bat")
            return False
        lan_ips = get_lan_ips()
        if lan_ips:
            print(f"  Certificate valid for IPs: {', '.join(lan_ips)}")
        return True
    else:
        # Existing certs — validate they are from mkcert (not self-signed)
        try:
            from cryptography.hazmat.backends import default_backend
            with open(cert_path, 'rb') as f:
                cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            # mkcert-signed certs have issuer != subject
            is_mkcert = cert.issuer != cert.subject
            if not is_mkcert:
                print("  Existing certificate is self-signed. Regenerating with mkcert...")
                os.remove(cert_path)
                os.remove(key_path)
                return ensure_cert_files(cert_path, key_path)
        except Exception:
            pass

        # Check CA is trusted
        trusted = _is_mkcert_ca_trusted()
        if not trusted:
            print("  WARNING: mkcert CA not in Windows trust store.")
            print("  Run start-mobile.bat as Administrator once to install.")
            print("  Continuing anyway — browser will show security warning.")
        else:
            print("  Certificate source: mkcert")
            print("  Status: TRUSTED")

        if cert_has_current_lan_ips(cert_path):
            lan_ips = get_lan_ips()
            if lan_ips:
                print(f"  Certificate valid for LAN IPs: {', '.join(lan_ips)}")
            return True
        print("  LAN IPs changed. Regenerating certificate...")
        os.remove(cert_path)
        os.remove(key_path)
        return ensure_cert_files(cert_path, key_path)


if __name__ == "__main__":
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(tools_dir, "cert.pem")
    key_path = os.path.join(tools_dir, "key.pem")
    ensure_cert_files(cert_path, key_path)
