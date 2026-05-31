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
    # Common WinGet install location
    user_profile = os.environ.get('USERPROFILE', '')
    pattern = os.path.join(user_profile,
        'AppData', 'Local', 'Microsoft', 'WinGet', 'Packages',
        'FiloSottile.mkcert*', 'mkcert*.exe')
    import glob
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return None


def generate_mkcert_certs(cert_path, key_path):
    """Generate locally-trusted certs using mkcert."""
    mkcert = _find_mkcert()
    if not mkcert:
        return False
    # Ensure mkcert CA is installed
    subprocess.run([mkcert, '-install'], capture_output=True, timeout=30)
    lan_ips = get_lan_ips()
    hosts = ['localhost'] + lan_ips
    try:
        result = subprocess.run(
            [mkcert, '-cert-file', cert_path, '-key-file', key_path] + hosts,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f'  mkcert certificate generated for: {", ".join(hosts)}')
            print(f'  Trusted by the system (no browser warning)')
            return True
    except Exception:
        pass
    return False


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
    # Prefer mkcert (system-trusted certs) over self-signed
    if _find_mkcert():
        if not (os.path.exists(cert_path) and os.path.exists(key_path)):
            print("  mkcert found — generating locally-trusted certificate...")
            if generate_mkcert_certs(cert_path, key_path):
                lan_ips = get_lan_ips()
                if lan_ips:
                    print(f"  Certificate valid for IPs: {', '.join(lan_ips)}")
                return True
            print("  mkcert generation failed, falling back to self-signed...")
        else:
            lan_ips = get_lan_ips()
            if lan_ips:
                print(f"  Certificate valid for LAN IPs: {', '.join(lan_ips)}")
            return True
    else:
        print("  mkcert not found — using self-signed certificate (browser warning will appear)")

    # Fallback: self-signed certificate
    if os.path.exists(cert_path) and os.path.exists(key_path):
        if cert_has_current_lan_ips(cert_path):
            lan_ips = get_lan_ips()
            if lan_ips:
                print(f"  Certificate valid for LAN IPs: {', '.join(lan_ips)}")
            return True
        print("  LAN IPs changed. Regenerating self-signed certificate...")
    else:
        print("  Generating self-signed SSL certificate...")
    try:
        generate_self_signed_cert(cert_path, key_path)
        return True
    except Exception as e:
        print(f"  ERROR: Failed to generate certificate: {e}")
        print("  Make sure 'cryptography' is installed: pip install cryptography")
        return False


if __name__ == "__main__":
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(tools_dir, "cert.pem")
    key_path = os.path.join(tools_dir, "key.pem")
    ensure_cert_files(cert_path, key_path)
