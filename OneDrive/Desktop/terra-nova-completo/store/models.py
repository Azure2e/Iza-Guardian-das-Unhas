from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone
from decimal import Decimal
import uuid


class Category(models.Model):
    name = models.CharField('Nome', max_length=80)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField('Ícone', max_length=8, default='🐾')

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    name = models.CharField('Nome', max_length=160)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField('Descrição')
    price = models.DecimalField('Preço', max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField('Estoque', default=0)
    featured = models.BooleanField('Mais relevante', default=False)
    active = models.BooleanField('Ativo', default=True)
    emoji = models.CharField('Emoji', max_length=8, default='🦴')
    accent = models.CharField('Cor de destaque', max_length=16, default='#A8C15A')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['-featured', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:50]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Discount(models.Model):
    KIND_PERCENT = 'percent'
    KIND_FIXED = 'fixed'
    KIND_CHOICES = (
        (KIND_PERCENT, 'Percentual'),
        (KIND_FIXED, 'Valor fixo'),
    )
    code = models.CharField('Código', max_length=32, unique=True)
    kind = models.CharField('Tipo', max_length=12, choices=KIND_CHOICES, default=KIND_PERCENT)
    value = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    active = models.BooleanField('Ativo', default=True)
    valid_until = models.DateTimeField('Válido até', null=True, blank=True)
    max_uses = models.PositiveIntegerField('Máximo de usos', default=100)
    uses = models.PositiveIntegerField('Usos', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Desconto'
        verbose_name_plural = 'Descontos'
        ordering = ['-created_at']

    def is_valid(self):
        if not self.active:
            return False
        if self.uses >= self.max_uses:
            return False
        if self.valid_until and timezone.now() > self.valid_until:
            return False
        return True

    def apply(self, subtotal: Decimal) -> Decimal:
        if not self.is_valid():
            return Decimal('0.00')
        if self.kind == self.KIND_PERCENT:
            return (subtotal * self.value / Decimal('100')).quantize(Decimal('0.01'))
        return min(self.value, subtotal)

    def __str__(self):
        return self.code


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Aguardando PIX'),
        (STATUS_PAID, 'Pago'),
        (STATUS_CANCELLED, 'Cancelado'),
    )
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer_name = models.CharField('Nome', max_length=120)
    customer_email = models.EmailField('E-mail')
    customer_phone = models.CharField('Telefone', max_length=30, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_code = models.CharField(max_length=32, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    pix_txid = models.CharField(max_length=64, unique=True)
    pix_payload = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    cart_token = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    gateway = models.CharField(max_length=32, default='local')
    gateway_payment_id = models.CharField(max_length=80, blank=True, db_index=True)
    gateway_order_id = models.CharField(max_length=80, blank=True, db_index=True)
    gateway_status = models.CharField(max_length=40, blank=True)
    ticket_url = models.TextField(blank=True)
    qr_base64 = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Pedido {self.public_id.hex[:8].upper()}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class AdminInvite(models.Model):
    """Registro de administradores criados pelo painel."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=40, default='Administrador')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_admins')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class PaymentEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='events', null=True, blank=True)
    gateway = models.CharField(max_length=32)
    event_type = models.CharField(max_length=80)
    external_id = models.CharField(max_length=80, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.gateway} {self.event_type}'



class PushDevice(models.Model):
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    user_agent = models.CharField(max_length=240, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def as_subscription(self):
        return {'endpoint': self.endpoint, 'keys': {'p256dh': self.p256dh, 'auth': self.auth}}

    def __str__(self):
        return self.endpoint[:48]
