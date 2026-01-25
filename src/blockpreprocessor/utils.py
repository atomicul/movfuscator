from typing import List, Set, Iterable
from itertools import chain
from textparser import (
    Function,
    Instruction,
    BasicBlock,
    DirectSuccessor,
    ConditionalSuccessor,
)


def iter_blocks(functions: List[Function]) -> Iterable[BasicBlock]:
    """
    Traverses the Control Flow Graph (CFG) of the provided functions
    and yields every unique BasicBlock exactly once.
    """
    visited: Set[int] = set()

    for func in functions:
        stack = [func.entry_block]

        while stack:
            block = stack.pop()
            if id(block) in visited:
                continue
            visited.add(id(block))

            yield block

            if block.successor:
                if isinstance(block.successor, DirectSuccessor):
                    stack.append(block.successor.block)
                elif isinstance(block.successor, ConditionalSuccessor):
                    stack.append(block.successor.true_block)
                    stack.append(block.successor.false_block)


def iter_all_instructions(functions: List[Function]) -> Iterable[Instruction]:
    """
    Helper to iterate over every single instruction across all provided functions.
    It abstracts away the hierarchy of Function -> BasicBlock -> Instruction.
    """
    return chain.from_iterable(block.instructions for block in iter_blocks(functions))
