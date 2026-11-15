# 处理器与配方注册器

共享引擎的 `nbt_extensions.py` 提供三个显式注册器，减少扩展时修改多处分支的需要。它们由可信 Python 代码在进程启动时配置，不扫描插件目录，也不接受 JSON 中的模块路径、代码或注册指令。

| 注册器 | 处理器签名 | 用途 |
| --- | --- | --- |
| `AGENT_TOOLS` | `(workspace, arguments) -> dict` | 高层工具分派；内置实现按工具族组织并延迟导入可选依赖 |
| `RECIPE_COMPILERS` | `(workspace, arguments) -> RecipeCompilation` | 工作模型与对象图共用的构件配方编译 |
| `MODEL_ACTIONS` | `(working_model, arguments) -> dict` | 工作模型命令操作；新增操作无需在 CLI 中增加分支 |

`register(name, handler)` 和 `@register(name)` 均可使用。重复名称默认报错；替换必须显式给 `replace=True`，`unregister(name)` 可用于测试清理或受控注销。`resolve(name)` 查询处理器，未知名称报错；注册器可迭代，可用 `keys()` 检查已注册名称。注册器不是授权系统，扩展处理器仍需遵守源绑定、保护、预算、真实看图和显式定稿流程。

## 新增本地配方

```python
from nbt_extensions import RECIPE_COMPILERS, RecipeCompilation

@RECIPE_COMPILERS.register("marker_cube")
def marker_cube(workspace, arguments):
    material = arguments.get("material", "stone_bricks")
    return RecipeCompilation(spec={
        "name": "标记构件",
        "size": [1, 1, 1],
        "anchor": [0, 0, 0],
        "operations": [{
            "kind": "box", "label": "标记方块", "classification": "body",
            "lo": [0, 0, 0], "hi": [0, 0, 0], "state": material,
        }],
    })

model.install("marker", {
    "tool": "marker_cube", "arguments": {"material": "quartz_block"},
}, position=[4, 1, 4])
```

处理器返回 `spec` 或原生 `component`，两者二选一；需要提供安装接口等信息时使用 `metadata`。公共 `compile_recipe` 会执行结构构建或原生构件验证，核对尺寸、重复坐标、方块状态、墙层和内容哈希。返回后继续经过宿主保护、覆盖、总预算和实例更新检查；注册器不能把原生数据直接写进当前建筑。

`structure`、参数化、纹样、建筑跨间和 `scene_compile` 等内置配方已注册。场景专用 `span_beam` 依赖已解析的承托接口，仍由场景装配阶段处理，不作为脱离上下文的纯配方注册。已有 SNBT、实例和配方格式保持兼容。

## 暴露到 CLI、对象图或公共 Agent 工具

本地 Python 注册与公共 JSON 接口有不同边界。仅注册 `marker_cube` 后，可在该 Python 进程的工作模型中使用；公共 CLI 和对象图仍按目录中的枚举与字段校验，未声明的名称会被拒绝。

要公开一个扩展，应同时完成：

1. 在共享引擎的 Python 启动代码中显式注册处理器。新增代码放在共享 `scripts/` 中，以便冻结运行时与源码 SHA256 一起分发；不要修改已冻结的创作工作区副本。
2. 在 `tool-catalog.json` 声明相关工具或操作 Schema。新 Agent 工具登记 `agent_tools`；新配方补齐所需工作模型及 scene_compile/save/update 的配方枚举；新工作模型操作声明其 action Schema 和请求方法枚举。
3. 使用 `AGENT_TOOLS.register`、`RECIPE_COMPILERS.register` 或 `MODEL_ACTIONS.register` 接入。Agent 工具目录和注册名称必须完全一致，缺失或多余实现都会报错。工具 Schema 在处理器执行前检查。
4. 仅纯候选或只读工具才考虑加入 `agent_session.tools`；注册本身不会增加 JSON 行会话权限，保存和定稿继续使用各自入口。
5. 从软件项目根目录运行 `mise exec -- npm run sync:tools`、`mise exec -- npm run check:tools` 和 `mise exec -- npm run test:extensions`，再运行适用建模回归。已有创作工作区通过应用重新同步 Skill。

新工作模型操作的处理器应调用 `patch`、`install` 等现有受检方法，避免直接修改 `model.blocks` 绕过变更政策。原来的内置操作也通过注册器调用；CLI 不再以任意 `getattr` 解析请求方法。

## 缓存、进程与版本

注册可用 `version="扩展制品摘要或版本"` 显式绑定实现；默认摘要绑定函数字节码、默认值、可序列化闭包及适配器字段。外部全局状态或不可序列化对象需要显式 version，状态改变后重新注册。注册、显式替换和注销都会改变注册器版本，版本摘要纳入 `engine_revision()`。依赖引擎版本的编译缓存不会复用注册变化前的结果；已运行的 JSON 行会话会返回 `STALE_ENGINE`，需要重启。内置注册在中央模块中一次完成，延迟导入具体处理器不会被误判成引擎变更。扩展自己的额外缓存也应把引擎版本和实际输入纳入缓存键。

实现应确定且可复现。在普通任务脚本中临时注册的函数不会自动复制到别的进程或打包；若需 CLI、桌面或冻结 Skill 共用，必须将实现和显式注册纳入共享引擎。修改闭包或模块全局变量不会自动触发注册通知，应显式替换处理器或重启进程；不能把注册器理解为任意 Python 状态的热更新监控。

回归 `tests/extensions.py` 覆盖重复注册、显式替换、目录约束、两种配方返回、场景/工作模型共享、宿主保护、缓存失效以及会话重启提示。此测试只使用独立临时工作区。
