"""Operations' own PlatformModule — the platform's pilot migration to the
official module architecture. This is the first (and, for now, only)
domain package authorized to import from app.platform: it implements
PlatformModule and supplies its own StageProvider, exactly as the
architecture's future CRM/Runtime/AI/Automation/Workflow modules will.
"""
