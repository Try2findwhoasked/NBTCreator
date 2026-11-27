"""Tessellate a Bézier patch and conservatively cover it with whole blocks."""
import math

import numpy as np

from nbt_assets.components import MAX_BLOCKS
from nbt_geometry.surface_fitting import bernstein


EPSILON = 1e-9
MAX_TRIANGLE_CELLS = 8_000_000


def _tessellate(net, tolerance):
    du, dv = np.asarray(net.shape[:2]) - 1
    uu = np.max(np.abs(np.diff(net, n=2, axis=0)), axis=(0, 1), initial=0) * du * (du - 1)
    vv = np.max(np.abs(np.diff(net, n=2, axis=1)), axis=(0, 1), initial=0) * dv * (dv - 1)
    uv = np.max(np.abs(np.diff(np.diff(net, axis=0), axis=1)), axis=(0, 1)) * du * dv
    # Second derivatives bound bilinear interpolation error. The mixed
    # derivative bounds the extra error from splitting the bilinear quad.
    error = (uu + vv) / 8 + uv / 4
    segments = max(1, math.ceil(math.sqrt(np.linalg.norm(error) / tolerance)))
    if segments > 128:
        raise ValueError('曲面细分超过每方向 128 段，请放宽 tolerance 或拆分曲面')
    uv_axis = np.linspace(0, 1, segments + 1)
    mesh = np.einsum('ui,vj,ijc->uvc', bernstein(uv_axis, du), bernstein(uv_axis, dv), net, optimize=True)
    return mesh, error / segments**2


def _intersects_cells(offsets, vertices, edges, normal):
    # XYZ axes are already tested by the integer candidate bounds.
    intersects = np.ones(len(offsets), dtype=bool)
    for axis in [normal, *np.cross(edges[:, None, :], np.eye(3)).reshape(-1, 3)]:
        projection = vertices @ axis
        centre = np.einsum('ij,j->i', offsets, axis)
        half_width = 0.5 * np.abs(axis).sum() + EPSILON * np.linalg.norm(axis)
        intersects &= (centre + half_width >= projection.min()) & (centre - half_width <= projection.max())
        if not intersects.any():
            break
    return intersects


def _within_radius(offsets, vertices, edges, normal, radius):
    unit_normal = normal / np.linalg.norm(normal)
    projected_inside = np.ones(len(offsets), dtype=bool)
    edge_distance_sq = np.full(len(offsets), np.inf)
    for vertex, edge in zip(vertices, edges):
        relative = offsets - vertex
        along = np.clip(np.einsum('ij,j->i', relative, edge) / (edge @ edge), 0, 1)
        nearest = relative - along[:, None] * edge
        edge_distance_sq = np.minimum(edge_distance_sq, np.einsum('ij,ij->i', nearest, nearest))
        projected_inside &= np.einsum('ij,j->i', relative, np.cross(unit_normal, edge)) >= -EPSILON
    plane_distance = np.einsum('ij,j->i', offsets, unit_normal)
    return np.where(projected_inside, plane_distance**2, edge_distance_sq) <= (radius + EPSILON)**2


def _rasterize(mesh, size, radius, budget):
    mask = np.zeros(size, dtype=bool)
    padding = max(0.5, radius) + EPSILON
    work = count = 0
    for i in range(len(mesh) - 1):
        for j in range(len(mesh) - 1):
            a, b, c, d = mesh[i, j], mesh[i + 1, j], mesh[i + 1, j + 1], mesh[i, j + 1]
            for triangle in (np.array([a, b, c]), np.array([a, c, d])):
                vertices = triangle - triangle[0]
                edges = np.roll(vertices, -1, axis=0) - vertices
                normal = np.cross(edges[0], edges[1])
                edge_scale = np.linalg.norm(edges[0]) * np.linalg.norm(edges[1])
                if np.linalg.norm(normal) <= EPSILON * edge_scale:
                    raise ValueError('曲面存在退化三角形，请检查重复控制点或收缩为一点的边界')
                lo = np.maximum(0, np.ceil(triangle.min(axis=0) - padding - 0.5).astype(int))
                hi = np.minimum(size, np.floor(triangle.max(axis=0) + padding - 0.5).astype(int) + 1)
                window = mask[tuple(slice(a, b) for a, b in zip(lo, hi))]
                work += window.size
                if work > MAX_TRIANGLE_CELLS:
                    raise ValueError('曲面体素化采样工作量超限，请减少厚度或拆分曲面')
                cells = np.argwhere(~window)
                if not len(cells):
                    continue
                offsets = cells + (lo + 0.5 - triangle[0])
                # Candidate padding can exceed the box half-width for thick shells.
                within_box_axes = np.all((offsets + 0.5 + EPSILON >= vertices.min(axis=0)) &
                                         (offsets - 0.5 - EPSILON <= vertices.max(axis=0)), axis=1)
                hits = np.zeros(len(cells), dtype=bool)
                hits[within_box_axes] = _intersects_cells(offsets[within_box_axes], vertices, edges, normal)
                if radius > 0 and not hits.all():
                    hits[~hits] = _within_radius(offsets[~hits], vertices, edges, normal, radius)
                selected = cells[hits]
                count += len(selected)
                if count > budget:
                    raise ValueError(f'曲面壳体超过方块预算 {budget}')
                window[tuple(selected.T)] = True
    return mask


def compile_surface(workspace, arguments):
    from nbt_agent.structure import build
    from nbt_collision import collision_cells
    from nbt_fields import connectivity
    from nbt_model import state

    rows = arguments['patch']['control_points']
    if len({len(row) for row in rows}) != 1:
        raise ValueError('曲面控制点须为矩形网格，每个 U 行的 V 控制点数须相同')
    net = np.asarray(rows, dtype=float)
    size = arguments['size']
    material = state(arguments.get('material', 'stone_bricks'))
    occupied, reason = collision_cells(material)
    if reason or len(occupied) != 8:
        raise ValueError('曲面壳体材质须为已知完整方块')
    thickness = arguments.get('thickness', 0)
    radius = thickness / 2
    mesh, error = _tessellate(net, arguments.get('tolerance', 0.1))
    # Intersect the control hull's bounds with the mesh/error enclosure.
    lo = np.maximum(net.min(axis=(0, 1)), mesh.min(axis=(0, 1)) - error) - radius
    hi = np.minimum(net.max(axis=(0, 1)), mesh.max(axis=(0, 1)) + error) + radius
    if np.any(lo < -EPSILON) or np.any(hi > np.array(size) + EPSILON):
        raise ValueError('显式画布无法完整容纳曲面及厚度，请平移控制网格或增大 size')

    budget = arguments.get('max_changed_blocks', MAX_BLOCKS)
    mask = _rasterize(mesh, size, radius, budget)
    points = np.argwhere(mask).tolist()
    if not points:
        raise ValueError('曲面体素化结果为空，请检查位置和画布')
    spec = dict(name=arguments.get('name', '自由曲面壳体'), size=size, max_changed_blocks=budget,
                operations=[dict(kind='paste_component', label='自由曲面壳体',
                                 classification=arguments.get('classification', 'body'),
                                 lo=[0, 0, 0], hi=[value - 1 for value in size], palette=[material],
                                 voxels=[[*point, 0] for point in points])])
    if 'anchor' in arguments:
        spec['anchor'] = arguments['anchor']
    component = build(workspace, spec)
    connection = connectivity(mask, [points[0]])
    return dict(spec=spec, block_count=len(points), content_sha256=component['content_sha256'],
                recipe=dict(tool='surface_compile', arguments=arguments), model_modified=False,
                tessellation=dict(segments_uv=[len(mesh) - 1] * 2, max_deviation_bound=float(np.linalg.norm(error))),
                thickness=thickness, connected_cells=connection['connected_cells'],
                face_connected=connection['all_selected_cells_connected'])
