from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from .api.routes import router as api_router
from .core.config import Settings

settings = Settings()

app = FastAPI(title="voice-cloning-app", version="0.1.0")

app.include_router(api_router, prefix="/api/v1")

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "voice-cloning-app"}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # RFC 9457 friendly problem+json
    return JSONResponse(status_code=exc.status_code, content={
        "type": "about:blank",
        "title": exc.detail or "HTTP Error",
        "status": exc.status_code,
        "instance": str(request.url.path)
    })

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": str(exc),
        "instance": str(request.url.path)
    })
