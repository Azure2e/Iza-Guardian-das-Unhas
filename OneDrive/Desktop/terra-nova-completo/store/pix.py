"""Geração de payload PIX (EMV BR Code) para QR Code."""
from __future__ import annotations

import hashlib
from decimal import Decimal


def _tlv(id_: str, value: str) -> str:
    return f'{id_}{len(value):02d}{value}'


def _crc16(payload: str) -> str:
    crc = 0xFFFF
    for ch in payload.encode('utf-8'):
        crc ^= ch << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f'{crc:04X}'


def build_pix_payload(key: str, name: str, city: str, amount: Decimal, txid: str) -> str:
    name = name[:25]
    city = city[:15]
    merchant_account = _tlv('00', 'BR.GOV.BCB.PIX') + _tlv('01', key)
    additional = _tlv('05', txid[:25])
    payload = (
        _tlv('00', '01')
        + _tlv('26', merchant_account)
        + _tlv('52', '0000')
        + _tlv('53', '986')
        + _tlv('54', f'{amount:.2f}')
        + _tlv('58', 'BR')
        + _tlv('59', name)
        + _tlv('60', city)
        + _tlv('62', additional)
        + '6304'
    )
    return payload + _crc16(payload)


def make_txid(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:25].upper()
