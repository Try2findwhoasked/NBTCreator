# 设置、关于与下载更新

顶部“设置”提供常规配置、更新和关于三个页签。常规项为界面缩放、自动效果预览、默认3D质量，以及工作区选择入口。保存后即时应用缩放和自动预览；预览质量在下次打开3D时使用，配置独立保存在当前用户preferences.json，不覆盖API或工作区配置。

关于显示应用版本、系统架构、Electron/Node版本、Python解释器与项目定位。

## 一键拉取更新

点击检查更新，读取固定项目GitHub最新稳定Release，按数值版本比较，避免降级。选择应用包或完整便携包后下载到用户配置目录的updates/版本/，下载进度可见，完成后检查长度与SHA256；成功才将partial文件转为正式ZIP。校验失败保留先前已验证文件，清理本次partial。

本阶段完成检查、下载和校验，**不自动安装或覆盖正在运行的程序**。点击“打开下载目录”，关闭应用后解压；依赖版本不兼容时选择完整版或配套runtime。更新包不写入建筑工作区。

私有仓库需要对本项目有Contents只读权限的GitHub令牌。更新页单独加密保存，可删除；不会复用AI Key，不把令牌传到下载CDN。公开可访问的发行版无需令牌。下载地址固定为本项目资产接口，重定向仅允许GitHub资产域；校验文件也从同一Release读取。

版本和下载协议参考GitHub官方接口：[Release](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)、[Release asset](https://docs.github.com/en/rest/releases/assets#get-a-release-asset)。
