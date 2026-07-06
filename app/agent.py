import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.events.request_input import RequestInput
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.workflow import Workflow
from google.adk.workflow._graph import DEFAULT_ROUTE, START
from google.adk.workflow._node import node
from mcp import StdioServerParameters

from .config import config

logger = logging.getLogger(__name__)

AUDIT_LOG: list[dict[str, Any]] = []

PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "phone": re.compile(r"\b\+?1?\d{10,15}\b"),
    "api_key": re.compile(r"\b(?:sk-[A-Za-z0-9]{32,}|[A-Za-z0-9]{40,})\b"),
    "internal_hostname": re.compile(r"\b(?:prod|stg|dev)-[a-z0-9-]+\.internal\.\w+\b"),
}

INJECTION_KEYWORDS = [
    "ignore all instructions",
    "ignore previous instructions",
    "you are now sysadmin",
    "override system prompt",
    "forget your instructions",
    "act as if",
    "do not follow",
    "sudo make me",
    "system override",
    "pretend you are",
]


def log_audit_entry(severity: str, event_type: str, details: dict[str, Any]) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "event_type": event_type,
        "details": details,
    }
    AUDIT_LOG.append(entry)
    logger.info("[AUDIT] %s | %s | %s", severity, event_type, json.dumps(details))


def scrub_pii(text: str) -> str:
    for label, pattern in PII_PATTERNS.items():
        text = pattern.sub(f"[REDACTED_{label}]", text)
    return text


def detect_injection(text: str) -> bool:
    lower = text.lower()
    for kw in INJECTION_KEYWORDS:
        if kw in lower:
            return True
    return False


@node
async def security_checkpoint(ctx: Any, node_input: Optional[str] = None) -> dict[str, Any]:
    user_message = node_input or ""

    if not user_message:
        ctx.state["original_input"] = node_input
        return {"status": "clean", "message": "No user input to check"}

    if config.pii_redaction_enabled:
        scrubbed = scrub_pii(user_message)
        if scrubbed != user_message:
            log_audit_entry("INFO", "PII_REDACTED", {"original": user_message, "scrubbed": scrubbed})
            ctx.state["scrubbed_input"] = scrubbed
        else:
            ctx.state["scrubbed_input"] = user_message
    else:
        ctx.state["scrubbed_input"] = user_message

    if config.injection_detection_enabled:
        if detect_injection(user_message):
            log_audit_entry("CRITICAL", "INJECTION_DETECTED", {"input": user_message})
            ctx.state["security_violation"] = True
            ctx.state["violation_reason"] = "Prompt injection keywords detected"
            ctx.route = "SECURITY_EVENT"
            return {"status": "violation", "reason": "Prompt injection detected"}

    ctx.state["original_input"] = node_input
    ctx.state["security_violation"] = False
    log_audit_entry("INFO", "INPUT_CLEAN", {"scrubbed_preview": ctx.state["scrubbed_input"][:80]})
    return {"status": "clean", "message": ctx.state["scrubbed_input"]}


@node
async def orchestrator(ctx: Any, node_input: Optional[dict] = None) -> dict[str, Any]:
    raw_message = node_input.get("message", "") if node_input else ""
    ctx.state["incident_title"] = "Untitled Incident"
    ctx.state["incident_description"] = raw_message
    ctx.state["incident_service"] = "unknown"
    ctx.state["incident_reporter"] = "anonymous"

    words = raw_message.split()
    for i, w in enumerate(words):
        if w.lower() == "service:" and i + 1 < len(words):
            ctx.state["incident_service"] = words[i + 1].rstrip(".,")
        if w.lower() == "reporter:" and i + 1 < len(words):
            ctx.state["incident_reporter"] = words[i + 1].rstrip(".,")

    first_sentence = raw_message.split(".")[0] if raw_message else ""
    if first_sentence:
        ctx.state["incident_title"] = first_sentence[:80]

    log_audit_entry("INFO", "INCIDENT_ROUTED", {
        "title": ctx.state.get("incident_title"),
        "service": ctx.state.get("incident_service"),
    })
    return {
        "incident_title": ctx.state["incident_title"],
        "incident_service": ctx.state["incident_service"],
    }


@node
async def security_violation_output(ctx: Any) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "reason": ctx.state.get("violation_reason", "Security policy violation"),
        "message": "This incident has been blocked by security policy. Contact your security team.",
    }


def _build_approval_summary(ctx: Any) -> str:
    diagnosis = ctx.state.get("diagnosis_result", {})
    incident_title = ctx.state.get("incident_title", "Unknown")
    summary = f"Incident: {incident_title}\n"
    if isinstance(diagnosis, dict):
        summary += f"Root Cause: {diagnosis.get('root_cause', diagnosis.get('summary', 'See details'))}\n"
        summary += f"Suggested Action: {diagnosis.get('recommended_action', 'Review and approve')}\n"
    else:
        summary += f"Diagnosis: {str(diagnosis)[:200]}\n"
    return summary


@node(rerun_on_resume=True)
async def human_approval(ctx: Any, node_input: Any) -> Any:
    resume_val = ctx.resume_inputs.get("approve_resolution", "")
    if resume_val:
        decision = "APPROVED" if "approv" in resume_val.lower() else "DENIED"
        ctx.route = decision
        log_audit_entry("INFO", "HUMAN_DECISION", {
            "incident": ctx.state.get("incident_title", "Unknown"),
            "decision": decision,
        })
        return {"decision": decision, "incident": ctx.state.get("incident_title", "Unknown")}

    incident_title = ctx.state.get("incident_title", "Unknown")
    summary = _build_approval_summary(ctx)
    return RequestInput(
        interrupt_id="approve_resolution",
        payload={
            "incident_title": incident_title,
            "diagnosis_summary": summary,
            "options": ["APPROVED", "DENIED"],
        },
        message=f"{summary}\n\nApprove or deny this resolution? (APPROVED / DENIED)",
    )


@node
async def final_output(ctx: Any) -> dict[str, Any]:
    return {
        "status": "COMPLETED",
        "incident": ctx.state.get("incident_title", "Unknown"),
        "severity": ctx.state.get("triage_result", {}).get("severity", "unclassified"),
        "diagnosis": ctx.state.get("diagnosis_result", {}),
        "resolution": ctx.state.get("documentation_result", ctx.state.get("human_decision", "No resolution recorded")),
    }


def create_mcp_toolset() -> McpToolset:
    server_script = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    return McpToolset(
        connection_params=StdioServerParameters(
            command="uv",
            args=["run", "python", server_script],
        ),
    )


def create_root_agent() -> App:
    mcp_toolset = create_mcp_toolset()

    triage_agent = LlmAgent(
        name="triage_agent",
        model=config.model,
        instruction=(
            "You are an incident triage specialist. Given an incident report, classify:\n"
            "- severity (CRITICAL / HIGH / MEDIUM / LOW)\n"
            "- affected service\n"
            "- impact scope\n"
            "- priority score (1-5)\n"
            "Output a JSON object with these fields. Be concise.\n\n"
            "You have these tools available:\n"
            '- create_incident_ticket(title, severity, description) — create a ticket\n'
            '- get_service_health(service_name) — check service health\n'
            '- search_runbooks(incident_type) — find runbook steps\n'
            '- get_recent_deployments(service_name) — check recent changes\n'
            '- escalate_to_team(incident_id, team, reason) — escalate incident\n'
            "Call ONLY the tools listed above with their EXACT names."
        ),
        tools=[mcp_toolset],
        mode="single_turn",
    )

    diagnosis_agent = LlmAgent(
        name="diagnosis_agent",
        model=config.model,
        instruction=(
            "You are a root cause analysis specialist. Given an incident with its triage "
            "classification, investigate the likely root cause.\n"
            "Output a JSON object with: root_cause, affected_components, "
            "recommended_action, confidence (HIGH/MEDIUM/LOW).\n\n"
            "Available tools (use only these exact names):\n"
            '- get_service_health(service_name)\n'
            '- search_runbooks(incident_type)\n'
            '- create_incident_ticket(title, severity, description)\n'
            '- get_recent_deployments(service_name)\n'
            '- escalate_to_team(incident_id, team, reason)\n'
            "Do NOT invent or guess tool names."
        ),
        tools=[mcp_toolset],
        mode="single_turn",
    )

    documentation_agent = LlmAgent(
        name="documentation_agent",
        model=config.model,
        instruction=(
            "You are an incident documentation specialist. Given the full incident details "
            "including triage, diagnosis, and resolution decision, produce a comprehensive "
            "incident report.\n"
            "Include: title, timeline, severity, root cause, resolution steps, "
            "prevention recommendations.\n"
            "Output in valid JSON.\n\n"
            "Available tools (use only these exact names):\n"
            '- create_incident_ticket(title, severity, description)\n'
            '- search_runbooks(incident_type)\n'
            '- escalate_to_team(incident_id, team, reason)\n'
            "Do NOT guess tool names."
        ),
        tools=[mcp_toolset],
        mode="single_turn",
    )

    wf = Workflow(
        name="incident_commander",
        description="DevOps Incident Commander — multi-agent workflow for incident management",
        edges=[
            (START, security_checkpoint),
            (security_checkpoint, {
                "SECURITY_EVENT": security_violation_output,
                DEFAULT_ROUTE: orchestrator,
            }),
            (orchestrator, triage_agent),
            (triage_agent, diagnosis_agent),
            (diagnosis_agent, human_approval),
            (human_approval, {
                "APPROVED": documentation_agent,
                "DENIED": final_output,
            }),
            (documentation_agent, final_output),
        ],
    )

    app = App(root_agent=wf, name="app")
    return app


app = create_root_agent()
