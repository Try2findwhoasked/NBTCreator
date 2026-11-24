# 论文依据与适用范围

| 原始材料 | 可直接借鉴 | 适用前提与限制 |
| --- | --- | --- |
| Fridh 与 Sy，*Settlement Generation in Minecraft*，§5.1、图 6、§5.4.5 图 21、§5.4.8 与图 24。[论文 PDF](https://www.diva-portal.org/smash/get/diva2%3A1480297/FULLTEXT01.pdf) | 家具作为以局部锚点放置的预制对象。图 6 用三块活板门表达扶手与椅背，§5.1 正文把坐面写为半砖，图注写为楼梯。图 21 沿墙留布置格，与门在各方向至少隔一格。部署取朝向空地的方向，并按房间分配家具。 | 论文的靠墙与一格避门适合其 MCEdit 生成器。这里让宿主声明实际可写盒、落脚点和必须保留的通路。半砖与楼梯都作为备选，状态、朝向和几何按 Java 1.20.1 实测。 |
| Lennon 等，*Image2Lego*，§3、图 7。[论文 PDF](https://arxiv.org/pdf/2108.08477) | 把图像解释、目标体积和最终积木实现分开。图 7 的测试椅保留了腿、扶手、背与大致比例，不同 LEGO 件共同实现体积。 | 单张图的深度细部会变粗，遮挡的后腿可能缺失。论文使用训练过的体素重建和 LEGO 转换，本文只借用阶段划分。每个遮挡假设在规格内独立记录。 |
| Li 等，*Learning 3D Part Assembly from a Single Image*，§3–4、§6 图 3–4。[ECCV PDF](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123510664.pdf) · [作者示例](https://cs.stanford.edu/~liyichen/projects/assembly/) | 给椅腿、背横档、桌支承、柜内水平板分别建部件实例，记录重复族与装配关系。图 3 中可见横档帮助定位被遮挡横档，柜内板由类别先验补全。 | 输入已含完整 3D 零件点云，输出为相机坐标中的部件位姿。实验来自 PartNet 合成数据，视角信息不足和异形对象会失败。这里由观察者先列部件，再单独冻结推断。 |
| Pun 等，*Generating Physically Stable and Buildable Brick Structures from Text*，§4 与图 3。[ICCV PDF](https://openaccess.thecvf.com/content/ICCV2025/papers/Pun_Generating_Physically_Stable_and_Buildable_Brick_Structures_from_Text_ICCV_2025_paper.pdf) · [作者全文](https://arxiv.org/html/2505.05469v3) | 按件先验格式、库存、边界和占用，再评完整结构。其回退从首个不稳定积木的前缀恢复；这里保存规格与已有配方，定位失败件后修订并另出新候选。 | 论文的摩擦、静力平衡及底板针对互锁玩具积木。这里仅测方块状态、占用、声明接合、源保护与有限静态通路。坐卧、红石、相邻更新、活板门动态及游戏实装单列。 |

这些研究分别支撑配方布置、单图歧义、部件关系和候选拒绝。家具外观及复现结果见本仓实测记录。
