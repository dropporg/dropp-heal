"""Entrypoint for the worker component."""

from api.config import get_settings
from api.monitor import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("worker:app", host=settings.host, port=settings.port)
