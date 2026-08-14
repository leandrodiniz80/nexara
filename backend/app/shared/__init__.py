"""Infrastructure shared across domains — generic building blocks with no
knowledge of any specific domain (not Commands, not Queries, not Modules,
not CRM, not Runtime). Domains depend on app.shared; app.shared never
depends on any domain.
"""
