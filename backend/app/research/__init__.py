"""Research Engine module.

Discovers companies from external sources (Google Maps, LinkedIn, Instagram, a
website, a CSV import, manual entry). Deliberately knows nothing about AI, Mission or
Campaign — it doesn't import `app.ai`, `app.models.mission`, or Campaign-related code,
and never will. Whatever calls this engine decides what a discovered company becomes.
"""
