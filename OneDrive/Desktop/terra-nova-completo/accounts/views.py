from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from store.models import AdminInvite
from .forms import LoginForm, NewAdminForm


def staff_required(user):
    return user.is_authenticated and user.is_staff


def login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('store:painel')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user and user.is_staff:
            login(request, user)
            messages.success(request, f'Bem-vindo de volta, {user.first_name or user.username}.')
            return redirect('store:painel')
        messages.error(request, 'Credenciais inválidas ou sem permissão de administrador.')
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Sessão encerrada com segurança.')
    return redirect('store:inicio')


@login_required
@user_passes_test(staff_required)
def cadastrar_admin(request):
    form = NewAdminForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
            first_name=form.cleaned_data['first_name'],
            last_name=form.cleaned_data['last_name'],
            is_staff=True,
        )
        AdminInvite.objects.create(
            user=user,
            role=form.cleaned_data['role'],
            created_by=request.user,
        )
        messages.success(request, f'Administrador {user.username} cadastrado.')
        return redirect('store:painel_admins')
    return render(request, 'painel/admins_form.html', {'form': form})
