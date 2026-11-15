# 1.5.0 · Portable与3D AI放置

新增版本标签自动发布Windows x64 Portable ZIP、SHA256和逐文件清单；构建失败不发布，已有Release拒绝覆盖。依赖内置Python 3.14.10、NumPy 2.4.2、Pillow 12.1.0、Electron Node和Playwright Chromium。API配置和用户建筑不入包，工作区规则保持。

3D选点可联动小型结构放置选区，设置宽高深后点击表面，再通过“生成并立即预览”调用API、校验步骤、插入候选并刷新3D。原稿保留，仍需主动导出下一版；没有扩展原模型边界，也不支持任意AI代码执行。

验证记录：

- 本机模拟API界面27项通过：build/api-desktop-1793631859952/results.json，含真实3D点击及一键生成预览。
- 最终Portable解压6项通过：build/portable-1793632371682/results.json，3496文件逐项校验，移除系统Node/Python路径后完成包内Python依赖、CLI、Skill生成、Chromium和Python→Node批量PNG渲染。
- 最终Portable桌面主流程20项通过：build/desktop-1793632382014/results.json。
- API契约12项、工作区Python8项/Node4项、Portable内容和越界路径契约2项通过。冻结资料库409文件哈希一致。
- GitHub首轮失败暴露英文Windows的中文stdout编码问题，改为UTF-8后云端构建成功：https://github.com/Try2findwhoasked/NBTCreator/actions/runs/41468647496 。发布标签会再次执行完整检查，发布结果以该标签的Actions/Release为准。

本地ZIP：dist/portable-1.5.0-final/NBTCreator-1.5.0-windows-x64-portable.zip，440015998字节，SHA256为9b468d47e467536bfd7b866e3a9ac6b8ce9d82d5f8cfb69e04728e0bd14084ad。源码提交信息和打包时间不同会改变ZIP哈希；Release以其附带的校验文件为准。

真实外部API效果未验证，测试使用模拟服务和合成模型；未触发全屏，不声称解决已知全屏问题。ZIP为免安装目录包，API密钥仍存在Windows当前用户配置目录，用户资产在自行选择的工作区。
