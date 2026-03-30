const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const { Parser } = require('../src/parser');
const { RuntimeState } = require('../src/state');

const GRAPH_SNAPSHOTS = path.resolve(__dirname, '..', '..', 'graph_snapshots');

function normalize(text) {
  return String(text).replace(/\r\n/g, '\n').replace(/^\uFEFF/, '').replace(/\n+$/g, '');
}

function readFixture(name) {
  return normalize(fs.readFileSync(path.join(GRAPH_SNAPSHOTS, name), 'utf8'));
}

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function run(source) {
  const parser = new Parser(new RuntimeState());
  await parser.execute(source);
  return parser.state;
}

async function capture(source) {
  const output = [];
  const originalLog = console.log;
  console.log = (line) => output.push(String(line));
  try {
    await run(source);
  } finally {
    console.log = originalLog;
  }
  return normalize(output.join('\n'));
}

test('nested append/index expression evaluates with expected precedence', async () => {
  const state = await run('[xs]=l(i)<^1^,^2^,^3^>:[idx]=^1^:[xs]~[xs]@[idx]');
  assert.deepEqual(state.variables.get('xs').value, [1, 2, 3, 2]);
});

test('invalid append target surfaces a friendly error', async () => {
  await assert.rejects(
    () => run('[x]=^1^:[x]~^2^'),
    /Append requires a typed list variable target/,
  );
});

test('plain numeric literal error includes hint text', async () => {
  await assert.rejects(
    () => run('[x]=3'),
    /Numeric literals must be wrapped with \^ \^/,
  );
});

test('typed list allows matrix elements', async () => {
  const state = await run('[mylist]=l(m)<m<0,1,2><3,1,5>,m<4,2,5><5,6,3>>');
  assert.equal(state.variables.get('mylist').type, 'l(m)');
});

test('pointer byte buffer supports arithmetic and dereference', async () => {
  const state = await run('++buffer==[0x48 0x65 0x6C 0x6C 0x6F]:buffer+-0:+buffer+1:-buffer>>2:[x]=--buffer');
  assert.equal(state.variables.get('x').value, 108);
});

test('type-query expression returns canonical type name', async () => {
  const state = await run('[title]=£hello:[kind]="[title]');
  assert.equal(state.variables.get('kind').value, 'String');
});

test('modulo in arithmetic expression is not treated as a comment', async () => {
  const state = await run('[a]=^7^:[b]=^3^:[m]=|`a%`b|');
  assert.equal(state.variables.get('m').value, 1);
});

test('graph output snapshots stay stable', async () => {
  for (const fileName of fs.readdirSync(GRAPH_SNAPSHOTS).filter((name) => name.endsWith('.elemens')).sort()) {
    const base = fileName.slice(0, -'.elemens'.length);
    const expectedPath = path.join(GRAPH_SNAPSHOTS, `${base}.out.txt`);
    if (!fs.existsSync(expectedPath)) continue;
    const source = readFixture(fileName);
    const expected = readFixture(`${base}.out.txt`);
    assert.equal(await capture(source), expected, base);
  }
});

test('graph error snapshots stay stable', async () => {
  for (const fileName of fs.readdirSync(GRAPH_SNAPSHOTS).filter((name) => name.endsWith('.elemens')).sort()) {
    const base = fileName.slice(0, -'.elemens'.length);
    const expectedPath = path.join(GRAPH_SNAPSHOTS, `${base}.err.txt`);
    if (!fs.existsSync(expectedPath)) continue;
    const source = readFixture(fileName);
    const expected = readFixture(`${base}.err.txt`);
    await assert.rejects(() => run(source), (error) => {
      assert.match(String(error.message), new RegExp(escapeRegex(expected)));
      return true;
    }, base);
  }
});

test('processed string injects variables and expressions', async () => {
  const state = await run('[name]=£Morgan:[msg]=&£hello $$[name], $$|10+8| total');
  assert.equal(state.variables.get('msg').value, 'hello Morgan, 18 total');
  assert.equal(state.variables.get('msg').type, '&£');
});

test('processed string type query returns canonical name', async () => {
  const state = await run('[msg]=&£value=$$|10+8|:[kind]="[msg]');
  assert.equal(state.variables.get('kind').value, 'ProcessedString');
});
