from dataclasses import dataclass
from typing import Optional


@dataclass
class Allocation:
    """Public read-only details about an allocation."""

    offset: int
    size: int


@dataclass
class AllocationDetails:
    """Internal representation of a memory block."""

    name: str
    offset: int
    size: int
    initial_value_str: Optional[str] = None
    # The asm directive (e.g. ".int", ".asciz", ".zero")
    directive: str = ".zero"
