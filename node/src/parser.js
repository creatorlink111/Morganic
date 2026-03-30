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
  const matches = [...text.matchAll(/\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)/g)];
  return matches.map((m) => [Number(m[1]), Number(m[2])]);
}

function renderGraph(points, xMin = -10, xMax = 10, yMin = -10, yMax = 10, labelStep = 0) {
  if (xMin >= xMax) throw new Error(`x-axis min must be less than max: ${xMin}&${xMax}`);
  if (yMin >= yMax) throw new Error(`y-axis min must be less than max: ${yMin}&${yMax}`);
  if (labelStep < 0) throw new Error('Graph label interval must be positive.');

  const xScale = 2;
  const leftMargin = labelStep > 0 ? 5 : 0;
  const bottomMargin = labelStep > 0 ? 2 : 0;
  const plotWidth = (xMax - xMin) * xScale + 1;
  const plotHeight = yMax - yMin + 1;
  const width = leftMargin + plotWidth;
  const height = plotHeight + bottomMargin;
  const grid = Array.from({ length: height }, () => Array.from({ length: width }, () => ' '));

  const toGridCoords = (x, y) => [leftMargin + (x - xMin) * xScale, yMax - y];

  if (xMin <= 0 && xMax >= 0) {
    const [axisX] = toGridCoords(0, 0);
    for (let row = 0; row < plotHeight; row += 1) grid[row][axisX] = '│';
  }
  if (yMin <= 0 && yMax >= 0) {
    const [, axisY] = toGridCoords(0, 0);
    for (let col = 0; col < width; col += 1) grid[axisY][col] = '─';
  }
  if (xMin <= 0 && xMax >= 0 && yMin <= 0 && yMax >= 0) {
    const [axisX, axisY] = toGridCoords(0, 0);
    grid[axisY][axisX] = '┼';
  }

  for (const [x, y] of points) {
    if (x < xMin || x > xMax || y < yMin || y > yMax) {
      throw new Error(`Point (${x},${y}) is outside graph range x[${xMin},${xMax}] y[${yMin},${yMax}].`);
    }
    const [gx, gy] = toGridCoords(x, y);
    grid[gy][gx] = '●';
  }

  if (xMin <= 0 && xMax >= 0 && labelStep === 0) {
    const [axisX] = toGridCoords(0, 0);
    if (grid[0][axisX] === ' ') grid[0][axisX] = 'y';
    else if (axisX + 1 < width && grid[0][axisX + 1] === ' ') grid[0][axisX + 1] = 'y';
  }
  if (yMin <= 0 && yMax >= 0 && labelStep === 0) {
    const [, axisY] = toGridCoords(0, 0);
    grid[axisY][width - 1] = 'x';
  }

  if (labelStep > 0) {
    if (yMin <= 0 && yMax >= 0) {
      const xLabelRow = Math.min(plotHeight, height - 1);
      for (let x = xMin; x <= xMax; x += 1) {
        if (x % labelStep !== 0) continue;
        const [gx] = toGridCoords(x, 0);
        const label = String(x);
        const start = gx - Math.floor(label.length / 2);
        if (start >= 0 && start + label.length <= width) {
          for (let i = 0; i < label.length; i += 1) grid[xLabelRow][start + i] = label[i];
        }
      }
    }
    if (xMin <= 0 && xMax >= 0) {
      const [axisX] = toGridCoords(0, 0);
      for (let y = yMin; y <= yMax; y += 1) {
        if (y % labelStep !== 0) continue;
        const [, gy] = toGridCoords(0, y);
        const label = String(y).padStart(leftMargin - 1, ' ');
        for (let i = 0; i < label.length; i += 1) if (i < axisX) grid[gy][i] = label[i];
      }
    }
  }
  return grid.map((row) => row.join('').replace(/\s+$/g, '')).join('\n');
}

function coerceGraphPoints(points) {
  if (!Array.isArray(points)) throw new Error('Graph points must be pairs, l(c), or m.');
  if (points.length === 0) throw new Error('Graph requires at least one point like {(0,0)}.');
  return points.map((item) => {
    if (!Array.isArray(item) || item.length !== 2) throw new Error('Graph points must be 2D coordinate pairs.');
    const [x, y] = item;
    if (!Number.isInteger(x) || !Number.isInteger(y)) throw new Error('Graph coordinates must be integer pairs.');
    return [x, y];
  });
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

function canonicalPrimitiveType(raw) {
  const token = raw.trim();
  const low = token.toLowerCase();
  if (low === 'bool' || low === 'boolean') return 'b';
  if (low === 'int' || low === 'integer') return 'i';
  if (low === 'float') return 'f';
  if (low === 'str' || low === 'string' || low === 's') return '£';
  if (low === 'pstring' || low === 'processedstring' || low === 'processed_string') return '&£';
  if (low === 'matrix') return 'm';
  return token;
}

function canonicalTypeName(typeCode) {
  if (!typeCode) return 'Unknown';
  if (typeCode === 'b') return 'Boolean';
  if (typeCode === 'f') return 'Float';
  if (typeCode === 'i') return 'Integer';
  if (typeCode === '£') return 'String';
  if (typeCode === '&£') return 'ProcessedString';
  if (/^i(?:2|4|8|16|32|64|128|256|512)$/.test(typeCode)) return `Integer${typeCode.slice(1)}`;
  if (typeCode === 'm') return 'MatrixCoords';
  if (typeCode === 'l(c)') return 'List<Coord>';
  if (typeCode.startsWith('l(') && typeCode.endsWith(')')) {
    return `List<${canonicalTypeName(typeCode.slice(2, -1))}>`;
  }
  return typeCode;
}

function isAllowedListElementType(typeCode) {
  const normalized = canonicalPrimitiveType(typeCode);
  if (/^(?:&£|£|b|f|c|m|i(?:2|4|8|16|32|64|128|256|512)?)$/.test(normalized)) return true;
  if (normalized.startsWith('l(') && normalized.endsWith(')')) {
    const inner = normalized.slice(2, -1).trim();
    return Boolean(inner) && isAllowedListElementType(inner);
  }
  return false;
}

function parsePointerAddress(raw) {
  const token = raw.trim();
  if (/^[+-]?\d+$/.test(token)) return Number(token);
  if (/^0x[0-9a-f]+$/i.test(token)) return Number.parseInt(token, 16);
  throw new Error(`Invalid pointer address: ${raw}`);
}


function findMatchingDelimiter(text, start, openCh, closeCh) {
  if (text[start] !== openCh) throw new Error(`Expected '${openCh}' at position ${start}.`);
  if (openCh === closeCh) {
    const end = text.indexOf(closeCh, start + 1);
    if (end === -1) throw new Error(`Unterminated expression starting with ${openCh}.`);
    return end;
  }
  let depth = 0;
  for (let i = start; i < text.length; i += 1) {
    if (text[i] === openCh) depth += 1;
    else if (text[i] === closeCh) {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  throw new Error(`Unterminated expression starting with ${openCh}.`);
}

function consumeProcessedInjection(raw) {
  if (!raw) throw new Error('Processed string injection is missing an expression after $$.');

  const consumeAtom = (segment) => {
    if (segment.startsWith('[')) return findMatchingDelimiter(segment, 0, '[', ']') + 1;
    if (segment.startsWith('"[')) return findMatchingDelimiter(segment, 1, '[', ']') + 1;
    if (segment.startsWith('|')) return findMatchingDelimiter(segment, 0, '|', '|') + 1;
    if (segment.startsWith('{')) return findMatchingDelimiter(segment, 0, '{', '}') + 1;
    if (segment.startsWith('^')) return findMatchingDelimiter(segment, 0, '^', '^') + 1;
    const typedInt = segment.match(/^i(?:2|4|8|16|32|64|128|256|512)?\^/);
    if (typedInt) return findMatchingDelimiter(segment, typedInt[0].length - 1, '^', '^') + 1;
    if (segment.startsWith('b/') || segment.startsWith("b\\")) return 2;
    if (segment.startsWith('/') || segment.startsWith("\\")) return 1;
    if (segment.startsWith('l(')) {
      const ltIdx = segment.indexOf('<');
      if (ltIdx !== -1) return findMatchingDelimiter(segment, ltIdx, '<', '>') + 1;
    }
    if (segment.startsWith('m<')) {
      const firstEnd = findMatchingDelimiter(segment, 1, '<', '>');
      if (segment[firstEnd + 1] === '<') return findMatchingDelimiter(segment, firstEnd + 1, '<', '>') + 1;
      return firstEnd + 1;
    }
    if (segment.startsWith('(')) return findMatchingDelimiter(segment, 0, '(', ')') + 1;
    throw new Error('Unsupported processed-string injection; use forms like $$[name] or $$|...|.');
  };

  let consumed = consumeAtom(raw);
  while (consumed < raw.length && (raw[consumed] === '@' || raw[consumed] === '~')) {
    consumed += 1 + consumeAtom(raw.slice(consumed + 1));
  }
  return [raw.slice(0, consumed), consumed];
}

function parseByteLiteral(raw) {
  const token = raw.trim();
  let value;
  if (/^0x[0-9a-f]{1,2}$/i.test(token)) value = Number.parseInt(token, 16);
  else if (/^\d{1,3}$/.test(token)) value = Number(token);
  else throw new Error(`Invalid byte literal: ${raw}`);
  if (value < 0 || value > 255) throw new Error(`Byte literal out of range 0..255: ${value}`);
  return value;
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
    if (existing && existing.type !== resolvedType) {
      throw new Error(`Type safety violation: variable '${name}' is ${existing.type}, cannot assign ${resolvedType}.`);
    }
    this.state.variables.set(name, { value, type: explicitType || (existing ? existing.type : resolvedType) });
  }

  simpleEval(raw) {
    if (raw.startsWith('^') && raw.endsWith('^')) return Number(raw.slice(1, -1));
    if (raw.startsWith('&£')) return raw.slice(2);
    if (raw.startsWith('£')) return raw.slice(1);
    if (raw === 'b/' || raw === '/') return true;
    if (raw === 'bfalse') return false;
    if (raw.startsWith('[') && raw.endsWith(']')) return this.readVar(raw.slice(1, -1));
    return raw;
  }


  async evaluateTypedValue(expr) {
    const raw = expr.trim();
    if (raw.startsWith('&£')) {
      let out = '';
      let idx = 2;
      while (idx < raw.length) {
        const marker = raw.indexOf('$$', idx);
        if (marker === -1) {
          out += raw.slice(idx);
          break;
        }
        out += raw.slice(idx, marker);
        const [injectedExpr, consumed] = consumeProcessedInjection(raw.slice(marker + 2));
        const { value } = await this.evaluateTypedValue(injectedExpr);
        out += String(value);
        idx = marker + 2 + consumed;
      }
      return { value: out, type: '&£' };
    }
    const value = await this.evaluateValue(raw);
    return { value, type: typeOfValue(value) };
  }

  async evaluateValue(expr) {
    const raw = expr.trim();
    const deref = raw.match(/^--([A-Za-z_]\w*)$/);
    if (deref) {
      const pointer = this.state.pointers.get(deref[1]);
      if (!pointer) throw new Error(`Undefined pointer: ${deref[1]}`);
      if (pointer.address == null) throw new Error(`Pointer '${deref[1]}' is free and cannot be dereferenced.`);
      if (pointer.address < 0 || pointer.address >= pointer.buffer.length) {
        throw new Error(`Pointer '${deref[1]}' address ${pointer.address} is out of bounds.`);
      }
      return pointer.buffer[pointer.address];
    }
    const appendSplit = splitTopLevelOperator(raw, '~');
    if (appendSplit) {
      const [leftRaw, rightRaw] = appendSplit;
      const targetMatch = leftRaw.match(/^\[([A-Za-z_]\w*)\]$/);
      if (!targetMatch) throw new Error('Append expression requires a list variable target like [list]~value.');
      const target = targetMatch[1];
      const current = this.readVar(target);
      if (!Array.isArray(current)) throw new Error('Append requires a list variable target.');
      const meta = this.state.variables.get(target);
      if (!meta || !meta.type.startsWith('l(') || !meta.type.endsWith(')')) throw new Error('Append requires a typed list variable target.');
      const elementType = meta.type.slice(2, -1);
      const { value, type } = await this.evaluateTypedValue(rightRaw);
      if (type !== elementType) throw new Error(`Type safety violation: append expects ${elementType}, got ${type}.`);
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
    if (raw.startsWith('"[') && raw.endsWith(']')) {
      const name = raw.slice(2, -1);
      if (!this.state.variables.has(name)) throw new Error(`Unknown variable: ${name}`);
      const entry = this.state.variables.get(name);
      return canonicalTypeName(entry?.type || typeOfValue(entry?.value));
    }
    if (/^i(?:\d+)?\^.*\^$/.test(raw)) {
      const typeCode = raw.slice(0, raw.indexOf('^'));
      if (!INTEGER_TYPE_PATTERN.test(typeCode)) {
        throw new Error(`Unknown integer type '${typeCode}'. Expected i, i8, i16, i32, etc.`);
      }
      const lit = raw.slice(raw.indexOf('^') + 1, -1).trim();
      if (!/^[+-]?\d+$/.test(lit)) throw new Error(`${typeCode} requires an integer literal inside ^ ^.`);
      return Number(lit);
    }
    if (raw.startsWith('&£')) return raw.slice(2);
    if (raw.startsWith('£')) return raw.slice(1);
    if (raw === 'b/' || raw === '/') return true;
    if (raw.startsWith('[') && raw.endsWith(']')) return this.readVar(raw.slice(1, -1));
    if (raw.startsWith('&')) return this.readVar(raw.slice(1));
    if (raw.startsWith('|') && raw.endsWith('|')) return safeEvalArithmetic(raw.slice(1, -1), this.state);
    if (raw.startsWith('l(c)<') && raw.endsWith('>')) return annotateListType(parsePairs(raw.slice(5, -1)), 'l(c)');
    if (raw.startsWith('m<')) {
      const parts = [...raw.matchAll(/<([^>]*)>/g)].map((m) => m[1]);
      const xs = parts[0].split(',').filter(Boolean).map(Number);
      const ys = parts[1].split(',').filter(Boolean).map(Number);
      return annotateListType(xs.map((x, i) => [x, ys[i]]), 'm');
    }
    if (raw.startsWith('l(') && raw.includes('<') && raw.endsWith('>')) {
      const typeClose = raw.indexOf(')');
      const elementTypeRaw = raw.slice(2, typeClose).trim();
      const elementType = canonicalPrimitiveType(elementTypeRaw);
      if (!isAllowedListElementType(elementType)) {
        throw new Error(`Unsupported list element type: ${elementType}`);
      }
      const body = raw.slice(raw.indexOf('<') + 1, -1);
      if (!body.trim()) return annotateListType([], `l(${elementType})`);
      const out = [];
      for (const item of splitTopLevel(body, ',')) {
        const { value, type } = await this.evaluateTypedValue(item);
        if (type !== elementType) {
          throw new Error(`Type safety violation: list expects ${elementType}, got ${type}.`);
        }
        out.push(value);
      }
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
      if (!input.isTTY) {
        this.setVar(inputStmt[1], '0', '£');
        return;
      }
      const rl = readline.createInterface({ input, output });
      const answer = await rl.question(String(prompt));
      rl.close();
      this.setVar(inputStmt[1], answer, '£');
      return;
    }

    const assign = s.match(/^\[([A-Za-z_]\w*)\]=(.*)$/);
    if (assign) {
      const { value, type } = await this.evaluateTypedValue(assign[2].trim());
      this.setVar(assign[1], value, type);
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
      const { value, type: valueType } = await this.evaluateTypedValue(append[2].trim());
      if (elementType !== valueType) {
        throw new Error(`Type safety violation: append expects ${elementType}, got ${valueType}.`);
      }
      meta.value.push(value);
      return;
    }

    const ptrBuffer = s.match(/^\+\+([A-Za-z_]\w*)==\[(.*)\]$/s);
    if (ptrBuffer) {
      const body = ptrBuffer[2].trim();
      const buffer = body ? body.split(/\s+/).map(parseByteLiteral) : [];
      this.state.pointers.set(ptrBuffer[1], { buffer, address: buffer.length ? 0 : null });
      return;
    }

    const ptrFree = s.match(/^\+\+([A-Za-z_]\w*)==$/);
    if (ptrFree) {
      this.state.pointers.set(ptrFree[1], { buffer: [], address: null });
      return;
    }

    const ptrCreate = s.match(/^\+\+([A-Za-z_]\w*)$/);
    if (ptrCreate) {
      if (!this.state.pointers.has(ptrCreate[1])) this.state.pointers.set(ptrCreate[1], { buffer: [], address: null });
      return;
    }

    const ptrAssign = s.match(/^([A-Za-z_]\w*)\+\-(.+)$/s);
    if (ptrAssign) {
      const pointer = this.state.pointers.get(ptrAssign[1]);
      if (!pointer) throw new Error(`Undefined pointer: ${ptrAssign[1]}`);
      pointer.address = parsePointerAddress(ptrAssign[2]);
      return;
    }

    const ptrMove = s.match(/^\+([A-Za-z_]\w*)([+-])(\d+)$/);
    if (ptrMove) {
      const pointer = this.state.pointers.get(ptrMove[1]);
      if (!pointer) throw new Error(`Undefined pointer: ${ptrMove[1]}`);
      if (pointer.address == null) throw new Error(`Pointer '${ptrMove[1]}' is free and cannot be shifted.`);
      pointer.address += ptrMove[2] === '+' ? Number(ptrMove[3]) : -Number(ptrMove[3]);
      return;
    }

    const ptrShift = s.match(/^-([A-Za-z_]\w*)>>(\d+)$/);
    if (ptrShift) {
      const pointer = this.state.pointers.get(ptrShift[1]);
      if (!pointer) throw new Error(`Undefined pointer: ${ptrShift[1]}`);
      if (pointer.address == null) throw new Error(`Pointer '${ptrShift[1]}' is free and cannot be shifted.`);
      pointer.address += Number(ptrShift[2]);
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
      const literalPoints = parsePairs(payload);
      const normalizedLiteral = literalPoints.map(([x, y]) => `(${x},${y})`).join('');
      const compactPayload = payload.replace(/\s+/g, '');
      const points = compactPayload === normalizedLiteral
        ? literalPoints
        : coerceGraphPoints(await this.evaluateValue(payload));
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
      for (let i = Number(forRange[1]); i < Number(forRange[2]); i += 1) {
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
