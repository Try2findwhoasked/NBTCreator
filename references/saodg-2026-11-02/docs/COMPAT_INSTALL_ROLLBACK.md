# 私有验收副本的脚本安装与回滚

工具 `tools/compat/compat_profile_install.py` 只支持本项目 `run/pack-acceptance-*` 下有匹配 acceptance-manifest.json 的私有副本，不能用于原服发布。当前 profile 为 sao-server-0.7，含清单中的六个既有钱包/实体/历史脚本。只处理这些现有脚本，不安装 JAR、新增桥接配置或任务章节，不操作世界、玩家数据、EULA 或开放开关。

先保存并停止该副本服务器，避免编辑/重载并发。工具会拒绝 localhost:25579 正在监听的情况，但端口检测不证明一个尚未开始监听的启动进程不存在，操作员仍须确保停服。

```powershell
# 默认仅计划：核对全部基线散列、精确补丁与 Node 合并后语法，打印前后散列。
python tools/compat/compat_profile_install.py --target run/pack-acceptance-实际目录

# 明确执行。仅当六个文件全部是清单中的原始字节时允许。
python tools/compat/compat_profile_install.py --target run/pack-acceptance-实际目录 --mode apply

# 使用上述输出的相对回执路径，恢复所有原始字节；可重复执行。
python tools/compat/compat_profile_install.py --target run/pack-acceptance-实际目录 --mode rollback --receipt compat-install-实际事务ID/receipt.json
```

现有已人工接入的验收副本不匹配原始基线，工具应拒绝，不要用改散列或强制覆盖绕过。这是安装/回滚工具，不是任意版本升级合并器；新基线须先审查并生成独立 profile。

应用前完整检查所有目标；逐文件备份并 fsync，在替换第一个脚本之前写 PREPARED 回执，结束写 APPLIED。替换为同目录临时文件 fsync 后 os.replace，逐文件原子，不声称多文件天然原子。若中途断电或失败，保留回执与备份，用 rollback 处理部分完成的事务。备份阶段尚未生成回执的失败不会改脚本，保留该目录供审计。

回滚预检全部备份散列和当前文件：当前文件仅允许等于原始或已安装字节。任何人工修改、损坏备份、错目标、越界/重定向路径、非脚本路径均拒绝。不会用旧备份盖掉管理员后续修改；需要先人工审查冲突。备份和回执不删除。工具不改变文件 ACL 的策略，部署有自定义 ACL 的环境需另行验收。

初始验证命令 `python -m unittest discover -s tools -p test_compat_profile_install.py -v`，5 项临时目录测试通过：原始 CRLF 字节恢复及重复回滚、基线变化时零写入、人工编辑/损坏备份时拒绝所有回滚、PREPARED 部分安装恢复、非法路径与非脚本回滚拒绝。该轮没有运行 Gradle 或启动 Minecraft，也未对当时已接入的副本执行 apply/rollback。

2026-10-29 另从只读原服创建全新独立副本，实际完成六份脚本 apply→读取安装后散列→rollback→逐字节核对原始源文件，回执 ROLLED_BACK，配置/EULA 不变，新服未启动。没有覆盖已有手工补丁的原生验收环境。[实际演练与散列](validation/COMPAT_INSTALL_ROLLBACK_2026-10-29.md)。

仅补齐 M6 的脚本安装工具部分，不能据此宣称发布完成；JAR 升降级、真实人物/世界恢复演练、完整资产故障和多人验收仍需独立完成。正式入场和奖励保持关闭。
