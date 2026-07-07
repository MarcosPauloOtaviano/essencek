import re

from django.core.exceptions import ValidationError


ONLY_DIGITS_RE = re.compile(r'\D+')


def only_digits(value):
    return ONLY_DIGITS_RE.sub('', value or '')


def normalize_email(value):
    return (value or '').strip().casefold()


def normalize_cpf(value):
    digits = only_digits(value)
    return digits or None


def normalize_whatsapp(value):
    digits = only_digits(value)
    if digits.startswith('55') and len(digits) in (12, 13):
        digits = digits[2:]
    return digits or None


def validate_cpf(value):
    cpf = normalize_cpf(value)
    if not cpf or len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValidationError('Informe um CPF válido.')

    def digit_for(numbers):
        total = sum(int(number) * weight for number, weight in zip(numbers, range(len(numbers) + 1, 1, -1)))
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    first_digit = digit_for(cpf[:9])
    second_digit = digit_for(cpf[:10])
    if cpf[-2:] != f'{first_digit}{second_digit}':
        raise ValidationError('Informe um CPF válido.')


def validate_whatsapp(value):
    whatsapp = normalize_whatsapp(value)
    if not whatsapp or len(whatsapp) not in (10, 11) or whatsapp == whatsapp[0] * len(whatsapp):
        raise ValidationError('Informe um telefone válido com DDD.')
