from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Service, Favorite, Category

def home(request):
    featured = Service.objects.filter(is_featured=True)[:3]
    services = Service.objects.all()[:6]
    user_name = None
    if request.user.is_authenticated:
        try:
            user_name = request.user.profile.full_name or request.user.username
        except:
            user_name = request.user.username
    context = {
        'featured': featured,
        'services': services,
        'user_name': user_name,
    }
    return render(request, 'catalog/home.html', context)

def catalog(request):
    services = Service.objects.all()
    categories = Category.objects.all()
    context = {
        'services': services,
        'categories': categories,
    }
    return render(request, 'catalog/catalog.html', context)

def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk)
    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, service=service).exists()
    context = {
        'service': service,
        'is_favorite': is_favorite,
    }
    return render(request, 'catalog/service_detail.html', context)

@login_required
def favorites(request):
    favs = Favorite.objects.filter(user=request.user).select_related('service')
    return render(request, 'catalog/favorites.html', {'favorites': favs})

@login_required
def toggle_favorite(request, pk):
    service = get_object_or_404(Service, pk=pk)
    fav, created = Favorite.objects.get_or_create(user=request.user, service=service)
    if not created:
        fav.delete()
        messages.success(request, 'Removido dos favoritos.')
    else:
        messages.success(request, 'Adicionado aos favoritos!')
    return redirect(request.META.get('HTTP_REFERER', 'home'))
