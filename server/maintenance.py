from fastapi import HTTPException

from system_settings import is_maintenance_enabled

MAINTENANCE_MESSAGE = "Технические работы. Пожалуйста, зайдите позже"


def is_maintenance() -> bool:
    return is_maintenance_enabled()


def maintenance_http_error() -> HTTPException:
    return HTTPException(status_code=503, detail=MAINTENANCE_MESSAGE)


async def refresh_maintenance_cache() -> bool:
    from system_settings import get_maintenance_enabled

    return await get_maintenance_enabled()