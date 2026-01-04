from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple


class EdgeType(str, Enum):
    TAKEN = "taken"
    NOT_TAKEN = "not_taken"
    DIRECT = "direct"

    def __str__(self) -> str:
        return self.value


@dataclass
class Instruction:
    mnemonic: str
    operands: List[str] = field(default_factory=list)
    line_number: int = 0

    def __str__(self):
        ops = ", ".join(self.operands)
        return f"{self.mnemonic} {ops}" if ops else self.mnemonic


@dataclass
class BasicBlock:
    name: str
    instructions: List[Instruction] = field(default_factory=list)
    successors: List[Tuple["BasicBlock", EdgeType]] = field(default_factory=list)


@dataclass
class Function:
    name: str
    entry_block: BasicBlock
