# 0.41.16 显式旧钱包资产所有者

源提交：`5b2456d306c2c81ebd8a48502418f01b5cc8c12e`。

旧 SAO 0.7 包体没有市场模块，默认 market 检查一直返回 UNKNOWN。新增明确选择的 legacy_wallet 模式，要求精确旧钱包参与者标记、同代注册及真实钱包锁，并由服务端只读检查已知市场代码/数据与人物内存/磁盘回执。子目录中的市场脚本同样阻止放行。默认 market、正式入口关闭及钱包所有权保持。

配置及安装边界见 [旧钱包说明](../../compat/legacy-wallet/README.md)。本轮没有安装、启动或修改任何原服、客户端或私有测试服。

## 实际验证

- `node compat/tests/asset_fence_test.cjs` 通过：旧/新所有者分支，缺证据、忙锁、异常类型、异常读取、市场存在、过期代际等检查。使用 VM 假读，不证明真实 Rhino。
- `python tools/verify_compat_patches.py D:/Documents/Coding/Game/Minecraft/SAO-server-0.7 --profile sao-server-0.7` 通过：6 个原始文件哈希、精确补丁和 JS 语法，源目录只读。
- `node compat/tests/legacy_wallet_policy_test.cjs build/compat-validation/sao-server-0.7/kubejs/server_scripts/sao_wallet.js` 通过：原有七处冻结和材料策略，新增真实补丁中 busy 对同一锁的读写观察及 profile 标记。
- 从已提交源码独立导出，执行 `tools/build_verified_release.py --java-home D:/Java/jdk-17 --package-only` 通过：编译、重混淆、41 个结构、474 项本地化回退和映射资源检查。用户 beta 结构未进入产物。
- 随后在同一源码导出单独执行 `test --tests cn.saodg.integration.kubejs.LegacyWalletAssetScopeTest --tests cn.saodg.integration.kubejs.ExternalAssetHistoryTest --offline --console=plain`（JDK 17、证书检查参数沿用开发配置）。5 项通过，0 失败/错误/跳过，Gradle 用时 9 秒。覆盖目录异常、根目录及子目录市场代码、市场备份/临时文件/目录、Forge/KubeJS 回执和异常命名空间。

没有重跑全量 JUnit、GameTest 或真人联机。真实 Rhino 新 API、实际钱包与奖励服务联动、原生经验持久死亡确认及完整发放仍未证明；不得把本记录视为整合包经济隔离或正式入场验收。

## 可追溯产物

开发包：`build/verified/0.41.16-dev-5b2456d306c2-20261029-035103-f16b0d3c/saodg-0.41.16-dev.jar`。

SHA256：`92e327bfbfdd19d0506c1c8a57a9e9b490d248728dbd3856493444e178d07471`。

构建记录：同目录 `verification.json` 和 `build.log`。其中 `junit_executed_by_this_tool=false` 正确表示打包工具自身未执行测试；上述 5 项来自后续独立命令。

测试原始 XML：`.gradle/source-release-5b2456d306c2-20261029-035103-f16b0d3c/build/test-results/test/`。

- `TEST-cn.saodg.integration.kubejs.ExternalAssetHistoryTest.xml`：`26e11ebaa18b0925e9d935d3a89efaa4554209bb56b178730f3bc1da6ddb9087`。
- `TEST-cn.saodg.integration.kubejs.LegacyWalletAssetScopeTest.xml`：`1c89d3c28be97eaa653cb414b7bbf28498acbbede37b23af2879ecef58f76d46`。
