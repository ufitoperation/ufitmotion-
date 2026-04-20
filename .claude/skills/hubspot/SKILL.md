# Hubspot Integration Skill

## When to Activate

- Syncing Ufit school contacts to Hubspot CRM
- Creating/updating Hubspot contacts for principals or school admins
- Logging program activity as Hubspot timeline events
- Mapping Ufit org/school/program data to Hubspot Company/Contact/Deal objects

## Ufit → Hubspot Data Model

| Ufit Object | Hubspot Object | Sync Direction |
|---|---|---|
| `organizations` | Company | Ufit → Hubspot |
| `schools` | Company (child, associated to org Company) | Ufit → Hubspot |
| `users` where role in (`principal`, `school_staff`) | Contact | Ufit → Hubspot |
| `programs` | Deal or custom object | Ufit → Hubspot |
| EOD report filed | Timeline event on Contact | Ufit → Hubspot |

## API Basics

```python
import httpx

HUBSPOT_BASE = "https://api.hubapi.com"
HUBSPOT_TOKEN = os.environ["HUBSPOT_API_KEY"]  # Private App token, NOT OAuth

headers = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}

# Create or update a contact (upsert by email)
def upsert_contact(email: str, props: dict) -> dict:
    resp = httpx.post(
        f"{HUBSPOT_BASE}/crm/v3/objects/contacts",
        headers=headers,
        json={"properties": {"email": email, **props}},
    )
    if resp.status_code == 409:  # already exists — update instead
        contact_id = resp.json()["message"].split("ID: ")[1]
        resp = httpx.patch(
            f"{HUBSPOT_BASE}/crm/v3/objects/contacts/{contact_id}",
            headers=headers,
            json={"properties": props},
        )
    resp.raise_for_status()
    return resp.json()
```

## Required Environment Variables

```
HUBSPOT_API_KEY=pat-na1-xxxxx   # Private App token from Hubspot developer account
```

Add to Railway environment. Never commit to git.

## Sync Strategy for Ufit Motion

### Phase 3C: Principal Sync

Trigger: When a new `principal` user is created in Ufit, or their contact info is updated.

```python
def sync_principal_to_hubspot(user: dict, school: dict, org: dict) -> None:
    upsert_contact(
        email=user["email"],
        props={
            "firstname": user["first_name"],
            "lastname": user["last_name"],
            "company": org["organization_name"],
            "jobtitle": "Principal",
            "hs_lead_status": "CONNECTED",
            # Custom Ufit properties (must be created in Hubspot first)
            "ufit_school_id": str(school["school_id"]),
            "ufit_school_name": school["school_name"],
            "ufit_org_id": str(org["organization_id"]),
        },
    )
```

### Custom Properties to Create in Hubspot

Before syncing, create these custom contact properties in Hubspot (Settings → Properties):

| Property Name | Type | Purpose |
|---|---|---|
| `ufit_school_id` | String | Foreign key back to Ufit |
| `ufit_school_name` | String | Denormalized for Hubspot search |
| `ufit_org_id` | String | Foreign key to organization |
| `ufit_last_eod_date` | Date | Last EOD filed at their school |
| `ufit_program_count` | Number | Active programs at their school |

## Sync Modes

**Real-time:** Call Hubspot API from the Flask route after the DB write (fire-and-forget via background thread or task queue). Never block the coach's response waiting for Hubspot.

**Batch:** Nightly cron job that reconciles all principals against Hubspot. Use for initial bulk sync.

```python
# Fire-and-forget pattern (don't block the route)
import threading

def _sync_async(user, school, org):
    try:
        sync_principal_to_hubspot(user, school, org)
    except Exception as exc:
        print(f"HUBSPOT SYNC FAILED: {exc}", file=sys.stderr)
        # Log to audit_log or notifications table if critical

threading.Thread(target=_sync_async, args=(user, school, org), daemon=True).start()
```

## Error Handling Rules

- **Never fail a Ufit write because Hubspot is down.** Hubspot sync is best-effort.
- **Log all sync failures** to stderr and to a `sync_failures` table or `notifications` table.
- **Retry failed syncs** in the nightly batch job.
- **Rate limits:** Hubspot Free = 100 requests/10 seconds. Batch syncs must respect this.

## Security Checklist

- [ ] `HUBSPOT_API_KEY` in Railway env vars, not in code
- [ ] Only sync non-student data (principals, school contacts) — never sync student records to Hubspot (FERPA)
- [ ] Outbound HTTP calls have a timeout: `httpx.post(..., timeout=5.0)`
- [ ] Hubspot API errors are caught and logged — never propagated as 500s to coaches

## Testing

Use Hubspot Sandbox (free developer account → sandbox environment) for all testing. Never test against the production Hubspot account.
