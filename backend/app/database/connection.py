
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


# Build the database URL safely, even if your password
# contains special characters.
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=settings.POSTGRES_USER,
    password=settings.POSTGRES_PASSWORD,
    host=settings.POSTGRES_HOST,
    port=settings.POSTGRES_PORT,
    database=settings.POSTGRES_DB,
)


# Create the SQLAlchemy database engine.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# Create database sessions for application requests.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Simple database connection test.
def test_database_connection():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
