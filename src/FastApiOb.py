from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.docs import (get_swagger_ui_html)
import uvicorn

from src.init import redis_manager

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

from src.api.Hotels import router as hotels_router
from src.api.users import router as users_router
from src.api.rooms import router as rooms_router
from src.api.booking import router as booking_router
from src.api.facilities import router as facilities_router
from src.api.images import router as images_router
from src.config import settings
from src.middleware import ImageUploadSizeLimitMiddleware
from src.upload_limits import MAX_IMAGE_REQUEST_BYTES
print(f'{settings.DB_NAME=}')

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    try:
        FastAPICache.init(RedisBackend(redis_manager.redis), prefix='fastapi-cache')
        yield
    finally:
        await redis_manager.close()

app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(
    ImageUploadSizeLimitMiddleware,
    max_bytes=MAX_IMAGE_REQUEST_BYTES,
)

app.include_router(users_router)
app.include_router(hotels_router)
app.include_router(rooms_router)
app.include_router(booking_router)
app.include_router(facilities_router)
app.include_router(images_router)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )


if __name__ == '__main__':
    uvicorn.run('FastApiOb:app',reload=True,port=8001)
