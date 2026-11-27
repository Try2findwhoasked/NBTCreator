"""Fit a tensor-product Bézier patch to parameterized samples or locked edges."""
from math import comb

import numpy as np


def bernstein(values, degree):
    return np.stack([
        comb(degree, i) * values**i * (1 - values)**(degree - i)
        for i in range(degree + 1)
    ], axis=-1)


def _elevate(points, degree):
    while len(points) <= degree:
        weight = (np.arange(1, len(points)) / len(points))[:, None]
        inner = weight * points[:-1] + (1 - weight) * points[1:]
        points = np.concatenate((points[:1], inner, points[-1:]))
    return points


def _boundary_net(boundaries, degree):
    du, dv = degree
    v0, v1 = (_elevate(np.asarray(boundaries[key], dtype=float), du) for key in ('v0', 'v1'))
    u0, u1 = (_elevate(np.asarray(boundaries[key], dtype=float), dv) for key in ('u0', 'u1'))
    corners = np.array([[v0[0], v1[0]], [v0[-1], v1[-1]]])
    if not np.allclose(corners, [u0[[0, -1]], u1[[0, -1]]], rtol=0, atol=1e-8):
        raise ValueError('曲面边界端点不一致，请按 U、V 增长方向排列并核对四个角')
    u0[[0, -1]], u1[[0, -1]] = corners
    u = np.linspace(0, 1, du + 1)[:, None, None]
    v = np.linspace(0, 1, dv + 1)[None, :, None]
    corners_at_v = corners[:, :1] * (1 - v) + corners[:, 1:] * v
    bilinear = corners_at_v[:1] * (1 - u) + corners_at_v[1:] * u
    net = v0[:, None] * (1 - v) + v1[:, None] * v + u0[None, :] * (1 - u) + u1[None, :] * u - bilinear
    net[:, 0], net[:, -1] = v0, v1
    net[0, :], net[-1, :] = u0, u1
    return net


def fit_surface(arguments):
    samples = arguments.get('samples')
    boundaries = arguments.get('boundaries')
    if samples is None and boundaries is None:
        raise ValueError('曲面拟合须提供 samples、boundaries 或两者')
    if samples is None and 'max_error' in arguments:
        raise ValueError('max_error 须与 samples 一起提供')

    degree = arguments.get('degree', [3, 3])
    if boundaries is not None:
        edge_degree = [max(len(boundaries[a]), len(boundaries[b])) - 1
                       for a, b in (('v0', 'v1'), ('u0', 'u1'))]
        degree = arguments.get('degree', edge_degree)
        if any(actual < required for actual, required in zip(degree, edge_degree)):
            raise ValueError('曲面次数不能低于同方向边界的 Bézier 次数')
        net = _boundary_net(boundaries, degree)
    else:
        net = np.zeros((degree[0] + 1, degree[1] + 1, 3))

    fit = None
    if samples is not None:
        uv = np.asarray([sample['uv'] for sample in samples])
        positions = np.asarray([sample['position'] for sample in samples])
        bu, bv = (bernstein(axis, d) for axis, d in zip(uv.T, degree))
        design = (bu[:, :, None] * bv[:, None, :]).reshape(len(samples), -1)
        free = np.ones(net.shape[:2], dtype=bool)
        if boundaries is not None:
            free[[0, -1], :] = False
            free[:, [0, -1]] = False
        unknowns = int(free.sum())
        rank, condition = 0, None
        if unknowns:
            if len(samples) < unknowns:
                raise ValueError(f'曲面样点不足，当前次数至少需要 {unknowns} 个独立样点')
            matrix = design[:, free.ravel()]
            net[free] = 0
            rhs = positions - design @ net.reshape(-1, 3)
            controls, _, rank, singular_values = np.linalg.lstsq(matrix, rhs, rcond=1e-8)
            if rank < unknowns:
                raise ValueError('曲面样点的 UV 分布不足以约束全部控制点，请补充样点或降低次数')
            net[free] = controls
            condition = float(singular_values[0] / singular_values[-1])

        errors = np.linalg.norm(design @ net.reshape(-1, 3) - positions, axis=1)
        worst = int(np.argmax(errors))
        max_error = float(errors[worst])
        limit = arguments.get('max_error')
        if limit is not None and max_error > limit + 1e-9:
            raise ValueError(f'曲面最大样点误差 {max_error:.6g} 格超过 {limit:.6g} 格（样点 {worst}）')
        fit = dict(sample_count=len(samples), rmse=float(np.sqrt(np.mean(errors**2))),
                   max_error=max_error, worst_sample=worst, uv_bounds=[uv.min(axis=0).tolist(), uv.max(axis=0).tolist()],
                   solved_controls=unknowns, rank=int(rank), condition_number=condition)

    if not np.all(np.isfinite(net)) or np.max(np.abs(net)) > 1024:
        raise ValueError('拟合控制点超出 ±1024 格，请补齐 UV 覆盖或降低次数')
    return dict(patch=dict(control_points=net.tolist()), degree=degree, locked_boundaries=boundaries is not None,
                fit=fit)
