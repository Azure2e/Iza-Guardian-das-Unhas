"""Carrinho com verificação de integridade (preço sempre no servidor)."""
from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from django.conf import settings
from django.core.signing import BadSignature, TimestampSigner

CART_KEY = 'tn_cart'
TOKEN_KEY = 'tn_cart_token'
DISCOUNT_KEY = 'tn_discount'
SIGNER = TimestampSigner(salt='terra-nova-cart-v1')


def _secret() -> bytes:
    return settings.SECRET_KEY.encode()


def new_token() -> str:
    raw = f'{time.time_ns()}'
    return hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()


def ensure_token(session) -> str:
    token = session.get(TOKEN_KEY)
    if not token:
        token = new_token()
        session[TOKEN_KEY] = token
        session.modified = True
    return token


def get_items(session) -> dict:
    return session.get(CART_KEY, {})


def _canonical(session) -> str:
    items = get_items(session)
    parts = [f"{k}:{int(v)}" for k, v in sorted(items.items(), key=lambda kv: int(kv[0]))]
    token = session.get(TOKEN_KEY, '')
    disc = session.get(DISCOUNT_KEY, '') or ''
    return f"{token}|{','.join(parts)}|{disc}"


def sign_state(session) -> str:
    ensure_token(session)
    return SIGNER.sign(_canonical(session))


def verify_state(session, signature: str) -> bool:
    try:
        payload = SIGNER.unsign(signature, max_age=60 * 60 * 6)
    except BadSignature:
        return False
    return hmac.compare_digest(payload, _canonical(session))


def add_item(session, product_id: int, qty: int = 1) -> None:
    items = get_items(session)
    pid = str(product_id)
    current = int(items.get(pid, 0))
    max_qty = getattr(settings, 'CART_MAX_QTY_PER_ITEM', 20)
    max_items = getattr(settings, 'CART_MAX_ITEMS', 30)
    if pid not in items and len(items) >= max_items:
        raise ValueError('Limite de itens no carrinho atingido.')
    items[pid] = min(current + qty, max_qty)
    session[CART_KEY] = items
    session.modified = True


def set_qty(session, product_id: int, qty: int) -> None:
    items = get_items(session)
    pid = str(product_id)
    max_qty = getattr(settings, 'CART_MAX_QTY_PER_ITEM', 20)
    if qty <= 0:
        items.pop(pid, None)
    else:
        items[pid] = min(qty, max_qty)
    session[CART_KEY] = items
    session.modified = True


def clear(session) -> None:
    session[CART_KEY] = {}
    session.pop(DISCOUNT_KEY, None)
    session.modified = True


def count(session) -> int:
    return sum(int(q) for q in get_items(session).values())
