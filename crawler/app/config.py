import os
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/newsdb")
    SQLITE_PATH: str = os.environ.get("SQLITE_PATH", "/app/data/urls.db")
    
    # API Keys
    COHERE_API_KEY: str = os.environ.get("COHERE_API_KEY", "")
    
    # Crawler Settings
    CRAWLER_INTERVAL: int = int(os.environ.get("CRAWLER_INTERVAL", 3600))  # 1 hour in seconds
    NEWS_RETENTION_DAYS: int = int(os.environ.get("NEWS_RETENTION_DAYS", 30))  # Keep news for 30 days
    NEWS_MAX_ITEMS: int = int(os.environ.get("NEWS_MAX_ITEMS", 10000))  # Maximum number of news items to keep
    
    # Concurrency settings
    MAX_CONCURRENT_REQUESTS: int = int(os.environ.get("MAX_CONCURRENT_REQUESTS", 5))
    REQUEST_TIMEOUT: int = int(os.environ.get("REQUEST_TIMEOUT", 30))  # seconds
    
    # User agent for crawler
    USER_AGENT: str = os.environ.get(
        "USER_AGENT", 
        "NewsBot Crawler/1.0 (https://github.com/yourusername/news-crawler)"
    )
    
    # Ensure SQLite directory exists
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure SQLite directory exists
        sqlite_dir = Path(self.SQLITE_PATH).parent
        sqlite_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()
