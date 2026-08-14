import enum


class StrategyKind(str, enum.Enum):
    """Which SearchStrategy a PipelineContext should run. One member per strategy in
    app.research.strategies — a pipeline-routing concern, kept separate from the
    strategies themselves so this package doesn't need to import strategy classes just
    to describe which one was requested."""

    CITY = "city"
    SEGMENT = "segment"
    CNAE = "cnae"
    NEARBY = "nearby"
