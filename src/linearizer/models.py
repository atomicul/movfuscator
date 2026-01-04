from dataclasses import dataclass
from symbolsresolver import Instruction
from typing import List, Union


class Label(str):
    pass


@dataclass
class Function:
    name: str
    instructions: List[Union[Instruction, Label]]
