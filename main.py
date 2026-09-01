"""Entrypoint for the api component."""

from api.config import get_settings
from api.heal import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("main:app", host=settings.host, port=settings.port)
