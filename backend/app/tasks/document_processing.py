from app.celery import celery_app
from app.db.session import SessionLocal
from app.services.document_processor import DocumentProcessor
from app.models.document import Document

@celery_app.task
def process_document_task(document_id: int, file_path: str, fund_id: int):
    """Background task to process the document"""
    db = SessionLocal()
    
    try:
        # Update status to 'processing' in DB
        document = db.query(Document).filter(Document.id == document_id).first()
        document.parsing_status = "processing"
        db.commit()
        
        # Process the document (extract tables, text, etc.)
        processor = DocumentProcessor(db)
        result = processor.process_document(file_path, document_id, fund_id)
        
        # Update status after processing
        document.parsing_status = result["status"]
        if result["status"] == "failed":
            document.error_message = result.get("error")
        db.commit()
        
    except Exception as e:
        # Handle failure
        document = db.query(Document).filter(Document.id == document_id).first()
        document.parsing_status = "failed"
        document.error_message = str(e)
        db.commit()
    finally:
        db.close()
