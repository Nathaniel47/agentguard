from agentguard.config import Config
from agentguard.guardrails.base import Guardrail
from agentguard.guardrails.input_screen import InputScreen
from agentguard.guardrails.memory_gate import MemoryGate
from agentguard.guardrails.output_filter import OutputFilter
from agentguard.guardrails.taint import TaintGuard
from agentguard.guardrails.tool_policy import ToolPolicy

REGISTRY: dict[str, type[Guardrail]] = {
    "g1_input_screen": InputScreen,
    "g2_tool_policy": ToolPolicy,
    "g3_taint": TaintGuard,
    "g4_memory_gate": MemoryGate,
    "g5_output_filter": OutputFilter,
}


def build_guardrails(config: Config) -> list[Guardrail]:
    """The enabled guardrails, in pipeline order G1 to G5."""
    return [cls() for name, cls in REGISTRY.items() if config.enabled(name)]
