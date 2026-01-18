import pytest
from typing import Set
from textparser import (
    parse_cfg,
    visualizer,
    Function,
    DirectSuccessor,
    ConditionalSuccessor,
)

EMPTY_ASM = """
.data
    .float 1
buff: .space 1024
.text
_start:
    ret
"""

MERGE_ARRAYS_ASM = """
.text
.global merge_arrays
.equ SAVED_REGISTERS, 3
.equ src1, SAVED_REGISTERS*4 + 4
.equ len1, src1+4
.equ src2, len1+4
.equ len2, src2+4
.equ dest, len2+4
merge_arrays:
    pushl %ebp
    pushl %esi
    pushl %edi
    MOVL  %esp, %ebp

    XORL %esi,   %esi # src1Counter
    xorl %edi, %edi # src2Counter
    xorl %edx, %edx # destCounter

loop:
    cmpl len1(%ebp), %esi
    jge  pick2


    cmpl len2(%ebp), %edi
    jge  pick1

    movl src1(%ebp), %eax // another comment
    movl (%eax, %esi, 4), %ecx # random comment

    movl src2(%ebp), %eax
    cmpl (%eax, %edi, 4), %ecx

    jge pick2

pick1:
    cmpl len1(%ebp), %esi
    jge  return

    movl src1(%ebp), %eax
    movl (%eax, %esi, 4), %ecx

    movl dest(%ebp), %eax
    movl %ecx, (%eax, %edx, 4)
    
    incl %esi
    incl %edx
    jmp  loop

pick2:
    cmpl len2(%ebp), %edi
    jge  return

    movl src2(%ebp), %eax
    movl (%eax, %edi, 4), %ecx

    movl dest(%ebp), %eax
    movl %ecx, (%eax, %edx, 4)
    
    incl %edi
    incl %edx
    jmp  loop

return:
    movl %ebp, %esp
    popl %edi
    popl %esi
    popl %ebp
    ret
"""

MULTI_FUNC_ASM = """
.text
.global main

main:
    movl $10, %eax
    call helper_func

    xorl %ecx, %ecx
lp:
    pushl %ecx
    incl %ecx
    cmpl %eax, %ecx
    jb lp

    addl $40, %esp

    xorl %eax, %eax
    ret

helper_func:
    cmpl $5, %eax
    jge  big_num

    addl $5, %eax
    ret

big_num:
big_num1:
    subl $1, %eax
    ret
"""

ALL_REGISTERS_ASM = """
.text
.global func_mix_32_16
.global func_mix_8_mem

func_mix_32_16:
    # Block 1 (Entry): 32-bit operations
    mov %eax, %ebx
    xor %ecx, %edx
    
    # Unconditional jump to force a new basic block
    jmp block_16bit

block_16bit:
    # Block 2 (Successor): 16-bit operations
    add %ax, %bx
    sub %si, %di
    ret

func_mix_8_mem:
    # Block 1 (Entry): 8-bit operations
    cmp %al, %bl
    inc %ah
    
    # Conditional jump to force branching
    je block_mem_imm
    ret

block_mem_imm:
    # Block 2 (Conditional Branch): Immediate to memory
    # Should default to long (32-bit) without suffix
    mov $42, (%edi)
    ret
"""

ALL_REGISTERS_ASM = """
.text
.global func_mix_32_16
.global func_mix_8_mem

func_mix_32_16:
    # Block 1 (Entry): 32-bit operations
    mov %eax, %ebx
    xor %ecx, %edx
    
    # Unconditional jump to force a new basic block
    jmp block_16bit

block_16bit:
    # Block 2 (Successor): 16-bit operations
    add %ax, %bx
    sub %si, %di
    ret

func_mix_8_mem:
    # Block 1 (Entry): 8-bit operations
    cmp %al, %bl
    inc %ah
    
    # Conditional jump to force branching
    je block_mem_imm
    ret

block_mem_imm:
    # Block 2 (Conditional Branch): Immediate to memory
    # Should default to long (32-bit) without suffix
    mov $42, (%edi)
    ret
"""


TEST_CASES = [
    ("empty", EMPTY_ASM),
    ("merge_arrays", MERGE_ARRAYS_ASM),
    ("multi_func", MULTI_FUNC_ASM),
    ("all_registers", ALL_REGISTERS_ASM),
]

CASE_IDS = [case[0] for case in TEST_CASES]
CASE_CODE = [case[1] for case in TEST_CASES]


def collect_instructions(func: Function):
    """Helper to traverse CFG and collect all instructions from all blocks."""
    visited: Set[int] = set()
    queue = [func.entry_block]
    instrs = []

    while queue:
        block = queue.pop(0)
        if id(block) in visited:
            continue
        visited.add(id(block))

        instrs.extend(block.instructions)

        if block.successor:
            if isinstance(block.successor, DirectSuccessor):
                queue.append(block.successor.block)
            elif isinstance(block.successor, ConditionalSuccessor):
                queue.append(block.successor.true_block)
                queue.append(block.successor.false_block)

    return instrs


@pytest.mark.parametrize("case_name, asm_code", TEST_CASES, ids=CASE_IDS)
def test_dot_graph_output(snapshot, case_name, asm_code):
    """
    Verifies the DOT graph (Graphviz) generation.
    """
    print(f"Testing DOT graph output of {case_name}")

    functions = parse_cfg(asm_code)
    assert functions, "No functions parsed"

    output_parts = []
    for func in functions:
        output_parts.append(f"// --- Function: {func.name} ---")
        output_parts.append(visualizer.dot_graph(func.entry_block))
        output_parts.append("")

    full_output = "\n".join(output_parts).strip()

    print(full_output)
    assert full_output == snapshot(name=f"{case_name}_dot")


@pytest.mark.parametrize("asm_code", CASE_CODE, ids=CASE_IDS)
def test_no_jumps_in_blocks(asm_code):
    """
    Checks that ALL jump instructions (conditional and unconditional) are removed 
    from the basic block instruction lists and moved to the CFG edges.
    """
    functions = parse_cfg(asm_code)
    
    for func in functions:
        instrs = collect_instructions(func)
        
        # Ensure we actually found instructions to test (except for very empty functions)
        assert len(instrs) > 0

        for instr in instrs:
            # Logic: No jumps allowed at all.
            # 'ret', 'call' are allowed. 'jmp' and conditional jumps are not.
            assert not instr.mnemonic.startswith("j"), \
                f"Found jump '{instr.mnemonic}' in block instructions. It should be removed."


@pytest.mark.parametrize("case_name, asm_code", TEST_CASES, ids=CASE_IDS)
def test_mnemonics_are_lowercase(case_name, asm_code):
    """
    Checks that mnemonics are normalized to lowercase.
    Also specifically validates that the uppercase instructions in MERGE_ARRAYS_ASM 
    were correctly converted.
    """
    functions = parse_cfg(asm_code)
    
    for func in functions:
        instrs = collect_instructions(func)
        assert len(instrs) > 0
        
        for instr in instrs:
            assert instr.mnemonic.islower(), \
                f"Mnemonic '{instr.mnemonic}' is not lowercase"

    # Specific check for the uppercase instructions we inserted into MERGE_ARRAYS_ASM
    if case_name == "merge_arrays":
        all_mnemonics = set()
        for func in functions:
            all_mnemonics.update(i.mnemonic for i in collect_instructions(func))
            
        assert "movl" in all_mnemonics
        assert "xorl" in all_mnemonics
        assert "MOVL" not in all_mnemonics
        assert "XORL" not in all_mnemonics
