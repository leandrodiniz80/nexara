from functools import wraps


def requires_auth(container_getter):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            container = container_getter()
            container.require_auth()
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def requires_role(container_getter, role: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            container = container_getter()
            container.require_role(role)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def requires_permission(container_getter, permission: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            container = container_getter()
            container.require_permission(permission)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def requires_organization(container_getter):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            container = container_getter()
            container.require_auth()

            if container.current_organization_id() is None:
                raise PermissionError("No organization context")

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def requires_same_organization(container_getter, resource_org_id_getter):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            container = container_getter()
            resource_org_id = resource_org_id_getter()
            container.require_same_organization(resource_org_id)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def requires_limit(container_getter, limit_key: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            container = container_getter()
            return container.execute_with_limit(limit_key, fn, *args, **kwargs)

        return wrapper

    return decorator
