"""Project a frozen prompt task without repeating its generated instructions."""

BRIEF_FIELDS = (
    'purpose', 'theme', 'style', 'footprint', 'spatial_character', 'layout', 'circulation',
    'materials', 'atmosphere', 'avoid', 'ceiling', 'floor', 'wall', 'props', 'preserve', 'extras',
)
CONSTRAINT_FIELDS = ('mode', 'require_enclosure', 'openings_policy', 'opening_size', 'cell_size')
COORDINATE_FIELDS = ('cells', 'openings', 'ports', 'interior_probes', 'protected_paths',
                     'protected_boxes', 'reserved_boxes', 'targets', 'route_legs', 'cameras')


def compact(data, previous, older):
    from nbt_agent.creation_policy import describe
    record, document, context = data['task'], data['document'] or {}, data['context'] or {}
    project = document.get('project',{})
    clipped = []

    def excerpt(value, path):
        if isinstance(value, str) and len(value) > 240:
            clipped.append(path)
            return value[:240]
        return value

    selected = document.get('constraints', [])
    rules = {key: value for row in selected for key, value in row['rules'].items()
             if key not in ('requirements', 'cells', 'footprint')}
    constraints = [dict(id=row['id'], name=row['name'], revision=row['revision'],
                        **{key: excerpt(row['rules'][key], f'document.constraints[{i}].rules.{key}')
                           for key in ('requirements', 'footprint') if key in row['rules']})
                   for i, row in enumerate(selected)]
    effective = {key: project[key] for key in ('buildingShape', 'size', 'size_policy', 'integration', 'budget')
                 if key in project}
    effective.update({k: context[k] for k in CONSTRAINT_FIELDS if k in context})
    effective.update(rules)
    if 'size' in rules and 'size_policy' not in rules:
        effective['size_policy'] = 'fixed'
    if effective.get('integration') == 'saodg' or effective.get('mode') == 'saodg':
        effective['size_policy'] = 'fixed'
    standard = document.get('design_standard') or {}
    fields = {key: excerpt(value, f'document.design_standard.fields.{key}')
              for key, value in standard.get('fields', {}).items() if value}
    change = None
    if previous is not None:
        comparable = older is not None and not data['attachment_issues']
        change = dict(task_id=previous['id'], revision=previous['revision'], available=comparable)
        if comparable:
            change['sections'] = [key for key in ('text', 'document', 'plan', 'context') if data[key] != older[key]]
            old_project = older['document']['project']
            change['project_fields'] = sorted(key for key in project.keys() | old_project.keys()
                                              if project.get(key) != old_project.get(key))
            old_document = older['document']
            change['design_fields'] = [key for key in ('constraints', 'design_standard', 'design_override', 'aiDraft','user_requirements')
                                       if document.get(key) != old_document.get(key)]
            change['creation_changed'] = describe(record.get('creation')) != describe(previous.get('creation'))
            change['context_fields'] = sorted(key for key in context.keys() | older['context'].keys()
                                              if context.get(key) != older['context'].get(key))
    operations = data['plan'].get('operations', []) if isinstance(data['plan'], dict) else None
    boxes = context.get('protected_boxes', [])
    return dict(
        view='compact', task={key: record[key] for key in ('id', 'name', 'stage', 'status', 'revision',
            'source', 'source_sha256', 'state_revision', 'lease', 'lease_expired') if key in record},
        source_matches=data['source_matches'], approval=data['approval'],
        creation=describe(record.get('creation')),
        user_requirements=excerpt(document.get('user_requirements'), 'document.user_requirements'),
        attachment_issues=data['attachment_issues'],ready_for_execution=data['ready_for_execution'],
        brief={key: excerpt(project[key], f'document.project.{key}') for key in BRIEF_FIELDS if project.get(key)},
        effective=effective, constraints=constraints, design_standard=dict(revision=standard.get('revision'), fields=fields),
        design_override=excerpt(document.get('design_override'), 'document.design_override'),
        coordinate_counts={key: len(context[key]) for key in COORDINATE_FIELDS if isinstance(context.get(key), (list, dict))},
        protected_boxes=boxes[:4] if isinstance(boxes, list) else [],
        context_path=project.get('contextPath') or None, review_path=project.get('reviewPath') or None,
        operation_count=len(operations) if isinstance(operations,list) else None,
        design_supplement_present='# 补充设计说明（以人工参数和硬条件为准）\n' in data['text'] if data['text'] is not None else None,
        previous=change, clipped=clipped, expand=['text','document','plan','context'],
    )
