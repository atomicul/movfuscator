from .models import BasicBlock, DirectSuccessor, ConditionalSuccessor, JumpCondition
from collections import deque
from typing import Set, assert_never


# Mapping from canonical condition (True path) to its inverse (False path)
_INVERSE_CONDITIONS = {
    JumpCondition.JE: "jne",
    JumpCondition.JL: "jge",
    JumpCondition.JG: "jle",
    JumpCondition.JB: "jae",
    JumpCondition.JA: "jbe",
}


def dot_graph(start_block: BasicBlock) -> str:
    output = [
        "digraph asm_flow {",
        '    node [shape=box fontname="Courier"];',
        "    // Edge definitions: Green=Condition Met (e.g. je), Red=Condition Not Met (e.g. jne)",
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

        match block.successor:
            case None:
                continue

            case DirectSuccessor(next_blk):
                output.append(
                    f'    "{block.name}" -> "{next_blk.name}" [color="black"];'
                )
                if next_blk.name not in visited:
                    queue.append(next_blk)

            case ConditionalSuccessor(true_blk, false_blk, cond):
                # True path (Green)
                label_t = cond.value
                output.append(
                    f'    "{block.name}" -> "{true_blk.name}" [color="green" label="{label_t}" fontcolor="green"];'
                )
                if true_blk.name not in visited:
                    queue.append(true_blk)

                # False path (Red)
                label_f = _INVERSE_CONDITIONS.get(cond, f"not {cond.value}")
                output.append(
                    f'    "{block.name}" -> "{false_blk.name}" [color="red" label="{label_f}" fontcolor="red"];'
                )
                if false_blk.name not in visited:
                    queue.append(false_blk)

            case x:
                assert_never(x)

    output.append("}")
    return "\n".join(output)
