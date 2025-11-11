from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import documents, funds, chat, metrics
import uvicorn
import logging

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Dependency to log each request
def log_request(request: dict = Depends()):
    logger.info(f"Handling request: {request}")
    return logger

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Fund Performance Analysis System API",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(funds.router, prefix="/api/funds", tags=["funds"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

@app.get("/")
async def root(logger: logging.Logger = Depends(log_request)):
    logger.info("Root endpoint hit.")
    return {
        "message": "Fund Performance Analysis System API",
        "version": settings.VERSION,
        "docs": "/docs",
    }

@app.get("/health")
async def health_check(logger: logging.Logger = Depends(log_request)):
    logger.info("Health check endpoint hit.")
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
