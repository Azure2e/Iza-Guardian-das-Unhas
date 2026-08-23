"""
Configuração central — carrega .env e expõe chaves para o app (injeção de dependência).
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path


def load_dotenv(path: Path | None = None) -> None:
    env = path or Path(__file__).resolve().parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Config:
    """Objeto injetável com todas as chaves de ambiente."""

    def __init__(self, env_file: Path | None = None):
        load_dotenv(env_file)
        self.secret_key = os.environ.get("ENCANTO_SECRET_KEY") or secrets.token_hex(32)
        self.admin_pass = os.environ.get("ENCANTO_ADMIN_PASS", "Encanto@2026")
        self.caixa_pass = os.environ.get("ENCANTO_CAIXA_PASS", "Caixa@2026")
        self.pix_key = os.environ.get("PIX_KEY", "").strip()
        self.pix_merchant = os.environ.get("PIX_MERCHANT_NAME", "Encanto Gelato").strip()
        self.pix_city = os.environ.get("PIX_CITY", "SAO PAULO").strip()

    @property
    def pix_configured(self) -> bool:
        return bool(self.pix_key)

    def as_pix_dict(self) -> dict:
        return {
            "key": self.pix_key,
            "merchant": self.pix_merchant,
            "city": self.pix_city,
            "configured": self.pix_configured,
        }
