from typing import Iterable, List, Dict, Optional, Set, Union, assert_never
from itertools import chain
from dataparser import Allocator, parse_data
from textparser import (
    Function,
    BasicBlock,
    Instruction,
    Operand,
    ImmediateOperand,
    MemoryOperand,
    Expression,
    DirectSuccessor,
    ConditionalSuccessor,
)
from textparser import parse_cfg as parse_text_cfg


def parse_cfg(asm: str, allocator: Allocator, data_label: str) -> List[Function]:
    """
    Parses the Control Flow Graph from the asm file, replacing the variables
    with offsets into the global memory label.
    Also registers the variables with an `Allocator`.

    Args:
        asm: The assembly source code.
        allocator: The memory allocator to register data variables with.

    Returns:
        A list of Function objects with all variable references resolved
        to 'MasterLabel + Offset'.
    """
    data_map = parse_data(allocator, asm)

    label_offsets: Dict[str, int] = dict(
        (name, allocations[0].offset) for name, allocations in data_map.items()
    )

    functions = parse_text_cfg(asm)

    for instruction in chain(*map(lambda func: instructions(func), functions)):
        resolve_instruction(instruction, label_offsets, data_label)

    return functions


def instructions(
    func: Union[Function, BasicBlock], *, visited: Optional[Set[int]] = None
) -> Iterable[Instruction]:
    if visited is None:
        visited = set()

    if isinstance(func, Function):
        yield from instructions(func.entry_block, visited=visited)
        return

    if id(func) in visited:
        return

    visited.add(id(func))

    yield from func.instructions

    if func.successor is None:
        return

    match func.successor:
        case DirectSuccessor(next_blk):
            yield from instructions(next_blk, visited=visited)
        case ConditionalSuccessor(true_blk, false_blk, _):
            yield from instructions(true_blk, visited=visited)
            yield from instructions(false_blk, visited=visited)
        case x:
            assert_never(x)


def resolve_instruction(
    instr: Instruction, label_offsets: Dict[str, int], data_label: str
):
    """
    Updates an instruction's operands by resolving symbols to offsets.
    Mutates the instruction in place.
    """
    instr.operands = [
        resolve_operand(op, label_offsets, data_label) for op in instr.operands
    ]


def resolve_operand(
    op: Operand, label_offsets: Dict[str, int], data_label: str
) -> Operand:
    """
    Returns a new Operand with expressions resolved.
    """
    match op:
        case ImmediateOperand(expr):
            return ImmediateOperand(resolve_expression(expr, label_offsets, data_label))

        case MemoryOperand(base, index, scale, disp):
            return MemoryOperand(
                base, index, scale, resolve_expression(disp, label_offsets, data_label)
            )

        case op:
            return op


def resolve_expression(
    expr: Expression, label_offsets: Dict[str, int], data_label: str
) -> Expression:
    """
    Algebraically substitutes symbols in the expression.

    Transformation:
        Symbol -> (MasterLabel + Offset)

    Example:
        If 'counter' is at offset 4 and MasterLabel is '__MEM':
        Expression("counter") -> Expression("__MEM") + 4
    """
    result = Expression(expr)

    symbols_to_resolve = [s for s in result.symbols if s in label_offsets]

    for sym in symbols_to_resolve:
        offset = label_offsets[sym]

        result.substitute_term(sym, Expression(data_label) + offset)

    return result
