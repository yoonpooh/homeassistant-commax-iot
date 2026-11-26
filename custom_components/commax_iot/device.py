import asyncio
from typing import Optional


def find_subdevice(device: dict, sort: str, read_write: bool = True) -> Optional[dict]:
    return next(
        (
            subdevice
            for subdevice in device.get("subDevice", [])
            if subdevice.get("sort") == sort
            and (not read_write or subdevice.get("type") == "readWrite")
        ),
        None,
    )


def get_current_subdevice(coordinator, root_uuid: str, sub_uuid: Optional[str]) -> Optional[dict]:
    device = coordinator.get_device_by_uuid(root_uuid)
    if not device:
        return None
    return next(
        (
            subdevice
            for subdevice in device.get("subDevice", [])
            if subdevice.get("subUuid") == sub_uuid
        ),
        None,
    )


def update_subdevice_value(coordinator, root_uuid: str, sub_uuid: Optional[str], value: str) -> bool:
    subdevice = get_current_subdevice(coordinator, root_uuid, sub_uuid) if sub_uuid else None
    if subdevice is None:
        return False
    subdevice["value"] = value
    return True


def build_set_command(subdevice: dict, value: str) -> dict:
    return {
        "value": value,
        "funcCommand": "set",
        "type": "readWrite",
        "subUuid": subdevice.get("subUuid"),
        "sort": subdevice.get("sort"),
    }


def build_device_command(device: dict, nickname: Optional[str], subcommand: dict) -> dict:
    return {
        "subDevice": [subcommand],
        "rootUuid": device.get("rootUuid"),
        "nickname": nickname,
        "rootDevice": device.get("rootDevice"),
    }


def schedule_refresh(coordinator) -> None:
    asyncio.create_task(_refresh_later(coordinator))


async def _refresh_later(coordinator) -> None:
    await asyncio.sleep(1)
    await coordinator.async_request_refresh()
