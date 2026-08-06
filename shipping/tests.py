from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .utils import calculate_shipping


class ShippingCalculationTests(SimpleTestCase):
    @override_settings(FRENET_TOKEN='')
    @patch('shipping.utils.validate_cep', return_value=True)
    def test_product_quote_has_safe_fallback_and_explanatory_note(self, _validate_mock):
        product = SimpleNamespace(
            weight=Decimal('0.4'),
            height=Decimal('12'),
            width=Decimal('8'),
            length=Decimal('20'),
        )

        result = calculate_shipping('01001000', product=product)

        self.assertTrue(result['success'])
        self.assertTrue(result['options'])
        self.assertIn('estimados', result['note'])
