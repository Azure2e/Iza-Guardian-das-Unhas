"""Checkout Stripe (cartão) via API REST — sem pacote extra."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

from django.conf import settings

from .gateway import Charge, PaymentError


def secret() -> str:
    return (getattr(settings, 'STRIPE_SECRET_KEY', '') or '').strip()


def webhook_secret() -> str:
    return (getattr(settings, 'STRIPE_WEBHOOK_SECRET', '') or '').strip()


def is_configured() -> bool:
    return bool(secret())


def _form_request(path: str, fields: list[tuple[str, str]]) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f'https://api.stripe.com{path}',
        data=data,
        method='POST',
        headers={
            'Authorization': f'Bearer {secret()}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Stripe-Version': '2024-06-20',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors='ignore')
        raise PaymentError(f'Stripe HTTP {exc.code}: {detail[:400]}') from exc
    except urllib.error.URLError as exc:
        raise PaymentError(f'Falha de conexão com a Stripe: {exc.reason}') from exc


def create_checkout(*, amount: Decimal, description: str, email: str,
                    public_id: str, success_url: str, cancel_url: str) -> Charge:
    if not secret():
        return Charge(
            gateway='stripe',
            status='open',
            pix_payload='',
            payment_id='cs_test_local',
            ticket_url='',
            txid=public_id,
            raw={'mode': 'demo'},
        )
    cents = int((amount * 100).quantize(Decimal('1')))
    fields = [
        ('mode', 'payment'),
        ('success_url', success_url),
        ('cancel_url', cancel_url),
        ('client_reference_id', public_id),
        ('customer_email', email),
        ('payment_method_types[0]', 'card'),
        ('line_items[0][quantity]', '1'),
        ('line_items[0][price_data][currency]', 'brl'),
        ('line_items[0][price_data][unit_amount]', str(cents)),
        ('line_items[0][price_data][product_data][name]', description[:120]),
        ('metadata[order]', public_id),
    ]
    data = _form_request('/v1/checkout/sessions', fields)
    url = data.get('url') or ''
    if not url:
        raise PaymentError('Stripe não devolveu a URL de checkout.')
    return Charge(
        gateway='stripe',
        status=data.get('status') or 'open',
        pix_payload='',
        payment_id=str(data.get('id') or ''),
        order_id=str(data.get('payment_intent') or ''),
        ticket_url=url,
        txid=str(data.get('id') or public_id),
        raw=data,
    )


def retrieve_session(session_id: str) -> dict:
    req = urllib.request.Request(
        f'https://api.stripe.com/v1/checkout/sessions/{session_id}',
        headers={'Authorization': f'Bearer {secret()}'},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def verify_webhook(payload: bytes, header: str) -> dict:
    """Valida Stripe-Signature (t=...,v1=...)."""
    secret_wh = webhook_secret()
    if not secret_wh:
        return json.loads(payload.decode())
    parts = {}
    for item in (header or '').split(','):
        if '=' in item:
            k, v = item.split('=', 1)
            parts.setdefault(k.strip(), []).append(v.strip())
    ts = (parts.get('t') or [''])[0]
    sigs = parts.get('v1') or []
    if not ts or not sigs:
        raise PaymentError('Assinatura Stripe ausente.')
    if abs(time.time() - int(ts)) > 300:
        raise PaymentError('Webhook Stripe expirado.')
    signed = f'{ts}.'.encode() + payload
    expect = hmac.new(secret_wh.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expect, s) for s in sigs):
        raise PaymentError('Assinatura Stripe inválida.')
    return json.loads(payload.decode())
