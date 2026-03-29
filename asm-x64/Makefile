ASM=nasm
LD=ld

all: morganic-asm

morganic-asm: main.asm
	$(ASM) -f elf64 -o main.o main.asm
	$(LD) -o morganic-asm main.o

run: morganic-asm
	PYTHONPATH=../python ./morganic-asm

check: morganic-asm
	PYTHONPATH=../python ./morganic-asm -c "1(^7^)"
	PYTHONPATH=../python ./morganic-asm "../example programs/program_pack_index.elemens"

clean:
	rm -f main.o morganic-asm
