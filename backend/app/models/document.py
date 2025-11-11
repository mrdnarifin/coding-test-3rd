"""
Document database model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base import Base


class Document(Base):
    """Document model"""
    
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id"))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500))
    upload_date = Column(DateTime, default=datetime.now(timezone.utc))
    parsing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    
    # Relationships
    fund = relationship("Fund", back_populates="documents")
