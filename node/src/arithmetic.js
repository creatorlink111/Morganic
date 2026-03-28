function safeEvalArithmetic(expr, state) {
  const replaced = expr.replace(/`([A-Za-z_]\w*)/g, (_, name) => {
    if (!state.variables.has(name)) {
      throw new Error(`Unknown variable in arithmetic: ${name}`);
    }
    const value = state.variables.get(name).value;
    if (typeof value !== 'number') {
      throw new Error(`Non-numeric variable in arithmetic: ${name}`);
    }
    return String(value);
  });

  if (!/^[0-9+\-*/%().\s]+$/.test(replaced)) {
    throw new Error(`Unsafe arithmetic expression: ${expr}`);
  }

  // eslint-disable-next-line no-new-func
  const result = Function(`"use strict"; return (${replaced});`)();
  if (!Number.isFinite(result)) {
    throw new Error(`Invalid arithmetic result: ${expr}`);
  }
  return result;
}

module.exports = { safeEvalArithmetic };
