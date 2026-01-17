import re
from typing import Iterator, List, Optional, Set, Tuple, Union
from .models import (
    BasicBlock,
    Instruction,
    Function,
    Operand,
    RegisterOperand,
    ImmediateOperand,
    MemoryOperand,
    DirectSuccessor,
    ConditionalSuccessor,
    JumpCondition,
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

            if curr.successor is None:
                continue

            match curr.successor:
                case DirectSuccessor(next_blk):
                    if id(next_blk) not in visited:
                        queue.append(next_blk)
                case ConditionalSuccessor(true_blk, false_blk, _):
                    if id(true_blk) not in visited:
                        queue.append(true_blk)
                    if id(false_blk) not in visited:
                        queue.append(false_blk)
                case _:
                    pass

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
    try:
        return RegisterOperand(text.lower())
    except ValueError:
        pass

    if text.startswith("$"):
        return ImmediateOperand(Expression.parse(text[1:]))

    match = re.match(r"^(.*?)(\((.*)\))?$", text)
    if not match:
        return MemoryOperand(displacement=Expression.parse(text))

    disp_str, _, paren_content = match.groups()
    displacement = (
        Expression.parse(disp_str) if disp_str and disp_str.strip() else Expression(0)
    )

    if paren_content is None:
        return MemoryOperand(displacement=displacement)

    sub_parts = [p.strip() for p in paren_content.split(",")]
    base = None
    index = None
    scale = 1

    def get_reg(s: str) -> Optional[RegisterOperand]:
        if not s:
            return None
        return RegisterOperand(s.lower())

    if len(sub_parts) >= 1:
        base = get_reg(sub_parts[0])
    if len(sub_parts) >= 2:
        index = get_reg(sub_parts[1])
    if len(sub_parts) == 3 and sub_parts[2]:
        scale = int(sub_parts[2])

    return MemoryOperand(base=base, index=index, scale=scale, displacement=displacement)


def build_blocks(elements: Iterator[Union[str, Instruction]]) -> List[BasicBlock]:
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
            case _:
                pass

    return blocks


def link_blocks(blocks: List[BasicBlock]) -> None:
    block_map = {b.name: b for b in blocks}

    for i, block in enumerate(blocks):
        if not block.instructions:
            if i + 1 < len(blocks):
                block.successor = DirectSuccessor(blocks[i + 1])
            continue

        last_instr = block.instructions[-1]
        mnem = last_instr.mnemonic.lower()

        terminates = is_terminator(mnem)
        conditional = terminates and not is_unconditional(mnem)

        # Resolve target block (the destination of the jump)
        target_block = None
        if terminates and not is_return(mnem) and last_instr.operands:
            target_op = last_instr.operands[0]
            target_label = None
            if isinstance(target_op, MemoryOperand):
                target_label = str(target_op.displacement)
            elif isinstance(target_op, ImmediateOperand):
                target_label = str(target_op.value)

            if target_label and target_label in block_map:
                target_block = block_map[target_label]

        # Resolve fallthrough block (the next physical block)
        next_physical = blocks[i + 1] if i + 1 < len(blocks) else None

        if conditional and target_block and next_physical:
            try:
                cond_enum, swap = JumpCondition.from_mnemonic(mnem)

                if swap:
                    # The jump condition was inverted (e.g. JNE).
                    # JNE Target implies "True" for JNE, which means "False" for JE.
                    # So the JNE-Target becomes the JE-False block.
                    # The Fallthrough implies "False" for JNE, which means "True" for JE.
                    # So the Fallthrough becomes the JE-True block.
                    block.successor = ConditionalSuccessor(
                        true_block=next_physical,
                        false_block=target_block,
                        condition=cond_enum,
                    )
                else:
                    # Standard case (e.g. JE)
                    block.successor = ConditionalSuccessor(
                        true_block=target_block,
                        false_block=next_physical,
                        condition=cond_enum,
                    )
            except ValueError:
                # If we can't parse the conditional jump, we treat it as a terminal failure
                # or a gap in the graph logic. For now, we raise, but in a robust tool
                # you might log and continue.
                raise

        elif is_unconditional(mnem) and not is_return(mnem) and target_block:
            block.successor = DirectSuccessor(target_block)

        elif not terminates and next_physical:
            block.successor = DirectSuccessor(next_physical)


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
