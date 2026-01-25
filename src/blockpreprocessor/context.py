from typing import List, Set, Dict

from dataparser import Allocator
from textparser import (
    Function,
    Instruction,
    RegisterOperand,
    MemoryOperand,
    Expression,
    BasicBlock,
)
from .utils import iter_blocks

TRACKED_REGISTERS = [
    RegisterOperand.EAX,
    RegisterOperand.EBX,
    RegisterOperand.ECX,
    RegisterOperand.EDX,
    RegisterOperand.ESI,
    RegisterOperand.EDI,
    RegisterOperand.EBP,
    RegisterOperand.ESP,
]


def inject_context_switching(
    functions: List[Function], allocator: Allocator, data_label: str
):
    """
    Virtualizes registers by enforcing a Load-Execute-Save lifecycle for every block.
    """
    reg_offsets = allocate_virtual_registers(allocator)

    for block in iter_blocks(functions):
        instrument_block(block, reg_offsets, data_label)


def allocate_virtual_registers(allocator: Allocator) -> Dict[RegisterOperand, int]:
    """
    Allocates 4 bytes in the global data section for each tracked 32-bit register.
    Returns a map of {Register: Offset}.
    """
    offsets = {}
    for reg in TRACKED_REGISTERS:
        name = f"{reg.name}"
        alloc = allocator.allocate_data(0, name)
        offsets[reg] = alloc.offset
    return offsets


def instrument_block(
    block: BasicBlock, reg_offsets: Dict[RegisterOperand, int], data_label: str
):
    """
    Detects used registers, then wraps the block's instructions with
    context load (prologue) and save (epilogue) operations.
    """
    used_regs = get_used_registers(block.instructions)

    if not used_regs:
        return

    sorted_regs = sorted(used_regs, key=lambda r: r.value)

    prologue = [create_load(reg, reg_offsets[reg], data_label) for reg in sorted_regs]

    epilogue = [create_save(reg, reg_offsets[reg], data_label) for reg in sorted_regs]

    block.instructions = prologue + block.instructions + epilogue


def get_used_registers(instructions: List[Instruction]) -> Set[RegisterOperand]:
    """
    Scans operands to find dependencies. Maps partial registers (AL, AX)
    to their 32-bit parents (EAX).

    Also handles implicit register usage for arithmetic instructions
    like mul, div, cdq, etc.
    """
    used = set()

    for instr in instructions:
        for op in instr.operands:
            match op:
                case RegisterOperand():
                    used.add(op.get_32bit_counterpart())

                case MemoryOperand(base=b, index=i):
                    if b:
                        used.add(b.get_32bit_counterpart())
                    if i:
                        used.add(i.get_32bit_counterpart())

        used |= get_implicit_registers(instr)

    return {r for r in used if r in TRACKED_REGISTERS}


def get_implicit_registers(instr: Instruction) -> Set[RegisterOperand]:
    """
    Returns the set of registers implicitly used or modified by a specific instruction.
    Examples:
      - mul/div implicitly use EAX and EDX.
      - cdq/cwd implicitly use EAX and EDX.
      - imul (1-operand form) implicitly uses EAX and EDX.
    """
    implicit = set()
    mnem = instr.mnemonic.lower()

    # Instructions that always use EAX + EDX (e.g. mul, div, cdq)
    # We check startswith to handle suffixes like mull, mulw, etc.
    # Note: 'imul' is handled separately because of its multi-operand forms.
    implicit_map = {
        "mul": [RegisterOperand.EAX, RegisterOperand.EDX],
        "div": [RegisterOperand.EAX, RegisterOperand.EDX],
        "idiv": [RegisterOperand.EAX, RegisterOperand.EDX],
        "cdq": [RegisterOperand.EAX, RegisterOperand.EDX],
        "cwd": [
            RegisterOperand.EAX,
            RegisterOperand.EDX,
        ],  # cwd: ax->dx:ax (mapped to 32-bit parent)
        "cbw": [RegisterOperand.EAX],  # cbw: al->ax (mapped to EAX)
        "cwde": [RegisterOperand.EAX],
    }

    for key, regs in implicit_map.items():
        if mnem.startswith(key):
            for r in regs:
                implicit.add(r.get_32bit_counterpart())
            return implicit

    # Special Case: imul
    # imul can take 1, 2, or 3 operands. Only the 1-operand form implicitly uses EDX:EAX.
    if mnem.startswith("imul"):
        if len(instr.operands) == 1:
            implicit.add(RegisterOperand.EAX)
            implicit.add(RegisterOperand.EDX)

    return implicit


def create_load(reg: RegisterOperand, offset: int, data_label: str) -> Instruction:
    """Generates: movl __GLOBAL_MEM + offset, %reg"""
    src = MemoryOperand(displacement=Expression(data_label) + offset)
    return Instruction("movl", [src, reg])


def create_save(reg: RegisterOperand, offset: int, data_label: str) -> Instruction:
    """Generates: movl %reg, __GLOBAL_MEM + offset"""
    dst = MemoryOperand(displacement=Expression(data_label) + offset)
    return Instruction("movl", [reg, dst])
