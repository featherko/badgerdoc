from assets import routers
from assets.config import settings
from fastapi import Depends, FastAPI
from tenant_dependency import get_tenant_info

tenant = get_tenant_info(url=settings.keycloak_uri, algorithm="RS256")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    root_path=settings.root_path,
    servers=[{"url": settings.root_path}],
    dependencies=[Depends(tenant)],
)
app.include_router(routers.minio_router.router)
app.include_router(routers.files_router.router)
app.include_router(routers.datasets_router.router)
app.include_router(routers.bonds_router.router)
app.include_router(routers.s3_router.router)
