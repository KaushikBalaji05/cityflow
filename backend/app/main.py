import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from app.core.config import settings
from app.api.v1.routes import router as api_v1_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multimodal Urban Journey Planner & Mobility Intelligence Platform for Bengaluru",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Open CORS configuration for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes under /api/v1
app.include_router(api_v1_router, prefix="/api/v1")
# Also alias API routes directly under /api and root for convenience
app.include_router(api_v1_router, prefix="/api")

# Convenience redirects for documentation
@app.get("/api/v1/docs", include_in_schema=False)
def redirect_v1_docs():
    return RedirectResponse(url="/docs")


@app.get("/api/v1/openapi.json", include_in_schema=False)
def redirect_v1_openapi():
    return RedirectResponse(url="/openapi.json")


# Mount static frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse(os.path.join(static_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn
    # Bind to 0.0.0.0 to support both IPv4 (127.0.0.1) and IPv6 (localhost / ::1)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
