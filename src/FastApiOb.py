from fastapi import FastAPI
from fastapi.openapi.docs import (get_swagger_ui_html)
import uvicorn
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.api.Hotels import router as hotels_router
from src.api.users import router as users_router
from src.config import settings
print(f'{settings.DB_NAME=}')

app = FastAPI(docs_url=None, redoc_url=None)

app.include_router(users_router)
app.include_router(hotels_router)


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