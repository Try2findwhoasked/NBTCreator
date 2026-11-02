# SAODG 结构工作台

统一管理模组已接入结构与作者结构库。代码位于 `tools/structures/workbench/`，数据位于 `build/structure_workbench/`；与原 `.agents/skills/minecraft-nbt-modeler/启动网页细节控制台.cmd` 分开。

双击仓库内 `tools/启动结构工作台.cmd`，或运行：

```powershell
python tools/structures/workbench/launch.py
```

支持 `--workspace <仓库>`、`--port <端口>`、`--no-open`、`--library` 和 `--data-root <独立数据目录>`。页面顶部两个标签在同一个本地服务中切换：

| 功能 | 读取与管理 |
| --- | --- |
| 模组结构管理 | 实际 `src/main/resources/data/saodg/rooms`、`dungeons` 和 `structures`。筛选用途/形状，勾选房间池、编辑0～100选择优先级、查看分层引用与实际NBT预览。 |
| 作者结构库 | `nbt_models` 的完整主模型。中文名、形状、历史版本、哈希匹配封面、收藏、批量选择清单及JSON导出。 |

模组配置先作为草稿，审核后写入目标room_pool/selection_priority，保留其他字段与NBT。缺失模板、过期资源修订及移除最后一个必要用途房间会被拦截。保存原始字节备份，失败回滚；这里只检查静态条件，不代替Java布局生成和游戏验收。源码修改需重新构建并更新模组，不自动部署。

作者素材的“在细节控制台中打开”会另起一个端口和子进程，打开原细节控制台并定位该完整模型；工作台不嵌入编辑表单或挂载细节控制台API。原启动器继续独立可用。关闭工作台服务会关闭它按需创建的预览与编辑子进程，不关闭用户另外启动的控制台。

## 目录与依赖

- `server.mjs`：独立Node HTTP服务；`web/`：原生HTML/CSS/JS，无前端构建步骤。
- `api/`：模组配置管理和作者收藏清单；`backend.py`：SAODG模板回读/合成/保存；`library_backend.py`：作者索引/封面。
- `toolkit.py`：显式复用当前工作区NBT基础库。需要Python及该skill的numpy/Pillow依赖；可用 `SAODG_NBT_TOOLKIT` 指定另一份完整安装位置。
- 普通列表/图片浏览不启动细节控制台、不加载WebGL。实际NBT的按需3D预览复用基础viewer，需其Node≥20.19和锁定npm依赖；Python命令使用启动器所用的当前解释器。

服务只绑定127.0.0.1，拒绝跨站请求，文件只通过已登记资源ID提供。管理器不删除模板，不修改存档或精修批准记录。

## 数据与兼容

新数据统一写入 `build/structure_workbench/`：收藏清单、索引、封面、只读3D快照、配置变更备份和锁。首次启动复制旧 `build/nbt_control/structure_library.json` 与管理器变更备份，记录SHA256迁移清单并保留旧字节；已有新数据不覆盖。细节控制台原有参数、效果、意见及工作目录维持原用途。

原skill目录的作者库/模组管理器启动器仅作兼容跳转；新增管理代码和页面不再存放于细节控制台目录。`nbt_detail_web.py --library/--mod-structures` 同样转发到本工作台，默认无参数仍启动原细节控制台。

## 验证

在仓库根目录使用全新输出目录：

```powershell
python tools/structures/workbench/tests/check_backend.py --output build/workbench_test/backend
node tools/structures/workbench/tests/test-mod-structures.mjs --fixture build/workbench_test/backend/workspace --output build/workbench_test/mod_ui
node tools/structures/workbench/tests/test-library.mjs --fixture <check_detail_control_fixtures输出> --output build/workbench_test/library_ui
node tools/structures/workbench/tests/test-separation.mjs --fixture build/workbench_test/backend/workspace --model <完整主模型JSON.GZ> --output build/workbench_test/separation
```

浏览器测试显式复用基础工具提供的Playwright启动器，测试只编辑合成工作区。迁移清单、真实生产内容审计、单元/浏览器测试及游戏验证分别报告。共享仓库Python工具测试仍使用根AGENTS.md命令；原细节控制台浏览器回归仍留在其自己的viewer目录。
