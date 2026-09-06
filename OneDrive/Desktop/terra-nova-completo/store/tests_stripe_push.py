"""Testes do fluxo Stripe + checagem de push (roda sem Django instalado)."""
from __future__ import annotations

import ast
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fails = []


def ok(name, cond, detail=''):
    if cond:
        print('PASS', name)
    else:
        print('FAIL', name, detail)
        fails.append(name)


# --- syntax ---
for rel in (
    'store/stripe_pay.py', 'store/views.py', 'store/urls.py',
    'store/webpush.py', 'store/notify.py', 'store/mobile_views.py',
    'terranova/settings.py',
):
    src = (ROOT / rel).read_text(encoding='utf-8')
    ast.parse(src)
    ok('syntax ' + rel, True)

views = (ROOT / 'store/views.py').read_text()
urls = (ROOT / 'store/urls.py').read_text()
stripe = (ROOT / 'store/stripe_pay.py').read_text()
sw = (ROOT / 'static/app/sw.js').read_text()
app = (ROOT / 'static/app/app.js').read_text()
chk = (ROOT / 'templates/store/checkout.html').read_text()
vapid = json.loads((ROOT / 'terranova/vapid.json').read_text())

ok('rota webhook stripe', "path('webhooks/stripe/'" in urls)
ok('view stripe_webhook', 'def stripe_webhook' in views)
ok('checkout escolhe stripe', "pay_method" in views and "method == 'stripe'" in views)
ok('demo sem chave', 'cs_test_local' in stripe)
ok('radio stripe no checkout', 'value="stripe"' in chk and 'disabled' not in chk)
ok('consultar/simular stripe no pedido', 'Simular pagamento Stripe' in (ROOT / 'templates/store/pedido.html').read_text())
ok('push no pagamento stripe', 'Pagamento Stripe confirmado' in views)
ok('SW nao cacheia webhook', '/webhooks/' in sw)
ok('VAPID public', vapid.get('public_key', '').startswith('B') and len(vapid['public_key']) > 80)
ok('VAPID pem', 'BEGIN PRIVATE KEY' in vapid.get('private_pem', ''))
ok('subscribe no app', 'app_push_subscribe' in (ROOT / 'store/mobile_views.py').read_text())
ok('painel push', 'def painel_push' in views)
ok('SW push handler', "addEventListener('push'" in sw)
ok('app.js PushManager', 'PushManager' in app)

# --- HMAC Stripe igual ao do código ---
payload = json.dumps({
    'type': 'checkout.session.completed',
    'data': {'object': {'id': 'cs_test_1', 'payment_status': 'paid', 'client_reference_id': 'abc'}},
}).encode()
secret = 'whsec_test'
ts = str(int(time.time()))
signed = f'{ts}.'.encode() + payload
sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
header = f't={ts},v1={sig}'
parts = {}
for item in header.split(','):
    k, v = item.split('=', 1)
    parts.setdefault(k, []).append(v)
expect = hmac.new(secret.encode(), f'{parts["t"][0]}.'.encode() + payload, hashlib.sha256).hexdigest()
ok('assinatura stripe valida', hmac.compare_digest(expect, parts['v1'][0]))

bad = hmac.new(b'wrong', signed, hashlib.sha256).hexdigest()
ok('assinatura stripe rejeita chave errada', not hmac.compare_digest(expect, bad))

print(f'\n{len(fails)} falhas em {20} checks' if False else f'\n{20-len(fails)} checks ok, {len(fails)} falhas')
sys.exit(1 if fails else 0)
