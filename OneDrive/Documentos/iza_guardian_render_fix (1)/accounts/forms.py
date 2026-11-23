from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .email_validator import verify_email_domain

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={'placeholder': 'seu@email.com'})
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("O email é obrigatório.")
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError("Digite um email válido.")

        # Verifica se o domínio é real
        try:
            verify_email_domain(email)
        except ValidationError as e:
            raise ValidationError(str(e))

        if User.objects.filter(email=email).exists():
            raise ValidationError("Este email já está cadastrado.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
