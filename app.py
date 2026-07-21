from pathlib import Path

from flask import Flask

from db import ensure_database


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(__file__).resolve().parent / "app.db"),
    )

    if test_config:
        app.config.update(test_config)

    ensure_database(app.config["DATABASE"])

    @app.get("/")
    def dashboard() -> str:
        return "Personal Productivity Loop"

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
