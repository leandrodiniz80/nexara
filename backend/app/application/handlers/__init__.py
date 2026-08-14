"""The platform's official Command Handler infrastructure: the abstract
contract (CommandHandler), the registry holding implementations of it, and
the platform's first concrete handler (ExecutiveDashboardHandler). Public
operations stay decoupled from CommandBus, which never knows a concrete
handler.
"""
