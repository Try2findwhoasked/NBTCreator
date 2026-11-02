# Windows Portable CI/CD

`.github/workflows/portable.yml` 在main、codex分支提交、PR和手动触发时构建Windows x64包；推送与package.json版本一致的 `v<版本>` 标签时，在构建及解压验证通过后自动创建GitHub Release。不覆盖已有Release或标签。预发行版本标签含连字符时标为prerelease。仓库保持私有，下载遵循仓库权限。

包内带固定版本及SHA256校验的Python 3.14.10、NumPy 2.4.2、Pillow 12.1.0；Electron提供Node，Playwright锁定版本提供Chromium用于批量出图。完整解压后运行NBTCreator.exe，无需另外安装这些运行环境。NBTCREATOR_PYTHON仍可显式覆盖解释器。

CI先运行工具一致性、冻结资料库、API/工作区/交接/提示词契约检查，再构建ZIP；逐文件验证解压内容，并在移除系统Node/Python搜索路径后检查私有Python、CLI、Skill生成和包内浏览器，之后运行打包版桌面和模拟API回归。失败不会发布。

发布产物为 `NBTCreator-<版本>-windows-x64-portable.zip`、`.zip.sha256` 和逐文件 `.manifest.json`。用自有ZIP脚本确保`.agents`隐藏目录被保留，拒绝用户资产、环境文件和API配置。普通CI产物保留14天，Release资产长期保留。

本地构建与检查：

```powershell
npm ci
npm ci --prefix .agents/skills/minecraft-nbt-modeler/assets/viewer
npm run package:portable -- --out dist/portable
npm run test:portable -- --archive-dir dist/portable
```

发布：更新package.json/package-lock.json版本，提交并推送；为该提交创建同版本的全新注解标签，再推送标签。已发布版本不能复用，应增加版本号。手动workflow_dispatch只生成构建产物，不另行发布未打标签的版本。

Portable表示免安装目录包；工作区仍由用户选择，API密钥仍使用Windows用户级加密配置，不会随ZIP发布。不要仅复制exe。未签名程序与已知全屏问题保持原记录；CI不触发全屏。

运行环境依据Python官方嵌入分发方式打包第三方库：https://docs.python.org/3/using/windows.html#the-embeddable-package 。GitHub触发与权限遵循官方Actions说明：https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow 。

## 1.7分离包

每次构建同时生成full Portable、app-update、runtime三个ZIP及各自SHA256/文件清单。首次可直接用Portable；也可将app-update与runtime解压到同一父文件夹，合并同名NBTCreator-win32-x64目录。后续依赖未改变时只更新app-update，保留已有runtime。

app-update包含应用源码、建模工具、预构建前端和Skill资料，不包含Electron、Python和Chromium。runtime包含Electron宿主、Python与Chromium；体积大但可复用。运行环境ID绑定Electron版本、Python/wheel锁和Playwright版本，启动时核对应用所需ID与runtime-info.json，不匹配时提示下载配套runtime或完整版。旧1.6运行包没有该标识，首次使用1.7应用更新包需要配套运行环境。

CI验证两份分离包文件互不重复且按路径/字节哈希恰好重组成完整包。完整解压测试仍运行私有Python、CLI、Skill生成、Chromium和批量出图。新版本校验文件随Release附带，不复用旧版本ZIP哈希。

本地仅制作应用更新包可运行 `npm run package:portable -- --app-only --out dist/update-版本`，它不下载/复制Python或Chromium；不能把该临时构建文件夹当完整免安装包。应用更新ZIP需解压覆盖已有兼容runtime，启动时仍验证runtime_id。云端发布继续构建完整与两种分离包并执行全套解压验证。
