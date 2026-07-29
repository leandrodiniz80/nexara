"""Internal event-driven communication infrastructure.

In-memory only — no RabbitMQ, no Kafka, no external broker. From this point on, no
module is allowed to import another module's engine/service just to trigger a process
in it: it publishes a DomainEvent through EventBus (via EventPublisher) instead, and
whatever needs to react subscribes an EventHandler (via EventSubscriber/EventRegistry).
"""
