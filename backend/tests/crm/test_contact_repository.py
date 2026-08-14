import uuid

from app.crm.models.crm_contact import CRMContact
from app.crm.repositories.contact_repository import ContactRepository


def test_save_and_get_contact_round_trip():
    repository = ContactRepository()
    contact = CRMContact(company_id=uuid.uuid4(), name="João")

    repository.save_contact(contact)

    assert repository.get_contact(contact.id) is contact


def test_get_contact_for_unknown_id_returns_none():
    repository = ContactRepository()

    assert repository.get_contact(uuid.uuid4()) is None


def test_list_contacts_returns_every_saved_contact_by_default():
    repository = ContactRepository()
    first = CRMContact(company_id=uuid.uuid4(), name="João")
    second = CRMContact(company_id=uuid.uuid4(), name="Maria")
    repository.save_contact(first)
    repository.save_contact(second)

    contacts = repository.list_contacts()

    assert {c.id for c in contacts} == {first.id, second.id}


def test_list_contacts_filters_by_company_id():
    company_id = uuid.uuid4()
    repository = ContactRepository()
    matching = CRMContact(company_id=company_id, name="João")
    other = CRMContact(company_id=uuid.uuid4(), name="Maria")
    repository.save_contact(matching)
    repository.save_contact(other)

    contacts = repository.list_contacts(company_id=company_id)

    assert [c.id for c in contacts] == [matching.id]
