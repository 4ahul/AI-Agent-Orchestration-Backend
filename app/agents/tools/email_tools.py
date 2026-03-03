"""
CrewAI-compatible tools for email composition and delivery using the StructuredTool pattern.
Uses pydantic.v1 for compatibility with LangChain's StructuredTool.
"""
import json
from langchain_core.tools import StructuredTool
from pydantic.v1 import BaseModel, Field

from app.core.logging_config import get_logger
from app.services.email_service import send_email

logger = get_logger(__name__)

class EmailCompositionInput(BaseModel):
    recipient_name: str = Field(default="", description="Recipient's name")
    title: str = Field(default="Document", description="Title of the analyzed document")
    summary: str = Field(..., description="Key summary extracted from the PDF")
    key_entities: str = Field(default="", description="Key entities found in the document")
    tone: str = Field(default="professional", description="Tone of email: professional|friendly|formal")

def run_email_template(
    summary: str,
    recipient_name: str = "",
    title: str = "Document",
    key_entities: str = "",
    tone: str = "professional",
) -> str:
    """Builds a professional email template."""
    try:
        greeting = f"Dear {recipient_name}," if recipient_name else "Dear Recipient,"
        subject = f"Analysis Report: {title[:80]}"

        body = f"""{greeting}

I hope this email finds you well.

I am writing to share the analysis of the document titled "{title}".

--- Document Summary ---
{summary}

--- Key Entities Identified ---
{key_entities or "Not available"}

Please feel free to reach out if you have any questions or need further clarification.

Best regards,
AI Agent Orchestrator
"""
        result = {"subject": subject, "body": body.strip()}
        logger.info("Email template generated", doc_title=title)
        return json.dumps(result)
    except Exception as e:
        logger.error("Email template generation failed", error=str(e))
        return json.dumps({"error": str(e)})

email_template_tool = StructuredTool.from_function(
    func=run_email_template,
    name="email_template_tool",
    description="Generates a professional email template from document analysis.",
    args_schema=EmailCompositionInput,
)


class EmailDeliveryInput(BaseModel):
    recipient: str = Field(..., description="Target recipient email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content")

def run_email_delivery(recipient: str, subject: str, body: str) -> str:
    """Sends an email via configured provider."""
    try:
        logger.info("EmailDeliveryTool invoked", recipient=recipient)
        result = send_email(to=recipient, subject=subject, body=body)
        return json.dumps({
            "success": result.success,
            "message_id": result.message_id,
            "provider_response": result.provider_response,
            "recipient": recipient,
        })
    except Exception as e:
        logger.error("Email delivery failed", error=str(e), recipient=recipient)
        return json.dumps({"success": False, "error": str(e), "recipient": recipient})

email_delivery_tool = StructuredTool.from_function(
    func=run_email_delivery,
    name="email_delivery_tool",
    description="Sends an email to the specified recipient.",
    args_schema=EmailDeliveryInput,
)
