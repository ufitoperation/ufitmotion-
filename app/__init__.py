from datetime import timedelta
from flask import Flask, g, jsonify, request
from app.config import get_config


def create_app(config=None):
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    cfg = config or get_config()
    app.config["UFIT_CONFIG"] = cfg
    app.config["SECRET_KEY"] = cfg.SECRET_KEY

    # FERPA / OWASP session hardening
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = cfg.APP_ENV == "production"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True

    from app.routes.auth_routes import auth_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.coach_routes import coach_bp
    from app.routes.shared_routes import shared_bp
    from app.routes.pages import pages_bp
    from app.routes.principal_routes import principal_bp
    from app.routes.parent_routes import parent_bp

    for bp in [auth_bp, admin_bp, coach_bp, shared_bp, pages_bp, principal_bp, parent_bp]:
        app.register_blueprint(bp)

    @app.teardown_appcontext
    def close_db(exc):
        conn = g.pop("_pg_conn", None)
        if conn is not None:
            conn.close()

    # Security headers on every response
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:;"
        )
        response.headers["Content-Security-Policy"] = csp
        proto = request.environ.get("HTTP_X_FORWARDED_PROTO", "")
        if cfg.APP_ENV == "production" or proto == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True, "env": cfg.APP_ENV})

    with app.app_context():
        from app.seeds import init_db
        init_db()

    return app
