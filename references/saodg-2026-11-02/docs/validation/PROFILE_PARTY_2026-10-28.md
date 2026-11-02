# SAO 在线资料与原生组队读取

2026-10-28，0.41.7-dev，在已授权私有副本 `run/pack-acceptance-20261028-081137-fd148a65` 验证。原服未修改，准入和经济奖励仍关闭。仅编译 packTestJar/reobf，没有全量构建或重复默认回归。

新增显式 `-Dsaodg.packProfilePartyAcceptance=true` 夹具，只在该目录、无人且无活动实例时运行。两名临时 PlayerList 人物由原生 SAOTeamManager.handleInvite / handleInviteResponse 邀请接受入队；不伪造记分板队伍或用户数据。

最终日志 `logs/pack-profile-party-role-20261028.log`，结果 `profile-party-probe-eeae1278-5978-40a5-bc97-d610a650f920.json`：passed=true，无人物/队伍清理错误。

- 人物 `16a0f73c-21e3-43ba-8b49-e69f008d0c4a`、`3af0d5fc-a9b8-490b-8fd8-a327be962b89` 均 level=1、level_status=KNOWN、downed=false、downed_status=KNOWN，与实际原生所有者方法逐项一致。
- 新人物尚未选职业，原生 role=0、valid=false；适配器保持 role_status=UNSUPPORTED，不编造职业。初次夹具要求新人物职业必为 KNOWN，错误断言失败，日志 `pack-profile-party-20261028.log`、结果 `profile-party-probe-9094c240-f6e0-44e1-93a8-6c80e74b700e.json` 保留。修正夹具后复测，生产代码未改。
- 两名人物取得相同原生 socialId `saomenu_16a0f73c-21e3-43ba-8b49-e69f008d0c4a`，在线名单精确包含两名 UUID，unresolvedMembers=0；leaderKnown=false，不把队伍成员资格当房主权限。
- 随机离线 UUID 的等级、濒死、队伍读取均为 UNAVAILABLE。
- 最终逆序调用原生清邀请/退队，移出临时人物并关闭 embedded channel。审计人物资料保留。

范围仅正常人物读取与实际两人原生邀请/接受。未选职业不是读取故障；有效职业的各角色、等级变化、实际倒地/救援、离线队员名字解析及队伍切换中的副本名单冻结仍待相关行为验收。没有因此修改兼容认证状态或开放正式入场。

最终管理状态无运行、回程或票据，四槽位空闲；正常全维度保存退出、端口释放，夹具移入 validation-history。
