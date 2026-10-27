# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""设备自定义名称的本地缓存。

用户改过的名字只存本地，不回写米家云端：设备名属于账号数据，本地
覆盖既能满足个性化，又不会影响手机端与其它客户端。键是 did，设备
换型号或重配后 did 变化，旧条目自然失效。
"""

import json

from app.core import _json_store

_FILENAME = "device_names.json"


def _read() -> dict[str, str]:
    path = _json_store.data_file(_FILENAME)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(did): name for did, name in raw.items()
            if isinstance(name, str) and name.strip()}


def get(did: str) -> str | None:
    """该设备的自定义名称，未设置返回 None。"""
    return _read().get(did)


def load_all() -> dict[str, str]:
    """did -> 自定义名称的完整映射，启动时批量应用。"""
    return _read()


def set_name(did: str, name: str) -> None:
    """写入自定义名称；传空串表示恢复默认（删除条目）。"""
    names = _read()
    clean = name.strip()
    if clean:
        names[did] = clean
    else:
        names.pop(did, None)
    _json_store.write_json(_json_store.data_file(_FILENAME), names)
