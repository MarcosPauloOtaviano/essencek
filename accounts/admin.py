from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'full_name', 'cpf', 'whatsapp', 'city', 'state', 'is_active', 'date_joined']
    search_fields = ['email', 'full_name', 'cpf', 'whatsapp']
    ordering = ['-date_joined']
    fieldsets = UserAdmin.fieldsets + (
        ('Dados extras', {'fields': ('full_name', 'cpf', 'whatsapp', 'cep', 'address',
                                     'address_number', 'address_complement',
                                     'neighborhood', 'city', 'state')}),
    )
