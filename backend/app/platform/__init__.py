"""Platform Kernel: the platform's single internal access point for registering
and querying which modules exist. It implements no business rules and knows
nothing about AI, CRM, Mission, or Prospect — it only registers descriptors and
will be used by the CLI, API, Workers, Scheduler, and the application's bootstrap
as their one shared point of module discovery.
"""
