"""Presentation layer: converts already-computed commercial domain models
(ExecutiveSalesDashboard, SalesKPICatalog, SalesReportBuilder) into plain,
serialization-ready View Models. It calculates nothing, decides nothing,
and integrates with nothing — every field it produces is a direct copy of
a value some CRM service already computed. Future interfaces (API, Web,
Mobile, PDF, HTML, Export) are meant to consume these View Models instead
of the domain objects themselves.
"""
