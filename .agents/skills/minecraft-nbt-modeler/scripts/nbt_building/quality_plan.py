"""Expand the frozen building assessment checklist into stable scoring items."""

RUBRIC = 'building-quality-v1'
DIMENSIONS = ('completion', 'aesthetics', 'circulation', 'style', 'details')
EXPERIENCE = {
    'turning_stops': '按声明的转身、停靠及使用空间复核各站',
    'wayfinding': '从玩家视角核对岔路及目标能否识辨',
    'purpose_fit': '按活动用途核对绕行、行程及流线',
}


def index(rows, label):
    result = {row['id']: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('质量清单 ID 重复：' + label)
    return result


def items(plan):
    quality = plan.get('quality', {})
    requirements = index(plan.get('requirements', []), 'requirements')
    locations = index(plan.get('review_locations', []), 'review_locations')
    activities = index(plan.get('activities', []), 'activities')
    views = index(plan['views'], 'views')
    rules = index(plan.get('rules', []), 'rules')
    parts = {row['id'] for key in ('parts', 'stairs', 'connections') for row in plan.get(key, [])}
    if plan.get('envelope'):
        parts.add('envelope')
    spaces = index(plan['spaces'], 'spaces')
    result = {}

    def add(dimension, group, key, row, **conditions):
        identifier = '.'.join(filter(None, (dimension, group, key)))
        target = row.get('target', {})
        if set(target).isdisjoint({'part', 'location', 'position'}) and 'target' in row:
            raise ValueError('质量项须登记位置或构件：' + identifier)
        if 'part' in target and target['part'] not in parts:
            raise ValueError('质量项引用未知构件：' + identifier)
        if 'position' in target and any(v >= n for v, n in zip(target['position'], plan['size'])):
            raise ValueError('质量项位置越界：' + identifier)
        location = locations.get(target.get('location'))
        if 'location' in target and location is None:
            raise ValueError('质量项引用未知审阅位置：' + identifier)
        selected = row.get('views', [])
        if len(set(selected)) != len(selected) or set(selected) - views.keys():
            raise ValueError('质量项机位不存在或重复：' + identifier)
        if location and selected and not set(selected) <= set(location['views']):
            raise ValueError('质量项机位未绑定目标位置：' + identifier)
        result[identifier] = dict(id=identifier, dimension=dimension, group=group, **conditions,
                                  **{k: v for k, v in row.items() if k != 'id'},
                                  view_conditions={name: views[name] for name in selected},
                                  location=location)

    metadata = index(quality.get('requirements', []), 'quality.requirements')
    if metadata.keys() - requirements.keys():
        raise ValueError('质量清单引用了未知需求')
    check_ids = {
        'requirement_targets': requirements.keys(), 'space_samples': spaces.keys(),
        'part_presence': {row['id'] for row in plan.get('parts', [])},
        'bearing_contact': {row['id'] for row in plan.get('connections', [])},
        'stair_segments': {row['id'] for row in plan.get('stairs', [])},
        'stair_accessories': {row['id'] + '_accessories' for row in plan.get('stairs', [])},
        'activity_routes': activities.keys(),
    }
    for kind in ('palette', 'extent', 'argument', 'ratio', 'proportion'):
        check_ids[kind] = {name for name, rule in rules.items() if rule['kind'] == kind}
    for name, requirement in requirements.items():
        row = dict(required=True, stage=quality.get('stage'), goal=requirement['text'])
        row.update(metadata.get(name, {}))
        for check in row.get('checks', []):
            if check['id'] not in check_ids[check['kind']]:
                raise ValueError('需求引用了未知检查：' + name)
        if row['stage'] != quality.get('stage') and not row.get('not_applicable'):
            row['not_applicable'] = '需求属于其他阶段：' + row['stage']
        add('completion', name, None, row, requirement=requirement,
            target_locations=[locations[key] for key in requirement.get('review_locations', [])],
            target_spaces=[spaces[key] for key in requirement.get('spaces', [])])

    entrance_views = {name for name, view in views.items() if 'feet' in view}
    massing_views = {name for name, view in views.items() if view['layer'] == 'massing'}
    for name, row in index(quality.get('aesthetics', []), 'quality.aesthetics').items():
        selected = set(row.get('views', []))
        if not row.get('not_applicable') and not selected:
            raise ValueError('美观度判据须登记取证机位：' + name)
        if name in ('massing', 'view_coherence') and not row.get('not_applicable'):
            if not selected & massing_views or not selected & entrance_views:
                raise ValueError('整体视觉判据须同时登记整体机位和玩家机位：' + name)
        add('aesthetics', name, None, row)

    settings = index(quality.get('activities', []), 'quality.activities')
    if settings.keys() - activities.keys():
        raise ValueError('通路体验引用了未知活动')
    for name, activity in activities.items():
        setting = settings.get(name, {})
        related = setting.get('requirements', [])
        if set(related) - requirements.keys():
            raise ValueError('活动关联了未知需求：' + name)
        applicable = {k: setting[k] for k in ('not_applicable',) if k in setting}
        common = dict(activity=activity, required=setting.get('required', True), linked_requirements=related)
        segments = index(setting.get('segments', []), name + '.segments')
        if segments and (len(segments) != len(activity['stops']) - 1 or setting.get('criteria')):
            raise ValueError('分段评分须按停靠顺序覆盖每段，并使用段内判据：' + name)
        scopes = list(segments.values()) if segments else [setting]
        for index_, scope in enumerate(scopes):
            prefix = scope['id'] + '.' if segments else ''
            segment_condition = dict(segment_index=index_) if segments else {}
            criteria = index(scope.get('criteria', []), name + '.' + prefix)
            for key, goal in dict(clearance='宽 1.2 格、高 1.8 格的沿途空间', **EXPERIENCE).items():
                row = dict(criteria.get(key, dict(goal=goal)), **applicable)
                add('circulation', name, prefix + key, row, **common, **segment_condition)

    quantitative_voxels = 0
    for name, feature in index(quality.get('style', []), 'quality.style').items():
        for site, row in index(feature['sites'], name).items():
            rule = rules.get(row.get('rule'))
            if 'rule' in row and (rule is None or row['target'].get('part') not in rule['parts']):
                raise ValueError('风格规则须检查该部位的目标构件：' + site)
            config = row.get('quantitative')
            if not row.get('not_applicable') and not (row.get('views') or rule or config):
                raise ValueError('风格部位须登记量化测量、实测规则或机位：' + site)
            if rule and not row.get('views') and not config and len(rule['parts']) != 1:
                raise ValueError('自动风格评分要求规则仅检查一个部位：' + site)
            materials = {role: plan['style'].get('materials', {}).get(role)
                         for role in rule.get('roles', [])} if rule else {}
            measurement = {}
            if config:
                from nbt_building.style_measurement import METHOD, MAX_PLAN_VOXELS, validate
                palette = plan['style'].get('materials', {})
                quantitative_voxels += validate(config, plan['size'], parts, palette, site)
                if quantitative_voxels > MAX_PLAN_VOXELS:
                    raise ValueError('风格量化采样总量超过 8388608 格')
                measurement = dict(quantitative_method=METHOD, quantitative_materials={
                    role: palette[role] for member in config['members'] for role in member['roles']})
            add('style', name, site, row, feature=feature['goal'], rule_condition=rule,
                material_roles=materials, **measurement)

    for name, node in index(quality.get('details', []), 'quality.details').items():
        for key, row in index(node['criteria'], name).items():
            if not row.get('not_applicable') and not row.get('views'):
                raise ValueError('细节判据须登记近景机位：' + name + '.' + key)
            add('details', name, key, dict(row, target=node['target']))

    previous, current = set(), set()
    for row in quality.get('changes', []):
        old, new = row.get('previous'), row.get('current')
        if not (old or new) or old in previous or new in current or (new and new not in result):
            raise ValueError('评估清单变更须使用唯一且有效的新旧 ID')
        if old:
            previous.add(old)
        if new:
            current.add(new)
    return result
