# 0.41.51 客户端纹理启动兼容修复

用户实际启动SAO-0.8后生成 `crash-2026-10-30_10.10.48-client.txt`。原日志、崩溃报告和崩溃后的options.txt已保存在忽略目录 `logs/client-startup-20261030-101048/`。

## 错误顺序与定位

初始资源重载先在PalettedPermutations$PalettedSpriteSupplier报Image is not allocated；Minecraft随后移除选中的资源包并重试，再在AAA Particles初始化EffekseerManager时崩溃。日志没有证明AAA Particles是首次失败的原因。

本机Paladin家具1.5.0的PFMAtlasLoaderMixin发现纹理时，过滤谓词先调用Supplier.get()，随后生成阶段又调用一次。此行为与[上游问题270](https://github.com/UnlikePaladin/paladins-furniture/issues/270)记录的调色板图片引用计数被提前消耗、并行加载读到已关闭图片一致。该上游报告是诊断线索；本机字节码已独立核对，实际启动修复效果仍待复测。

固定本机PFMAtlasLoaderMixin类SHA256 `2515d85a1aee7de5483ed88a65a22fc85d12ba7076b8276e0b4e158221443b36`；不修改第三方JAR。0.41.51新增可选客户端Mixin配置，只有该类指纹匹配时才应用。PFM合并方法完成后，在其发现谓词前为原版调色板Supplier直接返回false，让原版保留图片并自行加载；其他Supplier保持原调用。按完整类名比较，不访问不可公开的原版嵌套类。未知PFM版本不盲目应用此变换。

## 验证与安装

提交 `c3dd092bdd2ffd89991acd0fe5fb130c7c9f87de`。两项定向JUnit通过：实际加载并执行变换后的字节码，证明调色板Supplier不被get、普通Supplier仍get一次，重复应用不重复插入；缺失/歧义方法拒绝且不修改字节码。jar/reobfJar通过，未重复完整副本或GameTest。构建日志 `logs/pfm-palette-build-c3dd092-20261030.log`。

产物 `build/verified/0.41.51-dev-c3dd092bdd2f-pfm-palette-20261030/saodg-0.41.51-dev.jar`，SHA256 `7d010dc9c30bdaa96708dd541724afd355140e2edb982453fc40a798b3f2b76c`，75份正式NBT。主清单含saodg.pfm.mixins.json，修复只列在client；副本规则、实例放置及原生怪代码没有变化。

两运行端关闭后已备份更新：

- 服务器回执 `D:/Documents/Coding/Game/Minecraft/SAO-server-0.7/.saodg-backups/d3e1964a6f984ed4b6d342be854d9c66/receipt.json`，22项。
- SAO-0.8回执 `D:/Minecraft/.minecraft/versions/SAO-0.8/.saodg-backups/6218e33630634522a0848ae0eca129ab/receipt.json`，20项。

options.txt中resourcePacks已被Minecraft的失败恢复清空。按本次崩溃报告Last reload/Packs记录恢复5个仍实际存在的外部资源包，只改resourcePacks一行，其余设置保持；修改前复核options与保存快照字节一致。回执 `logs/client-startup-20261030-101048/resource-pack-selection-restored.json`。

## 当前边界

修复已编译、定向测试并安装，尚未再次启动真实客户端。不能把单元字节码测试当作实际Mixin已应用、成功进入主菜单或新局显示/通行通过；下一次启动需看到SAODG PFM palette supplier guard applied日志，再确认资源重载与主菜单。家具、AAA Particles和原资源包均保留，未采用移除模组来绕过问题。
