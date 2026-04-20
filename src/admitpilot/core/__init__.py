"""核心数据模型与跨模块共享类型定义。"""

from admitpilot.core.schemas import (
    AgentResult,
    AgentTask,
    ApplicationContext,
    UserProfile,
)
from admitpilot.core.user_artifacts import EvidenceArtifact, UserArtifactsBundle

__all__ = [
    "AgentResult",
    "AgentTask",
    "ApplicationContext",
    "UserProfile",
    "EvidenceArtifact",
    "UserArtifactsBundle",
]
