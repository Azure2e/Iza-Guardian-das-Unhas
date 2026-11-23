from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .models import Profile
from .forms import CustomUserCreationForm
from .email_validator import verify_email_domain

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Conta criada com sucesso!')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()

        # Validação de email
        if email:
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, 'Digite um email válido.')
                return render(request, 'accounts/profile.html', {'profile': profile})

            # Verifica domínio real
            try:
                verify_email_domain(email)
            except ValidationError as e:
                messages.error(request, str(e))
                return render(request, 'accounts/profile.html', {'profile': profile})

            # Verifica se o email já existe em outro usuário
            if User.objects.filter(email=email).exclude(pk=request.user.pk).exists():
                messages.error(request, 'Este email já está sendo usado por outra conta.')
                return render(request, 'accounts/profile.html', {'profile': profile})

        request.user.email = email
        request.user.save()

        profile.full_name = full_name
        profile.phone = phone

        if 'photo' in request.FILES:
            profile.photo = request.FILES['photo']

        profile.save()
        messages.success(request, 'Perfil atualizado com sucesso!')
        return redirect('profile')

    return render(request, 'accounts/profile.html', {'profile': profile})
