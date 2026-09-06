"""Checagens estáticas do SW / iOS — rode: python3 store/tests_ios_sw.py"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SW = (ROOT / 'static' / 'app' / 'sw.js').read_text()
APP = (ROOT / 'static' / 'app' / 'app.js').read_text()
BASE = (ROOT / 'templates' / 'mobile' / 'base.html').read_text()
MANIFEST = (ROOT / 'static' / 'app' / 'manifest.webmanifest').read_text()

checks = []

def ok(name, cond, detail=''):
    checks.append((bool(cond), name, detail))

ok('SW versionada', "VERSION = 'v5'" in SW)
ok('Precache não usa addAll atômico', 'addAll' not in SW.split('install')[1].split('activate')[0] or 'um 404' in SW)
ok('Precache item a item', 'Promise.all(PRECACHE.map' in SW)
ok('Só cacheia status 200 basic', 'res.status === 200' in SW and "res.type === 'basic'" in SW)
ok('ignoreSearch para ?source=pwa', 'ignoreSearch: true' in SW)
ok('SWR implementado', 'staleWhileRevalidate' in SW)
ok('TTL por bucket', 'TTL' in SW and 'X-TN-Cached-At' in SW)
ok('Trim / quota', 'LIMITS' in SW and 'trim(' in SW)
ok('Checkout/PIX network-only', 'isSensitive' in SW and '/checkout' in SW and '/pedido' in SW)
ok('Sem cache de Range', "headers.has('range')" in SW)
ok('Guarda navigate no iOS antigo', 'if (client.navigate)' in SW)
ok('Sem vibrate (iOS ignora/quebra opções)', 'vibrate' not in SW)
ok('Detecção iOS no app.js', 'iPad|iPhone|iPod' in APP)
ok('Push bloqueado fora do standalone iOS', 'Tela de Início' in APP)
ok('navigator.standalone', 'navigator.standalone' in APP)
ok('apple-touch-icon no HTML', 'apple-touch-icon' in BASE)
ok('apple-mobile-web-app-capable', 'apple-mobile-web-app-capable' in BASE)
ok('manifest standalone', '"display": "standalone"' in MANIFEST)
ok('ícones purpose any separados', '"purpose": "any"' in MANIFEST)
ok('instruções iOS no chrome', 'ios-install-bar' in BASE)
ok('roteador dinâmico', 'function routeFor' in SW)
ok('warm dinâmico', 'TN_WARM' in SW and 'TN_WARM' in APP)
ok('limite bytes imagem iOS', 'MAX_IMAGE_BYTES' in SW)
ok('splash iOS no HTML', 'apple-touch-startup-image' in BASE)


failed = [c for c in checks if not c[0]]
for good, name, detail in checks:
    print(('PASS' if good else 'FAIL'), '-', name, detail)
print(f'\n{len(checks)-len(failed)}/{len(checks)} checks')
sys.exit(1 if failed else 0)
