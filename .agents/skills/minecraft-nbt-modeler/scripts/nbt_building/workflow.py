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
    ('plan-save','nbt_building.plan','save'),('plan-get','nbt_building.plan','stored'),
    ('part-preflight','nbt_building.plan','preflight'),
    ('plan-build','nbt_building.plan','build'),('review-prepare','nbt_building.review','prepare'),
    ('review-record','nbt_building.review','record'),('review-compare','nbt_building.review','compare'),
    ('game-checklist','nbt_building.review','game_checklist'),('game-record','nbt_building.review','game_record')):
    ARCHITECT_ACTIONS.register(name,Action(module,handler))


@ARCHITECT_ACTIONS.register('plan-check')
def check(workspace,request):
    from nbt_building.review import load_model
    model=load_model(workspace,request)
    return dict(validation=model.validate(),plan=model.architecture['plan'],plan_sha256=model.architecture['sha256'],read_only=True)


def dispatch(workspace,action,request):
    from nbt_catalog import catalog
    from nbt_structure_agent import _schema
    definitions=catalog()['architecture']['actions']
    if set(definitions)!=set(ARCHITECT_ACTIONS):raise ValueError('建筑工作流目录与实现不一致')
    _schema(request,definitions[action],'建筑工作流请求')
    return ARCHITECT_ACTIONS.resolve(action)(Path(workspace).resolve(),request)
