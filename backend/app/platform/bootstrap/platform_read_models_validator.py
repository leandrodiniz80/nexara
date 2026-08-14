def validate_read_models(data: dict) -> None:
    if not isinstance(data, dict):
        raise TypeError("read_models must be a dict")

    required_keys = {"catalog", "services", "service_names", "service_map"}

    missing = required_keys - set(data.keys())

    if missing:
        raise ValueError(f"Missing read model keys: {missing}")
