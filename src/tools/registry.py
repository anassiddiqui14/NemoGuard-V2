from pydantic import BaseModel, ValidationError
from typing import Dict, Type, Callable, Any
from dataclasses import dataclass

from src.domain.enums import ToolRisk

class ToolExecutionError(Exception):
    pass

class PolicyViolationError(Exception):
    pass

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    risk: ToolRisk
    timeout_seconds: int
    requires_approval: bool
    handler: Callable[..., Any]

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool {definition.name} already registered.")
        self._tools[definition.name] = definition

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise ValueError(f"Tool {name} not found.")
        return self._tools[name]

    def execute_tool(self, name: str, arguments_dict: Dict[str, Any], caller_role: str = "agent", is_approved: bool = False) -> Any:
        """
        Executes a tool with strict policy enforcement.
        1. Validate tool exists
        2. Enforce risk policy and approval
        3. Validate input schema
        4. Execute handler
        5. Return result
        """
        tool = self.get_tool(name)
        
        # Policy Enforcement
        if tool.risk in (ToolRisk.HIGH, ToolRisk.MEDIUM) and tool.requires_approval and not is_approved:
            raise PolicyViolationError(f"Tool {name} ({tool.risk.value}) requires explicit human approval.")
        
        if tool.risk == ToolRisk.PROHIBITED:
            raise PolicyViolationError(f"Tool {name} is prohibited in this environment.")
            
        # Input Validation
        try:
            validated_input = tool.input_model(**arguments_dict)
        except ValidationError as e:
            raise ToolExecutionError(f"Input validation failed for {name}: {e.errors()}")
            
        # Execute Handler
        try:
            result = tool.handler(validated_input)
            return result
        except Exception as e:
            raise ToolExecutionError(f"Handler execution failed for {name}: {str(e)}")
