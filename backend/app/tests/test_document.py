import os
import io
from unittest.mock import MagicMock, patch
from app.tests.conftest import test_client, test_db_session
from app.models.document import Document
from app.core.config import settings

# Make sure the upload dir exists for tests
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

def test_upload_pdf_file(test_client, test_db_session):
    """Test uploading a valid PDF file"""
    file_content = b"%PDF-1.4 test pdf content"
    file = io.BytesIO(file_content)
    file.name = "test.pdf"

    # Mock the Celery task so it doesn't actually run
    with patch("app.api.endpoints.documents.process_document_task.delay") as mock_task:

        response = test_client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", file, "application/pdf")},
            data={"fund_id": 1}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["message"] == "Document uploaded successfully. Processing started."
        
        # Verify document is saved in DB
        doc = test_db_session.query(Document).filter(Document.id == data["document_id"]).first()
        assert doc is not None
        assert doc.file_name == "test.pdf"
        assert doc.parsing_status == "pending"
        assert os.path.exists(doc.file_path)

def test_upload_non_pdf_file(test_client):
    """Test uploading a non-PDF file should fail"""
    file_content = b"Not a PDF"
    file = io.BytesIO(file_content)
    file.name = "test.txt"

    response = test_client.post(
        "/api/documents/upload",
        files={"file": ("test.txt", file, "text/plain")},
        data={"fund_id": 1}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed"

def test_get_document_status(test_client, test_db_session):
    """Test retrieving document status"""
    # Add a document manually to the DB
    doc = Document(file_name="status.pdf", file_path="fakepath", parsing_status="completed")
    test_db_session.add(doc)
    test_db_session.commit()

    response = test_client.get(f"/api/documents/{doc.id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc.id
    assert data["status"] == "completed"
    assert data["error_message"] is None

def test_get_document_not_found(test_client):
    """Test getting a non-existing document"""
    response = test_client.get("/api/documents/9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"

def test_list_documents(test_client, test_db_session):
    """Test listing documents"""
    # Add multiple documents
    doc1 = Document(file_name="doc1.pdf", file_path="path1", parsing_status="pending")
    doc2 = Document(file_name="doc2.pdf", file_path="path2", parsing_status="pending")
    test_db_session.add_all([doc1, doc2])
    test_db_session.commit()

    response = test_client.get("/api/documents/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2  # At least the two we added
    filenames = [doc["file_name"] for doc in data]
    assert "doc1.pdf" in filenames and "doc2.pdf" in filenames

def test_delete_document(test_client, test_db_session):
    """Test deleting a document"""
    # Add a document manually
    file_path = os.path.join(settings.UPLOAD_DIR, "delete.pdf")
    with open(file_path, "wb") as f:
        f.write(b"dummy content")

    doc = Document(file_name="delete.pdf", file_path=file_path, parsing_status="pending")
    test_db_session.add(doc)
    test_db_session.commit()

    response = test_client.delete(f"/api/documents/{doc.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Document deleted successfully"

    # Verify it's removed from DB
    doc_check = test_db_session.query(Document).filter(Document.id == doc.id).first()
    assert doc_check is None
    # Verify file is deleted
    assert not os.path.exists(file_path)
