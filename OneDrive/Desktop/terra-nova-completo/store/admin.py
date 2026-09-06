from django.contrib import admin
from .models import Category, Product, Discount, Order, OrderItem, AdminInvite, PaymentEvent, PushDevice


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'featured', 'active')
    list_filter = ('category', 'featured', 'active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ('code', 'kind', 'value', 'active', 'uses', 'max_uses', 'valid_until')
    list_filter = ('active', 'kind')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'name', 'unit_price', 'quantity')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('public_id', 'customer_name', 'total', 'status', 'gateway', 'gateway_status', 'created_at')
    list_filter = ('status',)
    inlines = [OrderItemInline]


@admin.register(AdminInvite)
class AdminInviteAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_by', 'created_at')


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'gateway', 'event_type', 'external_id', 'order')
    readonly_fields = ('payload',)


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ('email', 'active', 'created_at', 'endpoint')
    list_filter = ('active',)
