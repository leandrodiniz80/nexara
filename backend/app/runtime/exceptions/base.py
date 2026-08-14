class ExecutionRuntimeError(Exception):
    """Root of every exception raised inside the Execution Runtime module. Named
    ExecutionRuntimeError rather than RuntimeError to avoid shadowing the Python
    builtin of the same name."""
