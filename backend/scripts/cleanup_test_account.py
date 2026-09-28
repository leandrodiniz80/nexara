"""Remove a test account and/or the demo leads POST /system/demo-seed created.

Dry-run by default: prints what would be deleted and changes nothing until
--apply is passed. Run from the backend/ folder, against whatever
DATABASE_URL the environment (or backend/.env) points at:

    python -m scripts.cleanup_test_account --email leandro@nexara.com
    python -m scripts.cleanup_test_account --email leandro@nexara.com --apply
    python -m scripts.cleanup_test_account --email leandro@nexara.com --demo-leads-only --apply

Safety guards — so this can never touch a real customer's data:
- demo leads are matched by the exact e-mails in system.py's _DEMO_LEADS,
  and only inside the given user's own organization;
- full-account mode refuses to run if that organization has any other
  member, or any lead that isn't one of those demo leads;
- everything runs in a single transaction (all or nothing).

Full-account mode deletes the organization row, and the database's own
ON DELETE CASCADE rules remove its leads, activity/status logs,
automations, notifications, usage and memberships; then the user row
(cascading its sessions).
"""

import argparse
import sys

from sqlalchemy import bindparam, text

from app.api.routers.system import _DEMO_LEADS
from app.db.sync_session import sync_engine

DEMO_LEAD_EMAILS = sorted({email for _name, email, _phone, _status in _DEMO_LEADS})

_demo_in = bindparam("demo_emails", expanding=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--email", required=True, help="E-mail of the test account")
    parser.add_argument(
        "--demo-leads-only",
        action="store_true",
        help="Only delete the demo leads; keep the account and organization",
    )
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    args = parser.parse_args()

    with sync_engine.begin() as conn:
        user = conn.execute(
            text("SELECT email, organization_id FROM platform_users WHERE email = :email"),
            {"email": args.email},
        ).first()
        if user is None:
            print(f"Usuário {args.email} não encontrado. Nada a fazer.")
            return 0
        org_id = user.organization_id
        print(f"Usuário: {user.email} | organização: {org_id}")

        if org_id is None:
            demo_count = other_count = members = 0
        else:
            demo_count = conn.execute(
                text(
                    "SELECT count(*) FROM leads WHERE organization_id = :org "
                    "AND email IN :demo_emails"
                ).bindparams(_demo_in),
                {"org": org_id, "demo_emails": DEMO_LEAD_EMAILS},
            ).scalar_one()
            other_count = conn.execute(
                text(
                    "SELECT count(*) FROM leads WHERE organization_id = :org "
                    "AND (email IS NULL OR email NOT IN :demo_emails)"
                ).bindparams(_demo_in),
                {"org": org_id, "demo_emails": DEMO_LEAD_EMAILS},
            ).scalar_one()
            members = conn.execute(
                text("SELECT count(*) FROM user_organizations WHERE organization_id = :org"),
                {"org": org_id},
            ).scalar_one()
        print(f"Leads demo: {demo_count} | outros leads: {other_count} | membros da org: {members}")

        if args.demo_leads_only:
            print(f"Ação: apagar {demo_count} lead(s) demo (usuário e organização são mantidos).")
            if args.apply and demo_count:
                conn.execute(
                    text(
                        "DELETE FROM leads WHERE organization_id = :org AND email IN :demo_emails"
                    ).bindparams(_demo_in),
                    {"org": org_id, "demo_emails": DEMO_LEAD_EMAILS},
                )
        else:
            if other_count or members > 1:
                print(
                    "ABORTADO: a organização tem leads que não são demo ou outros membros — "
                    "não parece uma conta de teste. Nada foi apagado."
                )
                return 1
            print(
                f"Ação: apagar o usuário {user.email}, a organização {org_id} "
                "e todos os seus dados."
            )
            if args.apply:
                if org_id is not None:
                    conn.execute(
                        text("DELETE FROM platform_organizations WHERE id = :org"), {"org": org_id}
                    )
                conn.execute(
                    text("DELETE FROM platform_users WHERE email = :email"), {"email": user.email}
                )

        if not args.apply:
            print("DRY-RUN: nada foi apagado. Rode de novo com --apply para confirmar.")
            conn.rollback()
        else:
            print("Concluído.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
