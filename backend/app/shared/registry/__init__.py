"""The platform's generic registry infrastructure — the single structural
pattern (register/register_many/find/exists/list, frozen, every mutation
returns a new instance) that CommandRegistry, QueryRegistry, and
ModuleRegistry each now encapsulate instead of separately reimplementing.
"""
