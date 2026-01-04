from .models import BasicBlock, EdgeType
from collections import deque
from typing import Set


def human_readable(block: BasicBlock) -> str:
    lines = []

    def _recurse(curr_block: BasicBlock, visited: Set[str], level: int, edge_type: str):
        indent = "    " * level
        instr_indent = indent + "   "

        is_cycle = curr_block.name in visited
        cycle_msg = " (CYCLE DETECTED - Stopping)" if is_cycle else ""
        lines.append(f"{indent}|- [{edge_type}] -> {curr_block.name}{cycle_msg}")

        for instr in curr_block.instructions:
            lines.append(f"{instr_indent} {instr}")

        if is_cycle:
            return

        new_visited = visited.copy()
        new_visited.add(curr_block.name)

        if not curr_block.successors and not is_cycle:
            lines.append(f"{indent}    (end of flow)")

        for succ_block, succ_edge in curr_block.successors:
            _recurse(succ_block, new_visited, level + 1, succ_edge)

    if block:
        _recurse(block, set(), 0, "Start")

    return "\n".join(lines)


def dot_graph(start_block: BasicBlock) -> str:
    output = [
        "digraph asm_flow {",
        '    node [shape=box fontname="Courier"];',
        "    // Edge definitions: Green=True (Taken), Red=False (Not Taken)",
    ]

    visited: Set[str] = set()
    queue = deque([start_block])

    while queue:
        block = queue.popleft()

        if block.name in visited:
            continue
        visited.add(block.name)

        code = (
            "\\l".join(str(i).replace('"', '\\"') for i in block.instructions) + "\\l"
        )
        node_label = f"{block.name}\\n----------------\\n{code}"
        output.append(f'    "{block.name}" [label="{node_label}"];')

        for succ_block, edge_type in block.successors:
            attrs = ""
            if edge_type == EdgeType.TAKEN:
                attrs = ' [color="green" label="true" fontcolor="green"]'
            elif edge_type == EdgeType.NOT_TAKEN:
                attrs = ' [color="red" label="false" fontcolor="red"]'
            else:
                attrs = ' [color="black"]'

            output.append(f'    "{block.name}" -> "{succ_block.name}"{attrs};')

            if succ_block.name not in visited:
                queue.append(succ_block)

    output.append("}")
    return "\n".join(output)
