"""The platform's official Composition Root: PlatformBootstrap, the single
object responsible for assembling the platform's whole dependency tree —
Runtime, Operations, CommandBus, QueryBus, Application, Presentation,
PlatformInterface, and the Orchestrator — exclusively through their own
official `build_default_*` factories. It never executes domain logic,
never instantiates a concrete class by hand, and never knows any
implementation detail beyond which factory to call.
"""
