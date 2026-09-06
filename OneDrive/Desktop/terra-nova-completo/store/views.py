import json
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q, Sum, Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
import qrcode

from django.views.decorators.csrf import csrf_exempt

from . import cart
from .models import AdminInvite, Category, Discount, Order, OrderItem, PaymentEvent, Product
from .pix import build_pix_payload, make_txid
from . import gateway as pay
from . import stripe_pay
from . import notify


def staff_required(user):
    return user.is_authenticated and user.is_staff


def _cart_detail(request):
    raw = cart.get_items(request.session)
    products = Product.objects.filter(id__in=raw.keys(), active=True)
    lines = []
    subtotal = Decimal('0.00')
    for p in products:
        qty = int(raw.get(str(p.id), 0))
        if qty <= 0:
            continue
        line = qty * p.price
        subtotal += line
        lines.append({'product': p, 'qty': qty, 'total': line})
    code = request.session.get(cart.DISCOUNT_KEY, '')
    discount_obj = None
    discount_amount = Decimal('0.00')
    if code:
        discount_obj = Discount.objects.filter(code__iexact=code).first()
        if discount_obj and discount_obj.is_valid():
            discount_amount = discount_obj.apply(subtotal)
        else:
            request.session.pop(cart.DISCOUNT_KEY, None)
            discount_obj = None
    total = max(subtotal - discount_amount, Decimal('0.00'))
    return {
        'lines': lines,
        'subtotal': subtotal,
        'discount': discount_obj,
        'discount_amount': discount_amount,
        'total': total,
        'signature': cart.sign_state(request.session),
    }


def inicio(request):
    featured = Product.objects.filter(active=True, featured=True)[:6]
    latest = Product.objects.filter(active=True).order_by('-created_at')[:8]
    categories = Category.objects.all()
    return render(request, 'store/inicio.html', {
        'featured': featured,
        'latest': latest,
        'categories': categories,
    })


def sobre(request):
    return render(request, 'store/sobre.html')


def garantia(request):
    return render(request, 'store/garantia.html')


def baixar_app(request):
    return render(request, 'store/app.html')


def baixar_zip(request):
    from django.conf import settings
    from django.http import FileResponse, Http404
    path = settings.BASE_DIR / 'static' / 'downloads' / 'terra-nova-completo.zip'
    if not path.exists():
        path = settings.BASE_DIR / 'terra-nova-completo.zip'
    if not path.exists():
        raise Http404('Arquivo de download não encontrado.')
    resp = FileResponse(open(path, 'rb'), as_attachment=True, filename='terra-nova-completo.zip')
    resp['Content-Type'] = 'application/zip'
    return resp


def produtos(request):
    qs = Product.objects.filter(active=True).select_related('category')
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('categoria', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if cat:
        qs = qs.filter(category__slug=cat)
    return render(request, 'store/produtos.html', {
        'products': qs,
        'q': q,
        'categories': Category.objects.all(),
        'cat': cat,
    })


def relevantes(request):
    products = Product.objects.filter(active=True, featured=True)
    return render(request, 'store/relevantes.html', {'products': products})


def produto_detalhe(request, slug):
    product = get_object_or_404(Product, slug=slug, active=True)
    related = Product.objects.filter(category=product.category, active=True).exclude(id=product.id)[:4]
    return render(request, 'store/produto.html', {'product': product, 'related': related})


@require_POST
def adicionar_carrinho(request, pk):
    product = get_object_or_404(Product, pk=pk, active=True)
    try:
        qty = max(1, int(request.POST.get('qty', 1)))
    except ValueError:
        qty = 1
    if product.stock < qty:
        messages.error(request, 'Estoque insuficiente para este produto.')
        return redirect(request.POST.get('next') or 'store:produtos')
    try:
        cart.add_item(request.session, product.id, qty)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('store:carrinho')
    messages.success(request, f'{product.name} adicionado ao carrinho.')
    return redirect(request.POST.get('next') or 'store:carrinho')


def carrinho(request):
    detail = _cart_detail(request)
    return render(request, 'store/carrinho.html', detail)


@require_POST
def atualizar_carrinho(request):
    signature = request.POST.get('signature', '')
    if not cart.verify_state(request.session, signature):
        messages.error(request, 'Carrinho alterado de forma inválida. Recarregamos por segurança.')
        return redirect(request.POST.get('next') or 'store:carrinho')
    for key, value in request.POST.items():
        if key.startswith('qty_'):
            try:
                pid = int(key.split('_', 1)[1])
                qty = int(value)
            except ValueError:
                continue
            cart.set_qty(request.session, pid, qty)
    messages.info(request, 'Carrinho atualizado.')
    return redirect(request.POST.get('next') or 'store:carrinho')


@require_POST
def aplicar_cupom(request):
    code = request.POST.get('code', '').strip().upper()
    signature = request.POST.get('signature', '')
    if not cart.verify_state(request.session, signature):
        messages.error(request, 'Sessão do carrinho inválida.')
        return redirect(request.POST.get('next') or 'store:carrinho')
    discount = Discount.objects.filter(code__iexact=code).first()
    if not discount or not discount.is_valid():
        messages.error(request, 'Cupom inválido ou expirado.')
        request.session.pop(cart.DISCOUNT_KEY, None)
    else:
        request.session[cart.DISCOUNT_KEY] = discount.code
        request.session.modified = True
        messages.success(request, f'Cupom {discount.code} aplicado.')
    return redirect(request.POST.get('next') or 'store:carrinho')


def checkout(request):
    detail = _cart_detail(request)
    if not detail['lines']:
        messages.info(request, 'Seu carrinho está vazio.')
        return redirect('store:produtos')
    if request.method == 'POST':
        signature = request.POST.get('signature', '')
        if not cart.verify_state(request.session, signature):
            messages.error(request, 'Falha de segurança no carrinho. Tente novamente.')
            return redirect('store:carrinho')
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        method = request.POST.get('pay_method', 'pix')
        if method not in ('pix', 'stripe'):
            method = 'pix'
        if not name or not email:
            messages.error(request, 'Informe nome e e-mail para pagar.')
            return render(request, 'store/checkout.html', {**detail, 'name': name, 'email': email, 'phone': phone, 'stripe_ok': stripe_pay.is_configured()})
        # Recalcula preços no servidor
        for line in detail['lines']:
            if line['product'].stock < line['qty']:
                messages.error(request, f'Estoque insuficiente: {line["product"].name}')
                return redirect('store:carrinho')
        order = Order.objects.create(
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            subtotal=detail['subtotal'],
            discount_code=detail['discount'].code if detail['discount'] else '',
            discount_amount=detail['discount_amount'],
            total=detail['total'],
            pix_txid=make_txid(f'{cart.ensure_token(request.session)}{timezone.now().isoformat()}{email}'),
            pix_payload='',
            cart_token=request.session.get(cart.TOKEN_KEY, ''),
            gateway=pay.gateway_name(),
        )
        for line in detail['lines']:
            OrderItem.objects.create(
                order=order,
                product=line['product'],
                name=line['product'].name,
                unit_price=line['product'].price,
                quantity=line['qty'],
            )
        try:
            if method == 'stripe':
                success = request.build_absolute_uri(f'/pedido/{order.public_id}/')
                if request.session.get('from_app'):
                    success = request.build_absolute_uri(f'/m/pedido/{order.public_id}/')
                cancel = request.build_absolute_uri('/checkout/')
                charge = stripe_pay.create_checkout(
                    amount=detail['total'],
                    description=f'TERRA NOVA {order.public_id.hex[:8].upper()}',
                    email=email,
                    public_id=str(order.public_id),
                    success_url=success + '?pago=stripe',
                    cancel_url=cancel,
                )
            else:
                notification = request.build_absolute_uri('/webhooks/mercadopago/')
                charge = pay.get_gateway().create(
                    amount=detail['total'],
                    description=f'TERRA NOVA {order.public_id.hex[:8].upper()}',
                    email=email,
                    name=name,
                    external_ref=str(order.public_id),
                    notification_url=notification,
                )
        except (pay.PaymentError, stripe_pay.PaymentError) as exc:
            order.status = Order.STATUS_CANCELLED
            order.gateway_status = 'error'
            order.save(update_fields=['status', 'gateway_status'])
            messages.error(request, f'Não foi possível iniciar o pagamento: {exc}')
            return render(request, 'store/checkout.html', {**detail, 'name': name, 'email': email, 'phone': phone, 'stripe_ok': stripe_pay.is_configured()})
        order.pix_payload = charge.pix_payload
        order.pix_txid = charge.txid or order.pix_txid
        order.gateway = charge.gateway
        order.gateway_payment_id = charge.payment_id
        order.gateway_order_id = charge.order_id
        order.gateway_status = charge.status
        order.ticket_url = charge.ticket_url
        order.qr_base64 = charge.qr_base64
        order.save()
        PaymentEvent.objects.create(
            order=order,
            gateway=charge.gateway,
            event_type='charge.created',
            external_id=charge.payment_id or charge.order_id,
            payload=charge.raw or {'txid': charge.txid},
        )
        if detail['discount']:
            detail['discount'].uses += 1
            detail['discount'].save(update_fields=['uses'])
        cart.clear(request.session)
        if charge.gateway == 'stripe' and charge.ticket_url:
            return redirect(charge.ticket_url)
        target = 'store:app_pedido' if request.session.get('from_app') else 'store:pedido'
        return redirect(target, public_id=order.public_id)
    return render(request, 'store/checkout.html', {**detail, 'stripe_ok': stripe_pay.is_configured()})


def pedido(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    return render(request, 'store/pedido.html', {'order': order})


def pix_qr(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    img = qrcode.make(order.pix_payload)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


@require_POST
def confirmar_pagamento(request, public_id):
    """Só disponível no gateway local (sem token MP)."""
    order = get_object_or_404(Order, public_id=public_id)
    if order.gateway == 'stripe' and stripe_pay.is_configured() and order.gateway_payment_id.startswith('cs_'):
        try:
            session = stripe_pay.retrieve_session(order.gateway_payment_id)
            if session.get('payment_status') == 'paid' and order.status != Order.STATUS_PAID:
                order.status = Order.STATUS_PAID
                order.paid_at = timezone.now()
                order.gateway_status = 'paid'
                order.save(update_fields=['status', 'paid_at', 'gateway_status'])
                try:
                    pay._consume_stock(order)
                except Exception:
                    pass
                notify.notify_email(
                    order.customer_email,
                    'Pagamento Stripe confirmado · TERRA NOVA',
                    f'Pedido {order.public_id.hex[:8].upper()} pago com cartão.',
                    f'/m/pedido/{order.public_id}/',
                )
                messages.success(request, 'Pagamento confirmado pela Stripe.')
            else:
                messages.info(request, 'Ainda aguardando o cartão na Stripe.')
        except Exception as exc:
            messages.error(request, f'Stripe: {exc}')
        target = 'store:app_pedido' if request.session.get('from_app') else 'store:pedido'
        return redirect(target, public_id=order.public_id)
    if pay.is_live() and order.gateway != 'stripe':
        pay.refresh_order(order)
        if order.status == Order.STATUS_PAID:
            messages.success(request, 'Pagamento confirmado pelo Mercado Pago.')
        else:
            messages.info(request, 'Ainda aguardando o PIX no Mercado Pago.')
        target = 'store:app_pedido' if request.session.get('from_app') else 'store:pedido'
        return redirect(target, public_id=order.public_id)
    if order.status == Order.STATUS_PENDING:
        order.status = Order.STATUS_PAID
        order.paid_at = timezone.now()
        order.gateway_status = 'approved'
        order.save(update_fields=['status', 'paid_at', 'gateway_status'])
        pay._consume_stock(order)
        notify.notify_email(
            order.customer_email,
            'PIX confirmado · TERRA NOVA',
            f'Pedido {order.public_id.hex[:8].upper()} pago com sucesso.',
            f'/m/pedido/{order.public_id}/',
        )
        messages.success(request, 'Pagamento PIX confirmado. Obrigado!')
    target = 'store:app_pedido' if request.session.get('from_app') else 'store:pedido'
    return redirect(target, public_id=order.public_id)


def pedido_status(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    if order.status == Order.STATUS_PENDING and pay.is_live():
        try:
            pay.refresh_order(order)
        except pay.PaymentError:
            pass
        order.refresh_from_db()
    return JsonResponse({
        'status': order.status,
        'gateway': order.gateway,
        'gateway_status': order.gateway_status,
        'paid_at': order.paid_at.isoformat() if order.paid_at else None,
        'total': str(order.total),
    })


@csrf_exempt
def stripe_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'ok': True})
    try:
        event = stripe_pay.verify_webhook(request.body, request.headers.get('Stripe-Signature', ''))
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    etype = event.get('type') or ''
    obj = (event.get('data') or {}).get('object') or {}
    session_id = obj.get('id') or ''
    ref = obj.get('client_reference_id') or (obj.get('metadata') or {}).get('order') or ''
    order = None
    if session_id:
        order = Order.objects.filter(gateway_payment_id=session_id).first()
    if not order and ref:
        order = Order.objects.filter(public_id=ref).first()
    PaymentEvent.objects.create(
        order=order,
        gateway='stripe',
        event_type=etype or 'webhook',
        external_id=session_id,
        payload=event,
    )
    paid = etype in ('checkout.session.completed', 'checkout.session.async_payment_succeeded')
    if paid and order and order.status != Order.STATUS_PAID and obj.get('payment_status') in ('paid', 'no_payment_required'):
        order.status = Order.STATUS_PAID
        order.paid_at = timezone.now()
        order.gateway_status = 'paid'
        order.save(update_fields=['status', 'paid_at', 'gateway_status'])
        try:
            pay._consume_stock(order)
        except Exception:
            pass
        notify.notify_email(
            order.customer_email,
            'Pagamento Stripe confirmado · TERRA NOVA',
            f'Pedido {order.public_id.hex[:8].upper()} pago com cartão.',
            f'/m/pedido/{order.public_id}/',
        )
    return JsonResponse({'ok': True})


@csrf_exempt
def mercadopago_webhook(request):
    """Recebe IPN/Webhooks do Mercado Pago e confirma o pedido."""
    if request.method != 'POST':
        return JsonResponse({'ok': True, 'hint': 'POST only'})

    body = {}
    if request.body:
        try:
            body = json.loads(request.body.decode() or '{}')
        except json.JSONDecodeError:
            body = {}
    topic = request.GET.get('topic') or request.GET.get('type') or body.get('type') or body.get('topic') or ''
    data = body.get('data') or {}
    external_id = str(
        request.GET.get('id')
        or request.GET.get('data.id')
        or data.get('id')
        or body.get('id')
        or ''
    )
    PaymentEvent.objects.create(
        gateway='mercadopago',
        event_type=topic or body.get('action') or 'webhook',
        external_id=external_id,
        payload={'query': request.GET.dict(), 'body': body},
    )
    if not pay.verify_mp_signature(request.headers, external_id):
        return JsonResponse({'ok': False, 'error': 'invalid signature'}, status=401)
    if not pay.is_live():
        return JsonResponse({'ok': True, 'ignored': 'no token'})

    gw = pay.get_gateway()
    remote = {}
    order = None
    try:
        if 'order' in str(topic).lower() and external_id:
            remote = gw.retrieve(order_id=external_id)
        elif external_id:
            remote = gw.retrieve(payment_id=external_id)
    except pay.PaymentError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    ext_ref = str(remote.get('external_reference') or '')
    pay_id = str(remote.get('id') or external_id)
    if ext_ref:
        order = Order.objects.filter(public_id=ext_ref).first()
    if order is None and pay_id:
        order = Order.objects.filter(gateway_payment_id=pay_id).first()
        if order is None:
            order = Order.objects.filter(gateway_order_id=pay_id).first()
    if order is None:
        return JsonResponse({'ok': True, 'matched': False})
    if not order.gateway_payment_id and 'order' not in str(topic).lower():
        order.gateway_payment_id = pay_id
    became_paid = pay.apply_remote_status(order, remote)
    PaymentEvent.objects.create(
        order=order,
        gateway='mercadopago',
        event_type='webhook.applied',
        external_id=pay_id,
        payload=remote,
    )
    if became_paid:
        notify.notify_email(
            order.customer_email,
            'PIX confirmado · TERRA NOVA',
            f'Pedido {order.public_id.hex[:8].upper()} pago com sucesso.',
            f'/m/pedido/{order.public_id}/',
        )
    return JsonResponse({'ok': True, 'order': str(order.public_id), 'status': order.status})


@login_required
@user_passes_test(staff_required)
def painel_pagamentos(request):
    events = PaymentEvent.objects.select_related('order')[:40]
    return render(request, 'painel/pagamentos.html', {
        'live': pay.is_live(),
        'mode': getattr(settings, 'MP_API_MODE', 'payments'),
        'token_set': bool(getattr(settings, 'MP_ACCESS_TOKEN', '')),
        'token_prefix': (getattr(settings, 'MP_ACCESS_TOKEN', '') or '')[:12],
        'events': events,
        'webhook_url': request.build_absolute_uri('/webhooks/mercadopago/'),
        'stripe_ok': stripe_pay.is_configured(),
        'stripe_webhook': request.build_absolute_uri('/webhooks/stripe/'),
        'stripe_pk': (getattr(settings, 'STRIPE_PUBLISHABLE_KEY', '') or '')[:12],
    })


# ---------------- Painel ----------------
@login_required
@user_passes_test(staff_required)
def painel(request):
    stats = {
        'produtos': Product.objects.count(),
        'pedidos': Order.objects.count(),
        'faturamento': Order.objects.filter(status=Order.STATUS_PAID).aggregate(s=Sum('total'))['s'] or 0,
        'pendentes': Order.objects.filter(status=Order.STATUS_PENDING).count(),
        'admins': User.objects.filter(is_staff=True).count(),
        'cupons': Discount.objects.filter(active=True).count(),
    }
    recent_orders = Order.objects.all()[:6]
    low_stock = Product.objects.filter(stock__lte=8, active=True)[:6]
    return render(request, 'painel/dashboard.html', {
        'stats': stats,
        'recent_orders': recent_orders,
        'low_stock': low_stock,
    })


@login_required
@user_passes_test(staff_required)
def painel_produtos(request):
    products = Product.objects.select_related('category').all()
    return render(request, 'painel/produtos.html', {'products': products})


@login_required
@user_passes_test(staff_required)
def painel_produto_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    categories = Category.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '0')
        stock = request.POST.get('stock', '0')
        category_id = request.POST.get('category')
        featured = request.POST.get('featured') == 'on'
        active = request.POST.get('active') == 'on'
        emoji = request.POST.get('emoji', '🦴')[:8]
        if not name or not description:
            messages.error(request, 'Nome e descrição são obrigatórios.')
        else:
            defaults = {
                'name': name,
                'description': description,
                'price': Decimal(price or '0'),
                'stock': int(stock or 0),
                'category_id': category_id,
                'featured': featured,
                'active': active,
                'emoji': emoji or '🦴',
            }
            if product:
                for k, v in defaults.items():
                    setattr(product, k, v)
                product.save()
                messages.success(request, 'Produto atualizado.')
            else:
                Product.objects.create(**defaults)
                messages.success(request, 'Produto cadastrado.')
            return redirect('store:painel_produtos')
    return render(request, 'painel/produto_form.html', {
        'product': product,
        'categories': categories,
    })


@login_required
@user_passes_test(staff_required)
def painel_descontos(request):
    discounts = Discount.objects.all()
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        kind = request.POST.get('kind', Discount.KIND_PERCENT)
        value = request.POST.get('value', '0')
        max_uses = request.POST.get('max_uses', '100')
        valid_until = request.POST.get('valid_until') or None
        if not code:
            messages.error(request, 'Informe o código do cupom.')
        elif Discount.objects.filter(code=code).exists():
            messages.error(request, 'Já existe um cupom com esse código.')
        else:
            Discount.objects.create(
                code=code,
                kind=kind,
                value=Decimal(value or '0'),
                max_uses=int(max_uses or 100),
                valid_until=valid_until,
                created_by=request.user,
            )
            messages.success(request, f'Cupom {code} criado.')
            return redirect('store:painel_descontos')
    return render(request, 'painel/descontos.html', {'discounts': discounts})


@login_required
@user_passes_test(staff_required)
@require_POST
def toggle_desconto(request, pk):
    d = get_object_or_404(Discount, pk=pk)
    d.active = not d.active
    d.save(update_fields=['active'])
    return redirect('store:painel_descontos')


@login_required
@user_passes_test(staff_required)
def painel_pedidos(request):
    orders = Order.objects.prefetch_related('items')
    return render(request, 'painel/pedidos.html', {'orders': orders})


@login_required
@user_passes_test(staff_required)
def painel_admins(request):
    invites = {i.user_id: i for i in AdminInvite.objects.select_related('created_by')}
    rows = []
    for user in User.objects.filter(is_staff=True).order_by('username'):
        inv = invites.get(user.id)
        rows.append({
            'user': user,
            'role': inv.role if inv else ('Superadmin' if user.is_superuser else 'Administrador'),
            'created_by': inv.created_by.username if inv and inv.created_by else '—',
        })
    return render(request, 'painel/admins.html', {'rows': rows})


def buscar_json(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    products = Product.objects.filter(active=True).filter(
        Q(name__icontains=q) | Q(description__icontains=q)
    )[:8]
    return JsonResponse({
        'results': [
            {'name': p.name, 'slug': p.slug, 'price': str(p.price), 'emoji': p.emoji}
            for p in products
        ]
    })



@login_required
@user_passes_test(staff_required)
def painel_push(request):
    from .models import PushDevice
    devices = PushDevice.objects.all()
    if request.method == 'POST':
        title = request.POST.get('title', '').strip() or 'TERRA NOVA'
        body = request.POST.get('body', '').strip() or 'Novidade na farmácia.'
        url = request.POST.get('url', '').strip() or '/m/'
        sent, gone = notify.notify_all(title, body, url)
        messages.success(request, f'Push enviado para {sent} aparelho(s). {gone} inscrição(ões) inativa(s) removida(s).')
        return redirect('store:painel_push')
    return render(request, 'painel/push.html', {
        'devices': devices,
        'active_count': devices.filter(active=True).count(),
        'vapid': bool(__import__('store.webpush', fromlist=['public_key']).public_key()),
    })
