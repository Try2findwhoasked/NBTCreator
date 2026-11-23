"""Creation preferences frozen at prompt handoff."""

import re


def normalize(value=None):
    defaults = dict(mode='economy', economy_model='', quality_model='')
    if value is None:
        return defaults
    if not isinstance(value, dict) or set(value) - defaults.keys():
        raise ValueError('创作模式字段无效')
    value = defaults | value
    if value['mode'] not in ('economy', 'maximum'):
        raise ValueError('创作模式须为 economy 或 maximum')
    for key in ('economy_model', 'quality_model'):
        name = value[key]
        if not isinstance(name, str) or name != name.strip() or len(name) > 150 or re.search(r'[\x00-\x1f\x7f]', name):
            raise ValueError('模型 ID 无效')
    return value


def describe(value=None):
    policy = normalize(value)
    maximum = policy['mode'] == 'maximum'
    return dict(policy, initial_candidates=2 if maximum else 1,
                initial_role='strong' if maximum else 'economy',
                local_repairs=1 if maximum else 2,
                blind_review=maximum, model_calls_automatic=False)
