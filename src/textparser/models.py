from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Literal, Union


class EdgeType(str, Enum):
    TAKEN = "taken"
    NOT_TAKEN = "not_taken"
    DIRECT = "direct"

    def __str__(self) -> str:
        return self.value


class Expression:
    """
    Represents assembler expressions
    Can contain symbols (labels, constants) and generally resolve to an integer
    """

    def __init__(self, expr: str):
        eval()
        pass

    def resolve_symbol(self, symbol: str, value: int):
        """Set a value for a symbol"""
        pass

    def __add__(self, other: Union[Expression, str]) -> Expression:
        """Adds two expressions together or an expression and a symbol"""
        # remember to validate the symbol not to contain itself an expression
        # raise a value error in that case
        pass

    # same thing for all arithmetic operators
    def __radd__(self, other: Union[Expression, str]) -> Expression:
        pass

    def __sub__(self, other: Union[Expression, str]) -> Expression:
        pass

    def __mul__(self, other: Union[Expression, str]) -> Expression:
        pass

    def __div__(self, other: Union[Expression, str]) -> Expression:
        pass

    def __str__(self) -> str:
        """
        Prints the expression in its simplest form
        (resolves known symbols and performs arithmetic
        """
        pass


class RegisterOperand(Enum):
    # --- 32-bit General Purpose ---
    EAX = "%eax"
    EBX = "%ebx"
    ECX = "%ecx"
    EDX = "%edx"
    ESI = "%esi"
    EDI = "%edi"
    EBP = "%ebp"
    ESP = "%esp"

    # --- 16-bit (Lower half of 32-bit) ---
    AX = "%ax"
    BX = "%bx"
    CX = "%cx"
    DX = "%dx"
    SI = "%si"
    DI = "%di"
    BP = "%bp"
    SP = "%sp"

    # --- 8-bit Low (Lower byte of 16-bit) ---
    AL = "%al"
    BL = "%bl"
    CL = "%cl"
    DL = "%dl"

    # --- 8-bit High (Upper byte of 16-bit) ---
    AH = "%ah"
    BH = "%bh"
    CH = "%ch"
    DH = "%dh"

    def __str__(self) -> str:
        return self.value


@dataclass
class ImmediateOperand:
    value: Expression

    def __str__(self) -> str:
        # AT&T syntax requires immediate values to be prefixed with '$'
        return f"${self.value}"


@dataclass
class MemoryOperand:
    base: Optional[RegisterOperand] = None
    index: Optional[RegisterOperand] = None
    scale: Literal[1, 2, 4, 8] = 1
    displacement: Expression = Expression("0")

    def __str__(self) -> str:
        if self.displacement == 0 and (self.base is not None or self.index is not None):
            res = ""
        else:
            res = str(self.displacement)

        if self.base is not None or self.index is not None:
            res += "("

            if self.base is not None:
                res += str(self.base)

            if self.index is not None:
                res += f",{self.index}"

                if self.scale != 1:
                    res += f",{self.scale}"

            res += ")"

        return res


Operand = Union[MemoryOperand, RegisterOperand, ImmediateOperand]


@dataclass
class Instruction:
    mnemonic: str
    operands: List[Operand] = field(default_factory=list)
    line_number: int = 0

    def __str__(self):
        ops = ", ".join(str(x) for x in self.operands)
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
