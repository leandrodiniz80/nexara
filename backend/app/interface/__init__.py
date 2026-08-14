"""The platform's single public door for any external consumer (REST API,
GraphQL, CLI, Workers, Scheduler, WebSocket, SDKs). It belongs to none of
Domain, Presentation, or Contracts — it is the Interface layer sitting on
top of all of them, and it only ever delegates to PresentationFacade and
ResponseMapper, returning nothing but PublicResponse.
"""
