function stripComments(source) {
  let out = '';
  let i = 0;
  let inArithmetic = false;
  while (i < source.length) {
    if (source[i] === '|') {
      inArithmetic = !inArithmetic;
      out += source[i];
      i += 1;
      continue;
    }
    if (!inArithmetic && source.startsWith('%%', i)) {
      const end = source.indexOf('%', i + 2);
      if (end === -1) break;
      i = end + 1;
      continue;
    }
    if (!inArithmetic && source[i] === '%' && !source.startsWith('%%', i)) {
      const end = source.indexOf('\n', i);
      if (end === -1) break;
      i = end + 1;
      continue;
    }
    out += source[i++];
  }
  return out;
}

function splitTopLevel(source, separator = ':') {
  const parts = [];
  let current = '';
  let depthParen = 0;
  let depthBrace = 0;
  let depthBracket = 0;
  let depthAngle = 0;
  let inNumber = false;

  for (let i = 0; i < source.length; i++) {
    const ch = source[i];
    if (ch === '^') inNumber = !inNumber;
    if (!inNumber) {
      if (ch === '(') depthParen++;
      else if (ch === ')') depthParen = Math.max(0, depthParen - 1);
      else if (ch === '{') depthBrace++;
      else if (ch === '}') depthBrace = Math.max(0, depthBrace - 1);
      else if (ch === '[') depthBracket++;
      else if (ch === ']') depthBracket = Math.max(0, depthBracket - 1);
      else if (ch === '<') depthAngle++;
      else if (ch === '>') depthAngle = Math.max(0, depthAngle - 1);

      if (
        ch === separator &&
        depthParen === 0 &&
        depthBrace === 0 &&
        depthBracket === 0 &&
        depthAngle === 0
      ) {
        if (current.trim()) parts.push(current.trim());
        current = '';
        continue;
      }
    }
    current += ch;
  }

  if (current.trim()) parts.push(current.trim());
  return parts;
}

function splitStatements(source) {
  return splitTopLevel(stripComments(source), ':');
}

module.exports = {
  stripComments,
  splitTopLevel,
  splitStatements,
};
