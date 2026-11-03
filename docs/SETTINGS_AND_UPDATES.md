# 设置、关于与下载更新

顶部“设置”采用常规、模型预览、工作区与存储、更新、关于五个分类。常规配置包含启动页、界面密度、缩放、窗口大小记忆和视口提示；模型预览包含自动预览、延迟、3D质量、范围框及图片数量。

应用偏好保存到当前工作区 `.nbtcreator/preferences.json`，切换工作区读取目标自己的配置；首次缺少本地配置时兼容迁入旧用户偏好，保留旧文件。模型质量和图片数量默认值用于之后打开的模型。API密钥和更新访问令牌仍在本机用户目录独立加密保存，设置页列出实际路径和打开目录入口。

工作区与存储页显示 `.agents/skills/nbtcreator-workspace/SKILL.md` 的实际位置，可预览入口并复制给Agent的接入说明。入口通过相对路径链接到工作区内的工具副本和启用资料；Agent需在同一项目下发现或主动读取入口，不保证所有Agent自动加载。

新修改方案位于当前结构版本的 `Agent交接/plan-任务编号/`，审阅位于同版本的 `review-任务编号/`。已有上层旧审阅继续按源路径和哈希匹配读取，不删除旧记录。

关于显示应用版本、系统架构、Electron/Node版本、Python解释器与项目定位。

## 一键拉取更新

点击检查更新，读取固定项目GitHub最新稳定Release，按数值版本比较，避免降级。选择应用包或完整便携包后下载到用户配置目录的updates/版本/，下载进度可见，完成后检查长度与SHA256；成功才将partial文件转为正式ZIP。校验失败保留先前已验证文件，清理本次partial。

本阶段完成检查、下载和校验，**不自动安装或覆盖正在运行的程序**。点击“打开下载目录”，关闭应用后解压；依赖版本不兼容时选择完整版或配套runtime。更新包不写入建筑工作区。

私有仓库需要对本项目有Contents只读权限的GitHub令牌。更新页单独加密保存，可删除；不会复用AI Key，不把令牌传到下载CDN。公开可访问的发行版无需令牌。下载地址固定为本项目资产接口，重定向仅允许GitHub资产域；校验文件也从同一Release读取。

版本和下载协议参考GitHub官方接口：[Release](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)、[Release asset](https://docs.github.com/en/rest/releases/assets#get-a-release-asset)。
