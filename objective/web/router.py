from fastapi.routing import APIRouter

from objective.web.routes import monitoring, projects, scenes, users

api_router = APIRouter()
api_router.include_router(monitoring.router, tags=["monitoring"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(scenes.router, tags=["scenes"])
api_router.include_router(users.router)
