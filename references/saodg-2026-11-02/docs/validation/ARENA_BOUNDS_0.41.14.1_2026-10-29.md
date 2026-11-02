# 独立首领区占地修正（0.41.14.1）

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

文档要求槽位内地图占地不超过 512×512。49 格物理间距下旧单元 (10,2) 放置到 x=490～537，超过限制；1024 格槽位间仍未相撞，但不符合原定占地。提交 `03f11c919b8a` 将新首领预留单元改为 (9,2)，实际模板 x=441～488，包含额外清理边缘的占地止于 489。探索区仍为 6×6，首领区继续独立、只有封印大厅传送边，没有步行连接。

历史单元 (10,2) 仍可在持久化 Region 中读取，严格保留原 cell 与 48/49 格 stride，回程/清理不会按新布局推测旧位置。去掉首领标记、非法位置、错误标记类型仍拒绝。世界日志 schema 3、协议 19 不变；内容版本 ruins-dev-21，新位置只用于新局。未执行跨进程整世界升级/清理，不把清单和边界检查外推为完整升级验收。

## 定向证据

使用最终打包工具创建的独立导出，运行：

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' test --tests cn.saodg.domain.layout.RoomGeometryTest runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_boss_arena -PgameTestRunDirectory=run/gameTestServer-arena-bounds-041141-20261029 --offline --console=plain
```

`logs/arena-bounds-041141-20261029.log`：2 项 JUnit、1 项 required GameTest 通过，46 秒，正常全维度保存，退出 0。验证实际生产 prepare 的全部结构/连接写入都落在槽位内 512×512，首领无步行边且石砖封闭出口、位置归属正确；旧 48 格无 stride 与 49 格清单的 (10,2) 精确保留并能按真实旧位置判断实例范围。此夹具没有实际把整张图放入世界；已有 0.41.14 放置/通关与 112 旋转运行记录仍是之前版本的证据，不声称本次重跑。

## 产物

- 文件：`D:\Documents\Coding\Game\Minecraft\SAODG\build\verified\0.41.14.1-dev-03f11c919b8a-20261029-012216-bc717312\saodg-0.41.14.1-dev.jar`
- SHA256：`f54200bdd69d82651a02cdb7c5c563e7bb91da8130c9bba9a794486370c08c23`
- 来源导出：`D:\Documents\Coding\Game\Minecraft\SAODG\.gradle\source-release-03f11c919b8a-20261029-012216-bc717312`
- `tools/build_verified_release.py --package-only`，日志 `logs/package-041141-20261029.log`，打包与 41 结构/资源/版本/中文键/Mixin refmap/发布排除项检查通过；工具本身未执行 JUnit，定向结果见上文。
- 未启动新客户端、未安装原整合包/原服。正式入场门禁未解除，全量联机/资产/故障矩阵仍未完成。
