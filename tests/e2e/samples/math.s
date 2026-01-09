.section .data
    msg_high: .asciz "Value %d is High\n"
    msg_low:  .asciz "Value %d is Low\n"
    values:   .int 10, 2, 8, 20, 5
    count:    .int 5

.text
.global main

main:
    pushl %ebp
    movl %esp, %ebp
    
    # %esi = index, %edi = array base
    xorl %esi, %esi
    # Load address of values manually or via label
    
process_loop:
    cmpl count, %esi
    jge end_main

    # Load values[esi] into %eax
    movl values(, %esi, 4), %eax

    # Compare value with 8
    cmpl $8, %eax
    jg is_high

is_low:
    # Print Low message
    pushl %eax          # Push value
    pushl $msg_low      # Push format
    call printf
    addl $8, %esp
    jmp next_iter

is_high:
    # Print High message
    pushl %eax          # Push value
    pushl $msg_high     # Push format
    call printf
    addl $8, %esp

next_iter:
    incl %esi
    jmp process_loop

end_main:
    xorl %eax, %eax
    leave
    ret
