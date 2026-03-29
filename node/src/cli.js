#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline/promises');
const { stdin: input, stdout: output } = require('node:process');
const { RuntimeState } = require('./state');
const { Parser } = require('./parser');

const IMPORT_PATTERN = /@([A-Za-z0-9_./\\-]+\.(?:morgan|elemens))@/g;

function candidateImportPaths(rawRef, baseDir) {
  const ref = rawRef.trim();
  const candidates = [path.resolve(baseDir, ref)];
  if (!ref.includes('/') && !ref.includes('\\')) {
    const projectRoot = path.resolve(__dirname, '..', '..');
    candidates.push(path.resolve(projectRoot, ref));
    candidates.push(path.resolve(projectRoot, 'std', ref));
  }
  return [...new Set(candidates)];
}

function resolveModuleImports(source, baseDir, stack = []) {
  return source.replace(IMPORT_PATTERN, (_, rawRef) => {
    const target = candidateImportPaths(rawRef, baseDir).find((candidate) => fs.existsSync(candidate));
    if (!target) throw new Error(`Import file not found: ${rawRef}`);
    if (!['.morgan', '.elemens'].includes(path.extname(target))) {
      throw new Error(`Unsupported import file type: ${rawRef}`);
    }
    if (stack.includes(target)) throw new Error(`Circular module import detected: ${[...stack, target].join(' -> ')}`);
    const nested = fs.readFileSync(target, 'utf8');
    return resolveModuleImports(nested, path.dirname(target), [...stack, target]);
  });
}

async function run() {
  const args = process.argv.slice(2);
  const state = new RuntimeState();
  const parser = new Parser(state);

  if (args[0] === '-c') {
    await parser.execute(resolveModuleImports(args[1] || '', process.cwd()));
    if (args.includes('--interactive')) return repl(parser);
    return;
  }

  if (args[0] === '--repl') return repl(parser);

  if (args[0]) {
    const sourcePath = path.resolve(args[0]);
    const src = resolveModuleImports(fs.readFileSync(sourcePath, 'utf8'), path.dirname(sourcePath));
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
      await parser.execute(resolveModuleImports(line, process.cwd()));
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
