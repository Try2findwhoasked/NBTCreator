# 构建与发布（Windows Portable）

## 工作流与运行环境

[Windows Portable](../../.github/workflows/portable.yml) 在 main 和 codex 分支推送以及手动运行时执行完整验证。PR 仍按改动选择文档、快速或完整检查。[Windows Release](../../.github/workflows/release.yml) 由 v* 标签触发，调用同一套 Windows 验证和打包，再校验 ZIP 的 SHA-256 并创建 GitHub Release。发布作业拥有写权限，验证作业使用只读权限。预发行版本标签含连字符时仍标记为 prerelease。

包内 mise 固定版本并通过 SHA256 校验，见 [portable-runtime.json](../../config/portable-runtime.json)。Electron 提供 Node，Playwright 固定版本的 Chromium 用于批量出图。运行时从环境解析 Python 和 Git，也可用 NBTCREATOR_PYTHON、NBTCREATOR_GIT 指定；CI 先在测试解释器中安装引擎依赖。

## 验证门禁

完整验证并行运行源码契约、素材库桌面流程、模型流水线、创作契约和便携包验收。模型流水线分为构件与曲面、协作与回传、渲染与交付三组，一组失败时其他组继续并各自记录诊断。各 Windows 作业使用同一 Action 安装锁定依赖并构建生产前端。快速验证运行源码契约、模型流程和桌面冒烟。纯文档 PR 运行范围判断与汇总检查。发布说明、测试、打包配置及其他未归类改动执行完整验证。

打包 job 验证 ZIP 解压内容、外部 Python 和 Git、包内 mise、CLI、Skill 生成和包内浏览器，随后运行打包版桌面和模拟 API 回归。汇总门禁继续使用 `build`，由它检查当前范围所需 job 是否全部成功。Release 在完整验证通过后复用已验收的 ZIP，并在上传之前校验 SHA256。

3.3.0 起，源码门禁还校验自带素材库的 121 项内容与哈希，运行外部库离线、刷新、回退及模块化构件回归，并在桌面端验证统一素材浏览、预览、复制和放置。桌面测试使用软件 WebGL 渲染以稳定运行最小化窗口中的真实 3D 预览。

源码门禁还先构建 web-dist，并用 viewer 锁定的 Playwright 显式安装完整 Chromium；`PLAYWRIGHT_BROWSERS_PATH` 固定到本次 `build/portable-browser`，在各自 job 内供源码回归或 portable 打包使用，不依赖 runner 偶然预装的 Edge或额外 headless-shell。随后运行共享渲染/快照校验、评论索引迁移与证据、独立开口、独立尺寸/非48网格交付、候选校验、工作区API取消、碰撞反例、整体精修及网页回导回归。核心夹具每次写入新的 `build/ci-model-delivery-*` 目录，失败直接返回非零退出码。模拟确认只用于合成夹具。打包后另用挂起的本机模拟API检查实际工作区切换会中止旧连接、允许新请求，并且不把旧结果/活动写到新工作区。

`tests/node/task-cancel.mjs`另用超过50万格的真实合成主稿启动Python，确认PID仍存活后分别取消前置inspect和实际preview任务，检查cancelled状态、诊断保留和后续任务可继续；服务关闭也须结束自己创建的非job inspect子进程。该测试不使用sleep伪造工作，不扫描杀死用户其他进程。

## 产物与本地构建

发布产物包括 `NBTCreator-<版本>-windows-x64-portable.zip`、`.zip.sha256` 和逐文件 `.manifest.json`，以及下面说明的应用更新包与运行环境包。用自有 ZIP 脚本确保 `.agents` 隐藏目录被保留，拒绝用户资产、运行日志、环境文件和 API 配置。普通 CI 产物保留 14 天，Release 资产长期保留。

先按[开发指南](DEVELOPMENT.md)准备依赖，再从软件源码根目录构建与检查：

```powershell
mise run ci:verify
mise run ci:package -- dist/portable-local
```

## 发布规则

发布时同步更新 package.json 与 package-lock.json，先在本地通过上述两项检查。将通过验证的提交推送到 main，再创建并推送与版本一致的新注解标签。每个发布标签对应一个固定提交，修复后使用新的未占用版本号。分支测试包通过 Actions 中的 Windows Portable 手动构建，成功后下载带提交 SHA 的 Artifact。

Portable 表示免安装目录包，工作区仍由用户选择。API 密钥仍保存在 Windows 用户级加密配置中，不随 ZIP 发布。请保留完整目录，不要仅复制 exe。未签名程序沿用原说明。全屏问题 NBTC-001 已根据用户于 2026-11-04 的确认关闭，CI 不触发全屏。

运行环境打包参考 [mise 发布资产](https://github.com/jdx/mise/releases)，触发与权限参考 [GitHub Actions 说明](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。仓库流程见 [Windows Portable](../../.github/workflows/portable.yml) 和 [Windows Release](../../.github/workflows/release.yml)。

## 完整包与分离包

每次构建同时生成 full Portable、app-update、runtime 三个 ZIP，以及各自的 SHA256/文件清单。首次使用可直接下载 Portable，也可将 app-update 与 runtime 解压到同一父文件夹，合并同名 NBTCreator-win32-x64 目录。后续依赖未改变时，只需更新 app-update，保留已有 runtime。

app-update 包含应用源码、建模工具、预构建前端和 Skill 资料。runtime 包含 Electron 宿主、mise 与 Chromium，可以与匹配的应用更新包复用。运行环境 ID 绑定 Electron 版本、mise 锁定值和 Playwright 版本，启动时核对应用所需ID与runtime-info.json，不匹配时提示下载配套runtime或完整版。旧1.6运行包没有该标识，首次使用1.7应用更新包需要配套运行环境。

CI 会验证两份分离包的文件互不重复，并按路径和字节哈希确认它们能完整重组为完整包。完整解压测试仍会运行外部 Python、CLI、Skill 生成、Chromium 和批量出图。新版本的校验文件随 Release 提供，不复用旧版本的 ZIP 哈希。

本地仅制作应用更新包可运行 `mise run package:portable -- --app-only --out dist/update-版本`，该构建只打包应用部分；不能把该临时构建文件夹当完整免安装包。应用更新ZIP需解压覆盖已有兼容runtime，启动时仍验证runtime_id。云端发布继续构建完整与两种分离包并执行全套解压验证。

本地需要完整免安装文件夹而无需ZIP时：`mise run package:portable -- --directory-only --out dist/full-folder`；校验：`mise run test -- portable --directory dist/full-folder`。目录模式仍打入完整运行环境，不可与 `--app-only` 同用。

返回[文档导航](../README.md)。
