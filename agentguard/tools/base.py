"""Tool interface shared by all five tools."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ToolResult:
    text: str
    # False when the text can contain content written by someone other than the user (pages,
    # inbox messages, calendar titles, database rows). The taint guardrail (G3) uses this.
    trusted: bool = True
    error: bool = False


@dataclass
class Tool:
    name: str
    description: str  # shown to the model, includes the argument names
    run: Callable[[dict], ToolResult]
    # Tools that change the world. Guardrails treat calls to these more strictly.
    sensitive: bool = False
