import os
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.routes import api, web
from app.services.db import init_db

class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        for header in ['x-forwarded-proto', 'x-forwarded-for', 'x-forwarded-host']:
            if header in request.headers:
                os.environ[header.upper().replace('-', '_')] = request.headers[header]
        response = await call_next(request)
        return response

# Create FastAPI app
app = FastAPI(title=settings.APP_NAME)

# Add security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(ProxyHeadersMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Setup templates with custom context
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals["current_year"] = lambda: datetime.now().year

# Include routers
app.include_router(api.router, prefix="/api")
app.include_router(web.router)

@app.on_event("startup")
async def startup_db_client():
    """Initialize database on startup."""
    await init_db()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# Make templates available in request
@app.middleware("http")
async def add_templates_to_request(request: Request, call_next):
    request.state.templates = templates
    response = await call_next(request)
    return response

# Add response headers for proxy
@app.middleware("http")
async def add_proxy_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
