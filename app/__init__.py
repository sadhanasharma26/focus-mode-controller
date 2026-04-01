"""Flask app factory for Focus Mode Controller."""

from flask import Flask

from .macos import check_permissions
from .main import main_bp
from .timer import set_demo_mode


def create_app(demo_mode: bool = False) -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["DEMO_MODE"] = demo_mode
    set_demo_mode(demo_mode)
    app.config["PERMISSIONS_SNAPSHOT"] = check_permissions()
    app.register_blueprint(main_bp)
    return app
