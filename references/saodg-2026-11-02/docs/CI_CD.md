# CI/CD 与工具验证

当前迁移分支基线为 Minecraft1.20.1、NeoForge47.1.106、ForgeGradle6.0.54、Gradle8.8、Temurin JDK17。不在流水线中运行项目级 `clean`。历史 Forge 发布与标签保持不变；[迁移验证](validation/NEOFORGE_MIGRATION_2026-10-31.md)。

## CI

`.github/workflows/ci.yml` 在 main/codex分支推送、main的PR和手动触发时执行，也可供发布流水线复用。所有Action固定完整提交SHA；默认令牌仅 `contents: read`，检出不保留凭据。并行的新分支提交会取消同分支旧CI，发布复用的固定SHA验证不会因此取消。

- `Python tools`：Python3.12，统一工具单测、生产内容引用审计，以及固定版本actionlint。
- `NeoForge build and full JUnit`：执行标准 `gradlew build`，**没有测试过滤、没有 `-x test`**，包括每档10,000种种子的重型布局检查，超时90分钟。两个可选原生弓二进制测试没有参考JAR时可跳过；Linux没有DOS短路径别名时，平台专用夹具也可能跳过。发布清单记录实际跳过项，不把跳过当作原生兼容通过。
- 两个独立GameTest作业：`core` 运行根Gradle默认命名空间（包含消息隔离），`features` 显式运行机关、实体箱/奖励/归途门、符文门、声音、刷怪/原生数值等附加命名空间。使用不同runner、新测试世界和45分钟超时；无图形服务器跳过客户端 `downloadAssets`，资源init仅限制JVM，不过滤测试或修改游戏门禁。
- 构建和运行报告无论成败都会保留14天；仅选择 `saodg-<mod_version>.jar` 为主产物，不发布 `*-pack-acceptance.jar`，产物含SHA256、验证元数据和当前版本说明。

受信分支可写Gradle缓存，PR缓存只读。没有引入私有JAR、密码、用户世界或对SAO/KubeJS服务器的部署权限。

## CD

`.github/workflows/release.yml` 由新 `v*` 标签触发，也可手动输入标签。仅对**包含这套CI工具的新快照**有效；旧 `v0.41.66-dev` 等历史标签不回写、不重打，也不会因本次新增工作流自动补发。

1. 检出标签，验证必须是注解标签、严格等于 `v<gradle.properties 中的 mod_version>`，且HEAD确为标签提交；不从标签覆盖版号。
2. 按已经解析的不可变提交SHA复用全部CI作业。任一构建、工具检查或GameTest失败都不能进入发布。
3. 发布作业不检出/执行源码，只下载本次验证的构建产物并核对SHA256、产物来源提交及版号；再次确认远程标签未移动。
4. 唯一拥有 `contents: write` 的作业用GitHub CLI先创建草稿并上传全部产物，上传成功才公开。`-dev` 等带后缀版本和本项目的紧凑版号 `0.5beta` / `0.5.1beta` 标记为预发布且不设为最新稳定版；已存在的Release/资产不强行覆盖。上传失败可能保留草稿，应人工核对后再处理。

目标是GitHub Releases；没有添加Modrinth/CurseForge发布或游戏服务器自动安装。使用仓库内置 `GITHUB_TOKEN`，不需要额外长期密钥。更改仓库Actions策略或为main配置保护规则属于仓库管理员操作；所需检查名称以首次运行界面为准。

发布前需同时更新 `gradle.properties` 和CHANGELOG对应的 `## <版本>` 段落，再创建新的注解标签。已有已发布标签不得改指向。普通代码整理不会为同一版号重打标签或发布旧JAR。

## 本地复验

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
python -m pip install -r tools/requirements.txt
python -m unittest discover -s tools -t . -p 'test_*.py' -v
python tools/verification/content_audit.py --check
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml .github/workflows/release.yml
.\gradlew.bat build
.\gradlew.bat -I tools/ci/runtime.init.gradle runGameTestServer -PgameTestRunDirectory=run/local-ci-core
```

Linux使用 `./gradlew`。不应在本机带作者资产的build目录运行 `clean`；新runner由Git检出天然隔离。本机短测/打包记录另列实际过滤，不能代替远程全量CI结果。

实现依据：[GitHub Actions安全使用](https://docs.github.com/en/actions/reference/security/secure-use)、[checkout](https://github.com/actions/checkout)、[Gradle Actions](https://github.com/gradle/actions)、[gh release create](https://cli.github.com/manual/gh_release_create)、[gh release edit](https://cli.github.com/manual/gh_release_edit)。Action SHA在配置时从官方标签解析，版本升级需重新核对并审阅。
