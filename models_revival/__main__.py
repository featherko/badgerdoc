import uvicorn
from fastapi import FastAPI

from .config import settings
from .routes import router

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        root_path=settings.root_path,
    )
