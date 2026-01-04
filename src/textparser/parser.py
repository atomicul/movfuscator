import re
from typing import Iterator, List, Optional, Set, Tuple, Union, assert_never
from .models import (
    BasicBlock,
    Instruction,
    EdgeType,
    Function,
    Operand,
    RegisterOperand,
    ImmediateOperand,
    MemoryOperand,
)
from .expression import Expression


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

        operands: List[Operand] = []
        if len(parts) > 1:
            raw_operands = split_operands_source(parts[1])
            operands = [parse_operand(op) for op in raw_operands]

        yield Instruction(mnemonic, operands, line_number=line_num)


def split_operands_source(text: str) -> List[str]:
    """
    Splits an operand string by comma, ignoring commas inside parentheses.
    E.g., "4(%eax, %ebx), $10" -> ["4(%eax, %ebx)", "$10"]
    """
    parts = []
    current = []
    depth = 0
    for char in text:
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            current.append(char)

    if current:
        parts.append("".join(current).strip())

    return [p for p in parts if p]


def parse_operand(text: str) -> Operand:
    """
    Parses a single operand string into the appropriate Operand model.
    """
    text = text.strip()

    # 1. Try Register
    try:
        # RegisterOperand definitions include the '%' (e.g., "%eax")
        return RegisterOperand(text.lower())
    except ValueError:
        pass

    # 2. Try Immediate
    if text.startswith("$"):
        # Parse expression after '$'
        return ImmediateOperand(Expression.parse(text[1:]))

    # 3. Memory (or Label/Direct Address)
    # Syntax: displacement(base, index, scale)
    # Regex Breakdown:
    #   ^          Start
    #   (.*?)      Group 1: Displacement (lazy match until parens)
    #   (?:        Non-capturing group for parens part
    #     \(       Literal '('
    #     (.*)     Group 2: Content inside parens
    #     \)       Literal ')'
    #   )?         Parens part is optional
    #   $          End
    match = re.match(r"^(.*?)(\((.*)\))?$", text)
    if not match:
        # Fallback: Treat whole string as displacement expression
        return MemoryOperand(displacement=Expression.parse(text))

    disp_str, _, paren_content = match.groups()

    displacement = (
        Expression.parse(disp_str) if disp_str and disp_str.strip() else Expression(0)
    )

    # If no parentheses (e.g. "Label"), it's just displacement
    if paren_content is None:
        return MemoryOperand(displacement=displacement)

    # Parse (base, index, scale)
    # Possible forms: (base), (base, index), (, index, scale), etc.
    sub_parts = [p.strip() for p in paren_content.split(",")]

    base = None
    index = None
    scale = 1

    if len(sub_parts) > 3:
        raise ValueError(f"Invalid memory operand format: {text}")

    # Helper to parse register part
    def get_reg(s: str) -> Optional[RegisterOperand]:
        if not s:
            return None
        return RegisterOperand(s.lower())

    if len(sub_parts) >= 1:
        base = get_reg(sub_parts[0])

    if len(sub_parts) >= 2:
        index = get_reg(sub_parts[1])

    if len(sub_parts) == 3 and sub_parts[2]:
        try:
            scale = int(sub_parts[2])
            if scale not in (1, 2, 4, 8):
                raise ValueError
        except ValueError:
            raise ValueError(f"Invalid scale factor: {sub_parts[2]}")

    return MemoryOperand(base=base, index=index, scale=scale, displacement=displacement)


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
            # Extract target label string from the operand
            target_op = last_instr.operands[0]
            target_label = None

            if isinstance(target_op, MemoryOperand):
                # Standard branch: jmp Label -> MemoryOperand(disp="Label")
                # We use the string representation of the expression (which reconstructs the label)
                target_label = str(target_op.displacement)
            elif isinstance(target_op, ImmediateOperand):
                # jmp $Label (rare for direct jumps, but possible)
                target_label = str(target_op.value)

            if target_label and target_label in block_map:
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
