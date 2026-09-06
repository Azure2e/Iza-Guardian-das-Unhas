from django import forms
from django.contrib.auth.models import User


class LoginForm(forms.Form):
    username = forms.CharField(label='Usuário')
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)


class NewAdminForm(forms.Form):
    first_name = forms.CharField(label='Nome', max_length=80)
    last_name = forms.CharField(label='Sobrenome', max_length=80, required=False)
    username = forms.CharField(label='Usuário', max_length=40)
    email = forms.EmailField(label='E-mail')
    password = forms.CharField(label='Senha', widget=forms.PasswordInput, min_length=8)
    password2 = forms.CharField(label='Confirmar senha', widget=forms.PasswordInput)
    role = forms.CharField(label='Função', max_length=40, initial='Administrador')

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este usuário já existe.')
        return username

    def clean(self):
        data = super().clean()
        if data.get('password') != data.get('password2'):
            raise forms.ValidationError('As senhas não coincidem.')
        return data
