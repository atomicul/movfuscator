from dataclasses import dataclass, field
from typing import Dict, List
from textparser import Instruction, BasicBlock, RegisterOperand


@dataclass
class Function:
    name: str
    entry_block: BasicBlock
    prologue: List[Instruction]
    reg_offsets: Dict[RegisterOperand, int] = field(default_factory=dict)
