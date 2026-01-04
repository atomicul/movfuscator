.section .data
    fmt: .asciz "Absolute value of %d is %d\n"
    # Test value (negative to ensure logic flows through the negation block)
    val: .int -42

.text
.global main

# ----------------------------------------------------------------------
# Helper Function: abs_val
# Purpose: Returns the absolute value of the integer argument.
# Input:   Argument 1 on stack (4 bytes)
# Output:  Result in %eax
# ----------------------------------------------------------------------
abs_val:
    pushl %ebp
    movl %esp, %ebp
    
    # Load argument into %eax
    movl 8(%ebp), %eax
    
    # Check if value is negative
    cmpl $0, %eax
    jge end_abs      # If positive/zero, skip negation

    # Negate value if negative
    negl %eax

end_abs:
    popl %ebp
    ret

# ----------------------------------------------------------------------
# Main Function
# ----------------------------------------------------------------------
main:
    pushl %ebp
    movl %esp, %ebp
    
    # 1. Call helper function: abs_val(val)
    pushl val
    call abs_val
    addl $4, %esp
    
    # 2. Print result
    # printf(fmt, val, result)
    pushl %eax       # Result from abs_val (in %eax)
    pushl val        # Original value
    pushl $fmt
    call printf
    addl $12, %esp   # Clean up stack (3 arguments * 4 bytes)
    
    # Return 0
    xorl %eax, %eax
    leave
    ret
