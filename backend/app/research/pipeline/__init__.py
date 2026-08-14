"""Lead Discovery Pipeline: turns Research Engine into something runnable end-to-end
against a MockProvider — search, normalize, dedup, score, persist, publish events.

Still no Google/LinkedIn/AI integration. Still no APIs, no frontend.
"""

from app.research.pipeline.factory import build_default_lead_discovery_pipeline
from app.research.pipeline.lead_discovery_pipeline import LeadDiscoveryPipeline
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_report import PipelineReport
from app.research.pipeline.pipeline_result import PipelineResult
from app.research.pipeline.pipeline_state import PipelineState
from app.research.pipeline.pipeline_step import PipelineStep
from app.research.pipeline.strategy_kind import StrategyKind

__all__ = [
    "LeadDiscoveryPipeline",
    "PipelineContext",
    "PipelineResult",
    "PipelineReport",
    "PipelineState",
    "PipelineStep",
    "StrategyKind",
    "build_default_lead_discovery_pipeline",
]
