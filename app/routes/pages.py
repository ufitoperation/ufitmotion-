"""
pages.py — SPA shell routes for Ufit Motion.

All non-API URLs render the index.html SPA shell. The frontend JavaScript
router handles the actual page rendering based on the URL path.

Flask serves index.html for:
  /          — home / dashboard redirect
  /login     — login page (SPA handles portal selection)
  /*         — all other non-API routes (SPA deep-link support)

The catch-all deliberately does NOT match /api/* to avoid swallowing
legitimate 404s on typo'd API routes.
"""

from flask import Blueprint, jsonify, render_template

pages_bp = Blueprint("pages", __name__)

_SPA_TEMPLATE = "index.html"


@pages_bp.route("/")
def index():
    """Serve the SPA shell at the root URL."""
    return render_template(_SPA_TEMPLATE)


@pages_bp.route("/login")
def login_page():
    """Serve the SPA shell at /login — the SPA renders the portal selector."""
    return render_template(_SPA_TEMPLATE)


@pages_bp.route("/<path:path>")
def catch_all(path: str):
    """
    Catch-all for any non-API, non-static path.

    SPA deep-links (e.g. /dashboard/schools/42) must return the shell HTML
    so the JS router can take over. We skip paths that look like API calls
    (those should return real 404s from Flask if no route matched) and let
    static file serving handle asset requests.
    """
    # Let Flask's static file handler deal with asset requests.
    # Static files are served from the /static prefix by Flask automatically;
    # this guard is for any edge-cases where a bare path slips through.
    if path.startswith("api/"):
        # API routes that fall through to here genuinely don't exist — 404.
        return jsonify({"error": "API endpoint not found.", "path": f"/{path}"}), 404

    # For all other paths, serve the SPA shell and let the JS router decide.
    return render_template(_SPA_TEMPLATE)
