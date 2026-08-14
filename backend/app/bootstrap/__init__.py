"""Composition Root / Dependency Injection Container: the platform's single
official place that calls every existing module's `build_default_*` Factory,
registers each result into a DependencyContainer, and exposes it as a
read-only ServiceLocator. It creates no business rule, no new Engine, and
integrates no module with another — it only builds and holds what already
exists. No existing module may import this package; only future executables
(CLI, FastAPI, Worker, Scheduler, main.py) will.
"""
