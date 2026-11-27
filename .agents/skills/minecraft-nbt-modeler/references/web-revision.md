# 网页保存JSON、修改意见与下一版建筑

本流程把当前参数效果保存为下一制作版。用户看过效果并明确要求导出时可以同时定稿。Agent 自主精修按 [缩略图确认流程](refinement.md) 执行。

## 意见文件位置

新标注自动保存在被标注建筑版本的 `修改意见/`。图片意见使用 `<源文件SHA256>/<图片SHA256>.json`，导出的 Markdown 在同一位置。建筑根目录的 `修改意见/` 和旧 `build/nbt_feedback` 中的历史标注可兼容读取。旧式源回导所用的参数副本仍归档在建筑目录的 `修改意见/设置/`。

网页中的“保存调整设置”只保存参数 JSON。“保存制作版”和“定稿导出 NBT”均绑定当前预览。CLI 默认保存制作版，明确要求定稿时才在请求 JSON 中设置 `"draft_only": false`。

## 转换命令

```powershell
mise run nbt -- control revision --request "D:/实际路径/保存的效果设置.json"
```

转换器根据源建筑分配下一版本目录，回执给出实际制作源路径。

独立脚本 `nbt_web_revision.py --input` 和 Python API `convert_web_json(input_file, workdir=None)` 还支持旧任务目录和 `after.json`。快照转换需保留同任务的原始请求，脚本复算并核对源、尺寸、状态与墙归属。参数 JSON 指明 source、settings 和坐标配置路径。

## 工作文件夹与版本

### 旧式源

旧版转换通过回读后推进建筑的当前版本。Git 归档失败时，回执中的 `history_pending` 和 `history_error` 标记待登记状态。恢复 Git 后可用 `history record --source <最新制作源> --set-current` 补登记，历史会按转换回执补齐父链。

从源路径识别原建筑目录。已有编号前缀按同前缀最大编号递增，例如 `v05` 之后分配 `v06`，`detail_v02` 之后分配 `detail_v03`。无编号时创建 `versions/YYYY-MM-DD_HHmmss_web_edit[_序号]/`，时间使用 Asia/Shanghai。历史布局需要指定工作文件夹时，独立脚本的 `--workdir` 指向同一工作区 `nbt_models/` 内的实际建筑目录。

- `master/model.snbt` 保存完整主模型和显式墙层。同目录的 `wall_mask.json` 提供墙层副本。
- 版本根目录的 `coordinates.json`、`cameras.json`、`settings.json`、`input.json` 和 `changes.json` 保存配置、视角、参数和变化记录。
- `validation/baseline.json` 和 `validation/whole_model.json` 保存原稿及候选的适用检查。
- `previews/README.json` 记录新版尚未出图。

### 受管制作版

在同一建筑目录下通过[工作模型](working-model.md#检查保存与恢复)发布 `v_model_<清单摘要前24位>/`，保留实例和父版本。

- `master/model.snbt`、`coordinates.json` 和 `model-instances.json` 保存完整主模型、墙层、坐标和实例。回导使用的机位保存在 `coordinates.json` 的 `cameras` 字段。
- `editing/settings.json` 和 `editing/input.json` 保存此次转换的参数与输入。版本根目录的 `changes.json` 保存相对父版本的变化。
- `validation/working-model.json` 记录当前制作阶段的检查。版本核心文件与父版本由 `model-version.json` 绑定。

### 回执与定稿

两种流程的 `conversion.json` 都记录实际来源、制作版路径和转换状态。制作版已发布但定稿失败时，错误给出实际 SNBT 路径，回执保留 `status: complete` 并记录 `release_status: failed`。从该 SNBT 单独重试定稿。需要看图时按 [渲染流程](rendering.md) 对新制作源出图。

定稿生成的完整 NBT、运行切片和分层交付写入 `nbt_models/_exports/` 的镜像版本目录，清单记录分片偏移、哈希和回读重组结果。

先在完整模型上复算并校验，再保存制作版。定稿时才机械切片和回读。独立模式支持非 48 倍数尺寸，按实际 `openings` 和路线检查，要求密闭时才提供探针。SAODG 模式沿用 48 格占地和专用端口。

旧模型的原坐标先在版本根目录查找，再查找该版本内的主稿所在目录及其父目录。每处按 `coordinates.json`、`config.json`、`context.json` 查找，最后可使用版本描述中指向本版本文件的 `context_file`。选择其他配置或单独调整机位时，原有的洞口或端口、密闭要求与探针、起点与目标、声明路线及占地继续生效。保护路径、保护区和留白也继续生效，改动预算取原制作版与本次设置中的较小值。下一版的显式墙层保存在 SNBT 内。

独立模式的定稿清单 `runtime/parts.json` 和 `delivery/delivery.json` 使用 `kind: standalone_xyz_tiles`，记录分片的 XYZ 索引、偏移和尺寸。每片保存含空气的运行模板，以及 body 和 walls 两层。整件没有墙层时，独立模式的上下文须显式设置 `allow_empty_wall_mask: true`。`nbt_standalone_delivery.verify_standalone(<定稿目录>)` 回读运行和分层文件，核对几何与墙层重组。

独立模式的非空 cells 描述有效 XZ 占地，保存时继承，定稿时据此切片。无 cells 或空 cells 使用完整包围盒的 XYZ 分片。

回归：`python scripts/fixtures/run.py check_web_revision_fixtures.py --output <全新目录>` 验证L形三片/六份分层、下一版编号、原稿保留、快照篡改拒绝与预算检查；这些只处理合成模型。
