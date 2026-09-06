from urllib.parse import quote
from django.conf import settings
from . import cart
from .models import Product


def cart_context(request):
    items_map = cart.get_items(request.session)
    qty = cart.count(request.session)
    return {
        'cart_count': qty,
        'cart_has_items': qty > 0,
        'cart_ids': list(items_map.keys()),
    }


def brand_context(request):
    number = ''.join(ch for ch in str(getattr(settings, 'CLINIC_WHATSAPP', '5511999999999')) if ch.isdigit()) or '5511999999999'
    msg = quote('Ola TERRA NOVA, vim pelo app.')
    return {
        'clinic_name': getattr(settings, 'CLINIC_NAME', 'TERRA NOVA'),
        'clinic_pix_key': getattr(settings, 'CLINIC_PIX_KEY', ''),
        'clinic_whatsapp': number,
        'whatsapp_url': f'https://wa.me/{number}?text={msg}',
        'meta_description': 'Clínica e farmácia veterinária TERRA NOVA. Produtos, app PWA, carrinho seguro e PIX.',
    }


def push_context(request):
    from . import webpush
    return {'vapid_public_key': webpush.public_key()}
