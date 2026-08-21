import os
import json
from typing import Dict, Any
from openai import AsyncOpenAI


def _sanitize_and_parse_json(content: str) -> Dict[str, Any]:
    """
    Parses LLM-produced JSON, tolerating literal (unescaped) control
    characters -- most commonly raw newlines -- inside string literals.

    Background: Nemotron (and LLMs generally) sometimes emit a JSON string
    value containing an actual newline character instead of the required
    `\\n` escape sequence (e.g. a multi-paragraph "feedback" field). Per the
    JSON spec this is invalid and `json.loads` raises
    "Invalid control character at: ...".

    The previous "fix" for this (`content.replace("\\n", "\\\\n"); content =
    content.replace("\\\\n", "\\n")`) was a complete no-op -- it replaced
    every literal newline with an escaped one, then immediately reversed
    that exact replacement, leaving the string byte-for-byte unchanged. It
    never actually escaped anything, so any response containing a raw
    newline inside a string value (observed in practice from the Grounding
    Critic's multi-sentence "feedback" field) still failed to parse,
    silently degrading a genuine successful investigation into an "LLM
    error" and forcing a fallback path.

    This function instead walks the raw text character-by-character,
    tracking whether we are currently inside a JSON string literal (i.e.
    between an opening and closing unescaped double-quote), and only
    escapes control characters (newline, carriage return, tab) when they
    occur INSIDE a string -- structural whitespace between JSON tokens is
    left untouched. This is a targeted repair of genuinely malformed input,
    not a semantic change to well-formed JSON.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    out = []
    in_string = False
    escaped = False
    for ch in content:
        if in_string:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                in_string = False
                out.append(ch)
                continue
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                out.append("\\r")
                continue
            if ch == "\t":
                out.append("\\t")
                continue
            out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)

    sanitized = "".join(out)
    return json.loads(sanitized)


class BaseAgent:
    def __init__(self, agent_name: str, system_prompt: str, model: str):
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.model = model
        # NVIDIA_API_KEY must be provided via environment/.env — no hardcoded fallback key.
        api_key = os.environ.get('NVIDIA_API_KEY')
        if not api_key:
            print(f"WARNING [{agent_name}]: NVIDIA_API_KEY is not set. LLM calls will fail.")
        self.client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key or "unset"
        )
        
    async def call_llm_json(self, prompt: str) -> Dict[str, Any]:
        """Calls NVIDIA Nemotron asynchronously and extracts JSON response."""
        try:
            print(f"[{self.agent_name}] Calling LLM...")
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Keep low for strict JSON adherence
                top_p=0.95,
                max_tokens=16384,
                extra_body={
                    "chat_template_kwargs": {"enable_thinking": True},
                    "reasoning_budget": 16384
                },
                stream=True
            )
            
            full_content = ""
            async for chunk in completion:
                if not chunk.choices:
                    continue
                reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
                if reasoning:
                    print(reasoning, end="", flush=True)
                if chunk.choices[0].delta.content is not None:
                    print(chunk.choices[0].delta.content, end="", flush=True)
                    full_content += chunk.choices[0].delta.content
            
            print(f"\n[{self.agent_name}] LLM Call Complete.")
            
            content = full_content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            try:
                return _sanitize_and_parse_json(content)
            except Exception as parse_e:
                return {"error": f"{str(parse_e)}. Content might be truncated."}
                
        except Exception as e:
            print(f"{self.agent_name} LLM Error: {e}")
            return {"error": str(e)}

    async def call_llm_with_tools(self, prompt: str, tools: list, execute_tool_fn, max_iterations: int = 5) -> Dict[str, Any]:
        """
        Calls LLM iteratively. If LLM wants to call a tool, calls execute_tool_fn.

        `max_iterations` bounds the number of LLM round-trips (each round-trip may
        include multiple tool calls in one response). The previous hardcoded
        value of 5 was too low for agents whose system prompts (e.g. RCAAgent
        in LocalStack-lab mode) legitimately instruct them to call several
        distinct real-infrastructure tools (query_cloudwatch_logs, list_s3_objects,
        read_s3_object, describe_lambda_invocation, check_table_staleness,
        list_recent_changes, ...) plus a final answer turn -- guaranteeing the
        cap was hit on any sufficiently thorough investigation and silently
        degrading every such agent to an "exceeded max iterations" error
        (observed in practice: RCA and Runbook agents both failed this way on
        a real LocalStack partial-write incident, forcing the Grounding Critic
        to fall back to synthesizing its own substitute plan). Callers that
        genuinely need more tool calls should pass a higher explicit value
        rather than relying on this default.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            iteration_count = 0
            while iteration_count < max_iterations:
                iteration_count += 1
                print(f"[{self.agent_name}] Calling LLM with {len(tools)} tools... (Iter {iteration_count}/{max_iterations})")
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    temperature=0.1,
                    top_p=0.95,
                    max_tokens=4096,
                )
                
                choice = completion.choices[0]
                message = choice.message
                
                if getattr(message, 'tool_calls', None):
                    # Nemotron Python SDK creates objects for message so we convert to dict for appending to messages
                    tool_calls_dict = []
                    for t in message.tool_calls:
                        tool_calls_dict.append({
                            "id": t.id,
                            "type": "function",
                            "function": {
                                "name": t.function.name,
                                "arguments": t.function.arguments
                            }
                        })
                    
                    messages.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": tool_calls_dict
                    })
                    
                    for tool_call in message.tool_calls:
                        print(f"[{self.agent_name}] Executing tool: {tool_call.function.name}")
                        result = await execute_tool_fn(tool_call.function.name, tool_call.function.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result)
                        })
                else:
                    # LLM finished
                    print(f"\n[{self.agent_name}] LLM Tool Execution Complete.")
                    content = (message.content or "").strip()
                    
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                        
                    try:
                        return _sanitize_and_parse_json(content)
                    except Exception as parse_e:
                        return {"error": f"{str(parse_e)}. Content might be truncated."}

            # Previously, exhausting max_iterations meant discarding ALL the
            # real tool-call evidence gathered up to this point (every
            # query_logs/query_cloudwatch_logs/check_table_staleness/etc.
            # result already sitting in `messages`) and returning a bare
            # `{"error": ...}` -- observed in practice on a real LocalStack
            # partial-write incident, where the Grounding Critic worked
            # through many read-only verification tools right up against its
            # budget, then had its entire independent-verification effort
            # thrown away, forcing run_critic() to fall back to synthesizing
            # a substitute plan with NO safety critique at all (exactly the
            # WP-003 Stage 6 gate this agent exists to provide). Instead,
            # make one final forced answer-only turn (tools removed from the
            # request so the model cannot request yet another tool call and
            # re-trigger the same loop) so the agent must synthesize its
            # final JSON answer from the evidence it already collected,
            # rather than losing that work entirely.
            print(f"[{self.agent_name}] Iteration budget ({max_iterations}) reached; forcing a final answer-only turn using evidence already gathered.")
            messages.append({
                "role": "user",
                "content": (
                    f"You have reached your tool-call budget ({max_iterations} iterations). "
                    "Do not request any further tool calls. Based ONLY on the evidence you have "
                    "already gathered above, return your final JSON answer now, in the exact "
                    "format specified in your instructions."
                ),
            })
            try:
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    top_p=0.95,
                    max_tokens=4096,
                )
                content = (completion.choices[0].message.content or "").strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                return _sanitize_and_parse_json(content)
            except Exception as forced_answer_e:
                # Even the forced final turn failed (LLM error or still-unparseable
                # JSON) -- fall back to the original explicit error, now annotated
                # so it's clear a recovery attempt was made rather than looking
                # like the loop was never bounded at all.
                return {
                    "error": (
                        f"LLM exceeded maximum allowed tool iterations ({max_iterations}), "
                        f"and the forced final answer attempt also failed: {forced_answer_e}"
                    )
                }

        except Exception as e:
            print(f"{self.agent_name} LLM Error: {e}")
            return {"error": str(e)}
