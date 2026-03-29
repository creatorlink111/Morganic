; Morganic x64 assembly runtime launcher
; Target: Linux x86_64
;
; This binary stays entirely in native x64 assembly and executes the
; repository's native Rust runtime binary (no Python dependency).
;
; Expected sibling binary: ./morganic-rs

%define SYS_write 1
%define SYS_execve 59
%define SYS_exit 60

%define STDERR_FD 2
%define EXIT_EXEC_FAILED 127
%define MAX_ARGV_PTRS 512

global _start

section .rodata
    path_runtime db "./morganic-rs", 0
    arg_runtime db "morganic-rs", 0

    exec_failed_msg db "morganic-asm: failed to exec ./morganic-rs", 10
    exec_failed_msg_len equ $ - exec_failed_msg

section .bss
    new_argv resq MAX_ARGV_PTRS

section .text
_start:
    ; Linux process entry stack layout:
    ;   [rsp+0]              = argc
    ;   [rsp+8 ..]           = argv[0..argc-1]
    ;   [rsp+8+argc*8]       = NULL
    ;   [rsp+8+(argc+1)*8..] = envp

    mov rbx, [rsp]          ; argc
    lea r12, [rsp + 8]      ; &argv[0]

    ; envp = &argv[argc + 1]
    lea r13, [r12 + rbx*8 + 8]

    ; Guard against pathological arg counts.
    cmp rbx, MAX_ARGV_PTRS - 1
    jle .build_argv
    mov rbx, MAX_ARGV_PTRS - 1

.build_argv:
    ; argv[0] for child runtime
    mov qword [new_argv + 0*8], arg_runtime

    ; Copy caller arguments except original argv[0].
    ; for i in [1, argc): new_argv[i] = argv[i]
    xor rcx, rcx
.copy_loop:
    inc rcx
    cmp rcx, rbx
    jge .copy_done

    mov rax, [r12 + rcx*8]         ; argv[i]
    mov [new_argv + rcx*8], rax
    jmp .copy_loop

.copy_done:
    ; terminate argv with NULL
    mov qword [new_argv + rbx*8], 0

    ; execve("./morganic-rs", new_argv, envp)
    mov rax, SYS_execve
    mov rdi, path_runtime
    mov rsi, new_argv
    mov rdx, r13
    syscall

    ; If we are here, execve failed.
    mov rax, SYS_write
    mov rdi, STDERR_FD
    mov rsi, exec_failed_msg
    mov rdx, exec_failed_msg_len
    syscall

    mov rax, SYS_exit
    mov rdi, EXIT_EXEC_FAILED
    syscall
