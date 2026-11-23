from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalogo/', views.catalog, name='catalog'),
    path('servico/<int:pk>/', views.service_detail, name='service_detail'),
    path('favoritos/', views.favorites, name='favorites'),
    path('favoritar/<int:pk>/', views.toggle_favorite, name='toggle_favorite'),
]
