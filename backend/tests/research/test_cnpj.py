from app.research.services.cnpj import is_valid_cnpj, normalize_cnpj

VALID_CNPJ = "11.222.333/0001-81"
INVALID_CNPJ = "11.222.333/0001-80"


def test_normalize_cnpj_strips_punctuation():
    assert normalize_cnpj(VALID_CNPJ) == "11222333000181"


def test_is_valid_cnpj_accepts_correct_check_digits():
    assert is_valid_cnpj(VALID_CNPJ) is True


def test_is_valid_cnpj_rejects_wrong_check_digit():
    assert is_valid_cnpj(INVALID_CNPJ) is False


def test_is_valid_cnpj_rejects_repeated_digits():
    assert is_valid_cnpj("11111111111111") is False


def test_is_valid_cnpj_rejects_wrong_length():
    assert is_valid_cnpj("123") is False
