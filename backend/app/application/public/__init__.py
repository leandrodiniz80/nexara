"""The platform's public use cases: what any future interface (REST,
GraphQL, CLI, Worker, SDK, Mobile) will actually execute. They belong to
none of Domain, Runtime, or CRM. Every use case now passes through
OperationsCoordinator before coordinating calls into
ApplicationInterfaceService, the Application layer's own public door.
"""
