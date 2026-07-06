import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("incident-commander-mcp", instructions="DevOps incident management tools")


SERVICES = {
    "api-gateway": {"status": "healthy", "latency_ms": 45, "uptime": 99.97},
    "auth-service": {"status": "healthy", "latency_ms": 12, "uptime": 99.99},
    "payment-processor": {"status": "degraded", "latency_ms": 320, "uptime": 98.50},
    "database-primary": {"status": "healthy", "latency_ms": 3, "uptime": 100.0},
    "cache-cluster": {"status": "healthy", "latency_ms": 1, "uptime": 99.95},
    "queue-worker": {"status": "healthy", "latency_ms": 8, "uptime": 99.90},
    "notification-service": {"status": "down", "latency_ms": 0, "uptime": 97.20},
    "search-indexer": {"status": "degraded", "latency_ms": 1500, "uptime": 95.00},
}

RUNBOOKS = {
    "database_outage": [
        "1. Check database-primary health endpoint",
        "2. Verify replica lag on database-replica-1, database-replica-2",
        "3. Review slow query log for recent changes",
        "4. Check disk space on primary node",
        "5. If disk full: extend volume and rotate WAL logs",
        "6. If replication lag: pause indexer backfill",
    ],
    "high_latency": [
        "1. Identify affected endpoints from metrics dashboard",
        "2. Check cache-cluster hit rate",
        "3. Review recent deployments in last 2 hours",
        "4. Check for connection pool exhaustion",
        "5. Scale up workers if queue backlog > 10K",
    ],
    "service_down": [
        "1. Confirm alert from monitoring system",
        "2. Check service health endpoint",
        "3. Review recent changes in deployment history",
        "4. Check upstream dependencies",
        "5. Restart service if no obvious cause",
        "6. Escalate to on-call team if restart fails",
    ],
    "security_incident": [
        "1. Isolate affected systems immediately",
        "2. Review authentication logs for unauthorized access",
        "3. Check for unusual API call patterns",
        "4. Rotate exposed credentials",
        "5. Engage security team per incident response plan",
        "6. Document all findings in post-mortem",
    ],
    "payment_failure": [
        "1. Check payment-processor health status",
        "2. Verify upstream payment gateway connectivity",
        "3. Review recent transaction error rates",
        "4. Check for failed webhook deliveries",
        "5. Verify idempotency keys are being used",
        "6. Contact payment provider if gateway is down",
    ],
}

RECENT_DEPLOYMENTS = [
    {"service": "api-gateway", "version": "v2.14.3", "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), "status": "success", "commits": 12},
    {"service": "payment-processor", "version": "v3.1.0", "timestamp": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(), "status": "success", "commits": 8},
    {"service": "auth-service", "version": "v1.8.2", "timestamp": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(), "status": "rollback", "commits": 5},
    {"service": "search-indexer", "version": "v0.9.5", "timestamp": (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat(), "status": "success", "commits": 15},
    {"service": "notification-service", "version": "v2.0.1", "timestamp": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(), "status": "failed", "commits": 3},
]

INCIDENT_TICKETS: list[dict[str, Any]] = []
TICKET_COUNTER = [0]


@mcp.tool()
async def get_service_health(service_name: str) -> str:
    """Check the health status of a named service.

    Args:
        service_name: The name of the service to check (e.g. api-gateway, auth-service, database-primary).
    """
    service = SERVICES.get(service_name.lower())
    if not service:
        known = ", ".join(sorted(SERVICES.keys()))
        return json.dumps({
            "error": f"Unknown service '{service_name}'",
            "known_services": known,
        }, indent=2)

    return json.dumps({
        "service": service_name,
        "status": service["status"],
        "latency_ms": service["latency_ms"],
        "uptime_pct": service["uptime"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2)


@mcp.tool()
async def search_runbooks(incident_type: str) -> str:
    """Search for a runbook matching the given incident type.

    Args:
        incident_type: The type of incident (e.g. database_outage, high_latency, service_down, security_incident, payment_failure).
    """
    incident_type = incident_type.lower().replace(" ", "_")
    runbook = RUNBOOKS.get(incident_type)
    if not runbook:
        known = ", ".join(sorted(RUNBOOKS.keys()))
        return json.dumps({
            "error": f"No runbook found for '{incident_type}'",
            "available_runbooks": known,
        }, indent=2)

    return json.dumps({
        "incident_type": incident_type,
        "steps": runbook,
    }, indent=2)


@mcp.tool()
async def create_incident_ticket(title: str, severity: str, description: str) -> str:
    """Create an incident ticket in the tracking system.

    Args:
        title: Short title of the incident.
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW).
        description: Detailed description of the incident.
    """
    TICKET_COUNTER[0] += 1
    ticket = {
        "id": f"INC-{TICKET_COUNTER[0]:05d}",
        "title": title,
        "severity": severity.upper(),
        "description": description,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assigned_to": "on-call-engineer",
    }
    INCIDENT_TICKETS.append(ticket)
    return json.dumps(ticket, indent=2)


@mcp.tool()
async def get_recent_deployments(service_name: str = "") -> str:
    """List recent deployments across all services or for a specific service.

    Args:
        service_name: Optional service name to filter by (e.g. api-gateway).
    """
    if service_name:
        filtered = [d for d in RECENT_DEPLOYMENTS if d["service"] == service_name.lower()]
        if not filtered:
            return json.dumps({"error": f"No deployments found for '{service_name}'"}, indent=2)
        return json.dumps({"deployments": filtered, "count": len(filtered)}, indent=2)

    return json.dumps({"deployments": RECENT_DEPLOYMENTS, "count": len(RECENT_DEPLOYMENTS)}, indent=2)


@mcp.tool()
async def escalate_to_team(incident_id: str, team: str, reason: str) -> str:
    """Escalate an incident to a specific team for resolution.

    Args:
        incident_id: The incident ticket ID (e.g. INC-00001).
        team: The team to escalate to (e.g. SRE, Security, Database, Frontend).
        reason: Brief reason for escalation.
    """
    escalation = {
        "incident_id": incident_id,
        "escalated_to": team.upper(),
        "reason": reason,
        "status": "escalated",
        "escalated_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged": False,
    }
    return json.dumps(escalation, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
