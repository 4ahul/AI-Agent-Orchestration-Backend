"""
CrewAI-compatible tools for PDF processing using the StructuredTool pattern.
Uses pydantic.v1 for compatibility with LangChain's StructuredTool.
"""
import json
from langchain_core.tools import StructuredTool
from pydantic.v1 import BaseModel, Field

from app.core.logging_config import get_logger
from app.services.pdf_service import extract_pdf_data

logger = get_logger(__name__)

class PDFExtractionInput(BaseModel):
    file_path: str = Field(..., description="Absolute file system path to the PDF file")

def run_pdf_extraction(file_path: str) -> str:
    """Extracts structured content from a PDF file."""
    try:
        logger.info("PDFExtractionTool invoked", file_path=file_path)
        data = extract_pdf_data(file_path)
        
        # Truncate text content to avoid token limit issues (max 10k chars)
        if "text" in data and len(data["text"]) > 10000:
            data["text"] = data["text"][:10000] + "... [TRUNCATED]"
            
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("PDFExtractionTool failed", error=str(e))
        return json.dumps({"error": str(e), "success": False})

pdf_extraction_tool = StructuredTool.from_function(
    func=run_pdf_extraction,
    name="pdf_extraction_tool",
    description="Extracts page text, headings, tables, and metadata from a PDF file.",
    args_schema=PDFExtractionInput,
)


class KeyEntityInput(BaseModel):
    text: str = Field(..., description="Raw text from which to identify key entities")

def run_key_entity_extraction(text: str) -> str:
    """Identifies key entities from raw text content."""
    try:
        # Truncate input text for entity extraction as well
        if len(text) > 5000:
            text = text[:5000]
            
        from app.services.pdf_service import _extract_key_entities
        entities = _extract_key_entities(text)
        return json.dumps(entities, ensure_ascii=False)
    except Exception as e:
        logger.error("KeyEntityExtractorTool failed", error=str(e))
        return json.dumps({"error": str(e)})

key_entity_extractor = StructuredTool.from_function(
    func=run_key_entity_extraction,
    name="key_entity_extractor",
    description="Identifies names, organizations, and dates from raw PDF text.",
    args_schema=KeyEntityInput,
)
