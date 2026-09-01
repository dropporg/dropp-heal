from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import Settings, get_settings
from api.db import database
from api.tsdb import influxdb


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async for session in database.session():
        yield session


def get_influxdb():
    return influxdb


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
InfluxDep = Annotated[object, Depends(get_influxdb)]
