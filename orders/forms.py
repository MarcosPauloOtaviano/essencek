from django import forms
from core.utils import sanitize_text
from .models import Order
from accounts.validators import only_digits, normalize_email, normalize_whatsapp, validate_whatsapp


STATES = [
    ('', 'Selecione'),
    ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
    ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
    ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins'),
]


class UpperStateChoiceField(forms.ChoiceField):
    def to_python(self, value):
        value = super().to_python(value)
        return value.upper() if value else value


SHIPPING_METHOD_CHOICES = [
    ('delivery', 'Entrega (envio pelos Correios/transportadora)'),
    ('pickup', 'Retirada na loja'),
]


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(label='Nome completo', max_length=200)
    customer_email = forms.EmailField(label='E-mail')
    customer_whatsapp = forms.CharField(label='Telefone', max_length=20)

    shipping_method = forms.ChoiceField(
        label='Forma de entrega',
        choices=SHIPPING_METHOD_CHOICES,
        widget=forms.RadioSelect,
        initial='delivery',
        required=False,
    )

    address = forms.CharField(label='Rua / Avenida', max_length=255, required=False)
    address_number = forms.CharField(label='Número', max_length=20, required=False)
    address_complement = forms.CharField(label='Complemento', max_length=100, required=False)
    neighborhood = forms.CharField(label='Bairro', max_length=100, required=False)
    city = forms.CharField(label='Cidade', max_length=100, required=False)
    state = UpperStateChoiceField(label='Estado', choices=STATES, required=False)
    cep = forms.CharField(label='CEP', max_length=9, required=False,
                          widget=forms.TextInput(attrs={'placeholder': '00000-000'}))

    payment_method = forms.ChoiceField(
        label='Forma de pagamento',
        choices=Order.PAYMENT_CHOICES,
        widget=forms.RadioSelect
    )

    customer_notes = forms.CharField(
        label='Observações (opcional)', required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Informações adicionais...'})
    )

    def clean_customer_name(self):
        name = sanitize_text(self.cleaned_data.get('customer_name') or '')
        if len(name.split()) < 2:
            raise forms.ValidationError('Informe nome e sobrenome.')
        return name

    def clean_customer_email(self):
        email = normalize_email(self.cleaned_data.get('customer_email'))
        if not email:
            raise forms.ValidationError('Informe um e-mail válido.')
        return email

    def clean_customer_whatsapp(self):
        whatsapp = normalize_whatsapp(self.cleaned_data.get('customer_whatsapp'))
        validate_whatsapp(whatsapp)
        return whatsapp

    def clean_shipping_method(self):
        return self.cleaned_data.get('shipping_method') or 'delivery'

    def clean_cep(self):
        cep = only_digits(self.cleaned_data.get('cep'))
        if len(cep) != 8:
            raise forms.ValidationError('Informe um CEP válido com 8 dígitos.')
        return f'{cep[:5]}-{cep[5:]}'

    def clean_address(self):
        return sanitize_text(self.cleaned_data.get('address') or '')

    def clean_address_complement(self):
        return sanitize_text(self.cleaned_data.get('address_complement') or '')

    def clean_neighborhood(self):
        return sanitize_text(self.cleaned_data.get('neighborhood') or '')

    def clean_city(self):
        return sanitize_text(self.cleaned_data.get('city') or '')

    def clean_customer_notes(self):
        return sanitize_text(self.cleaned_data.get('customer_notes') or '')

    def clean_state(self):
        state = (self.cleaned_data.get('state') or '').strip().upper()
        if not state:
            return state
        valid_states = {value for value, _ in STATES if value}
        if state not in valid_states:
            raise forms.ValidationError('Informe um estado válido.')
        return state

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('shipping_method') == 'delivery':
            required_fields = {
                'address': 'Informe o endereço.',
                'address_number': 'Informe o número.',
                'city': 'Informe a cidade.',
                'cep': 'Informe o CEP.',
            }
            for field, msg in required_fields.items():
                if not cleaned.get(field):
                    self.add_error(field, msg)
            if not cleaned.get('state'):
                self.add_error('state', 'Informe o estado.')
        return cleaned
