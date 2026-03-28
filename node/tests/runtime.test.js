const test = require('node:test');
const assert = require('node:assert/strict');
const { Parser } = require('../src/parser');
const { RuntimeState } = require('../src/state');

async function run(source) {
  const parser = new Parser(new RuntimeState());
  await parser.execute(source);
  return parser.state;
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

test('graph label mode adds axis label information', async () => {
  const output = [];
  const originalLog = console.log;
  console.log = (line) => output.push(String(line));
  try {
    await run('0.1(-1&1,-1&1){(0,0)}');
  } finally {
    console.log = originalLog;
  }
  const joined = output.join('\n');
  assert.match(joined, /x labels:/);
  assert.match(joined, /y labels:/);
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
