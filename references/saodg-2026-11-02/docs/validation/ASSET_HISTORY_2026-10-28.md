# 可选资产检查与原市场回执

0.41.8-dev 修复 owner-history 兜底：实际较新包的 sao_ui_data.js 通过脚本 getPersistentData() 写入 PlayerPersisted.sao_market_receipt_v2，即玩家文件 KubeJSPersistentData 下；旧 BridgeRegistry 仅查 ForgeData。正常 SAO_SERVER/默认 KubeJS 必需门禁已经拒绝，缺口影响 STANDALONE 显式关闭可选要求，或移除 KubeJS 后的已有市场参与者。

新增只读 ExternalAssetHistory：先查当前 Forge 根，再反射调用可选 KubeJS 的 kjs$getRawPersistentData（不分配新根，不静态加载可选类），随后独立回读原玩家文件的 ForgeData/KubeJSPersistentData 两处。任何既有回执（不解释其类型或是否完成）均要求真实外部所有者；畸形命名空间、反射/文件读取失败、人物 UUID 不符也保持要求。缺失文件和没有记录的新原版人物不凭空要求市场。不迁移字段、不修改回执，也不将 owner 配置改为 none。

该回读仅在全局预设/配置未已强制门禁时进入；默认 SAO_SERVER 检查不新增文件 I/O。未缓存“无所有者”结论，以免后续新记录绕过检查。

定向命令 `gradlew.bat test --tests cn.saodg.integration.kubejs.ExternalAssetHistoryTest --offline --console=plain`：两个测试通过，覆盖两种命名空间、只读不变、空状态、畸形根/PlayerPersisted，以及类型未知的既有回执仍要求门禁。日志 `logs/external-asset-history-targeted-20261028.log`。后续补充人物文件 UUID 不符拒绝，相同定向测试再次通过（`logs/external-asset-history-final-20261028.log`），该人物 UUID 分支未做实际玩家文件故障注入。

遵照减少重复检查要求，未运行全量构建、默认 GameTest 或整合包服务器；尚未在实际移除 KubeJS 的原生环境验证回读分支，不宣称市场事务兼容已通过。当前已安装私有运行时仍为 0.41.7-dev，修复未部署，正式入场和奖励继续关闭。

后续已在实际 0.41.8 私有包验证内存双根与磁盘单独保留回执读取；引擎卸载场景仍未覆盖。见[合并记录](JOINT_0.41.8_2026-10-28.md)。
