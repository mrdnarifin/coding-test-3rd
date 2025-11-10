"""
Document processing service using docling

- Extract tables from PDF using docling
- Extract text and fund information
- Chunk text for vector storage
- Parse tables using TableParser
"""
from typing import Dict, List, Any
import logging
import traceback
import re
from pathlib import Path
from sqlalchemy.orm import Session

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

from app.services.table_parser import TableParser
from app.services.vector_store import VectorStore
from app.models.document import Document
from app.models.fund import Fund

_log = logging.getLogger(__name__)

class DocumentProcessor:
    """Process PDF documents, extract structured data, and store embeddings"""

    def __init__(self, db: Session):
        self.db = db
        self.table_parser = TableParser(db)
        self.vector_store = VectorStore(db)

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=4, device=AcceleratorDevice.AUTO
        )

        self.doc_converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )

    def process_document(self, file_path: str, document_id: int, fund_id: int = None) -> Dict[str, Any]:
        """
        Process a PDF document
        
        TODO: Implement this method
        - Open PDF with docling
        - Extract tables from each page
        - Parse and classify tables using TableParser
        - Extract text and create chunks
        - Store chunks in vector database
        - Return processing statistics
        
        Args:
            file_path: Path to the PDF file
            document_id: Database document ID
            fund_id: Fund ID
            
        Returns:
            Processing result with statistics
        """
        result = {
            "document_id": document_id,
            "fund_id": fund_id,
            "tables_parsed": 0,
            "rows_parsed": 0,
            "text_chunks": 0,
            "status": "pending",
            "error": None
        }

        try:
            # Convert PDF ke Docling document
            conv_result = self.doc_converter.convert(Path(file_path))
            document = conv_result.document

            # --- EXTRACT FUND INFO DARI TEKS HALAMAN PERTAMA ---
            fund_info = {}
            if document.pages and document.texts:
                first_page_no = min(document.pages.keys())
                first_page_texts = [
                    t.text for t in document.texts
                    if any(p.page_no == first_page_no for p in t.prov)
                ]
                first_page_text = "\n".join(first_page_texts)
                fund_info = self._parse_fund_info_from_text(first_page_text)
            
            if any(fund_info.values()):
                fund = self._get_or_create_fund(fund_info)
                fund_id = fund.id
            else:
                fund_id = None

            all_tables = []
            all_texts = []

            # Extract tables from document
            if hasattr(document, 'tables') and document.tables:
                for table in document.tables:
                    headers = []
                    rows = []
                    
                    table_data = table.data if table.data else None
                    if table_data:
                        table_cells = table_data.table_cells
                        rows_data = {}
                        
                        for cell in table_cells:
                            row_idx = cell.start_row_offset_idx
                            col_idx = cell.start_col_offset_idx
                            
                            if row_idx not in rows_data:
                                rows_data[row_idx] = []
                            
                            rows_data[row_idx].append({
                                "col_idx": col_idx,
                                "text": cell.text,
                                "column_header": cell.column_header
                            })
                        
                        for row_idx in sorted(rows_data.keys()):
                            row_cells = rows_data[row_idx]
                            row = []
                            
                            for cell in row_cells:
                                if cell["column_header"] and row_idx == 0:
                                    headers.append(cell["text"])
                                if not cell["column_header"]:
                                    row.append(cell["text"])
                            
                            if row_idx > 0:
                                rows.append(row)

                    all_tables.append({
                        "headers": headers,
                        "rows": rows
                    })


            for page_no, page in document.pages.items():
                # Teks
                page_texts = [t.text for t in document.texts if any(p.page_no == page_no for p in t.prov)]
                if page_texts:
                    all_texts.append({
                        "page_number": page_no,
                        "text": "\n".join(page_texts)
                    })

            if all_tables:
                total_rows = 0
                for table in all_tables:
                    rows_count = self.table_parser.parse_table(fund_id=fund_id, table=table)
                    total_rows += rows_count

                result.update({
                    "tables_parsed": len(all_tables),
                    "rows_parsed": total_rows,
                })
            
            if all_texts:
                chunks = self._chunk_text(all_texts)
                for chunk in chunks:
                    self.vector_store.add_document(
                        content=chunk["text"],
                        metadata={
                            "document_id": document_id,
                            "fund_id": fund_id,
                            **chunk.get("metadata", {})
                        }
                    )
                result.update({
                    "text_chunks": len(chunks),
                })

            # Update status dokumen setelah selesai
            result.update({
                "status": "completed",
                "fund_id": fund_id
            })

        except Exception as e:
            traceback.print_exc()
            result.update({
                "status": "failed",
                "error": str(e)
            })

        # Update status dokumen di database
        try:
            self.db.query(Document).filter(Document.id == document_id).update({
                "parsing_status": result["status"],
                "error_message": result["error"]
            })
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            _log.error(f"Failed to update document status: {e}")

        return result

    def _chunk_text(self, text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk text content for vector storage
        
        TODO: Implement intelligent text chunking
        - Split text into semantic chunks
        - Maintain context overlap
        - Preserve sentence boundaries
        - Add metadata to each chunk
        
        Args:
            text_content: List of text content with metadata
            
        Returns:
            List of text chunks with metadata
        """
        chunks = []
        for block in text_blocks:
            text = block.get("text", "")
            page_number = block.get("page_number", 0)

            # Split by paragraph
            paragraphs = text.split("\n\n")
            for para in paragraphs:
                para = para.strip()
                if para:
                    chunks.append({
                        "text": para,
                        "metadata": {"page": page_number}
                    })
        return chunks

    def _parse_fund_info_from_text(self, text: str) -> dict:
        """Parse fund info from first page text"""
        fund_info = {}
        patterns = {
            "name": r"Fund Name:\s*(.+)",
            "gp": r"GP:\s*(.+)",
            "vintage_year": r"Vintage Year:\s*(\d{4})",
            "fund_size": r"Fund Size:\s*\$([\d,]+)",
            "report_date": r"Report Date:\s*(.+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                if key == "vintage_year" or key == "fund_size":
                    value = int(value.replace(",", ""))
                fund_info[key] = value
            else:
                fund_info[key] = None
        return fund_info

    def _get_or_create_fund(self, fund_info: dict) -> Fund:
        """Get fund from DB or create if not exists"""
        fund = self.db.query(Fund).filter(Fund.name == fund_info['name']).first()
        if not fund:
            fund = Fund(
                name=fund_info['name'],
                gp_name=fund_info.get('gp'),
                vintage_year=fund_info.get('vintage_year'),
                fund_size=fund_info.get('fund_size')
            )
            self.db.add(fund)
            self.db.commit()
            self.db.refresh(fund)
        return fund
