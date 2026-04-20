"""
hubspot.py — HubSpot CRM contact sync for school principals.

Sync is best-effort and fire-and-forget: a HubSpot failure never blocks
a Ufit write. All errors are logged to stderr. Missing HUBSPOT_API_KEY
silently no-ops so local dev works without credentials.
"""

import logging
import os
import threading

import httpx

_BASE = "https://api.hubapi.com"
_TIMEOUT = 5.0


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('HUBSPOT_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def upsert_contact(email: str, props: dict) -> dict:
    """Create or update a HubSpot contact by email address."""
    resp = httpx.post(
        f"{_BASE}/crm/v3/objects/contacts",
        headers=_headers(),
        json={"properties": {"email": email, **props}},
        timeout=_TIMEOUT,
    )
    if resp.status_code == 409:
        # Contact already exists — extract ID from error message and PATCH
        try:
            contact_id = resp.json()["message"].split("ID: ")[1]
        except (KeyError, IndexError, ValueError):
            resp.raise_for_status()
            return {}
        resp = httpx.patch(
            f"{_BASE}/crm/v3/objects/contacts/{contact_id}",
            headers=_headers(),
            json={"properties": props},
            timeout=_TIMEOUT,
        )
    resp.raise_for_status()
    return resp.json()


def sync_principal_to_hubspot(
    email: str,
    first_name: str,
    last_name: str,
    school_id: int,
    school_name: str,
    org_id: int,
    org_name: str,
) -> None:
    """Sync a principal's contact info to HubSpot CRM."""
    upsert_contact(
        email=email,
        props={
            "firstname": first_name,
            "lastname": last_name,
            "company": org_name,
            "jobtitle": "Principal",
            "hs_lead_status": "CONNECTED",
            "ufit_school_id": str(school_id),
            "ufit_school_name": school_name,
            "ufit_org_id": str(org_id),
        },
    )


def _run_sync(**kwargs) -> None:
    try:
        sync_principal_to_hubspot(**kwargs)
    except Exception:
        logging.exception("HUBSPOT SYNC FAILED")


def trigger_principal_sync(
    email: str,
    first_name: str,
    last_name: str,
    school_id: int,
    school_name: str,
    org_id: int,
    org_name: str,
) -> None:
    """Fire HubSpot sync in a background daemon thread. Never raises."""
    if not os.environ.get("HUBSPOT_API_KEY"):
        return
    threading.Thread(
        target=_run_sync,
        kwargs=dict(
            email=email,
            first_name=first_name,
            last_name=last_name,
            school_id=school_id,
            school_name=school_name,
            org_id=org_id,
            org_name=org_name,
        ),
        daemon=True,
    ).start()
