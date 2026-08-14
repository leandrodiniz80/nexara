"""Sales Intelligence Engine.

Turns commercial data into commercial decisions (scores, recommendations, rankings) —
purely rule-based, fully deterministic. Knows nothing about AI, Mission, Prospect,
Campaign, Workflow, or Research: it only knows CommercialProfile. Whatever calls this
module (today: nothing; tomorrow, most likely: AIOrchestrator) is responsible for
building a CommercialProfile from whatever real entities it has.
"""
