; Morganic x64 assembly prototype (very experimental)
; Target: Linux x86_64

global _start

section .data
    msg db "Morganic asm-x64 runtime prototype (very experimental)", 10
    msg_len equ $ - msg

section .text
_start:
    ; write(1, msg, msg_len)
    mov rax, 1          ; sys_write
    mov rdi, 1          ; stdout
    mov rsi, msg
    mov rdx, msg_len
    syscall

    ; exit(0)
    mov rax, 60         ; sys_exit
    xor rdi, rdi
    syscall
