from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from core.encryption import EncryptedCharField
from core.pii import make_pii_lookup

from .validators import normalize_cpf, normalize_email, normalize_whatsapp, validate_cpf, validate_whatsapp


class User(AbstractUser):
    email = models.EmailField('E-mail', unique=True)
    full_name = models.CharField('Nome completo', max_length=200)
    # Kept nullable for a reversible rolling deployment; new writes clear them.
    legacy_cpf = models.CharField(db_column='cpf', max_length=11, unique=True, null=True, blank=True, editable=False)
    legacy_whatsapp = models.CharField(db_column='whatsapp', max_length=11, unique=True, null=True, blank=True, editable=False)
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
        return self.legacy_cpf or self.cpf_encrypted

    @cpf.setter
    def cpf(self, value):
        normalized = normalize_cpf(value)
        self.cpf_encrypted = normalized or ''
        self.cpf_lookup = make_pii_lookup(normalized)
        self.legacy_cpf = None

    @property
    def whatsapp(self):
        return self.legacy_whatsapp or self.whatsapp_encrypted

    @whatsapp.setter
    def whatsapp(self, value):
        normalized = normalize_whatsapp(value)
        self.whatsapp_encrypted = normalized or ''
        self.whatsapp_lookup = make_pii_lookup(normalized)
        self.legacy_whatsapp = None

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
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
        self.email = normalize_email(self.email)
        if self.email:
            self.username = self.email
        for name in ('cpf', 'whatsapp'):
            identity_fields = {name, f'{name}_encrypted', f'{name}_lookup', f'legacy_{name}'}
            if update_fields is None or identity_fields & update_fields:
                setattr(self, name, getattr(self, name))
                if update_fields is not None:
                    update_fields.update(identity_fields - {name})
                    update_fields.discard(name)
        if update_fields is not None:
            if 'email' in update_fields:
                update_fields.add('username')
            kwargs['update_fields'] = update_fields
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
