"""Gateway de pagamento PIX.

Mercado Pago (produção/sandbox) é o provedor principal.
Se MP_ACCESS_TOKEN não estiver configurado, usa o emissor local (QR EMV)
apenas para desenvolvimento.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils import timezone

from .pix import build_pix_payload, make_txid


class PaymentError(Exception):
    pass


@dataclass
class Charge:
    gateway: str
    status: str
    pix_payload: str
    payment_id: str = ''
    order_id: str = ''
    ticket_url: str = ''
    qr_base64: str = ''
    txid: str = ''
    raw: dict = field(default_factory=dict)


PAID_STATUSES = {'approved', 'paid', 'accredited', 'processed'}
CANCEL_STATUSES = {'cancelled', 'canceled', 'rejected', 'expired', 'refunded'}


def _json_request(method: str, url: str, token: str, body: dict | None = None, idempotency: str = '') -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'TerraNova-Vet/1.0',
    }
    if idempotency:
        headers['X-Idempotency-Key'] = idempotency
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors='ignore')
        raise PaymentError(f'Mercado Pago HTTP {exc.code}: {detail[:500]}') from exc
    except urllib.error.URLError as exc:
        raise PaymentError(f'Falha de conexão com o Mercado Pago: {exc.reason}') from exc


def _token() -> str:
    return (getattr(settings, 'MP_ACCESS_TOKEN', '') or '').strip()


def gateway_name() -> str:
    return 'mercadopago' if _token() else 'local'


def is_live() -> bool:
    return bool(_token())


class LocalGateway:
    name = 'local'

    def create(self, *, amount: Decimal, description: str, email: str, name: str,
               external_ref: str, notification_url: str = '') -> Charge:
        txid = make_txid(external_ref)
        payload = build_pix_payload(
            settings.CLINIC_PIX_KEY,
            settings.CLINIC_PIX_NAME,
            settings.CLINIC_PIX_CITY,
            amount,
            txid,
        )
        return Charge(gateway=self.name, status='pending', pix_payload=payload, txid=txid, payment_id=txid)

    def retrieve(self, payment_id: str = '', order_id: str = '') -> dict:
        return {'status': 'pending', 'id': payment_id}


class MercadoPagoGateway:
    name = 'mercadopago'
    base = 'https://api.mercadopago.com'

    def create(self, *, amount: Decimal, description: str, email: str, name: str,
               external_ref: str, notification_url: str = '') -> Charge:
        mode = getattr(settings, 'MP_API_MODE', 'payments')
        if mode == 'orders':
            return self._create_order(amount, description, email, name, external_ref, notification_url)
        return self._create_payment(amount, description, email, name, external_ref, notification_url)

    def _create_payment(self, amount, description, email, name, external_ref, notification_url) -> Charge:
        body: dict[str, Any] = {
            'transaction_amount': float(amount),
            'description': description[:255],
            'payment_method_id': 'pix',
            'external_reference': external_ref,
            'payer': {
                'email': email,
                'first_name': (name.split() or ['Cliente'])[0][:60],
            },
        }
        if notification_url:
            body['notification_url'] = notification_url
        data = _json_request(
            'POST', f'{self.base}/v1/payments', _token(), body, idempotency=external_ref
        )
        poi = (data.get('point_of_interaction') or {}).get('transaction_data') or {}
        payload = poi.get('qr_code') or ''
        if not payload:
            raise PaymentError('Mercado Pago não retornou QR Code PIX. Verifique a conta e o token.')
        return Charge(
            gateway=self.name,
            status=data.get('status') or 'pending',
            pix_payload=payload,
            payment_id=str(data.get('id') or ''),
            ticket_url=poi.get('ticket_url') or '',
            qr_base64=poi.get('qr_code_base64') or '',
            txid=str(data.get('id') or external_ref),
            raw=data,
        )

    def _create_order(self, amount, description, email, name, external_ref, notification_url) -> Charge:
        value = f'{amount:.2f}'
        body: dict[str, Any] = {
            'type': 'online',
            'processing_mode': 'automatic',
            'total_amount': value,
            'external_reference': external_ref,
            'description': description[:127],
            'payer': {'email': email},
            'transactions': {
                'payments': [
                    {
                        'amount': value,
                        'payment_method': {'id': 'pix', 'type': 'bank_transfer'},
                        'expiration_time': 'PT24H',
                    }
                ]
            },
        }
        data = _json_request(
            'POST', f'{self.base}/v1/orders', _token(), body, idempotency=external_ref
        )
        payments = ((data.get('transactions') or {}).get('payments') or [{}])
        pay = payments[0] if payments else {}
        method = pay.get('payment_method') or {}
        payload = method.get('qr_code') or ''
        if not payload:
            raise PaymentError('Mercado Pago Orders não retornou QR Code PIX.')
        return Charge(
            gateway=self.name,
            status=data.get('status') or pay.get('status') or 'pending',
            pix_payload=payload,
            payment_id=str(pay.get('id') or ''),
            order_id=str(data.get('id') or ''),
            ticket_url=method.get('ticket_url') or '',
            qr_base64=method.get('qr_code_base64') or '',
            txid=str(data.get('id') or external_ref),
            raw=data,
        )

    def retrieve_payment(self, payment_id: str) -> dict:
        return _json_request('GET', f'{self.base}/v1/payments/{payment_id}', _token())

    def retrieve_order(self, order_id: str) -> dict:
        return _json_request('GET', f'{self.base}/v1/orders/{order_id}', _token())

    def retrieve(self, payment_id: str = '', order_id: str = '') -> dict:
        if order_id:
            return self.retrieve_order(order_id)
        if payment_id:
            return self.retrieve_payment(payment_id)
        return {}


def get_gateway():
    return MercadoPagoGateway() if _token() else LocalGateway()


def apply_remote_status(order, remote: dict) -> bool:
    """Atualiza o pedido a partir do status remoto. Retorna True se mudou para pago."""
    from .models import Order

    status = (remote.get('status') or '').lower()
    detail = (remote.get('status_detail') or '').lower()
    order.gateway_status = status or order.gateway_status
    changed = False
    if status in PAID_STATUSES or detail in {'accredited', 'approved'}:
        if order.status != Order.STATUS_PAID:
            order.status = Order.STATUS_PAID
            order.paid_at = timezone.now()
            changed = True
            _consume_stock(order)
    elif status in CANCEL_STATUSES and order.status == Order.STATUS_PENDING:
        order.status = Order.STATUS_CANCELLED
        changed = True
    order.save()
    return changed and order.status == Order.STATUS_PAID


def _consume_stock(order) -> None:
    if getattr(order, '_stock_consumed', False):
        return
    for item in order.items.select_related('product'):
        product = item.product
        product.stock = max(0, product.stock - item.quantity)
        product.save(update_fields=['stock'])
    order._stock_consumed = True


def refresh_order(order) -> dict:
    gw = get_gateway()
    if gw.name == 'local':
        return {'status': order.status, 'gateway': 'local'}
    remote = gw.retrieve(payment_id=order.gateway_payment_id, order_id=order.gateway_order_id)
    apply_remote_status(order, remote)
    order.refresh_from_db()
    return remote


def verify_mp_signature(headers, data_id: str) -> bool:
    """Valida x-signature do webhook quando MP_WEBHOOK_SECRET existe."""
    import hashlib
    import hmac
    from django.conf import settings
    secret = (getattr(settings, 'MP_WEBHOOK_SECRET', '') or '').strip()
    if not secret:
        return True
    signature = headers.get('x-signature') or headers.get('HTTP_X_SIGNATURE') or ''
    request_id = headers.get('x-request-id') or headers.get('HTTP_X_REQUEST_ID') or ''
    ts = ''
    v1 = ''
    for part in signature.split(','):
        if '=' in part:
            k, v = part.split('=', 1)
            if k.strip() == 'ts':
                ts = v.strip()
            if k.strip() == 'v1':
                v1 = v.strip()
    manifest = f'id:{data_id};request-id:{request_id};ts:{ts};'
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)
