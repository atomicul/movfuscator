from typing import List, Iterator, Set
from itertools import chain

from textparser import (
    Function,
    BasicBlock,
    Instruction,
    RegisterOperand,
    ImmediateOperand,
    MemoryOperand,
    Expression,
    DirectSuccessor,
    ConditionalSuccessor,
)

ESP = RegisterOperand.ESP


def expand_stack_ops(functions: List[Function]):
    """
    Scans all basic blocks and replaces explicit push/pop instructions
    with equivalent sequences of MOV, ADD, and SUB.
    """
    all_blocks = chain.from_iterable(iter_blocks(f) for f in functions)

    for block in all_blocks:
        block.instructions = list(
            chain.from_iterable(expand_instruction(i) for i in block.instructions)
        )


def iter_blocks(func: Function) -> Iterator[BasicBlock]:
    """
    Generator that traverses the CFG and yields every unique BasicBlock.
    Eliminates the need for deep nesting or manual recursion in the main logic.
    """
    visited: Set[int] = set()
    stack: List[BasicBlock] = [func.entry_block]

    while stack:
        block = stack.pop()
        if id(block) in visited:
            continue
        visited.add(id(block))

        yield block

        if block.successor:
            match block.successor:
                case DirectSuccessor(next_blk):
                    stack.append(next_blk)
                case ConditionalSuccessor(true_blk, false_blk, _):
                    stack.append(true_blk)
                    stack.append(false_blk)


def expand_instruction(instr: Instruction) -> List[Instruction]:
    """
    Maps a single instruction to a list of instructions (1-to-N expansion).
    """
    match instr.mnemonic:
        case "pushl":
            return expand_push(instr)
        case "popl":
            return expand_pop(instr)
        case _:
            return [instr]


def expand_push(instr: Instruction) -> List[Instruction]:
    """push %src  ->  sub $4, %esp; mov %src, (%esp)"""
    src = instr.operands[0]

    # Special Case: push %esp
    # Pushes the *old* value of ESP (value before decrement).
    # Implementation: movl %esp, -4(%esp) -> subl $4, %esp
    if isinstance(src, RegisterOperand) and src == ESP:
        return [
            Instruction(
                "movl", [ESP, MemoryOperand(base=ESP, displacement=Expression(-4))]
            ),
            Instruction("subl", [ImmediateOperand(Expression(4)), ESP]),
        ]

    return [
        Instruction("subl", [ImmediateOperand(Expression(4)), ESP]),
        Instruction("movl", [src, MemoryOperand(base=ESP)]),
    ]


def expand_pop(instr: Instruction) -> List[Instruction]:
    """pop %dst   ->  mov (%esp), %dst; add $4, %esp"""
    dst = instr.operands[0]

    # Special Case: pop %esp
    # Loads the stack pointer *from* the stack.
    # The standard increment (ESP + 4) is skipped/overwritten by the load.
    if isinstance(dst, RegisterOperand) and dst == ESP:
        return [
            Instruction("movl", [MemoryOperand(base=ESP), ESP]),
        ]

    return [
        Instruction("movl", [MemoryOperand(base=ESP), dst]),
        Instruction("addl", [ImmediateOperand(Expression(4)), ESP]),
    ]
