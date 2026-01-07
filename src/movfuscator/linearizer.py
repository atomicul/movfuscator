from typing import List, Dict
from collections import deque

from dataparser import parse_data
from memorymanager import MemoryManager
from textparser import parse_cfg
from textparser.models import BasicBlock, EdgeType, Function


def movfuscate(source_code: str) -> str:
    """
    Takes raw assembly, parses it, flattens the CFG of EACH function individually,
    and returns linearized assembly code.
    """
    # 1. Setup Memory Manager
    mm = MemoryManager(master_label="__GLOBAL_MEMORY")

    # 2. Parse and register existing .data sections
    data_map = parse_data(mm, source_code)

    # Build a simple lookup table: Label Name -> Memory Offset
    label_offsets = {}
    for label, allocations in data_map.items():
        if allocations:
            label_offsets[label] = allocations[0].offset

    # 3. Parse Control Flow Graph (returns list of Functions)
    functions = parse_cfg(source_code)
    if not functions:
        return "; Error: No executable code found."

    linearized_code = []
    linearized_code.append(".text")

    # 4. Process Each Function Individually
    for func in functions:
        # Create a unique state variable for this function
        state_var_name = f"__state_{func.name}"
        state_alloc = mm.allocate_data(0, state_var_name)

        # [FIX] Resolve the state variable to its absolute address string immediately
        # explicitly avoiding the use of the label name in the ASM logic.
        state_var_ref = f"{mm.master_label} + {state_alloc.offset}"

        _flatten_function(
            func, linearized_code, state_var_ref, label_offsets, mm.master_label
        )

    # 5. Generate Data Section
    data_asm = mm.generate_data_section()

    return data_asm + "\n\n" + "\n".join(linearized_code)


def _flatten_function(
    func: Function,
    lines: List[str],
    state_var_ref: str,
    label_offsets: Dict[str, int],
    master_label: str,
):
    """
    Flattens a single function into its own dispatch loop.
    state_var_ref is the resolved memory string (e.g., "__GLOBAL_MEMORY + 16")
    """
    # 1. Discover blocks belonging ONLY to this function
    blocks = _discover_blocks(func.entry_block)
    block_map = {block.name: i for i, block in enumerate(blocks)}

    # 2. Function Prologue
    lines.append(f"\n.global {func.name}")
    lines.append(f"{func.name}:")

    # Initialize state to the entry block ID
    entry_id = block_map[func.entry_block.name]
    lines.append(f"    movl ${entry_id}, {state_var_ref}")

    # 3. Dispatch Loop
    dispatch_label = f"__dispatch_{func.name}"
    lines.append(f"\n{dispatch_label}:")
    # [FIX] Do not clobber %eax. Compare memory directly.
    # lines.append(f"    movl {state_var_ref}, %eax")

    # Dispatcher Switch
    for block in blocks:
        block_id = block_map[block.name]
        # Use function-prefixed labels to avoid collisions between functions
        block_label = f"__flat_{func.name}_{block.name}"

        # [FIX] Compare immediate ID directly with memory variable
        lines.append(f"    cmpl ${block_id}, {state_var_ref}")
        lines.append(f"    je {block_label}")

    # Default case: exit
    lines.append("    ret")

    # 4. Block Handlers
    for block in blocks:
        _generate_block_handler(
            block,
            func.name,
            block_map,
            lines,
            state_var_ref,
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
    state_var_ref: str,
    dispatch_label: str,
    label_offsets: Dict[str, int],
    master_label: str,
):
    """
    Generates the code for a single block within a specific function.
    """
    lines.append(f"\n__flat_{func_name}_{block.name}:")

    last_instr = block.instructions[-1] if block.instructions else None

    # 1. Emit instructions
    for instr in block.instructions:
        if _is_control_flow(instr.mnemonic):
            continue

        # Operand Replacement
        new_operands = []
        for op in instr.operands:
            # [FIX] Handle immediate values (e.g. $fmtstr) by stripping '$'
            clean_op = op
            prefix = ""
            if op.startswith("$"):
                prefix = "$"
                clean_op = op[1:]

            if clean_op in label_offsets:
                offset = label_offsets[clean_op]
                new_operands.append(f"{prefix}{master_label} + {offset}")
            else:
                new_operands.append(op)

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
        # Unconditional Jump
        target_block = successors[0][0]
        target_id = block_map[target_block.name]
        lines.append(f"    movl ${target_id}, {state_var_ref}")
        lines.append(f"    jmp {dispatch_label}")

    elif len(successors) == 2:
        # Conditional Jump
        if last_instr is None:
            raise ValueError(
                f"Block {block.name} has split control flow but no instructions."
            )

        taken_node = next(s[0] for s in successors if s[1] == EdgeType.TAKEN)
        fall_node = next(s[0] for s in successors if s[1] == EdgeType.NOT_TAKEN)

        taken_id = block_map[taken_node.name]
        fall_id = block_map[fall_node.name]

        cond_suffix = _extract_condition(last_instr.mnemonic)

        # [FIX] Save scratch registers before using them for state calculation
        lines.append("    pushl %ebx")
        lines.append("    pushl %ecx")

        lines.append(f"    movl ${fall_id}, %ebx")
        lines.append(f"    movl ${taken_id}, %ecx")
        lines.append(f"    cmov{cond_suffix} %ecx, %ebx")
        lines.append(f"    movl %ebx, {state_var_ref}")

        # [FIX] Restore scratch registers
        lines.append("    popl %ecx")
        lines.append("    popl %ebx")

        lines.append(f"    jmp {dispatch_label}")


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
