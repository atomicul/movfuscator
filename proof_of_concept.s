.data

# LOOKUP TABLES
.align 4

# Logic
eq_grid: 
    .set i, 0
    .rept 256
        .fill i, 1, 0
        .byte 1
        .fill (255-i), 1, 0
        .set i, i+1
    .endr
neq_grid: 
    .set i, 0
    .rept 256
        .fill i, 1, 1
        .byte 0
        .fill (255-i), 1, 1
        .set i, i+1
    .endr

g_grid: 
    .set i, 0
    .rept 256
        .set j, 0
        .rept 256
            .byte i > j
            .set j, j+1
        .endr 
        .set i, i+1
    .endr

ge_grid: 
    .set i, 0
    .rept 256
        .set j, 0
        .rept 256
            .byte i >= j
            .set j, j+1
        .endr 
        .set i, i+1
    .endr

l_grid: 
    .set i, 0
    .rept 256
        .set j, 0
        .rept 256
            .byte i < j
            .set j, j+1
        .endr 
        .set i, i+1
    .endr

le_grid: 
    .set i, 0
    .rept 256
        .set j, 0
        .rept 256
            .byte i <= j
            .set j, j+1
        .endr 
        .set i, i+1
    .endr

# Arithmetic
sum_grid:
    .set i, 0
    .rept 256
        .set j, 0
        .rept 256
            .byte i+j
            .set j, j+1
        .endr 
        .set i, i+1
    .endr

sub_grid:
    .set i, 0
    .rept 256
        .set j, 0
        .rept 256
            .byte i-j
            .set j, j+1
        .endr 
        .set i, i+1
    .endr

mul_grid:
    .set i, 0
    .rept 256
        .set j, 0
        .rept 256
            .byte i*j
            .set j, j+1
        .endr 
        .set i, i+1
    .endr

div_grid:
    .set i, 0
    .rept 256
        .set j, 0
        .rept 256
            .if j != 0
                .byte i/j
            .else
                .byte 0
            .endif
            .set j, j+1
        .endr 
        .set i, i+1
    .endr

# VARS
fs: .asciz "%d "

EXEC_ON: .byte 1

# 1 + 1 + 4 + 4 + 1 = 11 bytes
.macro var var_name, initial_value
    \var_name\(): .byte \initial_value
    DUMMY_\var_name\(): .byte \initial_value
    SELECT_\var_name\(): .long DUMMY_\var_name\(), \var_name\()
.endm

var_decl_start:
var x, 6
var y, 0

.text
.global main

# MACROS

# Arithmetic & Logic
.macro m_lookup_base table, r, a, b
    mov \a, %eax
    mov \b, %ecx
    movzbl %al, %eax
    movzbl %cl, %ecx
    movl $0, %edx
    movb %al, %dh
    movb %cl, %dl
    movzbl \table\()(,%edx,1), \r
.endm

.macro create_op op_name, table_name
    .macro \op_name r, a, b
        m_lookup_base \table_name, \r, \a, \b
    .endm
.endm

# Logic

create_op m_eq, eq_grid
create_op m_neq, neq_grid
create_op m_l, l_grid
create_op m_le, le_grid
create_op m_g, g_grid
create_op m_ge, ge_grid

# Arithmetic

create_op m_sum, sum_grid
create_op m_sub, sub_grid
create_op m_mul, mul_grid
create_op m_div, div_grid

# Flow toggler
.macro m_on
    mov $1, EXEC_ON
.endm

.macro m_off
    mov $0, EXEC_ON
.endm

# Set var
.macro m_set n, val
    mov \val, %eax
    movzbl EXEC_ON, %ecx
    movl SELECT_\n\()(,%ecx,4), %edx
    movb %al, (%edx)
.endm

# PROGRAM
main:
    pushl %ebp
    movl %esp, %ebp

    m_off
    m_set x, $2
    m_on 
    m_set y, $2

    m_eq %eax, x, y
    
    pushl %eax
    pushl $fs
    call printf
    addl $8, %esp

    leave
    ret
