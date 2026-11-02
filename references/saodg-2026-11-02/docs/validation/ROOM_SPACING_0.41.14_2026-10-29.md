# 一格间隔与居中门（0.41.14）

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

用户要求房间之间多一格距离、门生成在中间。实现提交 `cf91d55a59f7`，旋转夹具适配 `c1883a10a924`，清理清单一致性校验 `6fdac55dfa15`。

模板和布局图仍用 48 格本地坐标，统一转换为 49 格物理单元。相邻外墙间只有一格连接，补齐石砖地面、侧墙和顶板；原墙面两侧打开，主线煤炭门只占中央层。支路不加门，未使用出口仍用石砖封闭。多格房每个内部拼接处补无门连接；旋转后的结构、刷怪/秘密/控制点、实际开门命中、出口粒子和地图位置统一换算。封印大厅继续用室内传送门将成员送到独立首领区，无步行首领走廊。

新实例和作者预览按 `stride=49` 持久化清理范围；缺失字段的旧清单仍按 48，混合/部分缺失/错误类型/未知值拒绝，不猜测清理范围。实例内判断、宠物扫描与回收票据、预算清理都读取范围实际间距。世界日志写 schema 3、读 1/2/3；作者预览写 schema 2、读 1/2。旧局仍依原策略重启中止/回程/清理，不能热转换现有地图。旧二进制拒绝新日志，降级须停服恢复一致备份；没有执行整世界升级/回退实验。

## 实际检查

| 源码 | 场景与日志 | 结果 |
| --- | --- | --- |
| `cf91d55a59f7` 独立导出 `.gradle/spacing-cf91d55a59f7` | `test --tests cn.saodg.domain.layout.RoomGeometryTest` 和 `runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_spacing,saodg_combat,saodg_map' -PgameTestRunDirectory=run/gameTestServer-spacing-04114-20261029`；`logs/spacing-04114-targeted-20261029.log` | 1 项 JUnit、4 项 required GameTest 通过，89 秒，退出 0。实局内部 3 次完整成功、必要敌人消失中止、确认死亡失败；中央煤炭层、两侧开放、内部无门通道、真实开门碰撞、奖励/清理与地图投影断言通过。 |
| `c1883a10a924` 打包导出 `.gradle/source-release-c1883a10a924-20261029-011357-b38bd959` | `runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_traversal -PgameTestRunDirectory=run/gameTestServer-spacing-traversal-04114-20261029`；`logs/spacing-traversal-04114-20261029.log` | 1 项 required 通过，88 秒，退出 0。日志复核 28 模板×4 朝向共 112 个互异实际放置、碰撞遍历、交互射线及清理案例。 |
| `6fdac55dfa15` 最终打包导出 | `runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_spacing -PgameTestRunDirectory=run/gameTestServer-spacing-manifest-04114-20261029`；`logs/spacing-manifest-04114-20261029.log` | 2 项 required 通过，46 秒，退出 0。新旧清单往返、部分缺失/混合/错误类型/未知间距拒绝；48 格旧边界和 49 格新间隔实际清理，范围外石砖保留，票据释放。 |

所有命令使用固定 JDK 17、根缓存、`'-Dnet.minecraftforge.gradle.check.certs=false' --offline --console=plain`，只在独立导出编译，未触碰当前客户端输出。初次未引号的命名空间逗号命令被 PowerShell 解析器拒绝，未启动任务；随后加引号执行。三个运行时进程都正常保存全维度退出。没有重跑全量测试或 50 局耐久；此前 0.41.13 的 50 局记录不外推成 0.41.14 耐久证明。

## 最终开发包

- 文件：`D:\Documents\Coding\Game\Minecraft\SAODG\build\verified\0.41.14-dev-6fdac55dfa15-20261029-011654-730a73bf\saodg-0.41.14-dev.jar`
- SHA256：`62635f2e63ee55eb513f29df1d774d0824de3633d6e0982854482fd913ad8fdb`
- `python tools/build_verified_release.py --java-home D:/Java/jdk-17 --package-only`，日志 `logs/package-04114-final-20261029.log`，退出 0；41 个结构与资源/版本/中文键/Mixin refmap/发布排除项检查通过。打包工具没有执行 JUnit，定向结果见上表。
- 协议 19、内容 ruins-dev-20。只改新生成的物理间距，无结构 NBT 再生成，用户 beta 资源未动。原整合包/原服未安装；正式入场门禁未解除。
- 尚未启动 0.41.14 客户端或取得新画面人工反馈。当前改动不宣称真实客户端联机、SAO/KubeJS/枪械/宠物或目标整合包性能通过。
