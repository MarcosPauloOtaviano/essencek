from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.db.models import Q

from core.pii import make_pii_lookup

from .models import User
from .validators import normalize_cpf, normalize_whatsapp, validate_cpf, validate_whatsapp


class SecureUserChangeForm(UserChangeForm):
    cpf = forms.CharField(label='CPF', max_length=14, required=False)
    whatsapp = forms.CharField(label='Telefone', max_length=20, required=False)

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['cpf'].initial = self.instance.cpf
            self.fields['whatsapp'].initial = self.instance.whatsapp

    def clean_cpf(self):
        value = normalize_cpf(self.cleaned_data.get('cpf'))
        if value:
            validate_cpf(value)
            if User.objects.exclude(pk=self.instance.pk).filter(cpf_lookup=make_pii_lookup(value)).exists():
                raise forms.ValidationError('Já existe uma conta com este CPF.')
        return value

    def clean_whatsapp(self):
        value = normalize_whatsapp(self.cleaned_data.get('whatsapp'))
        if value:
            validate_whatsapp(value)
            if User.objects.exclude(pk=self.instance.pk).filter(
                whatsapp_lookup=make_pii_lookup(value)
            ).exists():
                raise forms.ValidationError('Já existe uma conta com este telefone.')
        return value

    def save(self, commit=True):
        user = super().save(commit=False)
        user.cpf = self.cleaned_data.get('cpf')
        user.whatsapp = self.cleaned_data.get('whatsapp')
        if commit:
            user.save()
            self.save_m2m()
        return user


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    form = SecureUserChangeForm
    list_display = [
        'email', 'full_name', 'cpf_display', 'whatsapp_display',
        'city', 'state', 'is_active', 'date_joined',
    ]
    search_fields = ['email', 'full_name']
    ordering = ['-date_joined']
    fieldsets = UserAdmin.fieldsets + (
        ('Dados extras', {'fields': ('full_name', 'cpf', 'whatsapp', 'cep', 'address',
                                     'address_number', 'address_complement',
                                     'neighborhood', 'city', 'state')}),
    )

    @admin.display(description='CPF')
    def cpf_display(self, obj):
        return obj.cpf

    @admin.display(description='Telefone')
    def whatsapp_display(self, obj):
        return obj.whatsapp

    def get_search_results(self, request, queryset, search_term):
        original_queryset = queryset
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        cpf = normalize_cpf(search_term) or ''
        whatsapp = normalize_whatsapp(search_term) or ''
        identity_filter = Q()
        if len(cpf) == 11:
            identity_filter |= Q(cpf_lookup=make_pii_lookup(cpf))
        if len(whatsapp) in (10, 11):
            identity_filter |= Q(whatsapp_lookup=make_pii_lookup(whatsapp))
        if identity_filter:
            queryset |= original_queryset.filter(identity_filter)
        return queryset, may_have_duplicates
