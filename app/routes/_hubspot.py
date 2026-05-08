"""
_hubspot.py — HubSpot CRM integration for Ufit Motion.

Fires when a new school is created:
  1. Creates a HubSpot Company for the school
  2. If principal info is present, creates a HubSpot Contact and associates
     it with the Company

If HUBSPOT_API_KEY is not set, all functions log and return silently.
School creation always succeeds regardless of HubSpot status.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_HEADERS = lambda api_key: {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}


def notify_school_created(school: dict) -> None:
    """
    Create a HubSpot Company (and optional Contact) when a school is added.

    school dict keys used: school_name, city, state, principal_name, principal_email
    """
    api_key = os.environ.get("HUBSPOT_API_KEY", "").strip()
    if not api_key:
        logger.info("HUBSPOT_API_KEY not set — skipping HubSpot sync for school %s", school.get("school_name"))
        return

    headers = _HEADERS(api_key)

    # --- 1. Create Company ---
    company_id = None
    try:
        resp = httpx.post(
            "https://api.hubapi.com/crm/v3/objects/companies",
            headers=headers,
            json={"properties": {
                "name": school.get("school_name", ""),
                "city": school.get("city") or "",
                "state": school.get("state") or "",
            }},
            timeout=5.0,
        )
        if resp.status_code in (200, 201):
            company_id = resp.json().get("id")
            logger.info("HubSpot company created for school: %s (id=%s)", school.get("school_name"), company_id)
        else:
            logger.warning("HubSpot company creation returned %s for school %s: %s",
                           resp.status_code, school.get("school_name"), resp.text[:200])
            return
    except Exception as exc:
        logger.warning("HubSpot company creation failed for school %s: %s", school.get("school_name"), exc)
        return

    # --- 2. Create Contact for principal (if email provided) ---
    principal_email = (school.get("principal_email") or "").strip()
    if not principal_email or not company_id:
        return

    principal_name = (school.get("principal_name") or "").strip()
    parts = principal_name.split(" ", 1)
    firstname = parts[0] if parts else ""
    lastname = parts[1] if len(parts) > 1 else ""

    try:
        contact_resp = httpx.post(
            "https://api.hubapi.com/crm/v3/objects/contacts",
            headers=headers,
            json={"properties": {
                "email": principal_email,
                "firstname": firstname,
                "lastname": lastname,
                "jobtitle": "Principal",
            }},
            timeout=5.0,
        )
        if contact_resp.status_code in (200, 201):
            contact_id = contact_resp.json().get("id")
            logger.info("HubSpot contact created for principal: %s", principal_email)

            # --- 3. Associate Contact with Company ---
            httpx.put(
                f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/companies/{company_id}/contact_to_company",
                headers=headers,
                timeout=5.0,
            )
            logger.info("HubSpot contact %s associated with company %s", contact_id, company_id)
        elif contact_resp.status_code == 409:
            # Contact already exists — still associate with company
            existing = contact_resp.json().get("message", "")
            logger.info("HubSpot contact already exists for %s: %s", principal_email, existing)
        else:
            logger.warning("HubSpot contact creation returned %s for %s: %s",
                           contact_resp.status_code, principal_email, contact_resp.text[:200])
    except Exception as exc:
        logger.warning("HubSpot contact creation failed for %s: %s", principal_email, exc)
