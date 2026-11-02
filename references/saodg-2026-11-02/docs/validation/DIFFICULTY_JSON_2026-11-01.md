# JSON 难度、巨像与等级纪念品验证

2026-11-01，Java 17 / Minecraft 1.20.1 / NeoForge 47.1.106，当前工作区 `0.5.3-neoforge-dev`。工作区原有队伍准备、四档难度、SAO 楼层入口等未提交修改继续保留，本记录不把它们当作本次独立完成的变更。

## 本次实现

- 新增 `config/saodg/encounters.json` 的默认复制、完整校验与按新开局重读；四档角色/种类/房间属性、密度、深度成长和加权池。
- 配置在实例占用前读取并用于原生经验数量预算；同一不可变对象写入运行快照。`EncounterTuningCodec` 版本 2 保存 JSON，版本 1 和无字段旧记录维持旧策略。
- 新增重甲卫士与宽 2.4、高 6 格的末地巨像；使用本项目模型和原版材质，不复制外部代码/资产。巨像与重甲卫士使用自身近战 AI，保留独立名称和配置移速。
- JSON 数值应用于普通、精英房、血房、小 Boss、最终 Boss、援军。保留原生 Boss 身份，保留实体登记、出生装备资产检查、碰撞布点、窄空间替代及预算。脚本战斗注册时保留配置移速；新配置弓手的实际箭矢读取攻击属性，旧快照仍保留原箭矢行为。
- 原生奖励事务端口逐级产生等级纪念章，和经验、原奖励物品共用预备、回执与提交；背包不足全部暂缓，同事务不得重复发放。独立地牢等级不增加玩家战斗属性，不追溯补发旧等级。

## 实际执行

```powershell
$env:JAVA_HOME = 'D:/Java/jdk-17'
.\gradlew.bat test --tests 'cn.saodg.domain.encounter.*' --tests 'cn.saodg.domain.reward.*' --tests 'cn.saodg.domain.progression.*' build runGameTestServer -PgameTestNamespaces=saodg_config --console=plain
python -m unittest discover -s tools -t . -p 'test_*.py' -v
python tools/verification/content_audit.py --check
.\gradlew.bat jar reobfJar --console=plain
git diff --check
```

- 最终组合命令成功；这是**带 JUnit 过滤的 build**，不是默认全套构建通过。相关 JUnit 39 个，全部通过，无跳过。
- `saodg_config` 范围 GameTest 7 个，全部通过。其中本次新增 3 个：JSON 快照/版本 1 兼容、极难巨像实际属性及弓手箭矢；完整高度生成/低顶拒绝/小体型可放置；跨多级纪念章/背包满不写经验/重复计划不重复发放/获得者记录。
- Python 35 个工具测试全部通过。
- 内容审计：80 个活动房间、5 个受保护非活动功能定义、340 个生产模板全部被引用，无错误。
- `git diff --check` 通过。
- 最终本地化帮助文字更新后重新执行 `jar reobfJar` 成功，并检查 JAR 包含 JSON、巨像渲染类、属性策略类和纪念品物品模型。

最初另执行过未过滤 `build`。已通过简单/标准各一万种子布局检查，但在后续布局检查阶段主动终止测试进程；该次构建最终失败，不能作为全套通过证据。期间并行定向 JUnit 曾遇到 Windows 测试结果文件占用，已改为前次测试结束后串行执行，最终过滤测试成功。

日志均在忽略目录 `logs/`：`difficulty-final-validation.log`、`difficulty-python.log`、`difficulty-package.log`；最初全量中止记录为 `difficulty-build.log`。

## 产物与限制

产物：`build/libs/saodg-0.5.3-neoforge-dev.jar`。

SHA-256：`610cea76fcdff6fd0b2b4497412ec487392886c79621f4ad78b5036c8a80d462`。

未启动真实图形客户端，未部署至客户端或生产服务器；巨像视觉、窄门导航、SAO/Cataclysm 运行技能与此数值组合、两客户端隔离、断线/重启恢复、单人/四人实战强度仍需整合包验收。属性受游戏与其他模组最终范围限制。JSON 为可调初始预设，测试通过不表示生产平衡已验收。纯外部自定义奖励事务端口不会自动继承原生端口的纪念品行为，需遵守对应契约。

配置说明与默认数值见 [DIFFICULTY_JSON.md](../DIFFICULTY_JSON.md)。
