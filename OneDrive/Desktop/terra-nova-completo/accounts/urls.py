from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('entrar/', views.login_view, name='login'),
    path('sair/', views.logout_view, name='logout'),
    path('painel/admins/novo/', views.cadastrar_admin, name='cadastrar_admin'),
]
