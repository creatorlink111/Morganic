ASM=nasm
LD=ld

all: morganic-rs morganic-asm

morganic-rs:
	cd ../rust && cargo build --release
	cp ../rust/target/release/morganic-rs ./morganic-rs

morganic-asm: main.asm
	$(ASM) -f elf64 -o main.o main.asm
	$(LD) -o morganic-asm main.o

run: morganic-rs morganic-asm
	./morganic-asm

check: morganic-rs morganic-asm
	./morganic-asm -c "1(^7^)"
	./morganic-asm "../example programs/program_pack_index.elemens"
	./morganic-asm -c "@scicons.morgan@:[pi2]=|\`SCI_PI*2|:1([pi2])"

clean:
	rm -f main.o morganic-asm morganic-rs
