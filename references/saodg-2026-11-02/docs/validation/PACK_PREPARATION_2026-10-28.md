# 目标整合包的独立验收副本准备

本轮只准备环境，未启动整合包服务端，未宣称 SAO/KubeJS/FTB/TACZ 已兼容，未开放正式副本。
工具 `tools/prepare_pack_validation.py` 从指定发行目录复制白名单配置、模组、脚本、数据包和 Forge 库到本工程新的 `run/pack-acceptance-*`，每个文件复制前后核对源/副本 SHA-256。拒绝越界链接、已装 SAODG 的不明确基线和覆盖既有副本。
工具不运行原启动脚本，不复制原 server.properties、管理员/白名单、世界或 playerdata，不接受 EULA，也不启动任何 JVM；新副本仅绑定 127.0.0.1:25579，关闭 RCON/query，使用全新 acceptance_world，SAO_SERVER 预设但开本和奖励均关闭。

## 实际准备

源目录：`D:/Documents/Coding/Game/Minecraft/SAO-server-0.7`，只读。
加入的模组：已验证源码包 `build/verified/0.41.1-dev-0de4dcb202d1-20261028-075331-f0a5a767/saodg-0.41.1-dev.jar`，SHA-256 `7ca01830ea206744071ffbd3808d467fc44c58b79a28d61ae3d278888933972d`。
目标：`run/pack-acceptance-20261028-081137-fd148a65`。
实际复制 5612 个文件、1,054,565,085 字节，原包 121 个 JAR，另加 SAODG；完整 SHA-256、大小、Forge 模组元数据与依赖写在副本的 `acceptance-manifest.json`。原文件逐项复制前后校验一致。
源 kubejs/data 的 20 份文件检查为命名空间数据包内容（维度、掉落表、世界生成/群系标签），不是玩家账本；脚本共 58 份。HTTP/绝对路径粗筛唯一命中是 startup example 中的文档链接注释，不能把这种粗筛外推为完整脚本安全或存储兼容审计。

## 当前关键基线

| 模块 | 实际元数据版本 | JAR SHA-256 |
| --- | --- | --- |
| SAO 核心 mod_1cab0b39 | 1.2.0-r234，含 saomenu 1.0.0 | 4d6ff00c069ecacbab4353311bccf8fcb0abfc528ccd2f47fe10594113888d9b |
| sao_gameplay_fixes | 2.3.3（文件名仍写 1.0.0，不能按文件名判断） | 72e00091956d081c070af8e40dd132e07effeece3cf2ef7d30b72760f2118354 |
| KubeJS | 2001.6.5-build.26 | 1769312192fbf9d72f45054ba61130523bfb471b5f480a4bff8c210ec09400bb |
| FTB Quests | 2001.4.22 | 见完整 manifest |
| TACZ | JAR 元数据使用 file.jarVersion 占位；文件名为 1.1.8-hotfix | 9ed8ada1283ed7a793a70cc1b51c4a340f367ce84707e1a7b8cf21ee3d288d77 |

Forge 实际启动参数文件存在，版本 47.4.10 / Minecraft 1.20.1；未修改或重新接受源目录许可证。
准备时读取原 eula 为 false，工具把该快照记录在 manifest；后续复读源文件观察到 true，该外部变化不是本工具写入，也不会覆写本次副本的证据。副本自身始终保持 eula=false，等待用户明确确认后再启动。

## 下一步出口

经用户确认 EULA 后，仅在上述独立副本启动 Java 17，先验证完整原包加 SAODG 的服务端加载与诊断，不启用入场/奖励。
继续记录加载后的真实 Mixin、资料/濒死/队伍接口与脚本桥状态；再分项安装兼容材料到私有副本，验证原生技能、存储、奖励与真实多人。原目录和玩家数据保持不写入，当前准备工作不能替代这些验收。
