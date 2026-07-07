from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import ProfileForm, RegisterForm
from .models import User


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class UserIdentityValidationTests(TestCase):
    def valid_register_data(self, **overrides):
        data = {
            'full_name': 'Cliente Teste',
            'email': 'Cliente@Example.COM',
            'cpf': '529.982.247-25',
            'whatsapp': '(11) 98765-4321',
            'password1': 'SenhaForte123!',
            'password2': 'SenhaForte123!',
        }
        data.update(overrides)
        return data

    def create_user(self, **overrides):
        data = {
            'username': 'cliente@example.com',
            'email': 'cliente@example.com',
            'full_name': 'Cliente Existente',
            'cpf': '52998224725',
            'whatsapp': '11987654321',
            'password': 'SenhaForte123!',
        }
        data.update(overrides)
        return User.objects.create_user(**data)

    def test_register_form_saves_normalized_identity_fields(self):
        form = RegisterForm(data=self.valid_register_data())

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertEqual(user.email, 'cliente@example.com')
        self.assertEqual(user.username, 'cliente@example.com')
        self.assertEqual(user.cpf, '52998224725')
        self.assertEqual(user.whatsapp, '11987654321')

    def test_register_form_requires_identity_fields(self):
        form = RegisterForm(data=self.valid_register_data(email='', cpf='', whatsapp=''))

        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('cpf', form.errors)
        self.assertIn('whatsapp', form.errors)

    def test_register_form_rejects_duplicate_email_case_insensitive(self):
        self.create_user()
        form = RegisterForm(data=self.valid_register_data(
            email='CLIENTE@example.com',
            cpf='111.444.777-35',
            whatsapp='(21) 98765-4321',
        ))

        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_register_form_rejects_duplicate_cpf_after_formatting(self):
        self.create_user()
        form = RegisterForm(data=self.valid_register_data(
            email='outro@example.com',
            cpf='529.982.247-25',
            whatsapp='(21) 98765-4321',
        ))

        self.assertFalse(form.is_valid())
        self.assertIn('cpf', form.errors)

    def test_register_form_rejects_duplicate_whatsapp_after_formatting(self):
        self.create_user()
        form = RegisterForm(data=self.valid_register_data(
            email='outro@example.com',
            cpf='111.444.777-35',
            whatsapp='+55 (11) 98765-4321',
        ))

        self.assertFalse(form.is_valid())
        self.assertIn('whatsapp', form.errors)

    def test_register_form_rejects_invalid_cpf(self):
        form = RegisterForm(data=self.valid_register_data(cpf='123.456.789-00'))

        self.assertFalse(form.is_valid())
        self.assertIn('cpf', form.errors)

    def test_profile_form_updates_username_when_email_changes(self):
        user = self.create_user()
        form = ProfileForm(data={
            'full_name': 'Cliente Atualizado',
            'email': 'Novo.Email@Example.COM',
            'cpf': '529.982.247-25',
            'whatsapp': '(11) 98765-4321',
            'cep': '',
            'address': '',
            'address_number': '',
            'address_complement': '',
            'neighborhood': '',
            'city': '',
            'state': '',
        }, instance=user)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user.refresh_from_db()

        self.assertEqual(user.email, 'novo.email@example.com')
        self.assertEqual(user.username, 'novo.email@example.com')

    def test_register_view_does_not_create_duplicate_identity(self):
        self.create_user()

        response = self.client.post(reverse('register'), self.valid_register_data(
            email='novo@example.com',
            cpf='111.444.777-35',
            whatsapp='5511987654321',
        ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_login_view_rejects_external_next_redirect(self):
        self.create_user()

        response = self.client.post(
            f"{reverse('login')}?next=https://evil.example/phishing",
            {'username': 'cliente@example.com', 'password': 'SenhaForte123!'},
        )

        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_register_view_rejects_external_next_redirect(self):
        response = self.client.post(
            f"{reverse('register')}?next=https://evil.example/phishing",
            self.valid_register_data(email='novo@example.com', cpf='111.444.777-35', whatsapp='21987654321'),
        )

        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
