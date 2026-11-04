"""Shared catalogue parameter validation, independent from example defaults."""
import json,math
from pathlib import Path
CATALOG=json.loads((Path(__file__).resolve().parents[1]/'tool-catalog.json').read_text(encoding='utf8'))
def validate_operation(op):
    schema=CATALOG['operation_parameters'][op['kind']]
    def check(value,s):
        if 'anyOf' in s:
            for branch in s['anyOf']:
                try:check(value,branch);return
                except ValueError:pass
            raise ValueError('Invalid operation parameter alternatives')
        kind=s.get('type')
        valid={'integer':type(value) is int,'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,'string':isinstance(value,str),'array':isinstance(value,list),'object':isinstance(value,dict)}
        if kind and not valid.get(kind,True):raise ValueError('Invalid operation parameter type')
        if 'enum' in s and value not in s['enum']:raise ValueError('Invalid operation parameter choice')
        if kind in ('integer','number'):
            if value<s.get('minimum',-math.inf) or value>s.get('maximum',math.inf) or 'exclusiveMinimum' in s and value<=s['exclusiveMinimum']:raise ValueError('Operation parameter outside limits')
        if kind=='object':
            props=s.get('properties',{})
            if any(k not in value for k in s.get('required',[])):raise ValueError('Missing nested operation parameter')
            if s.get('additionalProperties') is False and set(value)-set(props):raise ValueError('Unknown nested operation parameter')
            for k,v in value.items():
                if k in props:check(v,props[k])
        if kind=='array':
            if not s.get('minItems',0)<=len(value)<=s.get('maxItems',1000000):raise ValueError('Invalid operation parameter length')
            for item in value:check(item,s.get('items',{}))
    for key,value in op.items():
        if key in schema['properties']:check(value,schema['properties'][key])
    required=list(schema.get('required',[]))
    rule=schema.get('mode_requirements')
    if rule:
        mode=op.get(rule['field'],rule['default'])
        if mode not in rule['choices']:raise ValueError('Unknown operation mode')
        required+=rule['choices'][mode]
    if op['kind']=='selection_replace' and op.get('selection','connected')!='surface':required+=['seed_position']
    if any(key not in op for key in required):raise ValueError('Missing operation parameter: '+','.join(key for key in required if key not in op))

    def geometry(spec,depth=0):
        if depth>16 or not isinstance(spec,dict):raise ValueError('Invalid geometry nesting')
        shape=spec.get('shape')
        if shape not in CATALOG['shapes']:raise ValueError('Unknown geometry shape')
        if shape in CATALOG.get('geometry_parameters',{}):check(spec,CATALOG['geometry_parameters'][shape])
        for child in spec.get('children',[]):geometry(child,depth+1)
    if op['kind']=='geometry':geometry(op.get('geometry'))
