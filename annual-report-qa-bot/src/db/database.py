import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(override=True)

# Build connection URL from environment, using DATABASE_URL or POSTGRES_* fallback
user = os.environ.get("POSTGRES_USER")
password = os.environ.get("POSTGRES_PASSWORD")
host = os.environ.get("POSTGRES_HOST")
port = os.environ.get("POSTGRES_PORT", "6543")
db_name = os.environ.get("POSTGRES_DB", "postgres")

if os.environ.get("DATABASE_URL"):
    database_url = os.environ.get("DATABASE_URL")
elif user and password and host:
    database_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
else:
    database_url = os.environ.get("DIRECT_URL", "postgresql://localhost:5432/postgres")

engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
