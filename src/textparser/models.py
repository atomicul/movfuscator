from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Literal, Union, Tuple
from .expression import Expression


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


class JumpCondition(str, Enum):
    """
    Represents the canonical condition code for a branch.
    Opposite conditions (e.g., JNE) are represented by JE
    with the true/false blocks swapped.
    """

    JE = "je"  # Equal (Z=1). Covers: je, jz. (Opposites: jne, jnz)
    JL = "jl"  # Less (SF!=OF). Covers: jl, jnge. (Opposites: jge, jnl)
    JG = "jg"  # Greater (Z=0 & SF=OF). Covers: jg, jnle. (Opposites: jle, jng)
    JB = "jb"  # Below (C=1). Covers: jb, jnae, jc. (Opposites: jae, jnb, jnc)
    JA = "ja"  # Above (C=0 & Z=0). Covers: ja, jnbe. (Opposites: jbe, jna)

    @classmethod
    def from_mnemonic(cls, mnemonic: str) -> Tuple["JumpCondition", bool]:
        """
        Parses a jump mnemonic into a canonical JumpCondition and a swap flag.

        Returns:
            (JumpCondition, swap_branches):
            If swap_branches is True, the instruction is an inverted jump (e.g. JNE),
            meaning the 'Taken' path corresponds to the 'False' logical state of the
            canonical condition (JE).

        Raises:
            ValueError: If the mnemonic is not a recognized conditional jump.
        """
        m = mnemonic.lower()

        if m in ["je", "jz"]:
            return cls.JE, False
        if m in ["jne", "jnz"]:
            return cls.JE, True

        if m in ["jl", "jnge"]:
            return cls.JL, False
        if m in ["jge", "jnl"]:
            return cls.JL, True

        if m in ["jg", "jnle"]:
            return cls.JG, False
        if m in ["jle", "jng"]:
            return cls.JG, True

        if m in ["jb", "jnae", "jc"]:
            return cls.JB, False
        if m in ["jae", "jnb", "jnc"]:
            return cls.JB, True

        if m in ["ja", "jnbe"]:
            return cls.JA, False
        if m in ["jbe", "jna"]:
            return cls.JA, True

        raise ValueError(
            f"Unknown or unsupported conditional jump mnemonic: {mnemonic}"
        )


@dataclass
class ImmediateOperand:
    value: Expression

    def __str__(self) -> str:
        return f"$({self.value})"


@dataclass
class MemoryOperand:
    base: Optional[RegisterOperand] = None
    index: Optional[RegisterOperand] = None
    scale: Literal[1, 2, 4, 8] = 1
    displacement: Expression = field(default_factory=lambda: Expression("0"))

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
class DirectSuccessor:
    block: "BasicBlock"


@dataclass
class ConditionalSuccessor:
    true_block: "BasicBlock"
    false_block: "BasicBlock"
    condition: JumpCondition


@dataclass
class BasicBlock:
    name: str
    instructions: List[Instruction] = field(default_factory=list)
    successor: Optional[Union[DirectSuccessor, ConditionalSuccessor]] = None


@dataclass
class Function:
    name: str
    entry_block: BasicBlock
