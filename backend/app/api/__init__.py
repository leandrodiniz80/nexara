"""Public HTTP API: a thin layer over the Application Services (app/application).
Routes never call an Engine, a Repository, or app/ai directly — only Application
Services, reached exclusively through Dependency Injection.
"""
