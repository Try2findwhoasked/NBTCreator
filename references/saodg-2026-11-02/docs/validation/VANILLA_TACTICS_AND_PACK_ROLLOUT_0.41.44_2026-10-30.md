# 原版怪战术角色与三端接入第一步

## 可玩内容

生产提交 `482f66e5777c`，0.41.44。普通房/精英房的显式波次行为现在同时适用于原版僵尸身体，原先原版测试配置跳过这些行为。重卫扇形横扫、游击者直线刃气、咏唱者定点圆环沿用现有参数与服务端碰撞/房间/视线约束，具备粒子、音效与文字预警。星标名称保留角色名称，清房与主路钥匙规则不变。原版身体仍使用原版外观，不宣称已增加新怪物模型或新建筑。

调度器只接受实际登记并入索引的原版Zombie或既有自定义敌人；对象身份与世界索引共同约束。原版Mob近战在实际战术控制器存在时停用，伤害仍由预警后的服务端范围攻击产生，防止贴身攻击绕过预警。其他怪物、同UUID/NBT替身不获得控制器身份。实际健康值降低经setHealth返回后的观察器记录，取消伤害不打断，伤后同tick回血不抹掉打断；退出时清理控制器。

从提交导出执行 `jar reobfJar runGameTestServer -PgameTestNamespaces=saodg_vanilla_tactical` 成功，日志 `logs/vanilla-tactical-482f66e-20261030.log` 明确执行1项并全部通过。测试实际原版身体登记/入索引、禁止未预警近战、复制体与普通怪负例、取消伤害、实际受伤后同tick回血及关闭清理。没有验证实际整合包的主动走位/预警命中、三种角色完整战斗、客户端效果或平衡，不把本次窄检查外推为完整联机通过。

产物 `build/verified/0.41.44-dev-482f66e5777c-vanilla-tactical-20261030/saodg-0.41.44-dev.jar`，SHA256 `8a4b691b75412429ed44563aa5bdce653ae987a7704bac2c8c7b6b9db3c3484b`。41个既有结构，未包含用户beta建筑、工作区未提交文件或测试夹具。未重跑完整套件。

## 用户确认的三端关系

| 角色 | 当前目录 | 核对结果 |
| --- | --- | --- |
| 服务器开发源码 | `D:/Documents/Coding/Game/Minecraft/Saomodpackdevidkwhy` | 静态脚本仓库，没有运行mods目录；保留现有NPC/商店工作 |
| 服务器本体 | `D:/Documents/Coding/Game/Minecraft/SAO-server-0.7` | r234核心、KubeJS build.26、FTB Teams已存在，没有SAODG JAR |
| 客户端本体 | `D:/Minecraft/.minecraft/versions/SAO-0.8` | 用户确认替代已不存在的SAO-0.76路径；已装SAODG 0.41.15 |

服务器核心JAR SHA256 `4d6ff00c…d9b`，客户端 `d64bb5b7…fdf`。比较实际ZIP内容：共同类仅 `com/sao/saomenu/forge/SAOMenuForgeHud.class` 和 `com/sao/saomenu/mixin/GuiMixin.class` 不同，客户端另有1个类。保留各自核心，不因同名r234而互相覆盖，也不据此证明所有兼容入口通过。

三个生命缩放脚本是不同基线。新增客户端精确补丁 `compat/patches/saodg-sao-client-0.8-mob-scaling.patch`，源散列 `58c4abb1…95815`，合并后 `a61e4f38…0157`；保留既有 `saoArenaRun075` 竞技场排除。合并语法检查与三份实际合并脚本的受管抑制/普通怪保留/可选桥缺失行为检查通过，客户端竞技场排除也检查通过。不能把其他端整份脚本覆盖给客户端。

## 已落地的开发源码改动

在开发源码仓库当前分支 `fix/npc-interaction-feedback` 形成独立提交 `1581a80`：6个optional兼容脚本、4个默认关闭配置、配置Git忽略例外以及精确单行生命缩放判断。没有导入MOD二进制、世界、人物数据，没有混入既有10份用户修改。回滚原始文件/新增项清单保存在SAODG的 `logs/development-pack-integration-9345dee7/receipt.json` 与同目录原件。未push，不触发该仓库push main部署流程；现有NPC/商店修改内容和状态保持。

本次没有声称已有钱包、市场、原生额外收益等旧脚本全部接入。开发配置保持disabled，未配置正式等级和任务ID；默认外部资产能力未知时拒绝相应路径，不伪造钱包所有者或开放正式经济。

## 暂存更新与后续

`tools/prepare_pack_rollout.py` 接受三角色路径、已核验开发JAR和全新build输出路径，只读源包，暂存分角色文件与逐项前后散列。可识别源码端已经应用的缩放补丁，禁止把不同版本混套；不访问世界/人物/令牌，不启动服务，不执行部署。

当前暂存目录 `build/integration/0.41.44-20261030-v2/`：开发脚本、服务器JAR/脚本、客户端JAR/独立脚本补丁和 `rollout.json`。这是接入材料，不是已部署整合包；尚未移除客户端0.41.15或替换正式服文件。独立私有验收服仍0.41.42。

接下来需要按三端各自版本合并钱包和旧战斗收益保护，在开发运行环境验证新角色实际攻击，再同步运行端的模组与脚本。正式奖励用途、材料兑换、房间丰富度、真实联机/GUI与平衡仍属于目标内未完成工作。
