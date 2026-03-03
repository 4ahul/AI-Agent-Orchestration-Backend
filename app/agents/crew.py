"""
CrewAI Agent Orchestration Layer.

Three-agent pipeline (no circular calls):
  PDF Analyzer Agent
       ↓
  Email Composer Agent
       ↓
  Email Delivery Agent
"""
import json
import os
import time
from typing import Any, Callable

from crewai import Agent, Crew, Process, Task
from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.tools.email_tools import email_delivery_tool, email_template_tool
from app.agents.tools.pdf_tools import key_entity_extractor, pdf_extraction_tool
from app.core.config import settings
from app.core.exceptions import AgentExecutionError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _build_llm() -> BaseChatModel:
    """
    Builds and returns the LLM instance with a resilient fallback chain:
    Groq (Primary - Fast/Reliable) → Gemini 1.5 → Ollama (Local)
    """
    # Force unset OpenAI
    os.environ["OPENAI_API_KEY"] = "none"

    # 1. Try Groq (Now Primary - Very reliable free tier)
    if settings.GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
            logger.info("Using Groq LLM (llama-3.3-70b-versatile)")
            return ChatGroq(
                api_key=settings.GROQ_API_KEY,
                model="llama-3.3-70b-versatile",
                temperature=0.1,
            )
        except Exception as e:
            logger.error(f"Groq initialization failed: {e}")

    # 2. Try Google Gemini 1.5 Flash
    if settings.GOOGLE_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.info("Using Google Gemini 1.5 Flash")
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.1,
            )
        except Exception as e:
            logger.error(f"Gemini 1.5 initialization failed: {e}")

    # 3. Try Ollama (Local Fallback - requires Ollama running on host)
    try:
        from langchain_community.chat_models import ChatOllama
        logger.info("Attempting Local Ollama (llama3.2)")
        return ChatOllama(
            model="llama3.2",
            base_url="http://host.docker.internal:11434",
            temperature=0.1,
        )
    except Exception as e:
        logger.warning(f"Ollama not available: {e}")

    # Final Fallback Error
    raise AgentExecutionError("No valid LLM providers available (Groq, Gemini, or Ollama).")


# ── Agent Definitions ─────────────────────────────────────────────────────────

def build_pdf_analyzer_agent(llm: BaseChatModel) -> Agent:
    return Agent(
        role="Senior PDF Document Analyst",
        goal=(
            "Extract and structure content from PDF. "
            "Return JSON with title, summary, key_entities, sections."
        ),
        backstory="Expert document analyst. Precise and efficient.",
        tools=[pdf_extraction_tool, key_entity_extractor],
        llm=llm,
        verbose=True,
        max_iter=3, # Reduced to save quota
        allow_delegation=False,
    )


def build_email_composer_agent(llm: BaseChatModel) -> Agent:
    return Agent(
        role="Professional Email Composer",
        goal="Craft professional emails from analysis.",
        backstory="Business communication expert.",
        tools=[email_template_tool],
        llm=llm,
        verbose=True,
        max_iter=2, # Reduced to save quota
        allow_delegation=False,
    )


def build_email_delivery_agent(llm: BaseChatModel) -> Agent:
    return Agent(
        role="Email Delivery Coordinator",
        goal="Send email and report status.",
        backstory="Reliable delivery expert.",
        tools=[email_delivery_tool],
        llm=llm,
        verbose=True,
        max_iter=2, # Reduced to save quota
        allow_delegation=False,
    )


# ── Task Definitions ──────────────────────────────────────────────────────────

def build_tasks(
    pdf_analyzer: Agent,
    email_composer: Agent,
    email_delivery: Agent,
    file_path: str,
    recipient_email: str,
    callback: Callable[[str, str], None] | None = None,
) -> list[Task]:

    task_extract = Task(
        description=f"Extract content from {file_path}. Return structured JSON.",
        expected_output="JSON: title, summary, key_entities, sections.",
        agent=pdf_analyzer,
        callback=lambda x: callback("PDF_ANALYZER", getattr(x, 'raw', str(x))) if callback else None,
    )

    task_compose = Task(
        description=f"Compose email to {recipient_email}. Return JSON: subject, body.",
        expected_output="JSON: subject, body.",
        agent=email_composer,
        context=[task_extract],
        callback=lambda x: callback("EMAIL_COMPOSER", getattr(x, 'raw', str(x))) if callback else None,
    )

    task_deliver = Task(
        description=f"Send email to {recipient_email}. Return JSON: success, message_id.",
        expected_output="JSON: success, message_id.",
        agent=email_delivery,
        context=[task_compose],
        callback=lambda x: callback("EMAIL_DELIVERY", getattr(x, 'raw', str(x))) if callback else None,
    )

    return [task_extract, task_compose, task_deliver]


# ── Crew Execution ────────────────────────────────────────────────────────────

def run_agent_pipeline(
    file_path: str,
    recipient_email: str,
    on_task_complete: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """
    Execute the full 3-agent pipeline.
    """
    logger.info("Agent pipeline starting", file=file_path, recipient=recipient_email)
    start_time = time.perf_counter()

    try:
        llm = _build_llm()

        # Build agents
        pdf_analyzer = build_pdf_analyzer_agent(llm)
        email_composer = build_email_composer_agent(llm)
        email_delivery = build_email_delivery_agent(llm)

        # Build tasks
        tasks = build_tasks(
            pdf_analyzer, email_composer, email_delivery,
            file_path=file_path,
            recipient_email=recipient_email,
            callback=on_task_complete,
        )

        # Assemble crew with strict rate limiting and disabled memory for RAM efficiency
        crew = Crew(
            agents=[pdf_analyzer, email_composer, email_delivery],
            tasks=tasks,
            process=Process.sequential,
            verbose=True,
            max_rpm=2, 
            memory=False, # Disable memory to save RAM
            embedder={
                "provider": "google",
                "config": {"model": "models/embedding-001"}
            } if settings.GOOGLE_API_KEY else None
        )

        crew_result = crew.kickoff()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Extract usage metrics if available (CrewAI >= 0.30.0)
        usage_metrics = {}
        if hasattr(crew_result, 'usage_metrics') and crew_result.usage_metrics:
            usage_metrics = {
                "total_tokens": getattr(crew_result.usage_metrics, 'total_tokens', 0),
                "prompt_tokens": getattr(crew_result.usage_metrics, 'prompt_tokens', 0),
                "completion_tokens": getattr(crew_result.usage_metrics, 'completion_tokens', 0),
            }

        # Parse final output defensively
        raw_output = str(crew_result)
        if hasattr(crew_result, 'raw'):
            raw_output = crew_result.raw
            
        delivery_data = _safe_parse_json(raw_output)

        # Build tasks_output with timing metadata
        final_tasks_output = []
        for task in tasks:
            t_out = ""
            t_time = 0.0
            if hasattr(task, 'output') and task.output:
                t_out = getattr(task.output, 'raw', str(task.output))
                # Attempt to get per-task execution time if CrewAI tracked it
                # Fallback to a portion of total time if not tracked individually
            
            final_tasks_output.append({
                "agent": task.agent.role,
                "output": t_out,
                "execution_time_ms": 0.0 # Will be estimated in worker if missing
            })

        pipeline_result = {
            "success": True,
            "elapsed_ms": round(elapsed_ms, 2),
            "usage": usage_metrics,
            "tasks_output": final_tasks_output,
            "delivery_result": delivery_data,
            "raw_crew_output": str(crew_result),
        }

        logger.info("Agent pipeline completed", elapsed_ms=pipeline_result["elapsed_ms"])
        return pipeline_result

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error("Agent pipeline failed", error=str(e), elapsed_ms=elapsed_ms)
        raise AgentExecutionError(f"Agent pipeline failed: {str(e)}")


def _safe_parse_json(text: str) -> dict:
    import re
    if not text or not isinstance(text, str):
        return {"raw": str(text)}
        
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {"raw": text}
