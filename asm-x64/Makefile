ASM=nasm
LD=ld

all: morganic-asm

morganic-asm: main.asm
	$(ASM) -f elf64 -o main.o main.asm
	$(LD) -o morganic-asm main.o

run: morganic-asm
	./morganic-asm

clean:
	rm -f main.o morganic-asm
