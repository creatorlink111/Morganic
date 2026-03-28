const readline = require('node:readline/promises');
const { stdin: input, stdout: output } = require('node:process');
const { splitTopLevel, splitStatements } = require('./splitter');
const { safeEvalArithmetic } = require('./arithmetic');

const INTEGER_TYPE_PATTERN = /^i(?:2|4|8|16|32|64|128|256|512)?$/;

function typeOfValue(value) {
  if (typeof value === 'number') return Number.isInteger(value) ? 'i' : 'f';
  if (typeof value === 'boolean') return 'b';
  if (typeof value === 'string') return '£';
  if (Array.isArray(value)) return value.__morganicType || 'l(?)';
  if (value && typeof value === 'object' && value.__class__) return `.${value.__class__}.`;
  return 'unknown';
}

function annotateListType(list, typeCode) {
  Object.defineProperty(list, '__morganicType', {
    value: typeCode,
    enumerable: false,
    configurable: true,
    writable: true,
  });
  return list;
}

function parsePairs(text) {
  const matches = [...text.matchAll(/\((-?\d+),(-?\d+)\)/g)];
  return matches.map((m) => [Number(m[1]), Number(m[2])]);
}

function renderGraph(points, xMin = -10, xMax = 10, yMin = -10, yMax = 10, labelStep = 0) {
  const width = xMax - xMin + 1;
  const height = yMax - yMin + 1;
  const grid = Array.from({ length: height }, () => Array.from({ length: width }, () => ' '));
  for (let x = xMin; x <= xMax; x += 1) if (0 >= yMin && 0 <= yMax) grid[yMax][x - xMin] = '-';
  for (let y = yMin; y <= yMax; y += 1) if (0 >= xMin && 0 <= xMax) grid[yMax - y][0 - xMin] = '|';
  if (0 >= xMin && 0 <= xMax && 0 >= yMin && 0 <= yMax) grid[yMax][0 - xMin] = '+';
  for (const [x, y] of points) if (x >= xMin && x <= xMax && y >= yMin && y <= yMax) grid[yMax - y][x - xMin] = '*';
  const lines = grid.map((r) => r.join(''));
  if (labelStep > 0) {
    lines.push(`x labels: ${xMin}..${xMax} step=${labelStep}`);
    lines.push(`y labels: ${yMin}..${yMax} step=${labelStep}`);
  }
  return lines.join('\n');
}

function splitTopLevelOperator(text, operator) {
  let paren = 0;
  let bracket = 0;
  let brace = 0;
  let angle = 0;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (ch === '(') paren += 1;
    else if (ch === ')') paren = Math.max(0, paren - 1);
    else if (ch === '[') bracket += 1;
    else if (ch === ']') bracket = Math.max(0, bracket - 1);
    else if (ch === '{') brace += 1;
    else if (ch === '}') brace = Math.max(0, brace - 1);
    else if (ch === '<') angle += 1;
    else if (ch === '>') angle = Math.max(0, angle - 1);
    if (ch === operator && paren === 0 && bracket === 0 && brace === 0 && angle === 0) {
      return [text.slice(0, i).trim(), text.slice(i + 1).trim()];
    }
  }
  return null;
}

class Parser {
  constructor(state) {
    this.state = state;
  }

  async execute(source) {
    const statements = splitStatements(source);
    for (const stmt of statements) await this.executeStatement(stmt);
  }

  readVar(name) {
    if (!this.state.variables.has(name)) throw new Error(`Unknown variable: ${name}`);
    return this.state.variables.get(name).value;
  }

  setVar(name, value, explicitType = null) {
    const resolvedType = explicitType || typeOfValue(value);
    const existing = this.state.variables.get(name);
    if (existing && explicitType == null && existing.type !== resolvedType) {
      throw new Error(`Type safety violation: variable '${name}' is ${existing.type}, cannot assign ${resolvedType}.`);
    }
    this.state.variables.set(name, { value, type: explicitType || (existing ? existing.type : resolvedType) });
  }

  simpleEval(raw) {
    if (raw.startsWith('^') && raw.endsWith('^')) return Number(raw.slice(1, -1));
    if (raw.startsWith('£')) return raw.slice(1);
    if (raw === 'b/' || raw === '/') return true;
    if (raw === 'bfalse') return false;
    if (raw.startsWith('[') && raw.endsWith(']')) return this.readVar(raw.slice(1, -1));
    return raw;
  }

  async evaluateValue(expr) {
    const raw = expr.trim();
    const appendSplit = splitTopLevelOperator(raw, '~');
    if (appendSplit) {
      const [leftRaw, rightRaw] = appendSplit;
      const targetMatch = leftRaw.match(/^\[([A-Za-z_]\w*)\]$/);
      if (!targetMatch) throw new Error('Append expression requires a list variable target like [list]~value.');
      const target = targetMatch[1];
      const current = this.readVar(target);
      if (!Array.isArray(current)) throw new Error('Append requires a list variable target.');
      const value = await this.evaluateValue(rightRaw);
      current.push(value);
      return current;
    }

    const indexSplit = splitTopLevelOperator(raw, '@');
    if (indexSplit) {
      const [leftRaw, rightRaw] = indexSplit;
      const sequence = await this.evaluateValue(leftRaw);
      if (!Array.isArray(sequence)) throw new Error("Index operator '@' requires a list value.");
      const idx = await this.evaluateValue(rightRaw);
      if (!Number.isInteger(idx)) throw new Error('List index must be an integer expression.');
      if (idx < 0 || idx >= sequence.length) throw new Error(`List index out of bounds: ${idx}`);
      return sequence[idx];
    }

    if (raw.startsWith('^') && raw.endsWith('^')) return Number(raw.slice(1, -1));
    if (/^i(?:\d+)?\^.*\^$/.test(raw)) {
      const typeCode = raw.slice(0, raw.indexOf('^'));
      if (!INTEGER_TYPE_PATTERN.test(typeCode)) {
        throw new Error(`Unknown integer type '${typeCode}'. Expected i, i8, i16, i32, etc.`);
      }
      const lit = raw.slice(raw.indexOf('^') + 1, -1).trim();
      if (!/^[+-]?\d+$/.test(lit)) throw new Error(`${typeCode} requires an integer literal inside ^ ^.`);
      return Number(lit);
    }
    if (raw.startsWith('£')) return raw.slice(1);
    if (raw === 'b/' || raw === '/') return true;
    if (raw.startsWith('[') && raw.endsWith(']')) return this.readVar(raw.slice(1, -1));
    if (raw.startsWith('&')) return this.readVar(raw.slice(1));
    if (raw.startsWith('|') && raw.endsWith('|')) return safeEvalArithmetic(raw.slice(1, -1), this.state);
    if (raw.startsWith('l(c)<') && raw.endsWith('>')) return parsePairs(raw.slice(5, -1));
    if (raw.startsWith('m<')) {
      const parts = [...raw.matchAll(/<([^>]*)>/g)].map((m) => m[1]);
      const xs = parts[0].split(',').filter(Boolean).map(Number);
      const ys = parts[1].split(',').filter(Boolean).map(Number);
      return xs.map((x, i) => [x, ys[i]]);
    }
    if (raw.startsWith('l(') && raw.includes('<') && raw.endsWith('>')) {
      const typeClose = raw.indexOf(')');
      const elementType = raw.slice(2, typeClose).trim();
      if (!/^(?:£|b|f|i(?:2|4|8|16|32|64|128|256|512)?|c)$/.test(elementType)) {
        throw new Error(`Unsupported list element type: ${elementType}`);
      }
      const body = raw.slice(raw.indexOf('<') + 1, -1);
      if (!body.trim()) return annotateListType([], `l(${elementType})`);
      const out = [];
      for (const item of splitTopLevel(body, ',')) out.push(await this.evaluateValue(item));
      return annotateListType(out, `l(${elementType})`);
    }
    if (raw.startsWith('"') && raw.endsWith('"')) return raw.slice(1, -1);
    if (raw.startsWith('*')) return this.instantiateStar(raw);
    if (raw.startsWith('.')) return this.instantiateDot(raw);
    const em = raw.match(/^"([^"]+)"(\w+)$/);
    if (em) {
      const set = this.state.enums.get(em[1]);
      if (!set || !set.has(em[2])) throw new Error(`Unknown enum value ${raw}`);
      return em[2];
    }
    if (/^[+-]?(?:\d+\.\d+|\d+)$/.test(raw)) {
      throw new Error(`Numeric literals must be wrapped with ^ ^ (example: ^${raw}^).`);
    }
    throw new Error(`Unsupported value expression: ${raw}`);
  }

  instantiateStar(raw) {
    const m = raw.match(/^\*([A-Za-z_]\w*)\{(.*)\}$/);
    if (!m) throw new Error(`Invalid constructor syntax: ${raw}`);
    const cls = this.state.classes.get(m[1]);
    if (!cls) throw new Error(`Unknown class: ${m[1]}`);
    const obj = { __class__: m[1], ...cls.defaults };
    if (m[2].trim()) {
      for (const entry of splitTopLevel(m[2], ',')) {
        const [k, v] = entry.includes('=') ? entry.split(/=(.+)/) : entry.split(/:(.+)/);
        obj[k.trim()] = this.simpleEval(v.trim());
      }
    }
    return obj;
  }

  instantiateDot(raw) {
    const m = raw.match(/^\.([A-Za-z_]\w*)\.(.+)$/);
    if (!m) throw new Error(`Invalid dot constructor syntax: ${raw}`);
    const cls = this.state.classes.get(m[1]);
    if (!cls) throw new Error(`Unknown class: ${m[1]}`);
    const obj = { __class__: m[1], ...cls.defaults };
    for (const entry of splitTopLevel(m[2], ',')) {
      const [k, v] = entry.split(/:(.+)/);
      obj[k.trim()] = this.simpleEval(v.trim());
    }
    return obj;
  }

  evalCondition(text) {
    const [left, right] = text.split('..').map((s) => s.trim());
    return this.simpleEval(left) === this.simpleEval(right);
  }

  async executeBlock(body) {
    for (const stmt of splitStatements(body)) await this.executeStatement(stmt);
  }

  async executeStatement(stmt) {
    const s = stmt.trim();
    if (!s) return;

    const inputStmt = s.match(/^\[([A-Za-z_]\w*)\]=;\((.*)\)$/s);
    if (inputStmt) {
      const prompt = await this.evaluateValue(inputStmt[2]);
      const rl = readline.createInterface({ input, output });
      const answer = await rl.question(String(prompt));
      rl.close();
      this.setVar(inputStmt[1], answer, '£');
      return;
    }

    const assign = s.match(/^\[([A-Za-z_]\w*)\]=(.*)$/);
    if (assign) {
      this.setVar(assign[1], await this.evaluateValue(assign[2].trim()));
      return;
    }

    const conv = s.match(/^\[([A-Za-z_]\w*)\]\$([A-Za-z0-9£()]+)$/);
    if (conv) {
      const val = this.readVar(conv[1]);
      const t = conv[2];
      let out = val;
      if (t === '£') out = String(val);
      else if (t === 'b') out = Boolean(val);
      else if (t === 'f') out = Number(val);
      else if (t.startsWith('i')) out = Math.trunc(Number(val));
      else throw new Error(`Unknown conversion target '${t}'. Supported targets: i, i8..i512, f, b, £.`);
      this.setVar(conv[1], out, t);
      return;
    }

    const append = s.match(/^\[([A-Za-z_]\w*)\]~(.+)$/s);
    if (append) {
      const meta = this.state.variables.get(append[1]);
      if (!meta || !meta.type.startsWith('l(') || !meta.type.endsWith(')')) {
        throw new Error('Append requires a typed list variable target like [items] of type l(...).');
      }
      if (!Array.isArray(meta.value)) {
        throw new Error('Append target is corrupted: expected list value.');
      }
      const elementType = meta.type.slice(2, -1);
      const value = await this.evaluateValue(append[2].trim());
      const valueType = typeOfValue(value);
      if (elementType !== valueType) {
        throw new Error(`Type safety violation: append expects ${elementType}, got ${valueType}.`);
      }
      meta.value.push(value);
      return;
    }

    const print = s.match(/^1\((.*)\)$/s);
    if (print) {
      const v = await this.evaluateValue(print[1]);
      console.log(typeof v === 'object' ? JSON.stringify(v) : v);
      return;
    }

    const graph = s.match(/^0(?:\.(\d+))?(?:\((-?\d+)&(-?\d+),(-?\d+)&(-?\d+)\))?\{(.*)\}$/s);
    if (graph) {
      const payload = graph[6].trim();
      const points = payload.startsWith('[') ? this.readVar(payload.slice(1, -1)) : parsePairs(payload);
      console.log(
        renderGraph(
          points,
          graph[2] ? Number(graph[2]) : -10,
          graph[3] ? Number(graph[3]) : 10,
          graph[4] ? Number(graph[4]) : -10,
          graph[5] ? Number(graph[5]) : 10,
          graph[1] ? Number(graph[1]) : 0,
        ),
      );
      return;
    }

    const ifStmt = s.match(/^2\((.*)\)\{(.*)\}$/s);
    if (ifStmt) {
      if (this.evalCondition(ifStmt[1])) await this.executeBlock(ifStmt[2]);
      return;
    }

    const whileStmt = s.match(/^3\((.*)\)\{(.*)\}$/s);
    if (whileStmt) {
      let n = 0;
      while (this.evalCondition(whileStmt[1])) {
        await this.executeBlock(whileStmt[2]);
        n += 1;
        if (n > 100000) throw new Error('Loop guard triggered');
      }
      return;
    }

    const forRange = s.match(/^4\((-?\d+),(-?\d+)\)\{(.*)\}$/s);
    if (forRange) {
      for (let i = Number(forRange[1]); i <= Number(forRange[2]); i += 1) {
        this.setVar('i', i, 'i');
        await this.executeBlock(forRange[3]);
      }
      return;
    }

    const forEach = s.match(/^4\(([A-Za-z_]\w*),(.+)\)\{(.*)\}$/s);
    if (forEach) {
      const iterableRaw = forEach[2].trim();
      const iterable = iterableRaw.startsWith('_[') ? this.readVar(iterableRaw.slice(2, -1)) : String(await this.evaluateValue(iterableRaw));
      for (const item of iterable) {
        this.setVar(forEach[1], item);
        await this.executeBlock(forEach[3]);
      }
      return;
    }

    const fnDef = s.match(/^#([A-Za-z_]\w*)'([^.]*)\.([^']+)'#\{(.*)\}$/s);
    if (fnDef) {
      this.state.functions.set(fnDef[1], { paramName: fnDef[2], paramType: fnDef[3], body: fnDef[4] });
      return;
    }

    const fnCall = s.match(/^#([A-Za-z_]\w*)\s+(.+)$/);
    if (fnCall) {
      const fn = this.state.functions.get(fnCall[1]);
      if (!fn) throw new Error(`Unknown function: ${fnCall[1]}`);
      this.setVar(fn.paramName, await this.evaluateValue(fnCall[2]), fn.paramType);
      await this.executeBlock(fn.body);
      return;
    }

    const classDef = s.match(/^\*([A-Za-z_]\w*)\{(.*)\}$/s);
    if (classDef) {
      const defaults = {};
      for (const inner of splitStatements(classDef[2])) {
        const m = inner.match(/^\[([A-Za-z_]\w*)\]=(.*)$/);
        if (m) defaults[m[1]] = this.simpleEval(m[2].trim());
      }
      this.state.classes.set(classDef[1], { defaults });
      return;
    }

    const enumDef = s.match(/^"([^"]+)"=(.+)$/);
    if (enumDef) {
      this.state.enums.set(enumDef[1], new Set(enumDef[2].split('¬').map((x) => x.trim()).filter(Boolean)));
      return;
    }

    throw new Error(`Unrecognized statement: ${s}`);
  }
}

module.exports = { Parser };
