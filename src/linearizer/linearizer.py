from typing import Iterable, List, Set, Optional, Iterator, Union, assert_never

from blockpreprocessor import (
    preprocess_cfg,
    Allocator,
    Function as CfgFunction,
    BasicBlock,
    Expression,
    MemoryOperand,
    Instruction,
    DirectSuccessor,
    ConditionalSuccessor,
)
from .models import Function, Label


def get_linearized_asm(
    asm: str, allocator: Allocator, data_label: str
) -> List[Function]:
    """
    Parses the assembly into a CFG (resolving symbols), then flattens it
    back into a linear list of instructions and labels.
    """
    cfg_functions = preprocess_cfg(asm, allocator, data_label)

    return [linearize_function(func) for func in cfg_functions]


def linearize_function(cfg_func: CfgFunction) -> Function:
    """
    Flattens a CFG into a linear sequence, injecting jumps for broken fall-throughs.
    """
    blocks = list(discover_blocks(cfg_func.entry_block))

    linear_stream = [Label(cfg_func.name)] + cfg_func.prologue

    linear_stream += [
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

    # TextParser moves the conditional jump OUT of the instruction list
    # and into the ConditionalSuccessor. We must restore it here to maintain
    # valid assembly output.
    if isinstance(block.successor, ConditionalSuccessor):
        cond_succ = block.successor
        # Construct: j<cond> <true_block>
        # e.g., je target_label
        jmp_mnemonic = cond_succ.condition.value
        jmp_target = Expression(cond_succ.true_block.name)
        yield Instruction(jmp_mnemonic, [MemoryOperand(displacement=jmp_target)])

    logical_fallthrough = get_fallthrough_successor(block)

    # Inject unconditional jump if the logical fallthrough (False path or Direct)
    # does not match the block that physically follows in the list.
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

    if block.successor is None:
        return

    match block.successor:
        case DirectSuccessor(next_blk):
            yield from discover_blocks(next_blk, visitors=visitors)
        case ConditionalSuccessor(true_blk, false_blk, _):
            yield from discover_blocks(true_blk, visitors=visitors)
            yield from discover_blocks(false_blk, visitors=visitors)
        case x:
            assert_never(x)


def get_fallthrough_successor(block: BasicBlock) -> Optional[BasicBlock]:
    """
    Returns the block reached if the branch is NOT taken.
    For DirectSuccessor, this is the only target.
    For ConditionalSuccessor, this is the 'false' block.
    """
    match block.successor:
        case DirectSuccessor(next_blk):
            return next_blk
        case ConditionalSuccessor(_, false_blk, _):
            return false_blk
        case None:
            return None
        case x:
            assert_never(x)


def ends_unconditionally(block: BasicBlock) -> bool:
    """Returns True if the block ends with an EXPLICIT ret, jmp, etc."""
    if not block.instructions:
        return False

    last = block.instructions[-1].mnemonic.lower()
    return last in ["jmp", "ret", "iret", "syscall"]
