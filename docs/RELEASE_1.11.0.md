# NBTCreator 1.11.0

本版补齐工作台与外部 Agent 从设计、标注到候选检查、另存 NBT 的共用流程，保留原模型和真实精修确认。

## 建模与交接

- `feedback scan/collect/archive` 扫描当前结构版本评论索引、校验源/图/3D锚点、将引用证据按哈希归档；迁移后通过相对索引读取。
- `paths` 返回当前冻结脚本和工具版本，Agent 无需猜安装目录；入口按新建、标注、精修、交付和只读维护分阶段阅读。
- 工作台“检查当前效果”和 `validate` 调用同一实现，重新计算参数并比对所看快照，分别检查预算、保护、墙归属、密闭和静态路线。失败保留报告，参数改变使旧结果失效。
- 新增独立建筑的声明开口 API、显式 `mode/openings` 上下文及真实XYZ边块导出。自由尺寸不强制48倍数；非空有效cells限制占地，L形三格不向缺角出片。原SAODG端口规则保留。
- 几何和层归属的唯一变更坐标共同计入预算及保护；合法纯层归属修改也有实际差异记录。部分细件以有依据的保守障碍证明通路，不伪装为精确碰撞。
- coordinates.json 必须包含应用接手所需的真实起点、目标、探针和适用开口；配置缺失时仍可只读查看和评论，不能宣称已可导出。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py paths
python .agents/skills/nbtcreator-workspace/nbt.py feedback scan --workspace .
python .agents/skills/nbtcreator-workspace/nbt.py validate --request 参数.json --snapshot preview/after.json --output nbt_models/_tasks/检查_新编号
```

## 任务与运行环境

- 切换工作区会取消旧API请求、等待结束并拒绝迟到结果，内部资料读取期间的取消同样有效。
- 本地任务的前置检查、实际Python处理和后置检查都按任务登记；取消写为cancelled，保留诊断，服务关闭仅结束自己创建的进程。预览期间也可取消，取消不冒充失败或成功。
- 未完成精修目录保留writing状态，避免部分结果被建筑目录当作已完成版本。
- 同步Skill关联共享Playwright、Node/Electron和Chromium，不给每个工作区复制node_modules。打包保留独立安装锁文件，完整Chrome不会误转向未安装的headless-shell。

## 验证与交付

CI包含API/提示词/设置/工作区契约、评论迁移和证据、自由尺寸/L形/XYZ交付、候选校验、碰撞反例、精修和网页回导；打包后以私有Python/浏览器和实际Electron复验。任何失败均阻止Release。

首次使用下载完整Portable；已有兼容运行环境可只更新app-update，runtime仍可单独下载。三个包都有SHA256与逐文件清单，用户资产、密钥和工作区配置不进入发布包。更新前关闭旧程序，解压合并同名目录；旧EXE未升级时仍会同步它自己的旧Skill。

版本不自动写入游戏存档或房间池。碰撞、几何出图、设计看图和游戏验证分别记录；未执行真实游戏/多人/光照验收。全屏问题继续按用户“先记录”的要求保留在 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)，本次不触发或宣称修复。
