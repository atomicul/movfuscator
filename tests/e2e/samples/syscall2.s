.data
x1: .ascii "maria"
x2: .long 0x61676362
x3: .ascii "maria2"
.text
.global main
main:
mov $4, %eax
mov $1, %ebx
mov $x1, %ecx
mov $14, %edx
int $0x80
end:
movl $1, %eax
xor %ebx, %ebx
int $0x80
