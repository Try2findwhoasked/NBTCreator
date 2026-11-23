"""Locate source members by matching a compiled frame footprint along Z."""
import numpy as np


KERNEL = np.array([1, 2, 4, 8, 4, 2, 1], dtype=float) / 8
RADIUS = len(KERNEL) // 2


class LocalFrameMatch:
    def __init__(self, model, objects, template, origin_xy, lo, hi):
        origin_x, origin_y = origin_xy
        self.lo_z = lo[2]
        self.depth = hi[2] - lo[2] + 1
        self.parts, counts = [], []
        for part in objects:
            result = np.zeros(self.depth, dtype=int)
            for x, y, _ in part['voxel_positions']:
                world_x, world_y = origin_x + x, origin_y + y
                if lo[0] <= world_x <= hi[0] and lo[1] <= world_y <= hi[1]:
                    expected = template[x, y]
                    for index in range(self.depth):
                        result[index] += model.get((world_x, world_y, self.lo_z + index)) == expected
            x, y, _ = part['bounds']['lo']
            self.parts.append((part['id'], origin_x + x, origin_y + y, len(part['voxel_positions'])))
            counts.append(result)
        self.counts = np.stack(counts)
        self.has_evidence = bool(self.counts.any())
        self.profiles = self.counts / np.asarray([part[3] for part in self.parts])[:, None]
        self.responses = {}

    def measure(self, starts, pitch):
        if not self.has_evidence:
            return dict(status='no_matching_source_evidence', strength=0., error=0., components=[])
        indices = np.asarray(starts) - self.lo_z
        # Non-overlapping windows prevent one source member from accounting for two frames.
        radius = min(RADIUS, (pitch - 1) // 2)
        if radius not in self.responses:
            kernel = KERNEL[RADIUS - radius:RADIUS + radius + 1]
            self.responses[radius] = np.stack([
                np.correlate(np.pad(profile, radius), kernel, mode='valid') for profile in self.profiles
            ])
        strength = float(np.minimum(1., self.responses[radius][:, indices]).mean())

        # Locate peaks on actual source positions. The kernel can spread their response.
        components = []
        for (name, x, y, expected), profile in zip(self.parts, self.counts):
            for index, z in zip(indices.tolist(), starts):
                positions = range(max(0, index - radius), min(self.depth, index + radius + 1))
                peak = max(positions, key=lambda p: (profile[p] * KERNEL[RADIUS + p - index], -abs(p - index), -p))
                matched = int(profile[peak])
                observed = peak + self.lo_z if matched else None
                status = ('missing' if observed is None else 'shifted' if observed != z else
                          'partial' if matched < expected else 'aligned')
                components.append(dict(component=name, status=status, expected_pos=[x, y, z],
                                       observed_pos=None if observed is None else [x, y, observed],
                                       delta_z=None if observed is None else observed - z,
                                       matched_voxels=matched, expected_voxels=expected))
        return dict(status='measured', strength=strength, error=1. - strength, search_radius=radius, components=components)
