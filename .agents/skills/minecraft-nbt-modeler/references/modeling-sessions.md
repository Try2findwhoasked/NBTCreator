# 建模会话与缓存边界

用于重复编译纯候选时复用进程和结果。首次生成、预览出图、保存新版本或定稿不需要先启动会话。参数化对象见[参数化构件](parametric-components.md)，跨对象联动见[对象图](object-scenes.md)。

## 建模会话与结果复用

微型拟合另缓存已经确定形状与颜色的单元，供不同名称、底板和铺排数量复用；尺寸、采样映射、形状选项、材质配色、误差及质量参数进入缓存身份，命中前仍读取真实图片验证SHA。世界安装、圆柱转角、保护、通路和最终预算继续逐次检查，不缓存上次安装通过的结论。

同一 Python 进程默认复用纯编译结果和通路数据。显式会话入口为 `nbt_modeling_session.ModellingSession(workspace)`，通过 `session.call(tool, arguments)` 调用相同工具；返回值仍是候选，会话不自动应用、保存、批准或导出。也可在 `with ModellingSession(workspace):` 中继续使用已有 dispatch 调用。默认缓存最多32项、估算32MiB，超限淘汰；返回深拷贝，修改上次结果不会污染下次调用。

先 pattern_microfit 再 pattern_mount / pattern_cylinder_mount 时，相同参数可复用拟合，不必让 Agent 重新计算。缓存区分工作区、原图SHA与采样参数、完整工具参数、引擎/目录/注册表版本；命中前仍核验实际图片SHA。碰撞索引按完整几何复用，路线结果另区分起终点及顺序、碰撞模式和搜索上限；每次重新计算几何指纹，模型改变后重新检查。安装面的原稿、快照、上下文哈希和保护检查保持执行。Python实现更新须重启进程。该缓存不跨进程，逐条启动CLI仍有启动开销；连续任务可在同一脚本或显式会话中运行。

### 连续调用的 JSON 行会话

外部 Agent 可运行 `node scripts/cli.mjs session --workspace <创作项目>`，保持标准输入开启，一行发送一个 JSON 请求并读取一行响应。例如：

```json
{"id":"fit-001","method":"agent","params":{"tool":"pattern_microfit","arguments":{"surface":"wall","size_uv":[4,8],"preset":"horizontal-stripes","micro_alignment":"fixed"}}}
```

响应以 id 对应请求，成功包含 ok=true、result、metrics.engine_ms 和缓存计数；失败包含 ok=false、error 和 code。能力清单的 agent_session 列出开放工具。此会话只读资产和编译候选，不开放保存、定稿、任意执行，也不生成 preview / review 文件；需要这些产物时使用原单次命令。输入最多8MiB、响应最多32MiB，超长输入关闭会话。引擎或工具目录改变后返回 STALE_ENGINE，重新启动进程后再发新请求；不自动重放失败请求。关闭标准输入即可结束。

桌面的纯候选工具和 AI 几何预检复用相同进程管理器：单进程依序处理、最多32个待办、运行超时30秒、空闲30秒退出；取消运行任务会终止其进程，其他排队请求在新进程继续。取消排队任务不影响运行邻项；关闭应用和切换工作区会关闭对应进程。预览、资产保存和显式导出继续走原入口。持续占用的缓存仅属于该进程，不跨工作区复用。

需要跨构件联动时，用[建筑对象图](object-scenes.md)保存稳定ID、尺寸引用和接触关系；scene_compile / scene_update 复验整图后返回候选，scene_save 显式保存不可变版本。它与下文一次性compose、同部件边界regenerate的适用范围不同，不自动接管已有手工几何。
