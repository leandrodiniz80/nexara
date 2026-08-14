import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.contracts import (
    public_contract_factory,
    public_error,
    public_metadata,
    public_response,
    public_warning,
)
from app.contracts.public_contract_factory import PublicContractFactory
from app.contracts.public_error import PublicError
from app.contracts.public_metadata import PublicMetadata
from app.contracts.public_response import PublicResponse
from app.contracts.public_warning import PublicWarning

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)

_MODULES = (
    public_response,
    public_metadata,
    public_error,
    public_warning,
    public_contract_factory,
)


def test_success_requires_a_payload_and_carries_no_errors():
    factory = PublicContractFactory()
    payload = {"revenue": 5000.0}

    response = factory.success(payload, now=_T0)

    assert isinstance(response, PublicResponse)
    assert response.success is True
    assert response.payload is payload
    assert response.errors == ()
    assert response.warnings == ()


def test_warning_requires_a_payload_and_carries_warnings_with_no_errors():
    factory = PublicContractFactory()
    payload = {"revenue": 5000.0}
    warning = PublicWarning(code="LOW_CONFIDENCE", message="Baixa confiança na previsão.")

    response = factory.warning(payload, [warning], now=_T0)

    assert response.success is True
    assert response.payload is payload
    assert response.warnings == (warning,)
    assert response.errors == ()


def test_failure_carries_no_payload_and_requires_errors():
    factory = PublicContractFactory()
    error = PublicError(code="NOT_FOUND", message="Oportunidade não encontrada.")

    response = factory.failure([error], now=_T0)

    assert response.success is False
    assert response.payload is None
    assert response.errors == (error,)
    assert response.warnings == ()


def test_imutabilidade_rejects_attribute_assignment():
    factory = PublicContractFactory()
    response = factory.success({"revenue": 5000.0}, now=_T0)

    with pytest.raises(ValidationError):
        response.success = False

    with pytest.raises(ValidationError):
        response.metadata.version = "2.0.0"

    error = PublicError(code="X", message="Erro X.")
    with pytest.raises(ValidationError):
        error.message = "Alterado"


def test_payload_preservado_is_never_converted_or_serialized():
    factory = PublicContractFactory()

    class _ArbitraryObject:
        pass

    payload = _ArbitraryObject()

    response = factory.success(payload, now=_T0)

    assert response.payload is payload


def test_metadata_preservada_contains_the_expected_fields():
    factory = PublicContractFactory()

    response = factory.success({"revenue": 5000.0}, request_id="req-123", now=_T0)

    assert isinstance(response.metadata, PublicMetadata)
    assert response.metadata.application == "Elevel Prospect AI"
    assert response.metadata.version == "1.0.0"
    assert response.metadata.generated_at == _T0
    assert response.metadata.request_id == "req-123"


def test_errors_preservados_in_the_same_order():
    factory = PublicContractFactory()
    error_a = PublicError(code="A", message="Erro A.")
    error_b = PublicError(code="B", message="Erro B.")

    response = factory.failure([error_a, error_b], now=_T0)

    assert response.errors == (error_a, error_b)


def test_warnings_preservados_in_the_same_order():
    factory = PublicContractFactory()
    warning_a = PublicWarning(code="A", message="Aviso A.")
    warning_b = PublicWarning(code="B", message="Aviso B.")

    response = factory.warning({"revenue": 5000.0}, [warning_a, warning_b], now=_T0)

    assert response.warnings == (warning_a, warning_b)


def test_factory_is_directly_usable_with_no_wiring():
    factory = PublicContractFactory()

    assert isinstance(factory, PublicContractFactory)
    response = factory.success({"revenue": 5000.0}, now=_T0)
    assert isinstance(response, PublicResponse)


def test_nenhum_import_de_crm():
    for module in _MODULES:
        assert "app.crm" not in inspect.getsource(module)


def test_nenhum_import_de_runtime():
    for module in _MODULES:
        assert "app.runtime" not in inspect.getsource(module)


def test_nenhum_import_de_workflow():
    for module in _MODULES:
        assert "app.workflows" not in inspect.getsource(module)


def test_nenhum_import_de_presentation():
    for module in _MODULES:
        assert "app.presentation" not in inspect.getsource(module)
