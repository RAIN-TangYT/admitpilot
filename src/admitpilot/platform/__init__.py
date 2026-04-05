"""Platform 层接口定义。

该包仅提供工程边界与协议骨架，不包含完整业务实现。
"""

from admitpilot.platform.bootstrap import PlatformCommonBundle, build_default_platform_common_bundle
from admitpilot.platform.types import AgentRole

__all__ = ["AgentRole", "PlatformCommonBundle", "build_default_platform_common_bundle"]
