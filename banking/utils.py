from __future__ import annotations

import random
from decimal import Decimal

SUSPECT_CHARS = {
    'Ð',
    'Ñ',
    'Ò',
    'Ó',
    'Â',
    'Ã',
    'Þ',
    'Ý',
    'Ø',
    'µ',
    '¶',
    '·',
    '¸',
    '¹',
    'º',
    '»',
    '¼',
    '½',
    '¾',
    '¿',
    'Ј',
}


def normalize_text(value: str | None) -> str | None:
    if not isinstance(value, str) or not value:
        return value

    if not any(char in value for char in SUSPECT_CHARS):
        return value

    for encoding in ('cp1251', 'latin1'):
        try:
            decoded = value.encode(encoding).decode('utf-8')
        except UnicodeError:
            continue
        if not any(char in decoded for char in SUSPECT_CHARS):
            return decoded
    return value


def biased_random_amount(
    min_amount: Decimal,
    max_amount: Decimal,
    skew: float = 2.5,
) -> Decimal:
    """
    Возвращает сумму в диапазоне [min_amount, max_amount] с уклоном
    к нижней границе. Значение 100000 ₽ встречается заметно реже
    за счёт параметра skew.
    """
    min_amount = Decimal(min_amount)
    max_amount = Decimal(max_amount)

    if min_amount >= max_amount:
        return min_amount

    if skew <= 0:
        skew = 1.0

    min_value = int(min_amount)
    max_value = int(max_amount)
    span = max_value - min_value

    if span <= 0:
        return Decimal(min_value)

    biased_factor = random.random() ** skew
    candidate = min_value + int((span + 1) * biased_factor)
    candidate = max(min_value, min(candidate, max_value))

    return Decimal(candidate)


def random_target_balance() -> Decimal:
    """
    Возвращает реалистичное значение баланса.
    Большинство значений лежат ниже 100k, но иногда встречаются крупные суммы.
    """
    buckets = [
        (0.05, (200000, 300000)),
        (0.15, (100000, 200000)),
        (0.20, (50000, 100000)),
        (0.35, (2000, 50000)),
        (0.25, (0, 2000))
    ]

    roll = random.random()
    cumulative = 0.0
    lower = 0
    upper = 50000

    for weight, (bucket_lower, bucket_upper) in buckets:
        cumulative += weight
        if roll <= cumulative:
            lower = bucket_lower
            upper = bucket_upper
            break
    else:
        lower, upper = buckets[-1][1]

    value = random.randint(lower, upper)
    cents = random.randint(0, 99)

    return Decimal(f"{value}.{cents:02d}")
