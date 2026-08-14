import re

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def extract_placeholders(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(_PLACEHOLDER_PATTERN.findall(text))


def substitute(text: str, variables: dict[str, object], *, on_missing) -> str:
    """Replaces every `{{name}}` in `text` with `str(variables[name])`. `on_missing` is
    called (and its return value used, or it may raise) for any placeholder without a
    matching variable — the caller decides what that means (AssetRenderer raises;
    a preview tool might substitute a placeholder instead)."""

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            return on_missing(key)
        return str(variables[key])

    return _PLACEHOLDER_PATTERN.sub(_replace, text)
