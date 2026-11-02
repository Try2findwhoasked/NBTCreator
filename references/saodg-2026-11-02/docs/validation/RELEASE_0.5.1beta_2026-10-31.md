# 0.5.1beta 配置与管理员GUI发布快照

日期：2026-10-31。版本 `0.5.1beta`，注解标签 `v0.5.1beta`，协议25；Minecraft1.20.1 / Forge47.4.10 / ForgeGradle6.0.54 / Gradle8.8 / JDK17。

## 内容和兼容

- 功能提交 `9d41668`：15项新增可调参数、六类36项配置的管理员GUI、OP2权限/在线对象校验、整批保存、版本冲突检测、控制台list/set，以及开局冻结的奖励参数。
- 发布提交：版号、CHANGELOG和当前文档统一为 `0.5.1beta`；发布工具支持三段紧凑beta版号，并验证预发布标记、注解标签和提交一致。
- 客户端和服务端需一起更新至协议25。旧运行记录缺省 `reward_tuning` 时使用历史默认值；自定义参数进入结算指纹，不追补旧局，不改变钱包归属；不保证旧版降级读写。
- 保留历史 `v0.5beta` 及更早标签。其他远端功能分支未合并到此次配置发布。

## 本次实际检查

| 检查 | 结果 |
| --- | --- |
| 定向JUnit | 13项通过，失败/错误/跳过均为0；`domain.config.*`、`domain.reward.*` |
| 统一Python工具测试 | 35项全部通过，包含新增 `v0.5.1beta` 版本/注解标签/预发布校验测试 |
| `build -x test` | 通过；整套JUnit明确跳过，Java及运行夹具编译、打包保留 |
| 内容审计 | 80间活动房和五个非活动功能定义保留，340/340份生产模板引用有效 |
| JAR检查 | 340份生产模板集合及字节与源码完全一致，中文/默认语言一致，包内版本正确，无GameTest/packTest/预览类 |
| Git检查 | `git diff --check`通过，无项目级clean、历史重写或旧标签移动 |

本次发布整理只改变版号、当前说明和发布工具，玩法实现与功能提交一致。上一开发轮17项定向Forge GameTest、增强后的管理员3项复验及四张实际客户端渲染截图见[功能验证](ADMIN_CONFIGURATION_2026-10-31.md)；本次未重复这些运行测试，不把它们标作新版重新运行的结果。

本机没有运行未过滤完整JUnit或默认全部GameTest。标签触发的既有GitHub发布流程仍会重新执行完整CI；全部门禁通过后才发布GitHub预发布产物，不能将本机定向结果代替远端门禁。

```powershell
.\gradlew.bat test --tests 'cn.saodg.domain.config.*' --tests 'cn.saodg.domain.reward.*' --console=plain
python -m unittest discover -s tools -t . -p 'test_*.py' -v
python tools/verification/content_audit.py --check
.\gradlew.bat build -x test --console=plain
```

原始日志：`build/release-0.5.1beta-{tests,tools,package}.log`；逐字节产物检查：`build/release-0.5.1beta-artifact.json`。JAR和运行世界不纳入Git。

## 本机产物

`build/libs/saodg-0.5.1beta.jar`，4,060,920字节：

```text
SHA256 c33c2d25e5669c5b0a2d0d4e00feb099b50166dff0e46266ebfac560c3b8cbdc
```

GitHub流水线重新构建的JAR以随附校验和及来源提交为准。管理员入口、配置字段及生效时机见[使用说明](../SERVER_CONFIGURATION.md)。

真人双客户端同时编辑、完整SAO整合包、真实进程重启后的配置恢复和生产经济未验收；本次没有安装到活动存档或部署游戏服务器。
