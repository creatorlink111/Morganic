class RuntimeState {
  constructor() {
    this.variables = new Map();
    this.functions = new Map();
    this.classes = new Map();
    this.enums = new Map();
    this.pointers = new Map();
  }
}

module.exports = { RuntimeState };
