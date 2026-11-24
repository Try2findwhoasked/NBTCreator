# 参考图与分区建模

独立家具从[构件或工作模型](parametric-components.md)出发。已有建筑中的一组家具可以用[选区编辑](selection-edit.md)读取宿主、保护支点和编译局部操作。多个空间共用楼板、梯洞、通道或装配接口，或者用户明确要求分工时，使用制作运行。

## 建立运行与分工

在创作工作区根目录，用 `mise run nbt -- batches create --request batch.json` 建立制作批次。用 `mise run nbt -- batches run --request attempt.json` 增加 `stage` 为 `authoring` 的尝试，传入批次 `id` 和当前 `revision`。后续调用传该 `batch_id` 和新尝试的 `run_id`。工作流和候选保存在该尝试目录，制作版仍随原建筑的版本链保存。

用 `mise run nbt -- machine --schema` 查询完整协议。`mise run nbt -- machine --request request.json` 接受如下请求。写请求使用唯一 `request_id`，重试保留原编号和参数。

```json
{
  "protocol_version": 1,
  "request_id": "synthetic-inn-create-01",
  "method": "authoring.create",
  "params": {
    "batch_id": "批次登记返回的 ID",
    "run_id": "批次尝试返回的 ID",
    "mode": "existing_draft",
    "task": "保留两层走线并完成旅店家具"
  }
}
```

1. `authoring.bind_reference` 登记工作区内 PNG 或 JPEG。每张图含 `id`、`path`、`sha256`、`kind`、`role` 和已知 `source`。裁片含 `id`、`role` 和 `[左, 上, 右, 下]` 原图半开像素范围。说明按 `observation`、`proposal`、`assumption` 或 `correction` 登记，校正须附依据。透视图没有尺度标定时只用于解释轮廓和布置。有标定的正交图继续用[三视图](orthographic-reference.md)，并可在 `calibration` 提交经校验的清单路径和哈希。
2. `authoring.bind_baseline` 冻结完整 SNBT 和源哈希。`spaces` 每项含唯一 `id`、`purpose` 与 `box`，建议同时交代用途所需的主件、配套和站位。`interfaces` 用 `id`、`box` 和两个空间 ID 指定共享接点。采用已有规划时传 `layout` 的路径和哈希。通路、禁改和预算沿用源建筑有效坐标上下文，普通独立整栋须有可验证的 `start` 和 `targets`。如无相邻坐标文件，在 `coordinates` 传入工作区内的文件路径和哈希。
3. 领取 `root` 后用 `authoring.issue` 把区域分给二级。二级可用一次命令签发多个三级工作包。每个叶子有独立写区，使用 `lo` 和 `hi` 的全局整数 XYZ，含两端。默认读区在写区外扩一格，并继承上级授权。可显式扩大读区以覆盖接口两侧。写区和保护不可越过上级，兄弟包的读区可交叠。
4. 每个叶子登记带 `id`、`position` 和 `intent` 的构件。`reference_refs` 可引用 `图片ID:裁片ID`，`expected_views` 保留必看机位。`authoring.context` 返回页内调色板、墙层、全局 `origin` 和 `page_receipt`。只在页内把未列出的坐标解释为空气。提交时传 `read_sha256`、必要 `page_receipts`、逐件结果和 `{pos,before:[state,wall],after:[state,wall]}` 补丁。空气用 `["minecraft:air",false]`。
5. 二级用 `authoring.report_region` 汇报覆盖和阻塞，仅引用本区叶子候选。二级制作的区域几何也通过独立叶子提交。叶子需要缩小读取页或返工时，二级可用 `authoring.reissue` 保留 ID 重新签发，生成新修订与邀请。父制作版已前进时，从当前制作版另建尝试并重签。

## 角色会话

经宿主中介调用同一 CLI。`authoring.issue` 返回的各项 `invitations` 分发给对应宿主。宿主把本包邀请写入自己的会话文件，领取成功后用返回的 `lease_token` 和 `lease.fence` 更新该文件。一级也可用已领取根包的 `batch_id`、`run_id`、`package_id`、`package_revision`、`lease_token` 和 `fence` 建立会话。

```powershell
mise run nbt -- machine --package-session <宿主会话文件> --schema
mise run nbt -- machine --package-session <宿主会话文件> --request <任务请求>
```

受限请求可省略会话已有的包和租约字段。`authoring.brief` 默认给当前层提示词及包摘要，`section=references` 按授权引用展开图片，`section=feedback` 展开本包或直接子包的回执。宿主只向代理暴露会话筛选后的动作和获准文件，不把邀请、租约文件或原始 `authoring.json` 加入提示词。文件与 shell 隔离由宿主负责。局部出图先由父级分享相关机位。

## 合模、渲染与发布

一级提交候选 ID 与哈希，运行 `authoring.plan_merge`。预检用同一父源重新应用全部旧值补丁，并核对实际墙层、保护、去重变化预算与声明路线。只读邻域受其他候选改动时回执会带读包、写包和实际位置，先重新签发或处理共享接点。

`authoring.prepare_review` 从改点定位受影响空间和两侧共享面，写出共同机位文件。每项 `views` 含 `camera`，可附 `space`、`feet`、`route_start` 和 `use_face`。`use_face` 用 `position` 与垂直 `face` 核对实际操作侧，`focus` 可指定须在画面中可辨的局部点。实际脚位与机位相差 1.62 格。按回执的 `render_commands`，用相同的预构建前端、纹理、画面尺寸、质量与机位分别出图，输出选择两个新目录。

看过前后图后用 `authoring.record_observation` 登记照片清单路径及哈希、机位、所见和问题。允许以稳定问题 ID 复验此前问题。双方图像、站位与适用路线均核验后，`authoring.save_draft` 可用候选审阅回执发布。CLI 显式传 `technical_trial=pending_visual_review` 可保存技术试用版。桌面从「制作批次」读取 `authoring` 尝试、授权范围和证据，根包可领取且候选通过审阅时可保存。

正式展示再用 `target=draft` 为已保存 SNBT 生成或核验实际图像。候选观察、落盘版实图、用户看图授权精修和显式定稿各有自己的记录。静态路线与操作面通过后，游戏行为仍为待实测。[精修](refinement.md) · [手动定稿](snbt-authoring.md)
