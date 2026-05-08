"""
_hubspot.py — HubSpot CRM integration for Ufit Motion.

Fires when a new school is created. Creates a Company record in HubSpot
so the school appears in the pipeline automatically.

Setup:
    1. Get a Private App token from HubSpot → Settings → Integrations → Private Apps
    2. Set HUBSPOT_API_KEY=pat-na1-xxxx in your .env / Render env vars
    3. That's it — school creation will auto-create HubSpot companies.

If HUBSPOT_API_KEY is not set, the function logs and returns silently.
School creation always succeeds regardless of HubSpot status.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

HUBSPOT_API_URL = "https://api.hubapi.com/crm/v3/objects/companies"


def notify_school_created(school: dict) -> None:
    """
    Create a HubSpot Company when a new school is added.

    school dict must have: school_name, city (optional), state (optional)
    """
    api_key = os.environ.get("HUBSPOT_API_KEY", "").strip()
    if not api_key:
        logger.info("HUBSPOT_API_KEY not set — skipping HubSpot sync for school %s", school.get("school_name"))
        return

    properties = {
        "name": school.get("school_name", ""),
        "city": school.get("city") or "",
        "state": school.get("state") or "",
    }

    try:
        response = httpx.post(
            HUBSPOT_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"properties": properties},
            timeout=5.0,
        )
        if response.status_code in (200, 201):
            logger.info("HubSpot company created for school: %s", school.get("school_name"))
        else:
            logger.warning(
                "HubSpot returned %s for school %s: %s",
                response.status_code,
                school.get("school_name"),
                response.text[:200],
            )
    except httpx.TimeoutException:
        logger.warning("HubSpot request timed out for school: %s", school.get("school_name"))
    except Exception as exc:
        logger.warning("HubSpot sync failed for school %s: %s", school.get("school_name"), exc)
