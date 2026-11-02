# 首次与增量同步：0.41.27

源码 `4c35d3aca4dba39d7db454a3b310ca3366933f19`。服务端首次周期同步原先可能生成 base=0 的增量，依赖客户端额外请求完整快照；客户端又会先检查 base 不匹配，再忽略重复包，因此已应用的旧增量会触发多余重同步。

现在服务端共用 `StateUpdate.diff`：新会话首次必为完整快照，内容不变的周期同步不占修订号，显式打开菜单仍发送。客户端使用不引用客户端类的 `StateProjection`：同流旧修订先忽略，缺失/错误流的增量整包拒绝，全量响应恢复、新流全量清除旧目标，断线重置。ClientState 保留单次待同步请求和真实界面打开逻辑。数据包增加 full/base/revision 一致性及移除键检查；编码格式与协议 20 不变，无存档变化。

独立导出编译/重混淆/包内检查通过（41 结构、482 中文键、beta 排除）。开发包 `build/verified/0.41.27-dev-4c35d3aca4db-20261029-062940-fff4b264/saodg-0.41.27-dev.jar`，SHA256 `7de7323b238eb3624fc7702ccbd786f36ba6b51a905a4c8708b37b89a3f07aac`。

仅运行 `-PgameTestNamespaces=saodg_sync`，目录 `run/gameTestServer-state-sync-04127`。生产 diff、共享 reducer 和真实 FriendlyByteBuf 编解码检查首次/差量、字段移除、重复/过期、缺失一包后的全量恢复、错误流拒绝、新流/断线清缓存、嵌套 NBT 独立持有及畸形 base/revision/列表/超大 NBT 拒绝。它在独立 Forge 服务端执行共享同步逻辑，没有启动 Minecraft 客户端或伪装真实远程网络丢包。

1 项检查通过，46 秒、退出 0。日志 `logs/state-sync-04127-20261029.log`，SHA256 `6893446a6a2542574f9c703bfbdf7ccefab7f76d9ccb8f994aceb30a1cb0487c`。没有 JUnit、全量回归、用户客户端或原服更新；真实端点握手、界面打开与远程多人仍待验收。
