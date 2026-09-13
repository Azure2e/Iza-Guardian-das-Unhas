"""Web Push (VAPID + aes128gcm) com a biblioteca cryptography."""

from __future__ import annotations

import base64
import json
import os
import struct
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from jwt import encode as jwt_encode

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
VAPID_FILE = DATA / "vapid.json"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    pad = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _public_raw(key) -> bytes:
    return key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )


def load_or_create_vapid() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    if VAPID_FILE.exists():
        return json.loads(VAPID_FILE.read_text("utf-8"))
    private = ec.generate_private_key(ec.SECP256R1())
    priv_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    pub_raw = _public_raw(private.public_key())
    payload = {
        "private_pem": priv_pem,
        "public": b64url(pub_raw),
        "subject": os.environ.get("VAPID_MAILTO", "mailto:admin@chat-aberto.local"),
    }
    VAPID_FILE.write_text(json.dumps(payload, indent=2), "utf-8")
    return payload


def public_key() -> str:
    return load_or_create_vapid()["public"]


def _encrypt(user_public_b64: str, auth_b64: str, plaintext: bytes) -> bytes:
    ua_pub_raw = b64url_decode(user_public_b64)
    auth = b64url_decode(auth_b64)
    ua_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub_raw)
    as_priv = ec.generate_private_key(ec.SECP256R1())
    as_pub_raw = _public_raw(as_priv.public_key())
    shared = as_priv.exchange(ec.ECDH(), ua_pub)

    prk_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=auth,
        info=b"WebPush: info\x00" + ua_pub_raw + as_pub_raw,
    ).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(
        algorithm=hashes.SHA256(),
        length=16,
        salt=salt,
        info=b"Content-Encoding: aes128gcm\x00",
    ).derive(prk_key)
    nonce = HKDF(
        algorithm=hashes.SHA256(),
        length=12,
        salt=salt,
        info=b"Content-Encoding: nonce\x00",
    ).derive(prk_key)

    # um registro: payload + delimitador 0x02
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    rs = 4096
    header = salt + struct.pack("!L", rs) + bytes([len(as_pub_raw)]) + as_pub_raw
    return header + ciphertext


def send_web_push(subscription: dict, payload: dict, ttl: int = 120) -> int:
    vapid = load_or_create_vapid()
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("inscrição inválida")

    body = _encrypt(keys["p256dh"], keys["auth"], json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    parsed = urlparse(endpoint)
    aud = f"{parsed.scheme}://{parsed.netloc}"
    token = jwt_encode(
        {
            "aud": aud,
            "exp": int(time.time()) + 12 * 3600,
            "sub": vapid.get("subject") or "mailto:admin@chat-aberto.local",
        },
        vapid["private_pem"],
        algorithm="ES256",
    )
    if isinstance(token, bytes):
        token = token.decode("ascii")

    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"vapid t={token}, k={vapid['public']}",
            "Content-Type": "application/octet-stream",
            "Content-Encoding": "aes128gcm",
            "TTL": str(ttl),
            "Urgency": "high",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
