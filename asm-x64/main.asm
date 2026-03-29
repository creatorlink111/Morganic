; Morganic x64 assembly launcher runtime
; Target: Linux x86_64
;
; This binary provides full language parity by delegating execution to
; the Python reference runtime through:
;   /usr/bin/env python3 -m morganic <args...>
;
; The Makefile sets PYTHONPATH=../python so the local package is resolved.

%define SYS_write 1
%define SYS_execve 59
%define SYS_exit 60

%define STDERR_FD 2
%define EXIT_EXEC_FAILED 127
%define MAX_ARGV_PTRS 512

global _start

section .rodata
    path_env db "/usr/bin/env", 0
    arg_env db "env", 0
    arg_python3 db "python3", 0
    arg_dash_m db "-m", 0
    arg_morganic db "morganic", 0

    exec_failed_msg db "morganic-asm: failed to exec /usr/bin/env python3 -m morganic", 10
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

    ; Basic safety guard against pathological arg counts.
    cmp rbx, MAX_ARGV_PTRS - 4
    jle .build_argv
    mov rbx, MAX_ARGV_PTRS - 4

.build_argv:
    ; Prefix argv for /usr/bin/env python3 -m morganic
    mov qword [new_argv + 0*8], arg_env
    mov qword [new_argv + 1*8], arg_python3
    mov qword [new_argv + 2*8], arg_dash_m
    mov qword [new_argv + 3*8], arg_morganic

    ; Copy caller arguments except original argv[0].
    ; for i in [1, argc): new_argv[i + 3] = argv[i]
    xor rcx, rcx
.copy_loop:
    inc rcx
    cmp rcx, rbx
    jge .copy_done

    mov rax, [r12 + rcx*8]         ; argv[i]
    mov [new_argv + rcx*8 + 24], rax
    jmp .copy_loop

.copy_done:
    ; new argc = argc + 3, terminate argv with NULL
    lea rdx, [rbx + 3]
    mov qword [new_argv + rdx*8], 0

    ; execve("/usr/bin/env", new_argv, envp)
    mov rax, SYS_execve
    mov rdi, path_env
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
