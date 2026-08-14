import inspect

from app.operations.module import operations_stage_provider
from app.operations.module.operations_module import OperationsModule
from app.operations.module.operations_stage_provider import OperationsStageProvider
from app.platform.modules.platform_module import PlatformModule
from app.platform.pipeline.operations_stage import OperationsStage
from app.platform.pipeline.stage_provider import StageProvider


def test_operations_module_e_um_platform_module():
    assert isinstance(OperationsModule(), PlatformModule)


def test_operations_module_name():
    assert OperationsModule().name() == "operations"


def test_operations_module_stage_provider_e_operations_stage_provider():
    module = OperationsModule()

    assert isinstance(module.stage_provider(), OperationsStageProvider)


def test_injecao_de_stage_provider_customizado_no_operations_module():
    custom = OperationsStageProvider()

    module = OperationsModule(stage_provider=custom)

    assert module.stage_provider() is custom


def test_operations_stage_provider_e_uma_stage_provider():
    assert isinstance(OperationsStageProvider(), StageProvider)


def test_operations_stage_provider_retorna_exclusivamente_operations_stage():
    stages = OperationsStageProvider().stages()

    assert len(stages) == 1
    assert isinstance(stages[0], OperationsStage)
    assert stages[0].name() == "operations"


def test_ordem_e_sempre_uma_tupla_de_um_elemento():
    stages = OperationsStageProvider().stages()

    assert isinstance(stages, tuple)
    assert len(stages) == 1


def test_injecao_de_operations_stage_customizado():
    stage = OperationsStage()

    provider = OperationsStageProvider(operations_stage=stage)

    assert provider.stages() == (stage,)


def test_operations_stage_provider_conhece_apenas_operations_stage():
    source = inspect.getsource(operations_stage_provider)
    assert "DecisionStage" not in source
    assert "RuntimeStage" not in source
    assert "ObservabilityStage" not in source
    assert "app.decision" not in source
    assert "app.runtime" not in source
    assert "app.observability" not in source
