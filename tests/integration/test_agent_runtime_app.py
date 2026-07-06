import pytest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent_runtime_app import agent_runtime


def test_agent_runtime_imports() -> None:
    assert agent_runtime is not None
    assert hasattr(agent_runtime, "root_agent")


@pytest.mark.asyncio
async def test_agent_stream_query() -> None:
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(
        agent=agent_runtime,
        session_service=session_service,
        app_name="test",
    )

    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text="Payment processor is slow. Service: payment-processor")],
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="test_user",
            session_id=session.id,
        )
    )
    assert len(events) > 0
