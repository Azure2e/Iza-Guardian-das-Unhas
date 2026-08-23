"""
Módulo PIX — gera payload EMV (BR Code) compatível com bancos brasileiros.
Recebe a chave por parâmetro (injeção), sem ler o ambiente diretamente.
"""
from __future__ import annotations

import re
import secrets


def _tlv(tag: str, value: str) -> str:
    value = value or ""
    return f"{tag}{len(value):02d}{value}"


def _crc16(payload: str) -> str:
    crc = 0xFFFF
    for ch in payload.encode("utf-8"):
        crc ^= ch << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _clean(text: str, max_len: int) -> str:
    text = re.sub(r"[^A-Za-z0-9 .]", "", (text or "").upper())
    return text[:max_len] or "LOJA"


def make_txid(order_id: int) -> str:
    base = f"ENC{order_id:06d}{secrets.token_hex(6).upper()}"
    return re.sub(r"[^A-Z0-9]", "", base)[:25]


def build_pix_payload(
    *,
    amount: float,
    txid: str,
    key: str,
    merchant: str = "Encanto Gelato",
    city: str = "SAO PAULO",
    description: str = "",
) -> str:
    """Gera o código copia-e-cola (EMV) do PIX com valor fixo."""
    key = (key or "").strip()
    if not key:
        raise ValueError("Chave PIX não configurada. Defina PIX_KEY no .env")

    merchant = _clean(merchant, 25)
    city = _clean(city, 15)
    txid = re.sub(r"[^A-Za-z0-9]", "", txid or "***")[:25] or "***"
    amount_str = f"{float(amount):.2f}"
    desc = (description or "")[:50]

    merchant_account = _tlv("00", "br.gov.bcb.pix") + _tlv("01", key)
    if desc:
        merchant_account += _tlv("02", desc)

    additional = _tlv("05", txid)

    payload = (
        _tlv("00", "01")
        + _tlv("01", "12")
        + _tlv("26", merchant_account)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("54", amount_str)
        + _tlv("58", "BR")
        + _tlv("59", merchant)
        + _tlv("60", city)
        + _tlv("62", additional)
        + "6304"
    )
    return payload + _crc16(payload)
