import json
import logging
import traceback
from datetime import timedelta
from flask import Flask, g, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import get_config
from app.extensions import limiter


class _JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def create_app(config=None):
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    cfg = config or get_config()
    app.config["UFIT_CONFIG"] = cfg
    app.config["SECRET_KEY"] = cfg.SECRET_KEY

    import os
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )

    # Trust Render's load-balancer so rate-limiter sees the real client IP.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    limiter.init_app(app)

    if not app.debug:
        handler = logging.StreamHandler()
        handler.setFormatter(_JSONFormatter())
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    # FERPA / OWASP session hardening
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
    app.config["SESSION_COOKIE_SECURE"] = cfg.APP_ENV == "production"
    app.config["SESSION_COOKIE_NAME"] = "__ufit_sess"   # avoid default "session" fingerprint
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

    @app.before_request
    def csrf_check():
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return
        if not request.path.startswith("/api/"):
            return
        # Auth endpoints accept plain form/JSON from password managers — exempt them.
        # Webhook endpoint uses HMAC-SHA256 as its own auth layer — exempt from CSRF.
        if request.path in ("/api/auth/login", "/api/auth/forgot-password", "/api/auth/reset-password",
                            "/api/webhooks/hubspot"):
            return
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            return jsonify({"error": "Forbidden."}), 403

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
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp
        proto = request.environ.get("HTTP_X_FORWARDED_PROTO", "")
        if cfg.APP_ENV == "production" or proto == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        if cfg.APP_ENV == "production":
            app.logger.error("Unhandled exception: %s — %s", type(e).__name__, str(e))
        else:
            app.logger.error("Unhandled exception: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred."}), 500

    @app.route("/api/health")
    def health():
        from app.database import get_db
        try:
            get_db().execute("SELECT 1")
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({"ok": True, "env": cfg.APP_ENV, "db": db_ok})

    with app.app_context():
        from app.seeds import init_db
        try:
            init_db()
        except Exception as e:
            app.logger.error("init_db failed at startup: %s", e)

    return app
