# 网页保存JSON、修改意见与下一版建筑

本流程用于用户手动调参后的明确导出，不是自动批准agent精修。用户在网页查看本次参数效果后主动点“导出建筑下一版”，或明确指定某份保存JSON交给agent转换，才能生成对应新版本。制作脚本和合成测试无需资产确认。不制造approval.json，不借测试或留言文本取得批准。既有nbt_refine确认流程继续适用于agent自主精修。

## 意见文件位置

原建筑工作文件夹下使用 `修改意见/`：图片文字意见仍按 `<源文件SHA256>/<图片SHA256>.json` 保存，导出Markdown同位置；设置副本在转换成功过程中另存为 `设置/<源SHA256>/<设置记录哈希>.json`。信息仍绑定原图、原建筑、标记与引用的效果文件。旧 `build/nbt_feedback` 意见保留且可回读；后续保存写到新位置，不删除或覆盖旧目录。

网页中的“保存调整设置”仍保存参数JSON到选定文件夹，便于分享和@引用；只有“导出建筑下一版”或下列脚本生成NBT。该按钮要求当前设置已有对应效果预览，避免把未更新的设置当成已看到的结果。

## 转换命令

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_web_revision.py --input "D:/实际路径/保存的效果设置.json"
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_web_revision.py --input "D:/实际任务/jobs/编号/result/after.json"
```

脚本也提供可导入API `convert_web_json(input_file, workdir=None)`。参数JSON须带source、settings和坐标配置路径，原稿哈希有记录时必须匹配。支持完整任务目录、plan.json/bundle.json/job.json，通过同任务的request.json/settings.json取回参数。after.json不是独立NBT源：须保留同任务request.json，脚本重新计算并逐项核对原稿哈希、几何哈希、尺寸、方块和墙归属，拒绝脱离上下文的单张快照或被改动的快照。不会执行JSON中的任何代码或指令。

## 工作文件夹与版本

从source路径识别原建筑目录：跳过master/runtime/parts，v05→同建筑v06，detail_v02→detail_v03，refined_v3→refined_v4；编号按现有同前缀最大值递增，通过mkdir排他创建，已有版本不覆盖。无编号版本时在原工作文件夹 `versions/YYYY-MM-DD_HHmmss_web_edit[_序号]/` 保存。时间使用Asia/Shanghai。异常旧布局可显式传 `--workdir "D:/原建筑工作文件夹"`，不能指向skill安装目录或磁盘根目录。

新版本目录：

- `master/master_geometry.json.gz`：完整未切割主模型，保留真实方块状态与显式全局墙mask；同目录wall_mask.json提供独立归属记录。
- `runtime/parts/<日期>_<建筑编号>_pXX.nbt`：完整含空气的48网格运行切片；runtime/parts.json记录偏移、哈希及48连续回读重组结果。
- `delivery/`：每个有效cell恰好body/walls两份稀疏NBT，L形缺角不产片，delivery.json记录分层重建验证。
- `coordinates.json`、`cameras.json`、`settings.json`、`input.json`、`changes.json`：原配置、视角、参数记录和改动明细。
- `validation/baseline.json`、`validation/whole_model.json`：原稿及修改后完整模型的端口回封密闭、碰撞路线和已声明路线检查。
- `conversion.json`：来源及输入哈希、原版本、新版本、改动数、交付数量和complete/failed状态。只有complete表示该次转换完成。
- `previews/README.json`：明确尚未为新版本重新渲染。原版本图片不冒充新图；需要看图时按render流程对新主模型批量出图。

先在完整模型上重新计算和校验，再纯切割并回读；保留源文件、原墙归属和源哈希。严格执行变化预算，不支持的碰撞、缺墙mask、缺坐标配置或不符合48有效cells的尺寸会报错。校验失败通常不分配版本；写出中失败保留failed诊断目录，后续分配新编号。不会自动放宽检查、删除未知形状或补造墙归属。48连续重建与49运行间距、真实客户端及多人验收仍分别报告。当前版本接入不支持的独立非48素材应使用已有独立模型交付流程，不强套本转换器。

回归：`check_web_revision_fixtures.py --output <全新目录>` 验证L形三片/六份分层、下一版编号、原稿保留、快照篡改拒绝与预算检查；这些只处理合成模型。
