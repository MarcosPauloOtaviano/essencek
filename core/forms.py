from django import forms
from .models import StoreSettings, NextTrip, ShowcaseSlide
from accounts.validators import only_digits, normalize_whatsapp, validate_whatsapp
from products.image_utils import validate_product_image_upload


ALLOWED_PAYMENT_GATEWAYS = {'sandbox', 'mercadopago'}


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = StoreSettings
        fields = ['store_name', 'logo', 'whatsapp', 'instagram', 'email',
                  'cep_origem', 'home_headline', 'home_subheadline', 'about_text',
                  'order_mode_active', 'shipping_active', 'payment_gateway']
        widgets = {
            'home_subheadline': forms.Textarea(attrs={'rows': 3}),
            'about_text': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['whatsapp'].label = 'Telefone da loja'

    def clean_whatsapp(self):
        raw = self.cleaned_data.get('whatsapp')
        digits = only_digits(raw)
        if not digits:
            return ''
        local_number = normalize_whatsapp(digits)
        validate_whatsapp(local_number)
        return digits if digits.startswith('55') else f'55{local_number}'

    def clean_instagram(self):
        instagram = (self.cleaned_data.get('instagram') or '').strip()
        instagram = instagram.removeprefix('@')
        instagram = instagram.rstrip('/').split('/')[-1]
        return instagram

    def clean_cep_origem(self):
        cep = only_digits(self.cleaned_data.get('cep_origem'))
        if cep and len(cep) != 8:
            raise forms.ValidationError('Informe um CEP válido com 8 dígitos.')
        return f'{cep[:5]}-{cep[5:]}' if cep else ''

    def clean_payment_gateway(self):
        gateway = (self.cleaned_data.get('payment_gateway') or 'sandbox').strip().lower()
        if gateway not in ALLOWED_PAYMENT_GATEWAYS:
            raise forms.ValidationError('Gateway de pagamento inválido.')
        return gateway

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo:
            validate_product_image_upload(logo)
        return logo


class ShowcaseTextSlideForm(forms.ModelForm):
    class Meta:
        model = ShowcaseSlide
        fields = ['title', 'description', 'background_style', 'link', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Ex: Frete grátis essa semana!'}),
            'description': forms.TextInput(attrs={'placeholder': 'Ex: Em compras acima de R$ 300'}),
            'link': forms.TextInput(attrs={'placeholder': '/produtos/ ou URL completa (opcional)'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('title') and not cleaned_data.get('description'):
            raise forms.ValidationError('Escreva um título ou um texto para o slide.')
        return cleaned_data


class NextTripForm(forms.ModelForm):
    class Meta:
        model = NextTrip
        fields = ['trip_date', 'order_deadline', 'message', 'is_active', 'notes']
        widgets = {
            'trip_date': forms.DateInput(attrs={'type': 'date'}),
            'order_deadline': forms.DateInput(attrs={'type': 'date'}),
            'message': forms.Textarea(attrs={'rows': 4}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
