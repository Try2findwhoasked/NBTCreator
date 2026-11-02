# KubeJS 冷启动与重载绑定

仅在已授权的私有整合包中复制 compat/kubejs 的 6 个新增脚本、4 个默认配置，未套用针对另一脚本版本的钱包/市场补丁，也未改变旧钱包、任务或 NPC 脚本。
新增文件列表及 SHA-256 保留在私有目录 bridge-installation-20261028.json。准入配置 enabled=false，任务桥 enabled=false，资产 owner=market 仍要求真实所有者；缺少市场接口时应 UNKNOWN，不通过改 none 宣称安全。

## 实际缺陷与修复

首次 `logs/pack-kube-bridge-20261028-081137-fd148a65.log`：6 个新增脚本均加载，但冷启动没有 saodg 绑定，随后 reload 虽有对象却每秒 stale_binding。
通过实际 KubeJS 2001.6.5-build.26 字节码确认：冷启动资源脚本求值时 ServerScriptManager.server 尚可为 null；onServerReload 回调在新脚本求值之后触发，而不是之前。旧实现漏绑初次启动，又在 reload 结束时撤销了刚发出的新 facade。
0.41.6 始终向服务端脚本提供 facade，冷启动只允许读取 API/epoch 元数据，实际服务器可用且在主线程进行登记时才附着。禁止 pending facade 覆盖已登记或查询中的所有者；替换空占位状态时保留外部资产所有者期望，并撤销原状态代际。
每次注册新脚本绑定前先使旧 facade 失效，已知服务器提前 beginReload；onServerReload 不再撤销刚生成的代际。移除服务端注册时同步撤销该状态，防止旧 closure 被复用。
新增独立批次夹具覆盖冷启动未准备、正常附着、竞争 facade 拒绝、reload 旧对象拒绝、新对象有效、停服移除与废弃 pending 对象拒绝。

## 实际整合包复测

在同一已授权私有目录内安装 `0.41.6-dev`，仅监听 `127.0.0.1:25579`，未开放副本或奖励。日志为 `logs/pack-kube-lifecycle-fixed-20261028-081137-fd148a65.log`。

| 检查 | 冷启动 | `/reload` 后 |
| --- | --- | --- |
| 脚本绑定 | 有效，generation=1 | 有效，generation=3 |
| 旧 facade 调用 | 不适用 | 明确拒绝，`old_rejected=true` |
| 实际准入回调 | `saodg.integration.pack_disabled` | `saodg.integration.pack_disabled` |
| 外部资产所有者状态 | `UNKNOWN` | `UNKNOWN` |
| 管理命令检查 | scripts/admission/external-assets 为 BOUND_UNVERIFIED | 同前，未再出现循环 stale_binding |

测试脚本在服务器 tick 中构造只读准入请求，并调用上一轮捕获的 facade 验证撤销；不创建大厅、副本、奖励或人物资产事务。冷启动和重载均加载 53/54 个脚本，唯一错误仍为原包 `sao_npc.js:177` 的 `registerPage` 未定义；6 个新增兼容脚本无加载错误。状态命令确认 runs/lobbies/pendingReturns/tickets 均为 0、四个槽位空闲。

使用忽略目录中的 JDK Attach 控制器核验 JVM 工作目录精确匹配该私有副本，再向其主线程提交 status/validate/reload，以及最后的正常停服。实际日志包含保存完成，端口已释放；没有强杀 JVM。机器记录保留在私有目录 `kube-lifecycle-20261028.json`。

钱包接口、事实接收与任务前置仍为 UNAVAILABLE，符合当前旧钱包没有事务端口、任务桥关闭的配置。外部市场缺少实际所有者注册时保持 UNKNOWN。此轮验证绑定生命周期，不代表钱包、市场、FTB 事实持久化或完整整合包验收通过；正式开本和奖励继续关闭。

## 构建与产物

源提交 `1cc2b65ad9ee3dca3b3bc936424835c2ccc60120` 的干净导出构建通过，100 项 JUnit、41 个结构及 422 个语言键检查通过。产物 `build/verified/0.41.6-dev-1cc2b65ad9ee-20261028-095024-62c1772e/saodg-0.41.6-dev.jar`，SHA-256 为 `5f5e01c832e67c7238b48c882713b2f4c30c4f6e41cc0c9adb4391632d9b79cd`；私有测试服安装包散列一致。随后根工程 `build runGameTestServer -PgameTestRunDirectory=run/gameTestServer-kube-lifecycle-20261028-1800 --offline --console=plain` 完成，100 项 JUnit（零失败/错误/跳过）、43 项必需 GameTest 全部通过，其中包括新增绑定生命周期夹具、双实例隔离、战斗与 28 房间四旋转的 112 项实际放置通行检查。完整日志：`logs/kube-lifecycle-default-20261028.log`。
