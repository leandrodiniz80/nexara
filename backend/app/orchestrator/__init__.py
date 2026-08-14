"""System Orchestrator: the platform's single point of coordination. It
implements no business rule and executes no logic of its own — it only calls,
in order, whichever Decision/Rules/Runtime/Observability ports were injected
into it (Protocols defined in this module), and reports what happened. This
sprint integrates no real module: those four ports are satisfied by fakes in
tests today; a future sprint supplies real adapters.
"""
