import os
import json
from typing import Dict, Any
from openai import AsyncOpenAI

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
                
            content = content.replace("\n", "\\n")
            content = content.replace("\\n", "\n")
            
            try:
                return json.loads(content)
            except Exception as parse_e:
                return {"error": f"{str(parse_e)}. Content might be truncated."}
                
        except Exception as e:
            print(f"{self.agent_name} LLM Error: {e}")
            return {"error": str(e)}

    async def call_llm_with_tools(self, prompt: str, tools: list, execute_tool_fn) -> Dict[str, Any]:
        """Calls LLM iteratively. If LLM wants to call a tool, calls execute_tool_fn."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            iteration_count = 0
            max_iterations = 5
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
                        
                    content = content.replace("\n", "\\n")
                    content = content.replace("\\n", "\n")
                    
                    try:
                        return json.loads(content)
                    except Exception as parse_e:
                        return {"error": f"{str(parse_e)}. Content might be truncated."}
            
            # If we exit the loop due to max_iterations
            return {"error": f"LLM exceeded maximum allowed tool iterations ({max_iterations})."}
                        
        except Exception as e:
            print(f"{self.agent_name} LLM Error: {e}")
            return {"error": str(e)}
