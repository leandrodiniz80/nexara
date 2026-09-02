import logging

from app.api.api_factory import create_app

# Nothing in this codebase called logging.basicConfig()/dictConfig() before
# now — every logging.getLogger("app....") call (this router's own, plus
# every existing one e.g. api/middleware/logging.py) inherited the root
# logger's default level (WARNING), so every .info() call across the whole
# app was silently dropped before it ever reached a handler, regardless of
# whether one was attached. uvicorn's own "uvicorn.access"/"uvicorn.error"
# loggers are unaffected (uvicorn configures those directly) — only
# everything else was silent. Must run before create_app() so every logger
# obtained anywhere at import time already sees this level.
logging.basicConfig(level=logging.INFO)

app = create_app()
