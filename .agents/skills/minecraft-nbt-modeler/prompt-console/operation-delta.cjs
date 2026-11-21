// Apply a validated batch against immutable one-based baseline slots, including
// identical operations. Never resolve a later edit against a shifted index.
function mergeOperationRows(operations, changes) {
  if (!Array.isArray(changes) || changes.length < 1 || changes.length > 16) throw Error('工具增量须包含1到16项修改');
  const rows = operations.map((op, index) => ({step:index+1, op:structuredClone(op)}));
  const used = new Set(), before = new Map(), after = new Map(), removed = new Set();
  function reserve(step) {
    if (!Number.isInteger(step) || step < 1 || step > rows.length || used.has(step)) throw Error('增量目标步骤或锚点无效、重复或冲突');
    used.add(step);
    return rows[step-1];
  }
  for (const change of changes) {
    const row = reserve(change.step);
    if (change.action === undefined) {
      Object.assign(row.op, structuredClone(change.set));
    } else if (change.action === 'remove') {
      removed.add(row.step);
    } else {
      if (!['insert','move'].includes(change.action) || !['before','after'].includes(change.position)) throw Error('增量结构动作或相对位置无效');
      const positions = change.position === 'before' ? before : after;
      if (change.action === 'insert') {
        positions.set(row.step, {step:null, op:structuredClone(change.operation)});
      } else {
        const anchor = reserve(change.anchor);
        removed.add(row.step);
        positions.set(anchor.step, row);
      }
    }
  }
  const result = rows.flatMap(row => [before.get(row.step), removed.has(row.step) ? null : row, after.get(row.step)].filter(Boolean));
  if (result.length > 128) throw Error('工具序列最多128项');
  return result;
}
if (typeof module !== 'undefined' && module.exports) module.exports = {mergeOperationRows};
else globalThis.mergeOperationRows = mergeOperationRows;
