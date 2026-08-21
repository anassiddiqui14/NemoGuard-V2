"""
Unit tests for src/domain/agents/base_agent.py::BaseAgent.call_llm_with_tools'
iteration-budget exhaustion path.

Regression coverage for a real production failure mode observed on a
genuine LocalStack partial-write incident: the Grounding Critic (which is
given a large tool budget specifically because it independently re-verifies
many claims using read-only tools) would occasionally exhaust
`max_iterations` while still in the middle of tool-calling. The PREVIOUS
behavior discarded every tool result already gathered in `messages` and
returned a bare `{"error": "LLM exceeded maximum allowed tool
iterations..."}`, which forced `run_critic()` in langgraph_investigator.py
to fall back to synthesizing a substitute plan with NO safety critique at
all -- silently defeating the entire purpose of the Grounding Critic (spec:
build plan Priority 5 / Stage 6 "Critic" gate).

The fix makes one final forced answer-only LLM turn (tools omitted from the
request) once the budget is exhausted, so the agent must synthesize its
final JSON answer from whatever evidence it already collected instead of
losing that work entirely.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.domain.agents.base_agent import BaseAgent


def _make_agent() -> BaseAgent:
    agent = BaseAgent(agent_name="TestAgent", system_prompt="You are a test agent.", model="test-model")
    agent.client = MagicMock()
    agent.client.chat = MagicMock()
    agent.client.chat.completions = MagicMock()
    agent.client.chat.completions.create = AsyncMock()
    return agent


def _completion_with_tool_call(tool_name: str, tool_call_id: str, arguments: str = "{}"):
    """Builds a fake completion object whose message requests a single tool call."""
    tool_call = MagicMock()
    tool_call.id = tool_call_id
    tool_call.function.name = tool_name
    tool_call.function.arguments = arguments

    message = MagicMock()
    message.tool_calls = [tool_call]
    message.content = None

    choice = MagicMock()
    choice.message = message

    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _completion_with_final_answer(content: str):
    """Builds a fake completion object whose message is a final (no tool call) answer."""
    message = MagicMock()
    message.tool_calls = None
    message.content = content

    choice = MagicMock()
    choice.message = message

    completion = MagicMock()
    completion.choices = [choice]
    return completion


class TestIterationBudgetExhaustion:
    @pytest.mark.asyncio
    async def test_exhausting_budget_makes_a_forced_final_answer_call_instead_of_erroring_immediately(self):
        """
        If the LLM keeps requesting tool calls for the entire iteration
        budget, the PREVIOUS code returned {"error": ...} immediately upon
        exiting the loop -- one extra "forced final answer" completion call
        must now be made instead.
        """
        agent = _make_agent()

        # Every iteration within budget requests another tool call (never a
        # final answer), so the loop runs out of budget. Then the forced
        # final turn (call N+1) returns a real, well-formed answer.
        tool_call_completions = [
            _completion_with_tool_call("some_tool", f"call-{i}") for i in range(3)
        ]
        forced_final_completion = _completion_with_final_answer('{"passed": true, "feedback": "ok"}')
        agent.client.chat.completions.create.side_effect = tool_call_completions + [forced_final_completion]

        execute_tool_fn = AsyncMock(return_value="tool result")

        result = await agent.call_llm_with_tools(
            prompt="investigate", tools=[{"type": "function"}], execute_tool_fn=execute_tool_fn, max_iterations=3
        )

        # The forced final turn's answer must be returned, NOT a bare error --
        # this is the actual behavioral fix.
        assert result == {"passed": True, "feedback": "ok"}
        # 3 tool-call iterations + 1 forced final-answer call.
        assert agent.client.chat.completions.create.call_count == 4

    @pytest.mark.asyncio
    async def test_forced_final_call_omits_tools_so_it_cannot_request_another_tool_call(self):
        """
        The forced final turn must NOT pass `tools=` in the request -- if it
        did, the model could simply request yet another tool call and
        recreate the exact same unbounded loop this fix exists to prevent.
        """
        agent = _make_agent()
        tool_call_completions = [_completion_with_tool_call("some_tool", "call-0")]
        forced_final_completion = _completion_with_final_answer('{"passed": false, "feedback": "budget exhausted"}')
        agent.client.chat.completions.create.side_effect = tool_call_completions + [forced_final_completion]

        execute_tool_fn = AsyncMock(return_value="tool result")

        await agent.call_llm_with_tools(
            prompt="investigate", tools=[{"type": "function"}], execute_tool_fn=execute_tool_fn, max_iterations=1
        )

        # Inspect the LAST call (the forced final turn) and confirm no `tools`
        # kwarg was passed.
        _, last_call_kwargs = agent.client.chat.completions.create.call_args_list[-1]
        assert "tools" not in last_call_kwargs

    @pytest.mark.asyncio
    async def test_gathered_tool_evidence_is_included_in_the_forced_final_call(self):
        """
        The whole point of the fix: the forced final turn's message history
        must include the actual tool results gathered during the exhausted
        iterations, not a fresh/empty context.
        """
        agent = _make_agent()
        tool_call_completions = [_completion_with_tool_call("check_table_staleness", "call-0")]
        forced_final_completion = _completion_with_final_answer('{"passed": true, "feedback": "verified"}')
        agent.client.chat.completions.create.side_effect = tool_call_completions + [forced_final_completion]

        execute_tool_fn = AsyncMock(return_value="table is stale: true")

        await agent.call_llm_with_tools(
            prompt="investigate", tools=[{"type": "function"}], execute_tool_fn=execute_tool_fn, max_iterations=1
        )

        _, last_call_kwargs = agent.client.chat.completions.create.call_args_list[-1]
        messages = last_call_kwargs["messages"]
        tool_result_messages = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_result_messages) == 1
        assert tool_result_messages[0]["content"] == "table is stale: true"

    @pytest.mark.asyncio
    async def test_forced_final_call_itself_failing_returns_an_annotated_error(self):
        """
        If even the forced final turn can't produce parseable JSON (or the
        LLM call itself errors), the method must still fail gracefully --
        but the error message should reflect that a recovery attempt was
        made, not look identical to the pre-fix bare timeout error.
        """
        agent = _make_agent()
        tool_call_completions = [_completion_with_tool_call("some_tool", "call-0")]
        # The forced final turn also just requests ANOTHER tool call (worst case) --
        # any non-final-answer response counts as "the forced attempt failed" for
        # our purposes since we don't loop again on it; simulate via unparseable content instead.
        unparseable_final_completion = _completion_with_final_answer("not valid json at all")
        agent.client.chat.completions.create.side_effect = tool_call_completions + [unparseable_final_completion]

        execute_tool_fn = AsyncMock(return_value="tool result")

        result = await agent.call_llm_with_tools(
            prompt="investigate", tools=[{"type": "function"}], execute_tool_fn=execute_tool_fn, max_iterations=1
        )

        assert "error" in result
        assert "maximum allowed tool iterations" in result["error"]
        assert "forced final answer attempt also failed" in result["error"]

    @pytest.mark.asyncio
    async def test_normal_completion_within_budget_is_unaffected(self):
        """Sanity check: when the LLM finishes within budget, behavior is unchanged (no forced extra call)."""
        agent = _make_agent()
        final_completion = _completion_with_final_answer('{"passed": true, "feedback": "done immediately"}')
        agent.client.chat.completions.create.side_effect = [final_completion]

        execute_tool_fn = AsyncMock()

        result = await agent.call_llm_with_tools(
            prompt="investigate", tools=[{"type": "function"}], execute_tool_fn=execute_tool_fn, max_iterations=5
        )

        assert result == {"passed": True, "feedback": "done immediately"}
        assert agent.client.chat.completions.create.call_count == 1
        execute_tool_fn.assert_not_called()
