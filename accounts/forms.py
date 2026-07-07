from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from core.utils import sanitize_text
from .models import User
from .validators import (
    normalize_cpf,
    normalize_email,
    normalize_whatsapp,
    validate_cpf,
    validate_whatsapp,
)


class UserIdentityValidationMixin:
    def _users_for_duplicate_check(self):
        qs = User.objects.all()
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        return qs

    def clean_full_name(self):
        full_name = sanitize_text(self.cleaned_data.get('full_name') or '')
        if not full_name:
            raise forms.ValidationError('Informe seu nome completo.')
        if len(full_name.split()) < 2:
            raise forms.ValidationError('Informe nome e sobrenome.')
        return full_name

    def clean_email(self):
        email = normalize_email(self.cleaned_data.get('email'))
        if not email:
            raise forms.ValidationError('Informe seu e-mail.')
        if self._users_for_duplicate_check().filter(email__iexact=email).exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean_cpf(self):
        cpf = normalize_cpf(self.cleaned_data.get('cpf'))
        validate_cpf(cpf)
        if self._users_for_duplicate_check().filter(cpf=cpf).exists():
            raise forms.ValidationError('Já existe uma conta com este CPF.')
        return cpf

    def clean_whatsapp(self):
        whatsapp = normalize_whatsapp(self.cleaned_data.get('whatsapp'))
        validate_whatsapp(whatsapp)
        if self._users_for_duplicate_check().filter(whatsapp=whatsapp).exists():
            raise forms.ValidationError('Já existe uma conta com este telefone.')
        return whatsapp


class RegisterForm(UserIdentityValidationMixin, UserCreationForm):
    full_name = forms.CharField(label='Nome completo', max_length=200,
                                widget=forms.TextInput(attrs={'placeholder': 'Seu nome completo'}))
    email = forms.EmailField(label='E-mail',
                             widget=forms.EmailInput(attrs={'placeholder': 'seu@email.com'}))
    cpf = forms.CharField(label='CPF', max_length=14,
                          widget=forms.TextInput(attrs={'placeholder': '000.000.000-00', 'maxlength': '14'}))
    whatsapp = forms.CharField(label='Telefone', max_length=20,
                               widget=forms.TextInput(attrs={'placeholder': '(11) 99999-9999'}))

    class Meta:
        model = User
        fields = ('full_name', 'email', 'cpf', 'whatsapp', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.cpf = self.cleaned_data['cpf']
        user.whatsapp = self.cleaned_data['whatsapp']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='E-mail',
                                widget=forms.EmailInput(attrs={'placeholder': 'seu@email.com'}))
    password = forms.CharField(label='Senha',
                               widget=forms.PasswordInput(attrs={'placeholder': 'Sua senha'}))

    def clean_username(self):
        return normalize_email(self.cleaned_data['username'])


class ProfileForm(UserIdentityValidationMixin, forms.ModelForm):
    full_name = forms.CharField(label='Nome completo', max_length=200)
    email = forms.EmailField(label='E-mail')
    cpf = forms.CharField(label='CPF', max_length=14,
                          widget=forms.TextInput(attrs={'placeholder': '000.000.000-00', 'maxlength': '14'}))
    whatsapp = forms.CharField(label='Telefone', max_length=20,
                               widget=forms.TextInput(attrs={'placeholder': '(11) 99999-9999'}))

    class Meta:
        model = User
        fields = ['full_name', 'email', 'cpf', 'whatsapp', 'cep', 'address',
                  'address_number', 'address_complement', 'neighborhood', 'city', 'state']
        widgets = {
            'cep': forms.TextInput(attrs={'placeholder': '00000-000', 'maxlength': '9'}),
            'state': forms.TextInput(attrs={'maxlength': '2', 'placeholder': 'SP'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        if commit:
            user.save()
        return user
