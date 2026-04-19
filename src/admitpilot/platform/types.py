"""Common platform type aliases."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

JSONDict = dict[str, Any]
StringList = list[str]
AgentRole: TypeAlias = Literal["pao", "aie", "sae", "dta", "cds"]
