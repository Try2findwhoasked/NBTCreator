# 0.41.50 服务端UI依赖补齐

0.41.50首次服务器本体冷启动证明SAODG内容可以加载，但原服务端包的sao_npc.js依赖global.saoUI，缺少UI核心而报错。进一步核对发现其已有商店分类JSON及分类NPC，却也缺少分类加载器。本次沿用已安装原生战斗代码，补齐依赖及导航，不复制或修改NPC、价格、钱包交易实现或任务数据。

## 来源与实现

来源提交 `3a4878e53548335987472ff763e499bb6dd6e255`：

- UI核心采用开发目录已有、且在 `compat/legacy-ui/SOURCE.json` 留有来源记录的干净版本，SHA256 `cf30717f3a3e674d2469dbef7a963b7b21087f4d5f72967b7013f06d5a2953a7`。安装还要求服务端现有NPC基线为 `3b73447ea4faaa866527d0f775c788020bf717a6089707c64c62fb210ff54693`。
- 商店分类加载器采用SAO-0.8现有版本，SHA256 `ef9187e0700877ae90f6cb2eeb119c73a43d481dc0ea46c8df64d2f01b6a0732`，读取服务器原有sao_shop_goods.json。两个源文件均在角色清单固定散列，目标只接受缺失或完全相同的文件；不替换其他版本。
- `sao_dungeon_navigation.js` 在钱包加载后解析现有服务。已有完整主页/商城的客户端与开发目录继续使用原页；旧服务器补充主页，连接NPC图鉴、原钱包商店、钱包查看及副本队伍。副本按钮直接使用该玩家的命令源，没有控制台权限回退。按钮文本使用模组中文语言文件。
- 暂存/安装工具支持角色依赖与NPC先决条件，安装前和写入前复核。四项定向安装/回滚测试通过，包括NPC被人工修改时整个安装开始前拒绝，以及回滚新增UI不改原NPC。JS语法检查通过。

同版本开发产物新增7个中文文本键，Java战斗代码与b9c5753逐文件无差异；因此只执行jar/reobfJar，没有重跑已通过的战斗流程、JUnit或GameTest。原生怪及最终首领自然攻击证据继续引用 `logs/native-dual-trial-probe-68f3d2df-8216-4e1f-8330-5db6bc700c3b.json`，不将旧二进制实测误称新UI按钮实测。

## 安装与实际重启

最新产物 `build/verified/0.41.50-dev-3a4878e53548-native-ui-20261030/saodg-0.41.50-dev.jar`，SHA256 `dde1435ff1c9d41a30eb30fea2a14795c9cf2340a87590ea8e1a682ec7cfa0eb`，75份正式NBT，未含beta或验收夹具。中文及en_us回退内容一致；构建日志 `logs/native-ui-build-3a4878e-20261030.log`。这是尚未正式发布的0.41.50开发修订，以产物散列及回执区分。

所有Java/Minecraft进程关闭后，两端通过备份事务更新并逐项复核：

- 服务器21项回执 `D:/Documents/Coding/Game/Minecraft/SAO-server-0.7/.saodg-backups/7857f66c374e47979a130983ab0f2dd7/receipt.json`。
- 客户端19项回执 `D:/Minecraft/.minecraft/versions/SAO-0.8/.saodg-backups/d08aacad975b4ce1adad9edfbf06a78f/receipt.json`。
- 开发目录只新增相同导航脚本；按该目录AGENTS规则未提交或推送，保留其全部既有NPC/商店/任务修改。可追溯的规范源在本工程compat中。

使用服务器自带Java17/Forge加载先前独立世界 `saodg_native_smoke_20261030_ebca7d9c`，仅监听127.0.0.1:25580：54/54份服务端脚本加载、0错误/0警告；实际输出NPC菜单ready、7商店分类/3商人、旧服主页导航ready。SAODG仍加载35房，内容散列未改变。到达Done，管理命令、保存与stop正常，Java7052退出0；既有EULA字节不变，server.properties恢复原始字节。

`logs/server-body-native-ui-20261030.json` passed=true；`logs/native-ui-3a4878e-installation-validation-20261030.json` 核对两端JAR和安装项，并确认旧服87份已有启动/服务端脚本及脚本配置全部字节保持，无意外变更。

## 范围与下一步

本次证明依赖加载及导航注册；没有真人点击NPC、购买物品或加入服务器。玩家交易/拍卖模块没有随UI基础补齐，原包未安装的页面仍需各自接入，不能称整个NPC经济系统已验收。新版客户端新局怪物显示与房间门洞通行仍待用户反馈，原生战斗平衡、全部攻击/投射物及性能也不由启动检查证明。完整目标保持进行。

客户端启动尝试：通过Computer Use打开既有PCL，实际读取到实例SAO-0.8及“启动游戏”控件。截图读取报FrameArrived timed out，重选窗口后纯辅助文本读取成功；按实际控件点击时又报coordinate input geometry is unavailable。随后重新枚举只有PCL窗口，无Java/javaw进程，客户端latest.log仍停留01:32旧退出记录，不能当作已启动或新版通过。未使用猜测坐标或登录参数；已请求用户手动点击启动并进入测试存档，再读取新日志。
