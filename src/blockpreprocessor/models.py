from dataclasses import dataclass
from typing import List
from textparser import Instruction, BasicBlock


@dataclass
class Function:
    name: str
    entry_block: BasicBlock
    prologue: List[Instruction]
