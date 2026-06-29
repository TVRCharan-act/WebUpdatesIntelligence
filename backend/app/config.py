from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://monitor:monitor@localhost:5432/website_monitor",
    )
    redis_url: str = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0",
    )


settings = Settings()
