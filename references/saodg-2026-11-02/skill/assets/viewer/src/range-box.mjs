import { BufferGeometry, Float32BufferAttribute, LineBasicMaterial, LineSegments } from 'three'

// Explicit, unindexed world-space edges. Avoid helper transforms and shared
// indexed draw state when rendering after the structure's multiple passes.
export class RangeBox extends LineSegments {
  constructor(box, color) {
    const geometry = new BufferGeometry()
    geometry.setAttribute('position', new Float32BufferAttribute(new Float32Array(72), 3))
    super(geometry, new LineBasicMaterial({color, toneMapped:false, depthTest:false, depthWrite:false, transparent:true, opacity:.95}))
    this.box = box
    this.frustumCulled = false
    this.lastBounds = ''
  }

  updateMatrixWorld(force) {
    const bounds = [...this.box.min.toArray(), ...this.box.max.toArray()]
    const key = bounds.join(',')
    if (key !== this.lastBounds) {
      const positions = this.geometry.attributes.position
      let index = 0
      for (let axis = 0; axis < 3; axis++) {
        const other = [0,1,2].filter(i => i !== axis)
        for (let a = 0; a < 2; a++) for (let b = 0; b < 2; b++) {
          const start = this.box.min.toArray()
          start[other[0]] = bounds[other[0]+a*3]
          start[other[1]] = bounds[other[1]+b*3]
          const end = [...start]
          end[axis] = this.box.max.getComponent(axis)
          positions.setXYZ(index++, ...start)
          positions.setXYZ(index++, ...end)
        }
      }
      positions.needsUpdate = true
      this.geometry.computeBoundingSphere()
      this.lastBounds = key
    }
    super.updateMatrixWorld(force)
  }
}
