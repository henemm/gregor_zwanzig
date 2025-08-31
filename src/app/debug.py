from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

@dataclass
class DebugBuffer:
    """
    Sammeln und Rendern von Debug-Informationen für Console & E-Mail.
    Console kann mehr zeigen, E-Mail nutzt ein definiertes Subset.
    """
    lines: List[str] = field(default_factory=list)

    def add(self, line: str) -> None:
        self.lines.append(line)

    def extend(self, items: List[str]) -> None:
        self.lines.extend(items)

    def as_text(self) -> str:
        return "\n".join(self.lines)

    def email_subset(self) -> str:
        return "\n".join(self.lines)
