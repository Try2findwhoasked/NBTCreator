"""Deterministic bounded search of orthogonal room layouts."""
from copy import deepcopy
from math import floor
from itertools import count

from nbt_building.planning import PlanningLayout, best_run, cells, contacts, result


DEFAULT_MAX_STEPS = 20_000
DEFAULT_CANDIDATE_LIMIT = 3


class SearchLimitReached(Exception):
    pass


class LayoutSearch:
    def __init__(self, request):
        self.baseline = PlanningLayout(request['program'], request.get('baseline', {'spaces': []}))
        self.locked = frozenset(request.get('locked', ()))
        if len(self.locked) != len(request.get('locked', ())):
            raise ValueError('锁定空间不可重复')
        if self.locked - self.baseline.placements.keys():
            raise ValueError('锁定空间必须在基线布局中已有区域')
        self.max_steps = request.get('max_steps', DEFAULT_MAX_STEPS)
        self.candidate_limit = request.get('candidate_limit', DEFAULT_CANDIDATE_LIMIT)
        self.attempts = 0
        self.candidates = []
        self.order = count()
        self.regions = {key: self.baseline.regions[key] for key in self.locked}
        self.placements = {key: self.baseline.placements[key] for key in self.locked}
        self.anchors = {key: set() for key in self.baseline.spaces}
        self.connected = {key: [] for key in self.baseline.spaces}
        self.stairs = []
        self.initial_issues = []
        self.branch_issues = {}

        entry_space = self.baseline.program.get('entry_space')
        if entry_space:
            self.anchors[entry_space].add(self.coordinate(self.baseline.program['entry']))
        for key, relation in self.baseline.relations.items():
            a, b = relation['from'], relation['to']
            if relation['kind'] == 'stair':
                link = self.baseline.links.get(key, {})
                if 'from_feet' not in link or 'to_feet' not in link:
                    self.initial_issues.append(result(f'relation:{key}', 'stair_anchors', True, False, None,
                                                      reason='missing_stair_landings'))
                    continue
                valid = all(link[field][1] == self.baseline.feet_y(space)
                            for field, space in (('from_feet', a), ('to_feet', b)))
                if not valid:
                    self.initial_issues.append(result(f'relation:{key}', 'stair_anchors', True, False, False,
                                                      reason='landing_height_mismatch'))
                    continue
                self.stairs.append(link)
                self.anchors[a].add(self.coordinate(link['from_feet']))
                self.anchors[b].add(self.coordinate(link['to_feet']))
            elif relation['kind'] != 'route':
                self.connected[a].append((b, relation))
                self.connected[b].append((a, relation))

        self.pending = sorted(self.baseline.spaces.keys() - self.locked,
                              key=lambda key: (-len(self.anchors[key]), -len(self.connected[key]),
                                               -self.baseline.spaces[key].get('min_area', 1), key))

    @staticmethod
    def coordinate(feet):
        return floor(feet[0]), floor(feet[2])

    def spend(self):
        if self.attempts >= self.max_steps:
            raise SearchLimitReached
        self.attempts += 1

    def layer(self, key):
        return self.baseline.levels[self.baseline.spaces[key]['level']]

    def occupied(self, key):
        level = self.layer(key)
        occupied = set()
        for previous, region in self.regions.items():
            if key == previous:
                continue
            other = self.layer(previous)
            if max(level['feet_y'], other['feet_y']) < min(level['ceiling_y'], other['ceiling_y']):
                occupied.update(region)
        return occupied

    def fits_relations(self, key, region):
        layer = self.baseline.spaces[key]['level']
        empty = self.baseline.usable[layer] - self.occupied(key) - region
        for other, relation in self.connected[key]:
            if other not in self.regions:
                continue
            lines = contacts(region, self.regions[other], empty, wall_only=relation['kind'] in ('door', 'wall'))
            width = len(best_run(lines))
            needed = relation.get('min_width', 1)
            if width < needed:
                identifier = 'relation:' + relation['id']
                self.branch_issues[identifier] = result(identifier, relation['kind'], needed, width, False,
                                                        reason='connection_in_search_branch', level=layer)
                return False
        return True

    def options(self, key):
        room = self.baseline.spaces[key]
        usable = self.baseline.usable[room['level']]
        occupied = self.occupied(key)
        available = usable - occupied
        low = room.get('min_area', 1)
        if len(available) < low or self.anchors[key] - available:
            identifier = f'space:{key}:capacity'
            missing = self.anchors[key] - available
            self.branch_issues[identifier] = result(identifier, 'search_capacity', low, len(available), False,
                level=room['level'], positions=self.baseline.positions(key, missing),
                reason='anchor_in_search_branch' if missing else 'capacity_in_search_branch')
            return
        old = self.baseline.regions[key]
        if (old and low <= len(old) <= room.get('max_area', len(available))
                and not old - available and not self.anchors[key] - old):
            self.spend()
            yield self.baseline.placements[key], old
        min_x = min(x for x, _ in available)
        min_z = min(z for _, z in available)
        max_x = max(x for x, _ in available)
        max_z = max(z for _, z in available)
        max_area = min(room.get('max_area', len(available)), len(available))
        target = room.get('target_area', low)
        span = room.get('min_span', 1)
        sizes = [(width, depth)
                 for width in range(span, min(max_x - min_x + 1, max_area // span) + 1)
                 for depth in range(max(span, (low + width - 1) // width),
                                    min(max_z - min_z + 1, max_area // width) + 1)]
        sizes.sort(key=lambda pair: (abs(pair[0] * pair[1] - target), abs(pair[0] - pair[1]), pair))
        for width, depth in sizes:
            for x in range(min_x, max_x - width + 2):
                for z in range(min_z, max_z - depth + 2):
                    self.spend()
                    right, bottom = x + width - 1, z + depth - 1
                    if any(not (x <= a <= right and z <= b <= bottom) for a, b in self.anchors[key]):
                        continue
                    box = dict(lo=[x, z], hi=[right, bottom])
                    region = cells([box])
                    if region != old and not region - available:
                        yield dict(id=key, regions=[box]), region

    def finish_candidate(self):
        draft = dict(spaces=[self.placements[key] for key in self.baseline.spaces], links=list(self.stairs))
        candidate = PlanningLayout(self.baseline.program, draft)
        for key, rule in self.baseline.relations.items():
            if rule['kind'] != 'door':
                continue
            left, right = rule['from'], rule['to']
            old = self.baseline.links.get(key)
            if old is not None and {left, right} <= self.locked:
                draft['links'].append(old)
                continue
            level = self.baseline.spaces[left]['level']
            empty = candidate.usable[level] - candidate.by_level[level]
            lines = contacts(candidate.regions[left], candidate.regions[right], empty, wall_only=True)
            run = best_run(lines)
            width = rule.get('min_width', 1)
            if len(run) < width:
                return
            x, z = zip(*(crossing[1] for crossing in run[:width]))
            draft['links'].append(dict(id=key, opening=dict(lo=[min(x), min(z)], hi=[max(x), max(z)])))
        report = PlanningLayout(candidate.program, draft).assess()
        for row in report['checks']:
            if not row['passed']:
                self.branch_issues[row['id']] = dict(row, reason='condition_in_search_branch')
        if report['passed'] and all(row['report']['layout_sha256'] != report['layout_sha256']
                                    for row in self.candidates):
            changes = sum(self.regions[key] != self.baseline.regions[key] for key in self.baseline.placements)
            self.candidates.append(dict(layout=deepcopy(draft), report=report, changed_spaces=changes,
                                        order=next(self.order)))

    def assign(self, index):
        if index == len(self.pending):
            self.finish_candidate()
            return
        key = self.pending[index]
        for placement, region in self.options(key):
            if self.fits_relations(key, region):
                self.regions[key] = region
                self.placements[key] = placement
                self.assign(index + 1)
                self.regions.pop(key)
                self.placements.pop(key)
            if len(self.candidates) >= self.candidate_limit:
                return

    def run(self):
        fixed_issues = [row for row in self.baseline.room_results()
                        if not row['passed'] and any(row['id'].startswith(f'space:{key}:') for key in self.locked)]
        # An unlocked baseline occupant can be moved out of a fixed room's way.
        fixed_issues = [row for row in fixed_issues if row['kind'] != 'space_overlap']
        for key in sorted(self.locked):
            if self.anchors[key] - self.regions[key]:
                fixed_issues.append(result(f'space:{key}:landing', 'fixed_landing', True, False, False,
                                           reason='fixed_region_misses_landing'))
        issues = self.initial_issues + fixed_issues
        if issues:
            state = 'input_required' if any(row['status'] == 'pending' for row in issues) else 'infeasible'
            return self.response(state, state, issues)
        try:
            self.assign(0)
        except SearchLimitReached:
            return self.response('found' if self.candidates else 'budget_exhausted', 'step_limit',
                                 () if self.candidates else self.branch_issues.values())
        termination = 'candidate_limit' if len(self.candidates) >= self.candidate_limit else 'exhausted'
        return self.response('found' if self.candidates else 'infeasible', termination,
                             () if self.candidates else self.branch_issues.values())

    def response(self, state, termination, issues=()):
        self.candidates.sort(key=lambda row: (row['report']['metrics']['area_target_deviation'],
                                              row['changed_spaces'], row['order']))
        for row in self.candidates:
            del row['order']
        return dict(schema_version=1, status=state, termination=termination, attempts=self.attempts,
                    candidates=self.candidates, checks=list(issues), locked=sorted(self.locked))


def search(workspace, request):
    return LayoutSearch(request).run()
