#!/usr/bin/env node
const fs = require('node:fs');
const readline = require('node:readline/promises');
const { stdin: input, stdout: output } = require('node:process');
const { RuntimeState } = require('./state');
const { Parser } = require('./parser');

async function run() {
  const args = process.argv.slice(2);
  const state = new RuntimeState();
  const parser = new Parser(state);

  if (args[0] === '-c') {
    await parser.execute(args[1] || '');
    if (args.includes('--interactive')) return repl(parser);
    return;
  }

  if (args[0] === '--repl') return repl(parser);

  if (args[0]) {
    const src = fs.readFileSync(args[0], 'utf8');
    await parser.execute(src);
    if (args.includes('--interactive')) return repl(parser);
    return;
  }

  console.error('Usage: morganic-js --repl | -c "code" | <file.elemens>');
  process.exit(1);
}

async function repl(parser) {
  const rl = readline.createInterface({ input, output });
  console.log('Morganic JS REPL. Type :quit to exit.');
  while (true) {
    const line = await rl.question('>>> ');
    if (line.trim() === ':quit') break;
    try {
      await parser.execute(line);
    } catch (error) {
      console.error(`Error: ${error.message}`);
    }
  }
  rl.close();
}

run().catch((error) => {
  console.error(`Fatal: ${error.message}`);
  process.exit(1);
});
