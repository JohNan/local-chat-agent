"""
Main application package initialization.
"""

import sys
import logging
from flask import Flask


def create_app():
    """
    Creates and configures the Flask application.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    app = Flask(__name__)

    # Import and register blueprint
    # pylint: disable=import-outside-toplevel
    from app.routes import bp

    app.register_blueprint(bp)

    return app
