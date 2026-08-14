"""Configuration System: the platform's official, centralized configuration —
PlatformSettings (immutable, loaded once), a ConfigurationLoader that merges
DefaultConfiguration, EnvironmentVariables, and (as infrastructure only) JSON/
YAML file sources, and a ConfigurationValidator enforcing required fields,
types, and value constraints. Completely self-contained: it imports nothing
from any other app module and integrates with none of them. Bootstrap, API,
Runtime, Workers, Scheduler, CLI, and Frontend will consume this in a future
sprint; no existing module imports it yet.
"""
