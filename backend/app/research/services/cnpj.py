import re

_FIRST_DIGIT_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_SECOND_DIGIT_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def normalize_cnpj(cnpj: str) -> str:
    """Strips everything but digits (e.g. "12.345.678/0001-90" -> "12345678000190")."""
    return re.sub(r"\D", "", cnpj)


def _check_digit(digits: list[int], weights: list[int]) -> int:
    total = sum(d * w for d, w in zip(digits, weights))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_cnpj(cnpj: str) -> bool:
    """Standard Brazilian CNPJ mod-11 check-digit validation. Pure arithmetic, no
    external lookup — just confirms the number is well-formed, not that it's registered.
    """
    digits_only = normalize_cnpj(cnpj)
    if len(digits_only) != 14:
        return False
    if digits_only == digits_only[0] * 14:
        return False

    numbers = [int(d) for d in digits_only]
    first_check = _check_digit(numbers[:12], _FIRST_DIGIT_WEIGHTS)
    if first_check != numbers[12]:
        return False
    second_check = _check_digit(numbers[:13], _SECOND_DIGIT_WEIGHTS)
    return second_check == numbers[13]
