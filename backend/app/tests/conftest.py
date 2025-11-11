import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import get_db
from app.core.config import settings
from app.db.base import Base
from app.models.document import Document
from app.models.fund import Fund
from app.models.transaction import CapitalCall, Distribution, Adjustment
import os

# Specify a path to your test database file
TEST_DATABASE_URL = "sqlite:///./test_database.db"

# Create engine and sessionmaker for the SQLite file-based database
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables in the test database
Base.metadata.create_all(bind=engine)

@pytest.fixture
def test_db_session():
    """Fixture to create and close a test database session"""
    db = TestingSessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()

@pytest.fixture
def test_client(test_db_session):
    """Fixture to create FastAPI TestClient with a test database session"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    # Override the database session for testing
    app.dependency_overrides[get_db] = lambda: test_db_session
    
    client = TestClient(app)
    return client

@pytest.fixture(scope="module", autouse=True)
def cleanup_db():
    """Clean up the database before the test starts"""
    if os.path.exists(TEST_DATABASE_URL):
        os.remove(TEST_DATABASE_URL)

    yield  # Continue running the tests

    # Cleanup: Delete the test database file after all tests are done
    if os.path.exists(TEST_DATABASE_URL):
        os.remove(TEST_DATABASE_URL)