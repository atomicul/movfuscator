from typing import Iterable, List, Set, Optional, Iterator, Union

from symbolsresolver import (
    parse_cfg,
    Allocator,
    Function as CfgFunction,
    BasicBlock,
    EdgeType,
    Expression,
    MemoryOperand,
    Instruction,
)
from .models import Function, Label


def get_linearized_asm(
    asm: str, allocator: Allocator, data_label: str
) -> List[Function]:
    """
    Parses the assembly into a CFG (resolving symbols), then flattens it
    back into a linear list of instructions and labels.
    """
    cfg_functions = parse_cfg(asm, allocator, data_label)

    return [linearize_function(func) for func in cfg_functions]


def linearize_function(cfg_func: CfgFunction) -> Function:
    """
    Flattens a CFG into a linear sequence, injecting jumps for broken fall-throughs.
    """
    blocks = list(discover_blocks(cfg_func.entry_block))

    linear_stream = [
        instr
        for i, block in enumerate(blocks)
        for instr in generate_block_content(
            block, blocks[i + 1].name if i + 1 < len(blocks) else None
        )
    ]

    return Function(name=cfg_func.name, instructions=linear_stream)


def generate_block_content(
    block: BasicBlock, physical_next_name: Optional[str]
) -> Iterator[Union[Instruction, Label]]:
    """
    Yields the label, original instructions, and any necessary connector jumps
    for a single block.
    """
    yield Label(block.name)

    if block.instructions:
        yield from block.instructions

    logical_fallthrough = get_fallthrough_successor(block)

    if (
        logical_fallthrough
        and logical_fallthrough.name != physical_next_name
        and not ends_unconditionally(block)
    ):
        jmp_op = MemoryOperand(displacement=Expression(logical_fallthrough.name))
        yield Instruction("jmp", [jmp_op])


def discover_blocks(
    block: BasicBlock, *, visitors: Optional[Set[int]] = None
) -> Iterable[BasicBlock]:
    """
    Recursive DFS traversal to find all reachable blocks.
    Tracks visited blocks by ID to handle cycles.
    """
    if visitors is None:
        visitors = set()

    if id(block) in visitors:
        return

    visitors.add(id(block))

    yield block

    for succ, _ in block.successors:
        yield from discover_blocks(succ, visitors=visitors)


def get_fallthrough_successor(block: BasicBlock) -> Optional[BasicBlock]:
    """Returns the block reached if a conditional jump is NOT taken."""
    return next(
        (
            succ
            for succ, edge_type in block.successors
            if edge_type in (EdgeType.NOT_TAKEN, EdgeType.DIRECT)
        ),
        None,
    )


def ends_unconditionally(block: BasicBlock) -> bool:
    """Returns True if the block ends with ret, jmp, etc."""
    if not block.instructions:
        return False

    last = block.instructions[-1].mnemonic.lower()
    return last in ["jmp", "ret", "iret", "syscall"]
