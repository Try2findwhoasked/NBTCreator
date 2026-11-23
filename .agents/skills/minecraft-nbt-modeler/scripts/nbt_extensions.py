"""Explicit trusted-Python extension points; never a JSON plugin loader.

Public schemas and session permissions remain in tool-catalog.json. Register
extensions at startup. Changes invalidate versioned caches and live sessions.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import import_module
from hashlib import sha256
import json
import marshal
from types import CodeType
import re
from threading import RLock


def implementation_token(handler, version=None):
    """A registration generation invalidates caches, this binds its implementation."""
    if version is not None:
        if not isinstance(version, str) or not version.strip():
            raise ValueError('扩展实现版本须为非空字符串')
        return sha256(version.encode('utf8')).hexdigest()

    def code_identity(code):
        constants = tuple(code_identity(value) if isinstance(value, CodeType) else value for value in code.co_consts)
        return code.replace(co_filename='', co_firstlineno=1, co_consts=constants)

    code = getattr(handler, '__code__', None) or getattr(type(handler).__call__, '__code__', None)
    body = marshal.dumps(code_identity(code)) if code else b''
    # Snapshot JSON-compatible defaults, closures and callable adapter fields.
    # Mutable globals need an explicit version and a fresh registration.
    fields = [getattr(handler, '__defaults__', None), getattr(handler, '__kwdefaults__', None),
        [cell.cell_contents for cell in (getattr(handler, '__closure__', None) or ())],
        vars(handler) if hasattr(handler, '__dict__') else None]
    descriptor = [handler.__class__.__module__, handler.__class__.__qualname__,
        getattr(handler, '__module__', ''), getattr(handler, '__qualname__', ''), fields]
    try:
        raw = json.dumps(descriptor, sort_keys=True, ensure_ascii=False,
            default=lambda value: [type(value).__module__, type(value).__qualname__]).encode('utf8')
    except (TypeError, ValueError, RecursionError):
        raw = json.dumps(descriptor[:4]).encode('utf8')
    return sha256(body + raw).hexdigest()


class HandlerRegistry(Mapping):
    """Named handlers with duplicate protection and deterministic revision data."""

    def __init__(self, name):
        self.name = name
        self._handlers = {}
        self._implementations = {}
        self._generation = 0
        self._lock = RLock()

    def register(self, name, handler=None, *, replace=False, version=None):
        if type(replace) is not bool:
            raise ValueError('替换注册须显式使用布尔开关')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,127}', name):
            raise ValueError('注册名称无效：' + str(name))
        if handler is None:
            return lambda function: self.register(name, function, replace=replace, version=version)
        if not callable(handler):
            raise TypeError('注册处理器须可调用')
        with self._lock:
            if name in self._handlers and not replace:
                raise ValueError('处理器已注册：' + self.name + '/' + name)
            self._implementations[name] = implementation_token(handler, version)
            self._handlers[name] = handler
            self._generation += 1
        return handler

    def unregister(self, name):
        with self._lock:
            handler = self._handlers.pop(name)
            self._implementations.pop(name)
            self._generation += 1
            return handler

    def __getitem__(self, name):
        with self._lock:
            return self._handlers[name]

    def __iter__(self):
        with self._lock:
            return iter(tuple(sorted(self._handlers)))

    def __len__(self):
        with self._lock:
            return len(self._handlers)

    def resolve(self, name):
        try:
            return self[name]
        except KeyError:
            raise ValueError('未注册处理器：' + self.name + '/' + str(name)) from None

    def revision(self):
        with self._lock:
            return self.name, self._generation, tuple(sorted(self._implementations.items()))


@dataclass(frozen=True)
class _LazyTool:
    module: str
    handler: str
    tool: str

    def __call__(self, workspace, arguments):
        return getattr(import_module(self.module), self.handler)(workspace, self.tool, arguments)


@dataclass(frozen=True)
class RecipeCompilation:
    """Return a spec OR component; the shared compiler validates the result."""
    spec: dict | None = None
    component: dict | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _AgentRecipe:
    tool: str

    def __call__(self, workspace, arguments):
        from nbt_agent.structure import dispatch
        if arguments.get('preview') or arguments.get('review'):
            raise ValueError('纯配方编译不接收预览或审阅写入选项')
        result = dispatch(workspace, self.tool, arguments)
        return RecipeCompilation(spec=result['spec'], metadata=result)


def _structure_recipe(workspace, arguments):
    return RecipeCompilation(spec=arguments)


@dataclass(frozen=True)
class _ModelAction:
    method: str

    def __call__(self, model, arguments):
        return getattr(model, self.method)(**arguments)


AGENT_TOOLS = HandlerRegistry('agent_tools')
RECIPE_COMPILERS = HandlerRegistry('recipe_compilers')
MODEL_ACTIONS = HandlerRegistry('model_actions')


# Lazy adapters keep optional compute/render dependencies off the import path.
# A new public tool needs one registry entry and its catalogue contract.
_TOOL_GROUPS = {
    '_handle_compute_info': ('compute_info',),
    '_handle_field_compile': ('field_compile',),
    '_handle_pattern_warp': ('pattern_warp',),
    '_handle_architecture': ('tracery_compile', 'vault_compile', 'bay_compile', 'facade_compile'),
    '_handle_mount_batch': ('mount_batch', 'surface_decorate'),
    '_handle_scene': ('scene_compile', 'scene_save', 'scene_read', 'scene_update'),
    '_handle_pattern_filter': ('pattern_filter',),
    '_handle_pattern_repeat_detect': ('pattern_repeat_detect',),
    '_handle_pattern_create': ('pattern_create',),
    '_handle_pattern_assets': ('pattern_assets',),
    '_handle_pattern_cylinder_mount': ('pattern_cylinder_mount',),
    '_handle_pattern': ('pattern_list', 'pattern_compile', 'pattern_preview', 'pattern_microfit'),
    '_handle_surface': ('parametric_surface', 'parametric_mount', 'parametric_layout', 'pattern_mount'),
    '_handle_composition': ('parametric_compose', 'parametric_regenerate'),
    '_handle_contract': ('parametric_contract',),
    '_handle_parametric_validate': ('parametric_validate',),
    '_handle_parametric_list': ('parametric_list',),
    '_handle_parametric': ('parametric_compile', 'parametric_preview'),
    '_handle_structure_save': ('structure_save',),
    '_handle_structure_list': ('structure_list',),
    '_handle_structure_read': ('structure_read',),
    '_handle_structure_view': ('structure_view',),
    '_handle_structure_preview': ('structure_preview',),
    '_handle_structure_write': ('structure_write',),
    '_handle_structure_place': ('structure_place',),
}
for _handler, _tools in _TOOL_GROUPS.items():
    for _tool in _tools:
        AGENT_TOOLS.register(_tool, _LazyTool('nbt_agent.structure', _handler, _tool))

RECIPE_COMPILERS.register('structure', _structure_recipe)
for _tool in ('parametric_compile', 'pattern_compile', 'pattern_microfit', 'surface_decorate',
              'bay_compile', 'vault_compile', 'tracery_compile', 'facade_compile', 'field_compile', 'scene_compile'):
    RECIPE_COMPILERS.register(_tool, _AgentRecipe(_tool))

for _method in ('install', 'preflight_update', 'update', 'remove', 'detach', 'patch', 'apply_operations',
                'beam_rhythm', 'adopt_beam_rhythm', 'wavelet_eave', 'adopt_wavelet_eave',
                'site_selection', 'adopt_site_selection', 'seal', 'open_declared'):
    MODEL_ACTIONS.register(_method, _ModelAction(_method))


def revision_token():
    from nbt_fit_shapes import FIT_SHAPES
    from nbt_building.construction_systems import CONSTRUCTION_SYSTEMS
    from nbt_building.plan import DESIGN_CHECKS
    from nbt_building.workflow import ARCHITECT_ACTIONS
    return tuple(registry.revision() for registry in (AGENT_TOOLS, RECIPE_COMPILERS, MODEL_ACTIONS, FIT_SHAPES,CONSTRUCTION_SYSTEMS,DESIGN_CHECKS,ARCHITECT_ACTIONS))


def compile_recipe(workspace, recipe):
    """Shared by object scenes and the working model, including local plugins."""
    from copy import deepcopy
    from nbt_agent.structure import build
    from nbt_assets.components import validate
    if not isinstance(recipe, dict) or set(recipe) != {'tool', 'arguments'} or not isinstance(recipe['arguments'], dict):
        raise ValueError('构件配方须含 tool 和 arguments 对象')
    result = RECIPE_COMPILERS.resolve(recipe['tool'])(workspace, deepcopy(recipe['arguments']))
    if not isinstance(result, RecipeCompilation) or (result.spec is None) == (result.component is None):
        raise ValueError('配方编译器须返回 RecipeCompilation，并在 spec/component 中二选一')
    if not isinstance(result.metadata, dict):
        raise ValueError('配方编译元数据须为对象')
    data = validate(result.component) if result.component is not None else build(workspace, result.spec)
    return data, deepcopy(result.metadata)
