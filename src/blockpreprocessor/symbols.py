from typing import List, Dict
from textparser import (
    Function,
    Instruction,
    Operand,
    ImmediateOperand,
    MemoryOperand,
    Expression,
)
from .utils import iter_all_instructions


def resolve_symbols(
    functions: List[Function], symbol_offsets: Dict[str, int], data_label: str
):
    """
    Mutates the instructions in place, replacing symbolic references
    with their calculated memory offsets relative to the data_label.
    """
    for instruction in iter_all_instructions(functions):
        resolve_instruction(instruction, symbol_offsets, data_label)


def resolve_instruction(instr: Instruction, offsets: Dict[str, int], data_label: str):
    instr.operands = [resolve_operand(op, offsets, data_label) for op in instr.operands]


def resolve_operand(op: Operand, offsets: Dict[str, int], data_label: str) -> Operand:
    match op:
        case ImmediateOperand(expr):
            return ImmediateOperand(resolve_expression(expr, offsets, data_label))
        case MemoryOperand(base, index, scale, disp):
            return MemoryOperand(
                base, index, scale, resolve_expression(disp, offsets, data_label)
            )
        case _:
            return op


def resolve_expression(
    expr: Expression, offsets: Dict[str, int], data_label: str
) -> Expression:
    result = Expression(expr)

    # Find symbols in the expression that exist in our data map
    targets = [s for s in result.symbols if s in offsets]

    for sym in targets:
        offset = offsets[sym]
        # Replace 'Sym' with 'GlobalBase + Offset'
        replacement = Expression(data_label) + offset
        result.substitute_term(sym, replacement)

    return result
