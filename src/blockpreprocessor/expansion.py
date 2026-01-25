from typing import List
from itertools import chain

from textparser import (
    Function,
    Instruction,
    RegisterOperand,
    ImmediateOperand,
    MemoryOperand,
    Expression,
    Operand,
)
from .utils import iter_blocks

ESP = RegisterOperand.ESP
EAX = RegisterOperand.EAX
EBX = RegisterOperand.EBX


def expand_stack_ops(functions: List[Function], scratch_offset: int, data_label: str):
    """
    Scans all basic blocks and replaces explicit push/pop instructions.
    Uses scratch_offset to safely handle Memory-to-Memory moves.
    """

    for block in iter_blocks(functions):
        block.instructions = list(
            chain.from_iterable(
                expand_instruction(i, scratch_offset, data_label)
                for i in block.instructions
            )
        )


def expand_instruction(
    instr: Instruction, scratch_offset: int, data_label: str
) -> List[Instruction]:
    match instr.mnemonic:
        case "pushl":
            return expand_push(instr, scratch_offset, data_label)
        case "popl":
            return expand_pop(instr, scratch_offset, data_label)
        case _:
            return [instr]


def get_safe_scratch(op: Operand) -> RegisterOperand:
    """Returns EBX if operand uses EAX, else returns EAX."""
    if isinstance(op, MemoryOperand):
        used = {op.base, op.index}
        if EAX in used:
            return EBX
    return EAX


def scratch_op(
    reg: RegisterOperand, offset: int, data_label: str, is_load: bool
) -> Instruction:
    """Helper to generate load/save for scratch register."""
    mem = MemoryOperand(displacement=Expression(data_label) + offset)
    if is_load:
        return Instruction("movl", [mem, reg])
    return Instruction("movl", [reg, mem])


def expand_push(
    instr: Instruction, scratch_offset: int, data_label: str
) -> List[Instruction]:
    """push %src -> sub $4, %esp; mov %src, (%esp)"""
    src = instr.operands[0]

    # Special Case: push %esp (pushes value BEFORE decrement)
    if isinstance(src, RegisterOperand) and src == ESP:
        return [
            Instruction(
                "movl", [ESP, MemoryOperand(base=ESP, displacement=Expression(-4))]
            ),
            Instruction("subl", [ImmediateOperand(Expression(4)), ESP]),
        ]

    # Standard Case: Register or Immediate
    if not isinstance(src, MemoryOperand):
        return [
            Instruction("subl", [ImmediateOperand(Expression(4)), ESP]),
            Instruction("movl", [src, MemoryOperand(base=ESP)]),
        ]

    # Edge Case: Memory Operand (Requires Scratch)
    tmp = get_safe_scratch(src)
    return [
        scratch_op(tmp, scratch_offset, data_label, is_load=False),
        Instruction("movl", [src, tmp]),
        Instruction("subl", [ImmediateOperand(Expression(4)), ESP]),
        Instruction("movl", [tmp, MemoryOperand(base=ESP)]),
        scratch_op(tmp, scratch_offset, data_label, is_load=True),
    ]


def expand_pop(
    instr: Instruction, scratch_offset: int, data_label: str
) -> List[Instruction]:
    """pop %dst -> mov (%esp), %dst; add $4, %esp"""
    dst = instr.operands[0]

    # Special Case: pop %esp
    if isinstance(dst, RegisterOperand) and dst == ESP:
        return [Instruction("movl", [MemoryOperand(base=ESP), ESP])]

    # Standard Case: Register
    if not isinstance(dst, MemoryOperand):
        return [
            Instruction("movl", [MemoryOperand(base=ESP), dst]),
            Instruction("addl", [ImmediateOperand(Expression(4)), ESP]),
        ]

    # Edge Case: Memory Operand (Requires Scratch)
    tmp = get_safe_scratch(dst)
    return [
        scratch_op(tmp, scratch_offset, data_label, is_load=False),
        Instruction("movl", [MemoryOperand(base=ESP), tmp]),
        Instruction("addl", [ImmediateOperand(Expression(4)), ESP]),
        Instruction("movl", [tmp, dst]),
        scratch_op(tmp, scratch_offset, data_label, is_load=True),
    ]
