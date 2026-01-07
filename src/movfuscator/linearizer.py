from typing import List, Dict, assert_never
from collections import deque

from dataparser import parse_data
from memorymanager import MemoryManager
from textparser import (
    parse_cfg,
    Expression,
    BasicBlock,
    EdgeType,
    Function,
    ImmediateOperand,
    MemoryOperand,
    RegisterOperand,
    Operand,
)


def movfuscate(source_code: str) -> str:
    """
    Takes raw assembly, parses it, flattens the CFG of EACH function individually,
    and returns linearized assembly code.
    """
    mm = MemoryManager(master_label="__GLOBAL_MEMORY")

    data_map = parse_data(mm, source_code)

    label_offsets = {}
    for label, allocations in data_map.items():
        if allocations:
            label_offsets[label] = allocations[0].offset

    functions = parse_cfg(source_code)
    if not functions:
        return "; Error: No executable code found."

    linearized_code = []
    linearized_code.append(".text")

    for func in functions:
        state_var_name = f"__state_{func.name}"
        state_alloc = mm.allocate_data(0, state_var_name)

        state_var_expr = Expression(mm.master_label) + state_alloc.offset

        _flatten_function(
            func, linearized_code, state_var_expr, label_offsets, mm.master_label
        )

    data_asm = mm.generate_data_section()

    return data_asm + "\n\n" + "\n".join(linearized_code)


def _flatten_function(
    func: Function,
    lines: List[str],
    state_var_expr: Expression,
    label_offsets: Dict[str, int],
    master_label: str,
):
    """
    Flattens a single function into its own dispatch loop.
    """
    blocks = _discover_blocks(func.entry_block)
    block_map = {block.name: i for i, block in enumerate(blocks)}

    lines.append(f"\n.global {func.name}")
    lines.append(f"{func.name}:")

    entry_id = block_map[func.entry_block.name]

    lines.append(f"    movl ${entry_id}, {state_var_expr}")

    dispatch_label = f"__dispatch_{func.name}"
    lines.append(f"\n{dispatch_label}:")

    for block in blocks:
        block_id = block_map[block.name]
        block_label = f"__flat_{func.name}_{block.name}"

        lines.append(f"    cmpl ${block_id}, {state_var_expr}")
        lines.append(f"    je {block_label}")

    lines.append("    ret")

    for block in blocks:
        _generate_block_handler(
            block,
            func.name,
            block_map,
            lines,
            state_var_expr,
            dispatch_label,
            label_offsets,
            master_label,
        )


def _discover_blocks(entry: BasicBlock) -> List[BasicBlock]:
    """BFS traversal to find all reachable blocks."""
    visited = set()
    queue = deque([entry])
    blocks = []

    while queue:
        blk = queue.popleft()
        if blk.name in visited:
            continue
        visited.add(blk.name)
        blocks.append(blk)

        for succ, _ in blk.successors:
            if succ.name not in visited:
                queue.append(succ)

    blocks.sort(key=lambda b: b.name)
    return blocks


def _generate_block_handler(
    block: BasicBlock,
    func_name: str,
    block_map: Dict[str, int],
    lines: List[str],
    state_var_expr: Expression,
    dispatch_label: str,
    label_offsets: Dict[str, int],
    master_label: str,
):
    """
    Generates the code for a single block within a specific function.
    """
    lines.append(f"\n__flat_{func_name}_{block.name}:")

    last_instr = block.instructions[-1] if block.instructions else None

    for instr in block.instructions:
        if _is_control_flow(instr.mnemonic):
            continue

        new_operands = []
        for op in instr.operands:
            resolved_op_str = _resolve_operand(op, label_offsets, master_label)
            new_operands.append(resolved_op_str)

        if new_operands:
            lines.append(f"    {instr.mnemonic} {', '.join(new_operands)}")
        else:
            lines.append(f"    {instr.mnemonic}")

    # 2. Calculate Next State
    successors = block.successors

    if not successors:
        if last_instr and _is_return(last_instr.mnemonic):
            lines.append(f"    {last_instr.mnemonic}")
        else:
            lines.append("    ret")

    elif len(successors) == 1:
        target_block = successors[0][0]
        target_id = block_map[target_block.name]
        lines.append(f"    movl ${target_id}, {state_var_expr}")
        lines.append(f"    jmp {dispatch_label}")

    elif len(successors) == 2:
        if last_instr is None:
            raise ValueError(
                f"Block {block.name} has split control flow but no instructions."
            )

        taken_node = next(s[0] for s in successors if s[1] == EdgeType.TAKEN)
        fall_node = next(s[0] for s in successors if s[1] == EdgeType.NOT_TAKEN)

        taken_id = block_map[taken_node.name]
        fall_id = block_map[fall_node.name]

        cond_suffix = _extract_condition(last_instr.mnemonic)

        lines.append("    pushl %ebx")
        lines.append("    pushl %ecx")

        lines.append(f"    movl ${fall_id}, %ebx")
        lines.append(f"    movl ${taken_id}, %ecx")
        lines.append(f"    cmov{cond_suffix} %ecx, %ebx")
        lines.append(f"    movl %ebx, {state_var_expr}")

        lines.append("    popl %ecx")
        lines.append("    popl %ebx")

        lines.append(f"    jmp {dispatch_label}")


def _resolve_operand(
    op: Operand, label_offsets: Dict[str, int], master_label: str
) -> str:
    """
    Transforms an operand by resolving any symbols (labels) found within it
    to their absolute address in the master memory block.
    """
    match op:
        case RegisterOperand():
            return str(op)

        case ImmediateOperand(value=expr):
            new_expr = _resolve_expression_symbols(expr, label_offsets, master_label)
            return str(ImmediateOperand(new_expr))

        case MemoryOperand(displacement=expr):
            new_expr = _resolve_expression_symbols(expr, label_offsets, master_label)
            new_mem = MemoryOperand(
                base=op.base, index=op.index, scale=op.scale, displacement=new_expr
            )
            return str(new_mem)

        case x:
            assert_never(x)


def _resolve_expression_symbols(
    expr: Expression, label_offsets: Dict[str, int], master_label: str
) -> Expression:
    """
    Algebraically substitutes symbols in the expression that exist in label_offsets.
    Replacement: Symbol -> (MasterLabel + Offset)
    """
    result = Expression(expr)

    symbols_to_resolve = [s for s in result._terms if s in label_offsets]

    for sym in symbols_to_resolve:
        offset = label_offsets[sym]
        coeff = result._terms[sym]

        del result._terms[sym]

        replacement = (Expression(master_label) + offset) * coeff
        result = result + replacement

    return result


def _is_control_flow(mnemonic: str) -> bool:
    m = mnemonic.lower()
    return m.startswith("j") or m in ["ret", "iret", "syscall"]


def _is_return(mnemonic: str) -> bool:
    return mnemonic.lower() in ["ret", "iret", "syscall"]


def _extract_condition(mnemonic: str) -> str:
    m = mnemonic.lower()
    if m.startswith("j"):
        return m[1:]
    return "e"
