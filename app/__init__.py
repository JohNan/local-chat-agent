import sys
import logging
from flask import Flask


def create_app():
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    app = Flask(__name__)

    # Import and register blueprint
    from app.routes import bp

    app.register_blueprint(bp)

    return app
