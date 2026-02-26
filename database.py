from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://fastapi_db1_user:gFG8QNHcCYQPymjCNJCCDntQKUOv9Aat@dpg-d6bdq90gjchc739t6js0-a.oregon-postgres.render.com/fastapi_db1"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
