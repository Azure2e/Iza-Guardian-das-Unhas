from django.db.models import Q
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Category, Product
from .views import _cart_detail


def _mark_app(request):
    request.session['from_app'] = True


def app_inicio(request):
    _mark_app(request)
    featured = Product.objects.filter(active=True, featured=True)[:6]
    latest = Product.objects.filter(active=True).order_by('-created_at')[:8]
    return render(request, 'mobile/inicio.html', {
        'featured': featured,
        'latest': latest,
        'app_tab': 'inicio',
    })


def app_produtos(request):
    _mark_app(request)
    qs = Product.objects.filter(active=True).select_related('category')
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('categoria', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if cat:
        qs = qs.filter(category__slug=cat)
    return render(request, 'mobile/produtos.html', {
        'products': qs,
        'q': q,
        'categories': Category.objects.all(),
        'cat': cat,
        'app_tab': 'produtos',
    })


def app_relevantes(request):
    _mark_app(request)
    return render(request, 'mobile/relevantes.html', {
        'products': Product.objects.filter(active=True, featured=True),
        'app_tab': 'relevantes',
    })


def app_produto(request, slug):
    _mark_app(request)
    product = get_object_or_404(Product, slug=slug, active=True)
    return render(request, 'mobile/produto.html', {
        'product': product,
        'app_tab': 'produtos',
    })


def app_carrinho(request):
    _mark_app(request)
    ctx = _cart_detail(request)
    ctx['app_tab'] = 'carrinho'
    return render(request, 'mobile/carrinho.html', ctx)


def app_checkout(request):
    from .views import checkout
    _mark_app(request)
    if request.method != 'POST':
        detail = _cart_detail(request)
        if not detail['lines']:
            from django.shortcuts import redirect
            return redirect('store:app_produtos')
        detail['app_tab'] = 'carrinho'
        from . import stripe_pay
        detail['stripe_ok'] = stripe_pay.is_configured()
        return render(request, 'mobile/checkout.html', detail)
    return checkout(request)


def app_pedido(request, public_id):
    _mark_app(request)
    from .models import Order
    order = get_object_or_404(Order, public_id=public_id)
    return render(request, 'mobile/pedido.html', {'order': order, 'app_tab': 'carrinho'})


def app_conta(request):
    _mark_app(request)
    return render(request, 'mobile/conta.html', {'app_tab': 'conta'})


def app_service_worker(request):
    path = settings.BASE_DIR / 'static' / 'app' / 'sw.js'
    body = path.read_text(encoding='utf-8')
    resp = HttpResponse(body, content_type='application/javascript')
    resp['Service-Worker-Allowed'] = '/m/'
    resp['Cache-Control'] = 'no-cache'
    return resp


import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import PushDevice
from . import webpush


def app_offline(request):
    _mark_app(request)
    return render(request, 'mobile/offline.html', {'app_tab': 'inicio'})


def app_catalogo_json(request):
    products = Product.objects.filter(active=True).select_related('category')
    return JsonResponse({
        'updated': timezone.now().isoformat(),
        'results': [
            {
                'id': p.id,
                'name': p.name,
                'slug': p.slug,
                'price': str(p.price),
                'emoji': p.emoji,
                'category': p.category.name,
                'featured': p.featured,
                'description': p.description[:180],
            }
            for p in products
        ],
    })


@require_POST
def app_push_subscribe(request):
    try:
        data = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False}, status=400)
    endpoint = data.get('endpoint') or ''
    keys = data.get('keys') or {}
    if not endpoint or not keys.get('p256dh') or not keys.get('auth'):
        return JsonResponse({'ok': False, 'error': 'inscrição inválida'}, status=400)
    if not request.session.session_key:
        request.session.save()
    device, _ = PushDevice.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'p256dh': keys['p256dh'],
            'auth': keys['auth'],
            'email': (data.get('email') or '')[:120],
            'session_key': request.session.session_key or '',
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:240],
            'active': True,
        },
    )
    return JsonResponse({'ok': True, 'id': device.id})


@require_POST
def app_push_unsubscribe(request):
    try:
        data = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        data = {}
    endpoint = data.get('endpoint') or ''
    PushDevice.objects.filter(endpoint=endpoint).update(active=False)
    return JsonResponse({'ok': True})


def app_compat(request):
    _mark_app(request)
    return render(request, 'mobile/compat.html', {'app_tab': 'conta'})
