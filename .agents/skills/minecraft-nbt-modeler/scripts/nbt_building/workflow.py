"""Data-only architect workflow actions; schema is owned by tool-catalog.json."""
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from nbt_extensions import HandlerRegistry

ARCHITECT_ACTIONS=HandlerRegistry('architect_workflow_actions')


@dataclass(frozen=True)
class Action:
    module:str
    handler:str
    def __call__(self,workspace,request):return getattr(import_module(self.module),self.handler)(workspace,request)


for name,module,handler in (
    ('layout-check','nbt_building.planning','check'),
    ('program-layout-search','nbt_building.planning_search','search'),
    ('layout-prepare','nbt_building.planning_adapter','prepare'),
    ('plan-save','nbt_building.plan','save'),('plan-get','nbt_building.plan','stored'),
    ('part-preflight','nbt_building.plan','preflight'),
    ('layout-search','nbt_building.layout','search'),
    ('plan-build','nbt_building.plan','build'),('review-prepare','nbt_building.review','prepare'),
    ('review-recommend','nbt_building.review_recommend','recommend'),
    ('failure-replay','nbt_building.failure_replay','run'),
    ('review-record','nbt_building.review','record'),('review-compare','nbt_building.review','compare'),
    ('quality-check','nbt_building.quality_review','check'),('quality-compare','nbt_building.quality_review','compare'),
    ('game-checklist','nbt_building.review','game_checklist'),('game-record','nbt_building.review','game_record')):
    ARCHITECT_ACTIONS.register(name,Action(module,handler))


@ARCHITECT_ACTIONS.register('plan-check')
def check(workspace,request):
    from nbt_building.review import load_model
    from nbt_building.quality import BLOCKING_CODES, from_model
    from nbt_composition.working_model import ModelConflict
    model=load_model(workspace,request)
    try:
        if model.phase == 'opened' and not model.context.get('require_routes'):
            model._routes(model.model)
        validation = model.validate()
    except ModelConflict as error:
        if error.code in BLOCKING_CODES:
            error.quality = from_model(model)
        raise
    binding = model.architecture
    result = dict(validation=validation,plan=binding['plan'],plan_sha256=binding['sha256'],read_only=True)
    if 'quality' in binding['plan']:
        result['quality'] = from_model(model, validation=validation)
    return result


def dispatch(workspace,action,request):
    from nbt_runtime.catalog import catalog
    from nbt_agent.structure import _schema
    definitions=catalog()['architecture']['actions']
    if set(definitions)!=set(ARCHITECT_ACTIONS):raise ValueError('建筑工作流目录与实现不一致')
    _schema(request,definitions[action],'建筑工作流请求')
    return ARCHITECT_ACTIONS.resolve(action)(Path(workspace).resolve(),request)
