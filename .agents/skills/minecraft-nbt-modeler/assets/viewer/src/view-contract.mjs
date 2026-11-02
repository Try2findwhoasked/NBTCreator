// Shared by the browser and the batch CLI. Coordinates follow Minecraft XYZ.
export function vector(value, label) {
  if (!Array.isArray(value) || value.length !== 3 || !value.every(Number.isFinite)) {
    throw new Error(`${label} must contain three finite numbers`)
  }
  return [...value]
}

export function cameraView(view) {
  const eye = vector(view.eye, 'eye')
  const target = vector(view.target, 'target')
  const up = vector(view.up ?? [0, 1, 0], 'up')
  const d = target.map((v, i) => v - eye[i])
  const cross = [d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0]]
  if (Math.hypot(...cross) < 1e-8) throw new Error('Camera needs distinct eye/target and a non-parallel up vector')
  const fov = view.fov ?? 60
  if (!Number.isFinite(fov) || fov < 10 || fov > 120) throw new Error('fov must be 10..120 degrees')
  return { eye, target, up, fov }
}

export function normalizeView(view, size, index = 0) {
  if (!view || typeof view !== 'object' || Array.isArray(view)) throw new Error('Expected a camera object')
  const allowed = new Set(['id', 'role', 'eye', 'target', 'up', 'fov', 'lighting', 'layer', 'cut_y', 'cuts'])
  for (const key of Object.keys(view)) if (!allowed.has(key)) throw new Error(`Unknown view field: ${key}`)
  const id = view.id ?? `view_${String(index + 1).padStart(3, '0')}`
  if (typeof id !== 'string' || !/^[a-z0-9][a-z0-9_-]*$/.test(id)) throw new Error('View id must be a portable lowercase basename')
  const layer = view.layer ?? 'all'
  const lighting = view.lighting ?? 'day'
  if (!['all', 'body', 'walls'].includes(layer)) throw new Error('layer must be all/body/walls')
  if (!['day', 'night'].includes(lighting)) throw new Error('lighting must be day/night')
  if (view.role !== undefined && (typeof view.role !== 'string' || !view.role.trim())) throw new Error('role must be non-empty text')
  if (view.cuts !== undefined && !Array.isArray(view.cuts)) throw new Error('cuts must be an array')
  const cuts = (view.cuts ?? []).map(cut => {
    if (!cut || typeof cut !== 'object' || Array.isArray(cut)) throw new Error('Expected a cut object')
    for (const key of Object.keys(cut)) if (!['axis', 'position', 'removed_side', 'side'].includes(key)) throw new Error(`Unknown cut field: ${key}`)
    const axis = cut.axis
    const side = cut.removed_side ?? cut.side ?? 'above'
    const position = cut.position
    if (!['x', 'y', 'z'].includes(axis) || !['above', 'below'].includes(side)) throw new Error('Invalid cut axis or removed_side')
    if (!Number.isInteger(position) || position < 0 || position > size['xyz'.indexOf(axis)]) {
      throw new Error('Texture cuts require integer block boundaries within the model; use nbt_preview for half-block diagnostic cuts')
    }
    return { axis, position, removed_side: side }
  })
  if (view.cut_y !== undefined) {
    if (!Number.isInteger(view.cut_y) || view.cut_y < 0 || view.cut_y >= size[1]) throw new Error('cut_y must be a saved Y layer')
    cuts.push({ axis: 'y', position: view.cut_y + 1, removed_side: 'above' })
  }
  return { id, role: view.role ?? id, ...cameraView(view), lighting, layer, cuts }
}

export function normalizeViews(views, size) {
  if (!Array.isArray(views) || views.length < 1 || views.length > 64) throw new Error('Provide 1..64 views')
  const result = views.map((view, index) => normalizeView(view, size, index))
  if (new Set(result.map(view => view.id)).size !== result.length) throw new Error('Duplicate view IDs')
  return result
}

export function includesBlock(position, cuts) {
  return cuts.every(cut => cut.removed_side === 'above'
    ? position['xyz'.indexOf(cut.axis)] < cut.position
    : position['xyz'.indexOf(cut.axis)] >= cut.position)
}
