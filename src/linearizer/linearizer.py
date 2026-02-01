from typing import Dict, List, Set, Optional, Iterator, Union, Tuple
from dataclasses import dataclass

from blockpreprocessor import (
    preprocess_cfg,
    Allocator,
    Symbol,
    Function as CfgFunction,
    BasicBlock,
    Expression,
    MemoryOperand,
    ImmediateOperand,
    RegisterOperand,
    Instruction,
    DirectSuccessor,
    ConditionalSuccessor,
    JumpCondition,
)
from .models import Function, Label


EXIT_SENTINEL = -1
INDIRECTION_REG = RegisterOperand.EDI


@dataclass
class WriteTarget:
    real_offset: int
    table_offset: int


@dataclass
class LinearizationContext:
    data_label: str
    num_blocks: int
    block_ids: Dict[int, int]
    dispatch_var_offset: int
    scratch_offset: int
    dispatch_targets_offset: int
    temp_enabled_offset: int
    temp_write_reg_offset: int
    enabled_table_offsets: Dict[int, int]
    write_targets: Dict[int, WriteTarget]
    call_targets: Dict[Tuple[int, int], int]
    conditional_dispatch_offsets: Dict[int, int]
    noop_stub_label: str


def get_linearized_asm(
    asm: str, allocator: Allocator, data_label: str
) -> List[Function]:
    cfg_functions = preprocess_cfg(asm, allocator, data_label)
    return [linearize_function(func, allocator, data_label) for func in cfg_functions]


def linearize_function(
    cfg_func: CfgFunction, allocator: Allocator, data_label: str
) -> Function:
    blocks = list(discover_blocks(cfg_func.entry_block))
    block_ids = assign_block_ids(blocks)
    write_offsets = collect_write_destinations(blocks)
    call_sites = collect_call_sites(blocks, block_ids)

    ctx = allocate_linearization_tables(
        allocator, data_label, len(blocks), block_ids, write_offsets, call_sites, blocks
    )

    linear_stream: List[Union[Instruction, Label]] = []

    linear_stream.append(Label(cfg_func.name))
    linear_stream.extend(cfg_func.prologue)
    linear_stream.append(create_mov_imm_to_mem(0, ctx.dispatch_var_offset, data_label))

    linear_stream.append(Label(f"{cfg_func.name}__loop"))
    linear_stream.extend(emit_exit_check(ctx, cfg_func.name))

    for block in blocks:
        linear_stream.extend(emit_linearized_block(block, block_ids, ctx))

    linear_stream.append(
        Instruction(
            "jmp", [MemoryOperand(displacement=Expression(f"{cfg_func.name}__loop"))]
        )
    )

    linear_stream.append(Label(f"{cfg_func.name}__exit"))
    linear_stream.append(Instruction("ret", []))

    return Function(name=cfg_func.name, instructions=linear_stream)


def discover_blocks(
    block: BasicBlock, *, visited: Optional[Set[int]] = None
) -> Iterator[BasicBlock]:
    if visited is None:
        visited = set()

    if id(block) in visited:
        return

    visited.add(id(block))
    yield block

    if block.successor is None:
        return

    match block.successor:
        case DirectSuccessor(next_blk):
            yield from discover_blocks(next_blk, visited=visited)
        case ConditionalSuccessor(true_blk, false_blk, _):
            yield from discover_blocks(true_blk, visited=visited)
            yield from discover_blocks(false_blk, visited=visited)


def assign_block_ids(blocks: List[BasicBlock]) -> Dict[int, int]:
    return {id(block): idx for idx, block in enumerate(blocks)}


def collect_write_destinations(blocks: List[BasicBlock]) -> Set[int]:
    offsets: Set[int] = set()
    for block in blocks:
        for instr in block.instructions:
            dest = get_memory_write_destination(instr)
            if dest is not None and is_global_mem_access(dest):
                offset = extract_offset(dest.displacement)
                if offset is not None:
                    offsets.add(offset)
    return offsets


def collect_call_sites(
    blocks: List[BasicBlock], block_ids: Dict[int, int]
) -> List[Tuple[int, int, str]]:
    sites: List[Tuple[int, int, str]] = []
    for block in blocks:
        block_id = block_ids[id(block)]
        call_idx = 0
        for instr in block.instructions:
            if instr.mnemonic.lower() == "call":
                target = get_call_target(instr)
                if target:
                    sites.append((block_id, call_idx, target))
                call_idx += 1
    return sites


def get_call_target(instr: Instruction) -> Optional[str]:
    if not instr.operands:
        return None
    op = instr.operands[0]
    if isinstance(op, MemoryOperand) and op.base is None and op.index is None:
        return str(op.displacement)
    return None


def get_memory_write_destination(instr: Instruction) -> Optional[MemoryOperand]:
    mnem = instr.mnemonic.lower()

    if mnem.startswith("mov") and len(instr.operands) == 2:
        dest = instr.operands[1]
        if isinstance(dest, MemoryOperand):
            return dest

    rw_mnemonics = [
        "add",
        "sub",
        "and",
        "or",
        "xor",
        "inc",
        "dec",
        "neg",
        "not",
        "sal",
        "sar",
        "shl",
        "shr",
        "rol",
        "ror",
    ]

    for prefix in rw_mnemonics:
        if mnem.startswith(prefix):
            if len(instr.operands) >= 1:
                dest = instr.operands[-1]
                if isinstance(dest, MemoryOperand):
                    return dest
            break

    return None


def is_global_mem_access(op: MemoryOperand) -> bool:
    if op.base is not None or op.index is not None:
        return False
    return True


def extract_offset(expr: Expression) -> Optional[int]:
    return expr._constant


def allocate_linearization_tables(
    allocator: Allocator,
    data_label: str,
    num_blocks: int,
    block_ids: Dict[int, int],
    write_offsets: Set[int],
    call_sites: List[Tuple[int, int, str]],
    blocks: List[BasicBlock],
) -> LinearizationContext:
    dispatch_var = allocator.allocate_data(0, "dispatch_var")
    scratch = allocator.allocate_data(0, "scratch")

    dispatch_targets = allocator.allocate_data(
        [scratch.offset, dispatch_var.offset], "dispatch_targets"
    )

    temp_enabled = allocator.allocate_data(0, "temp_enabled")
    temp_write_reg = allocator.allocate_data(0, "temp_write_reg")

    enabled_table_offsets: Dict[int, int] = {}
    for block_obj_id, block_idx in block_ids.items():
        enabled_data: List[Union[int, float, Symbol]] = [0] * num_blocks
        enabled_data[block_idx] = 1
        alloc = allocator.allocate_data(enabled_data, f"block_{block_idx}_enabled")
        enabled_table_offsets[block_idx] = alloc.offset

    write_targets: Dict[int, WriteTarget] = {}
    for offset in write_offsets:
        write_data: List[Union[int, float, Symbol]] = [scratch.offset, offset]
        alloc = allocator.allocate_data(write_data, f"write_target_{offset}")
        write_targets[offset] = WriteTarget(
            real_offset=offset, table_offset=alloc.offset
        )

    call_targets_map: Dict[Tuple[int, int], int] = {}
    noop_stub_label = "__noop_stub"

    for block_id, call_idx, target in call_sites:
        call_data: List[Union[int, float, Symbol]] = [
            Symbol(noop_stub_label),
            Symbol(target),
        ]
        alloc = allocator.allocate_data(
            call_data, f"call_{block_id}_{call_idx}_targets"
        )
        call_targets_map[(block_id, call_idx)] = alloc.offset

    conditional_dispatch_offsets: Dict[int, int] = {}
    for block in blocks:
        if isinstance(block.successor, ConditionalSuccessor):
            block_id = block_ids[id(block)]
            true_id = block_ids[id(block.successor.true_block)]
            false_id = block_ids[id(block.successor.false_block)]
            cond_data: List[Union[int, float, Symbol]] = [false_id, true_id]
            alloc = allocator.allocate_data(cond_data, f"cond_dispatch_{block_id}")
            conditional_dispatch_offsets[block_id] = alloc.offset

    return LinearizationContext(
        data_label=data_label,
        num_blocks=num_blocks,
        block_ids=block_ids,
        dispatch_var_offset=dispatch_var.offset,
        scratch_offset=scratch.offset,
        dispatch_targets_offset=dispatch_targets.offset,
        temp_enabled_offset=temp_enabled.offset,
        temp_write_reg_offset=temp_write_reg.offset,
        enabled_table_offsets=enabled_table_offsets,
        write_targets=write_targets,
        call_targets=call_targets_map,
        conditional_dispatch_offsets=conditional_dispatch_offsets,
        noop_stub_label=noop_stub_label,
    )


def emit_exit_check(ctx: LinearizationContext, func_name: str) -> List[Instruction]:
    return [
        Instruction(
            "cmpl",
            [
                ImmediateOperand(Expression(EXIT_SENTINEL)),
                MemoryOperand(
                    displacement=Expression(ctx.data_label) + ctx.dispatch_var_offset
                ),
            ],
        ),
        Instruction(
            "je", [MemoryOperand(displacement=Expression(f"{func_name}__exit"))]
        ),
    ]


def emit_linearized_block(
    block: BasicBlock, block_ids: Dict[int, int], ctx: LinearizationContext
) -> Iterator[Union[Instruction, Label]]:
    block_id = block_ids[id(block)]

    yield Label(block.name)

    yield from emit_block_preamble(block_id, ctx)

    call_idx = 0
    for instr in block.instructions:
        mnem = instr.mnemonic.lower()
        if mnem == "ret":
            continue
        if mnem == "call":
            yield from emit_call_with_indirection(block_id, call_idx, instr, ctx)
            call_idx += 1
        elif is_memory_write(instr):
            yield from emit_write_with_indirection(instr, ctx)
        else:
            yield instr

    yield from emit_dispatch_update(block, block_id, block_ids, ctx)


def emit_block_preamble(
    block_id: int, ctx: LinearizationContext
) -> Iterator[Instruction]:
    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.dispatch_var_offset
            ),
            INDIRECTION_REG,
        ],
    )

    enabled_table_offset = ctx.enabled_table_offsets[block_id]
    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + enabled_table_offset,
                index=INDIRECTION_REG,
                scale=4,
            ),
            INDIRECTION_REG,
        ],
    )

    yield Instruction(
        "movl",
        [
            INDIRECTION_REG,
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.temp_enabled_offset
            ),
        ],
    )


def is_memory_write(instr: Instruction) -> bool:
    return get_memory_write_destination(instr) is not None


def emit_write_with_indirection(
    instr: Instruction, ctx: LinearizationContext
) -> Iterator[Instruction]:
    dest = get_memory_write_destination(instr)
    if dest is None:
        yield instr
        return

    offset = extract_offset(dest.displacement)
    if offset is None or offset not in ctx.write_targets:
        yield instr
        return

    target_info = ctx.write_targets[offset]

    yield Instruction(
        "movl",
        [
            INDIRECTION_REG,
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.temp_write_reg_offset
            ),
        ],
    )

    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.temp_enabled_offset
            ),
            INDIRECTION_REG,
        ],
    )

    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + target_info.table_offset,
                index=INDIRECTION_REG,
                scale=4,
            ),
            INDIRECTION_REG,
        ],
    )

    yield Instruction(
        "addl",
        [
            ImmediateOperand(Expression(ctx.data_label)),
            INDIRECTION_REG,
        ],
    )

    new_dest = MemoryOperand(base=INDIRECTION_REG)
    new_instr = transform_instruction_destination(instr, new_dest)
    yield new_instr

    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.temp_write_reg_offset
            ),
            INDIRECTION_REG,
        ],
    )


def transform_instruction_destination(
    instr: Instruction, new_dest: MemoryOperand
) -> Instruction:
    mnem = instr.mnemonic.lower()

    if mnem.startswith("mov") and len(instr.operands) == 2:
        return Instruction(instr.mnemonic, [instr.operands[0], new_dest])

    if len(instr.operands) == 1:
        return Instruction(instr.mnemonic, [new_dest])

    if len(instr.operands) == 2:
        return Instruction(instr.mnemonic, [instr.operands[0], new_dest])

    return instr


def emit_call_with_indirection(
    block_id: int, call_idx: int, instr: Instruction, ctx: LinearizationContext
) -> Iterator[Instruction]:
    call_key = (block_id, call_idx)
    if call_key not in ctx.call_targets:
        yield instr
        return

    call_table_offset = ctx.call_targets[call_key]

    yield Instruction(
        "movl",
        [
            INDIRECTION_REG,
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.temp_write_reg_offset
            ),
        ],
    )

    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.temp_enabled_offset
            ),
            INDIRECTION_REG,
        ],
    )

    yield Instruction(
        "call",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + call_table_offset,
                index=INDIRECTION_REG,
                scale=4,
            ),
        ],
    )

    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.temp_write_reg_offset
            ),
            INDIRECTION_REG,
        ],
    )


def emit_dispatch_update(
    block: BasicBlock,
    block_id: int,
    block_ids: Dict[int, int],
    ctx: LinearizationContext,
) -> Iterator[Instruction]:
    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.temp_enabled_offset
            ),
            INDIRECTION_REG,
        ],
    )

    yield Instruction(
        "movl",
        [
            MemoryOperand(
                displacement=Expression(ctx.data_label) + ctx.dispatch_targets_offset,
                index=INDIRECTION_REG,
                scale=4,
            ),
            INDIRECTION_REG,
        ],
    )

    yield Instruction(
        "addl",
        [
            ImmediateOperand(Expression(ctx.data_label)),
            INDIRECTION_REG,
        ],
    )

    match block.successor:
        case None:
            yield Instruction(
                "movl",
                [
                    ImmediateOperand(Expression(EXIT_SENTINEL)),
                    MemoryOperand(base=INDIRECTION_REG),
                ],
            )

        case DirectSuccessor(next_blk):
            next_id = block_ids[id(next_blk)]
            yield Instruction(
                "movl",
                [
                    ImmediateOperand(Expression(next_id)),
                    MemoryOperand(base=INDIRECTION_REG),
                ],
            )

        case ConditionalSuccessor(_, _, condition):
            setcc_mnem = condition_to_setcc(condition)

            yield Instruction(setcc_mnem, [RegisterOperand.CL])
            yield Instruction("movzbl", [RegisterOperand.CL, RegisterOperand.ECX])

            cond_table_offset = ctx.conditional_dispatch_offsets[block_id]
            yield Instruction(
                "movl",
                [
                    MemoryOperand(
                        displacement=Expression(ctx.data_label) + cond_table_offset,
                        index=RegisterOperand.ECX,
                        scale=4,
                    ),
                    RegisterOperand.EAX,
                ],
            )

            yield Instruction(
                "movl",
                [RegisterOperand.EAX, MemoryOperand(base=INDIRECTION_REG)],
            )


def condition_to_setcc(cond: JumpCondition) -> str:
    mapping = {
        JumpCondition.JE: "sete",
        JumpCondition.JL: "setl",
        JumpCondition.JG: "setg",
        JumpCondition.JB: "setb",
        JumpCondition.JA: "seta",
    }
    return mapping[cond]


def create_mov_imm_to_mem(value: int, offset: int, data_label: str) -> Instruction:
    return Instruction(
        "movl",
        [
            ImmediateOperand(Expression(value)),
            MemoryOperand(displacement=Expression(data_label) + offset),
        ],
    )
