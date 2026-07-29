import uuid

from app.events.bus.event_bus import EventBus
from app.events.publishers.event_publisher import EventPublisher
from app.events.registry.event_registry import EventRegistry
from app.events.schemas.mission_events import MissionCreated
from tests.events.chain_demo_handlers import (
    EmailApprovalHandler,
    EmailGenerationHandler,
    EmailSenderHandler,
    EmailSentCollectorHandler,
    ProspectCreationHandler,
    ResearchCompletionHandler,
    ResearchStarterHandler,
    WorkflowStarterHandler,
)

_ALL_EVENT_NAMES_IN_THE_CHAIN = {
    "mission.created",
    "research.started",
    "research.completed",
    "prospect.created",
    "workflow.started",
    "email.generated",
    "email.approved",
    "email.sent",
}


def _wire_the_chain(bus: EventBus, publisher: EventPublisher, collector: EmailSentCollectorHandler) -> None:
    registry = EventRegistry()
    registry.register_many(
        [
            ResearchStarterHandler(publisher),
            ResearchCompletionHandler(publisher),
            ProspectCreationHandler(publisher),
            WorkflowStarterHandler(publisher),
            EmailGenerationHandler(publisher),
            EmailApprovalHandler(publisher),
            EmailSenderHandler(publisher),
            collector,
        ]
    )
    registry.attach(bus)


async def test_mission_created_cascades_all_the_way_to_email_sent_via_the_event_bus():
    """The full chain from the task: MissionCreated -> ResearchStarted ->
    ResearchCompleted -> ProspectCreated -> WorkflowStarted -> EmailGenerated ->
    EmailApproved -> EmailSent — nothing here calls another handler directly; every
    step only happens because EventBus routed one event to the handler subscribed to it.
    """
    bus = EventBus()
    publisher = EventPublisher(bus)
    collector = EmailSentCollectorHandler()
    _wire_the_chain(bus, publisher, collector)

    mission_created = MissionCreated(
        aggregate_id=uuid.uuid4(),
        payload={"name": "Missão Verão 2027", "target_segment": "Pet Shop", "target_city": "Goiânia"},
    )

    await publisher.publish(mission_created)

    assert len(collector.received) == 1
    assert collector.received[0].event_name == "email.sent"

    logs = bus.list_execution_logs()
    assert {log.event_name for log in logs} == _ALL_EVENT_NAMES_IN_THE_CHAIN
    assert all(log.success for log in logs), [log for log in logs if not log.success]


async def test_execution_log_order_reflects_handler_completion_not_trigger_order():
    """A quirk worth locking down in a test: because dispatch() is synchronous and
    recursive (a handler's own publish() call runs — and fully finishes — inside
    handler.handle(), before that handler's own EventExecutionLog gets appended), the
    log for the *root* event (mission.created) is only appended once the *entire*
    downstream cascade it triggered has already completed. So the log ends up in
    reverse-causal (post-)order: the last event in the chain (email.sent) is logged
    first, and the one that started everything (mission.created) is logged last.
    """
    bus = EventBus()
    publisher = EventPublisher(bus)
    collector = EmailSentCollectorHandler()
    _wire_the_chain(bus, publisher, collector)

    await publisher.publish(MissionCreated(aggregate_id=uuid.uuid4()))

    logged_order = [log.event_name for log in bus.list_execution_logs()]
    assert logged_order == [
        "email.sent",
        "email.approved",
        "email.generated",
        "workflow.started",
        "prospect.created",
        "research.completed",
        "research.started",
        "mission.created",
    ]


async def test_correlation_id_stays_constant_across_the_whole_chain():
    bus = EventBus()
    publisher = EventPublisher(bus)
    collector = EmailSentCollectorHandler()
    _wire_the_chain(bus, publisher, collector)

    mission_created = MissionCreated(aggregate_id=uuid.uuid4())
    root_envelope = await publisher.publish(mission_created)

    email_sent = collector.received[0]
    assert email_sent.metadata["correlation_id"] == root_envelope.correlation_id
    # causation always points at the immediately preceding event, never straight to the root
    assert email_sent.metadata["causation_id"] != mission_created.event_id
