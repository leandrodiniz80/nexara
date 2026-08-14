import inspect

import pytest
from pydantic import ValidationError

from app.platform.health import health_report, health_report_factory
from app.platform.health.health_report import HealthReport
from app.platform.health.health_report_factory import build_health_report


def test_lista_vazia_healthy_true():
    report = build_health_report(())

    assert report.results == ()
    assert report.healthy is True


def test_um_true():
    report = build_health_report((True,))

    assert report.results == (True,)
    assert report.healthy is True


def test_um_false():
    report = build_health_report((False,))

    assert report.results == (False,)
    assert report.healthy is False


def test_varios_resultados_all_true():
    report = build_health_report((True, True, True))

    assert report.results == (True, True, True)
    assert report.healthy is True


def test_mistura_true_false():
    report = build_health_report((True, False, True))

    assert report.results == (True, False, True)
    assert report.healthy is False


def test_factory_preserva_ordem():
    results = (True, False, False, True)

    report = build_health_report(results)

    assert report.results == results


def test_factory_calcula_healthy_corretamente():
    assert build_health_report((True, True)).healthy is True
    assert build_health_report((True, False)).healthy is False
    assert build_health_report((False, False)).healthy is False
    assert build_health_report(()).healthy is True


def test_imutabilidade_rejects_attribute_assignment():
    report = build_health_report((True,))

    with pytest.raises(ValidationError):
        report.results = ()

    with pytest.raises(ValidationError):
        report.healthy = False


def test_health_report_campos_diretos():
    report = HealthReport(results=(True, False), healthy=False)

    assert report.results == (True, False)
    assert report.healthy is False


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(health_report)
    assert "app.runtime" not in source
    source_factory = inspect.getsource(health_report_factory)
    assert "app.runtime" not in source_factory


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(health_report)
    assert "app.operations" not in source
    source_factory = inspect.getsource(health_report_factory)
    assert "app.operations" not in source_factory


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(health_report)
    assert "app.crm" not in source
    source_factory = inspect.getsource(health_report_factory)
    assert "app.crm" not in source_factory


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(health_report)
    assert "app.workflows" not in source
    source_factory = inspect.getsource(health_report_factory)
    assert "app.workflows" not in source_factory


def test_nenhuma_referencia_a_lifecycle():
    source = inspect.getsource(health_report)
    assert "Lifecycle" not in source
    source_factory = inspect.getsource(health_report_factory)
    assert "Lifecycle" not in source_factory


def test_nenhuma_referencia_a_platform_bootstrap():
    source = inspect.getsource(health_report)
    assert "PlatformBootstrap" not in source
    source_factory = inspect.getsource(health_report_factory)
    assert "PlatformBootstrap" not in source_factory
