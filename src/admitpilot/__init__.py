"""admitpilot 项目包入口。"""

from __future__ import annotations

import dataclasses
import sys
from typing import Any, Callable, TypeVar

_T = TypeVar("_T")


if sys.version_info < (3, 10):
    _orig_dataclass = dataclasses.dataclass

    def _dataclass_compat(*args: Any, **kwargs: Any) -> Callable[[_T], _T]:
        try:
            return _orig_dataclass(*args, **kwargs)
        except TypeError:
            if "slots" not in kwargs:
                raise
            kwargs = dict(kwargs)
            kwargs.pop("slots", None)
            return _orig_dataclass(*args, **kwargs)

    dataclasses.dataclass = _dataclass_compat  # type: ignore[assignment]
