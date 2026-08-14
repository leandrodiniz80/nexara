import uuid

from app.crm.models.crm_contact import CRMContact


class ContactRepository:
    """In-memory store of every CRMContact."""

    def __init__(self) -> None:
        self._contacts: dict[uuid.UUID, CRMContact] = {}

    def save_contact(self, contact: CRMContact) -> CRMContact:
        self._contacts[contact.id] = contact
        return contact

    def get_contact(self, contact_id: uuid.UUID) -> CRMContact | None:
        return self._contacts.get(contact_id)

    def list_contacts(self, *, company_id: uuid.UUID | None = None) -> list[CRMContact]:
        contacts = list(self._contacts.values())
        if company_id is not None:
            contacts = [c for c in contacts if c.company_id == company_id]
        return contacts
