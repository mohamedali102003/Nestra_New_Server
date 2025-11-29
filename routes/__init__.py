# routes/__init__.py

from .auth import router as auth_router
from .projects import router as projects_router
from .ideas import router as ideas_router
from .tasks import router as tasks_router
from .chat import router as chat_router
from .users import router as users_router
from .activity import router as activity_router
from .polls import router as polls_router
from .realtime import router as realtime_router
from .resources import router as resources_router # [جديد]
from .feedback import router as feedback_router

__all__ = [
    "auth_router",
    "projects_router",
    "ideas_router",
    "tasks_router",
    "chat_router",
    "users_router",
    "activity_router",
    "polls_router",
    "realtime_router",
    "resources_router", # [جديد]
    "feedback_router", # [جديد]
]