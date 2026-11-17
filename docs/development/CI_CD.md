# 构建与发布（Windows Portable）

## 工作流与运行环境

`.github/workflows/portable.yml` 在main、codex分支提交、PR和手动触发时构建Windows x64包；推送与package.json版本一致的 `v<版本>` 标签时，在构建及解压验证通过后自动创建GitHub Release。不覆盖已有Release或标签。预发行版本标签含连字符时标为prerelease。当前仓库按用户确认保持公开，发行包可直接下载；若将部署改为私有，下载仍遵循仓库权限。

包内包含固定版本且经过 SHA256 校验的 Python 3.14.10、NumPy 2.4.2、Pillow 12.1.0、nbtlib 和 MinGit，具体锁定值见 [portable-runtime.json](../../config/portable-runtime.json)。Electron 提供 Node，锁定版本的 Playwright 提供 Chromium，用于批量出图。完整解压后运行 NBTCreator.exe 即可，无需另行安装这些运行环境。仍可通过 NBTCREATOR_PYTHON 显式指定其他解释器。

## 验证门禁

CI 先检查工具一致性、冻结资料库及 API/工作区/交接/提示词契约，再构建 ZIP。随后逐文件验证解压内容，移除系统 Node/Python 搜索路径，检查私有 Python、CLI、Skill 生成和包内浏览器，最后运行打包版桌面和模拟 API 回归。任何检查失败都会阻止发布。

3.3.0 起，源码门禁还校验自带素材库的 121 项内容与哈希，运行外部库离线、刷新、回退及模块化构件回归，并在桌面端验证统一素材浏览、预览、复制和放置。桌面测试使用软件 WebGL 渲染以稳定运行最小化窗口中的真实 3D 预览。

源码门禁还先构建 web-dist，并用 viewer 锁定的 Playwright 显式安装完整 Chromium；`PLAYWRIGHT_BROWSERS_PATH` 固定到本次 `build/portable-browser`，供源码回归和后续 portable 打包共用，不依赖 runner 偶然预装的 Edge或额外 headless-shell。随后运行共享渲染/快照校验、评论索引迁移与证据、独立开口、独立尺寸/非48网格交付、候选校验、工作区API取消、碰撞反例、整体精修及网页回导回归。核心夹具只写全新的 `build/ci-model-pipelines`，既有目录或任何检查失败直接使CI失败，不静默跳过，也不把模拟确认用于真实作者模型。打包后另用挂起的本机模拟API检查实际工作区切换会中止旧连接、允许新请求，并且不把旧结果/活动写到新工作区。

`tests/node/task-cancel.mjs`另用超过50万格的真实合成主稿启动Python，确认PID仍存活后分别取消前置inspect和实际preview任务，检查cancelled状态、诊断保留和后续任务可继续；服务关闭也须结束自己创建的非job inspect子进程。该测试不使用sleep伪造工作，不扫描杀死用户其他进程。

## 产物与本地构建

发布产物包括 `NBTCreator-<版本>-windows-x64-portable.zip`、`.zip.sha256` 和逐文件 `.manifest.json`，以及下面说明的应用更新包与运行环境包。用自有 ZIP 脚本确保 `.agents` 隐藏目录被保留，拒绝用户资产、运行日志、环境文件和 API 配置。普通 CI 产物保留 14 天，Release 资产长期保留。

先按[开发指南](DEVELOPMENT.md)准备依赖，再从软件源码根目录构建与检查：

```powershell
mise exec -- npm run package:portable -- --out dist/portable
mise exec -- npm run test:portable -- --archive-dir dist/portable
```

## 发布规则

发布时，更新 package.json/package-lock.json 的版本，提交并推送，再为该提交创建与版本一致的全新注解标签并推送。已发布版本不可复用，需要增加版本号。手动 workflow_dispatch 只生成构建产物，不发布未打标签的版本。

Portable 表示免安装目录包，工作区仍由用户选择。API 密钥仍保存在 Windows 用户级加密配置中，不随 ZIP 发布。请保留完整目录，不要仅复制 exe。未签名程序沿用原说明。全屏问题 NBTC-001 已根据用户于 2026-11-04 的确认关闭，CI 不触发全屏。

运行环境打包参考 [Python 嵌入分发说明](https://docs.python.org/3/using/windows.html#the-embeddable-package)，触发与权限参考 [GitHub Actions 说明](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。仓库实际流程以 [portable.yml](../../.github/workflows/portable.yml)为准。

## 完整包与分离包

每次构建同时生成 full Portable、app-update、runtime 三个 ZIP，以及各自的 SHA256/文件清单。首次使用可直接下载 Portable，也可将 app-update 与 runtime 解压到同一父文件夹，合并同名 NBTCreator-win32-x64 目录。后续依赖未改变时，只需更新 app-update，保留已有 runtime。

app-update包含应用源码、建模工具、预构建前端和Skill资料，不包含Electron、Python和Chromium。runtime包含Electron宿主、Python与Chromium；体积大但可复用。运行环境ID绑定Electron版本、Python/wheel锁和Playwright版本，启动时核对应用所需ID与runtime-info.json，不匹配时提示下载配套runtime或完整版。旧1.6运行包没有该标识，首次使用1.7应用更新包需要配套运行环境。

CI 会验证两份分离包的文件互不重复，并按路径和字节哈希确认它们能完整重组为完整包。完整解压测试仍会运行私有 Python、CLI、Skill 生成、Chromium 和批量出图。新版本的校验文件随 Release 提供，不复用旧版本的 ZIP 哈希。

本地仅制作应用更新包可运行 `mise exec -- npm run package:portable -- --app-only --out dist/update-版本`，它不下载/复制Python或Chromium；不能把该临时构建文件夹当完整免安装包。应用更新ZIP需解压覆盖已有兼容runtime，启动时仍验证runtime_id。云端发布继续构建完整与两种分离包并执行全套解压验证。

本地需要完整免安装文件夹而无需ZIP时：`mise exec -- npm run package:portable -- --directory-only --out dist/full-folder`；校验：`mise exec -- npm run test:portable -- --directory dist/full-folder`。目录模式仍打入完整运行环境，不可与 `--app-only` 同用。

返回[文档导航](../README.md)。
