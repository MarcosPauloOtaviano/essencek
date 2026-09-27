from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from core.encryption import EncryptedCharField
from core.pii import make_pii_lookup

from .validators import normalize_cpf, normalize_email, normalize_whatsapp, validate_cpf, validate_whatsapp


class User(AbstractUser):
    email = models.EmailField('E-mail', unique=True)
    full_name = models.CharField('Nome completo', max_length=200)
    cpf_encrypted = EncryptedCharField('CPF criptografado', max_length=200, blank=True, default='')
    whatsapp_encrypted = EncryptedCharField('Telefone criptografado', max_length=200, blank=True, default='')
    cpf_lookup = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    whatsapp_lookup = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    # Address
    cep = models.CharField('CEP', max_length=9, blank=True)
    address = models.CharField('Endereço', max_length=255, blank=True)
    address_number = models.CharField('Número', max_length=20, blank=True)
    address_complement = models.CharField('Complemento', max_length=100, blank=True)
    neighborhood = models.CharField('Bairro', max_length=100, blank=True)
    city = models.CharField('Cidade', max_length=100, blank=True)
    state = models.CharField('Estado', max_length=2, blank=True)

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        constraints = [
            models.UniqueConstraint(Lower('email'), name='accounts_user_email_ci_unique'),
        ]

    REQUIRED_FIELDS = ['email', 'full_name']

    def __str__(self):
        return self.full_name or self.username

    @property
    def cpf(self):
        return self.cpf_encrypted

    @cpf.setter
    def cpf(self, value):
        normalized = normalize_cpf(value)
        self.cpf_encrypted = normalized or ''
        self.cpf_lookup = make_pii_lookup(normalized)

    @property
    def whatsapp(self):
        return self.whatsapp_encrypted

    @whatsapp.setter
    def whatsapp(self, value):
        normalized = normalize_whatsapp(value)
        self.whatsapp_encrypted = normalized or ''
        self.whatsapp_lookup = make_pii_lookup(normalized)

    def clean(self):
        super().clean()
        self.email = normalize_email(self.email)
        self.username = self.email
        self.cpf = self.cpf
        self.whatsapp = self.whatsapp
        if self.cpf:
            validate_cpf(self.cpf)
        if self.whatsapp:
            validate_whatsapp(self.whatsapp)

    def save(self, *args, **kwargs):
        self.email = normalize_email(self.email)
        if self.email:
            self.username = self.email
        self.cpf = self.cpf
        self.whatsapp = self.whatsapp
        super().save(*args, **kwargs)

    def get_full_address(self):
        parts = [self.address]
        if self.address_number:
            parts.append(f', {self.address_number}')
        if self.address_complement:
            parts.append(f' - {self.address_complement}')
        if self.neighborhood:
            parts.append(f', {self.neighborhood}')
        if self.city:
            parts.append(f', {self.city}')
        if self.state:
            parts.append(f'/{self.state}')
        if self.cep:
            parts.append(f' - CEP: {self.cep}')
        return ''.join(parts)
