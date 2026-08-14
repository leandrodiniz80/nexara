import base64
import json
import os


class PlatformStorage:
    def load(self) -> dict:
        return {}

    def save(self, data: dict) -> None:
        pass


class InMemoryStorage(PlatformStorage):
    def __init__(self):
        self._data: dict = {}

    def load(self) -> dict:
        return self._data

    def save(self, data: dict) -> None:
        self._data = data


class FileStorage(PlatformStorage):
    def __init__(self, path: str):
        self._path = path

    def load(self) -> dict:
        if not os.path.exists(self._path):
            return {}

        with open(self._path, encoding="utf-8") as f:
            raw = json.load(f)

        return _decode_bytes(raw)

    def save(self, data: dict) -> None:
        encoded = _encode_bytes(data)

        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(encoded, f)


def _encode_bytes(value):
    if isinstance(value, bytes):
        return {"__bytes__": base64.b64encode(value).decode("ascii")}

    if isinstance(value, dict):
        return {key: _encode_bytes(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_encode_bytes(item) for item in value]

    return value


def _decode_bytes(value):
    if isinstance(value, dict):
        if set(value.keys()) == {"__bytes__"}:
            return base64.b64decode(value["__bytes__"])

        return {key: _decode_bytes(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_decode_bytes(item) for item in value]

    return value
