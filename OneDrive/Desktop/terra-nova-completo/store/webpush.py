"""Web Push (RFC 8291 + VAPID) sem dependência extra além de cryptography."""
from __future__ import annotations

import base64
import json
import os
import struct
import time
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64url_decode(data: str) -> bytes:
    pad = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def load_vapid():
    env_pub = os.environ.get('VAPID_PUBLIC_KEY', '').strip()
    env_pem = os.environ.get('VAPID_PRIVATE_PEM', '').strip()
    if env_pub and env_pem:
        return env_pub, env_pem.replace('\\n', '\n')
    path = Path(settings.BASE_DIR) / 'terranova' / 'vapid.json'
    if path.exists():
        data = json.loads(path.read_text())
        return data['public_key'], data['private_pem']
    return '', ''


def public_key() -> str:
    return load_vapid()[0]


def _private_key():
    _, pem = load_vapid()
    if not pem:
        return None
    return serialization.load_pem_private_key(pem.encode(), password=None, backend=default_backend())


def _jwt(audience: str) -> str:
    key = _private_key()
    header = _b64url(json.dumps({'typ': 'JWT', 'alg': 'ES256'}, separators=(',', ':')).encode())
    payload = _b64url(json.dumps({
        'aud': audience,
        'exp': int(time.time()) + 12 * 3600,
        'sub': getattr(settings, 'VAPID_MAILTO', 'mailto:iris.p@example.org'),
    }, separators=(',', ':')).encode())
    signing = f'{header}.{payload}'.encode()
    sig = key.sign(signing, ec.ECDSA(hashes.SHA256()))
    # Convert DER signature to raw r||s (64 bytes) for ES256 JWT
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    r, s = decode_dss_signature(sig)
    raw = r.to_bytes(32, 'big') + s.to_bytes(32, 'big')
    return f'{header}.{payload}.{_b64url(raw)}'


def _uncompress(pub: ec.EllipticCurvePublicKey) -> bytes:
    nums = pub.public_numbers()
    return b'\x04' + nums.x.to_bytes(32, 'big') + nums.y.to_bytes(32, 'big')


def _encrypt(plaintext: bytes, p256dh: str, auth: str) -> bytes:
    receiver = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _b64url_decode(p256dh))
    ephemeral = ec.generate_private_key(ec.SECP256R1(), default_backend())
    shared = ephemeral.exchange(ec.ECDH(), receiver)
    as_pub = _uncompress(ephemeral.public_key())
    ua_pub = _b64url_decode(p256dh)
    auth_secret = _b64url_decode(auth)
    info = b'WebPush: info\x00' + ua_pub + as_pub
    ikm = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth_secret, info=info, backend=default_backend()).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt, info=b'Content-Encoding: aes128gcm\x00', backend=default_backend()).derive(ikm)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt, info=b'Content-Encoding: nonce\x00', backend=default_backend()).derive(ikm)
    # um registro: payload + delimitador 0x02
    body = AESGCM(cek).encrypt(nonce, plaintext + b'\x02', None)
    rs = struct.pack('!I', 4096)
    header = salt + rs + bytes([len(as_pub)]) + as_pub
    return header + body


def send_web_push(subscription: dict, payload: dict) -> tuple[int, str]:
    endpoint = subscription.get('endpoint') or ''
    keys = subscription.get('keys') or {}
    if not endpoint or not keys.get('p256dh') or not keys.get('auth'):
        raise ValueError('Inscrição de push incompleta.')
    pub, pem = load_vapid()
    if not pub or not pem:
        raise ValueError('Chaves VAPID ausentes.')
    from urllib.parse import urlparse
    parsed = urlparse(endpoint)
    audience = f'{parsed.scheme}://{parsed.netloc}'
    token = _jwt(audience)
    body = _encrypt(json.dumps(payload, ensure_ascii=False).encode(), keys['p256dh'], keys['auth'])
    req = urllib.request.Request(
        endpoint,
        data=body,
        method='POST',
        headers={
            'Authorization': f'vapid t={token}, k={pub}',
            'Content-Type': 'application/octet-stream',
            'Content-Encoding': 'aes128gcm',
            'TTL': '86400',
            'Urgency': 'normal',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode(errors='ignore')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors='ignore')
