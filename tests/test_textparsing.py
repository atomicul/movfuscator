import pytest
from textparser import parse_cfg, visualizer


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
    movl  %esp, %ebp

    xorl %esi,   %esi # src1Counter
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
    subl $1, %eax
    ret
"""


@pytest.mark.parametrize(
    "case_name, asm_code",
    [
        ("empty", EMPTY_ASM),
        ("merge_arrays", MERGE_ARRAYS_ASM),
        ("multi_func", MULTI_FUNC_ASM),
    ],
)
def test_human_readable_output(snapshot, case_name, asm_code):
    """
    Verifies the recursive text tree visualization.
    Now supports multiple functions in a single file.
    """
    print(f"Testing human readable output of {case_name}")

    functions = parse_cfg(asm_code)
    assert functions, "No functions parsed"

    output_parts = []
    for func in functions:
        output_parts.append(f"=== Function: {func.name} ===")
        output_parts.append(visualizer.human_readable(func.entry_block))
        output_parts.append("")  # Add spacing between functions

    full_output = "\n".join(output_parts).strip()

    print(full_output)
    assert full_output == snapshot(name=f"{case_name}_human")


@pytest.mark.parametrize(
    "case_name, asm_code",
    [
        ("empty", EMPTY_ASM),
        ("merge_arrays", MERGE_ARRAYS_ASM),
        ("multi_func", MULTI_FUNC_ASM),
    ],
)
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
