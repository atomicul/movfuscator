from typing import Iterator, List, Optional, Set, Tuple, Union, assert_never
from .models import BasicBlock, Instruction, EdgeType, Function


def parse_cfg(source_code: str) -> List[Function]:
    """
    Parses assembly source code and returns a list of detected Functions.
    Each Function contains a name and an entry BasicBlock.
    """
    stream = iter_source_lines(source_code)
    stream = strip_comments(stream)
    stream = filter_text_section(stream)
    elements = parse_elements(stream)

    blocks = build_blocks(elements)

    if not blocks:
        return []

    link_blocks(blocks)
    return extract_functions(blocks)


def extract_functions(blocks: List[BasicBlock]) -> List[Function]:
    """
    Identifies distinct functions by finding connected components in the CFG.

    Assumption: Functions are disjoint graphs. If Block A falls through
    or jumps to Block B, they are in the same function. If Block A returns
    (and doesn't fall through), the next block in the list is a new function entry.
    """
    functions: List[Function] = []
    visited: Set[int] = set()

    for block in blocks:
        if id(block) in visited:
            continue

        func = Function(name=block.name, entry_block=block)
        functions.append(func)

        queue = [block]
        while queue:
            curr = queue.pop(0)
            if curr.name in visited:
                continue

            visited.add(id(curr))

            for succ_block, _ in curr.successors:
                if id(succ_block) not in visited:
                    queue.append(succ_block)

    return functions


def strip_comments(
    source_stream: Iterator[Tuple[int, str]],
) -> Iterator[Tuple[int, str]]:
    for line_num, line in source_stream:
        line = line.split("#", 1)[0]
        line = line.split("//", 1)[0]
        line = line.strip()
        if line:
            yield line_num, line


def filter_text_section(
    source_stream: Iterator[Tuple[int, str]],
) -> Iterator[Tuple[int, str]]:
    in_text_section = False
    for line_num, line in source_stream:
        if line.startswith(".section .text") or line == ".text":
            in_text_section = True
            continue
        elif line.startswith(".section") or line in [".data", ".bss"]:
            in_text_section = False
            continue

        if in_text_section:
            yield line_num, line


def parse_elements(
    source_stream: Iterator[Tuple[int, str]],
) -> Iterator[Union[str, Instruction]]:
    """
    Transforms raw source lines into a stream of parsed elements.
    Yields `str` for labels and `Instruction` objects for code.
    """
    for line_num, line in source_stream:
        if line.endswith(":"):
            yield line[:-1]
            continue

        parts = line.split(maxsplit=1)
        mnemonic = parts[0]

        if mnemonic.startswith("."):
            continue  # do not parse assembler directives

        operands = []
        if len(parts) > 1:
            operands = [op.strip() for op in parts[1].split(",")]

        yield Instruction(mnemonic, operands, line_number=line_num)


def build_blocks(elements: Iterator[Union[str, Instruction]]) -> List[BasicBlock]:
    """
    Groups the stream of instructions and labels into `BasicBlock` objects.
    """
    blocks: List[BasicBlock] = []
    current_block: Optional[BasicBlock] = None

    for item in elements:
        match item:
            case str(label_name):
                if current_block and not current_block.instructions:
                    current_block.name = label_name
                else:
                    current_block = BasicBlock(name=label_name)
                    blocks.append(current_block)

            case Instruction() as instr:
                if current_block is None:
                    current_block = BasicBlock(name=f"loc_{instr.line_number}")
                    blocks.append(current_block)

                current_block.instructions.append(instr)

                if is_terminator(instr.mnemonic):
                    current_block = None

            case x:
                assert_never(x)

    return blocks


def link_blocks(blocks: List[BasicBlock]) -> None:
    """
    Connects BasicBlocks to form a Control Flow Graph (CFG).
    """
    block_map = {b.name: b for b in blocks}

    for i, block in enumerate(blocks):
        if not block.instructions:
            continue

        last_instr = block.instructions[-1]
        mnem = last_instr.mnemonic.lower()
        is_conditional = is_terminator(mnem) and not is_unconditional(mnem)

        if is_terminator(mnem) and not is_return(mnem) and last_instr.operands:
            target_label = last_instr.operands[0]
            if target_label in block_map:
                edge_type = EdgeType.TAKEN if is_conditional else EdgeType.DIRECT
                block.successors.append((block_map[target_label], edge_type))

        if not is_unconditional(mnem):
            if i + 1 < len(blocks):
                edge_type = EdgeType.NOT_TAKEN if is_conditional else EdgeType.DIRECT
                block.successors.append((blocks[i + 1], edge_type))


def is_terminator(mnemonic: str) -> bool:
    m = mnemonic.lower()
    return m.startswith("j") or m.startswith("b") or m in ["ret", "iret", "syscall"]


def is_unconditional(mnemonic: str) -> bool:
    return mnemonic.lower() in ["jmp", "b", "ret", "iret", "syscall"]


def is_return(mnemonic: str) -> bool:
    return mnemonic.lower() in ["ret", "iret", "syscall"]


def iter_source_lines(source_code: str) -> Iterator[Tuple[int, str]]:
    for i, line in enumerate(source_code.splitlines()):
        yield i + 1, line
