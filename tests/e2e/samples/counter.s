.section .data
counter:
    .int 0          # Variable at offset 0 (relative to input data)
limit:
    .int 5          # Variable at offset 4

fmtstr: .asciz "%d\n"

.text
.global main
main:
    # Load counter into register
    movl counter, %eax

check_loop:
    cmpl limit, %eax
    jge  exit_block

body:
    pushl %eax
    pushl $fmtstr
    call  printf
    addl  $4, %esp
    popl  %eax

    incl %eax
    movl %eax, counter
    jmp  check_loop

exit_block:
    xorl %eax, %eax
    ret
