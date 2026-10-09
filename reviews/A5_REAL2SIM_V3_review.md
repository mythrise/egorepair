# A5_REAL2SIM_V3 方案审阅意见

- **审阅对象**：A5主方案 `A5_REAL2SIM_V3_20261006`（PLAN.md，共153行；下文"第N行"均指该文件）
- **审阅日期**：2026-10-09
- **依据**：
  - PLAN.md 正文。
  - 本仓库中的上游真实工件，主要是 `EgoRepair_Studio_视频制作素材_原始文件/P1/scene/basic_pick_place_117`（下文简称 `pick117/`）。
  - `P2/reports/TASKS.md` 和 `EXPERIMENT_LOG.md`。
  - MuJoCo、PhysX、OpenUSD、Isaac Sim 的官方文档。
- **复核方式**：每条意见都经过独立复核：
  - 数值用原始JSON重新计算。
  - 仿真器行为对照官方文档。
  - 每条意见都逐行对照方案原文，尝试反驳。方案已覆盖或被误读的意见，已经删除或改写（见附录B）。
- **未覆盖范围**：
  - 第97行链接的4个 `real2sim/*.md` 子文档不在上传内容和仓库里，没有审。
  - 所有 `.npz` 都是 Git LFS 指针，只读了JSON元数据，没有读深度数组本身。

---

## 总体判断

方案的方向和边界大体合理。来源分层、VLM不签物理、settle不回写、禁止weld、技能做留出验证、两个后端分别验收，这些设计都应保留（见第4节）。

主要问题集中在三个方面：

1. **冻结的上游估计和物理一致性之间有冲突。** 上游估计本身有厘米级的不一致。方案禁止A5修正这些量，却没有给出一条有界、可记录的处理路径。按现行规则，第一条pilot很可能卡在R3/R4（H1、H2、M10）。
2. **物理和坐标约定缺失。** 缺的包括重力方向、相机轴约定、后端之间的参数映射，以及机器人模型的动力学缺口（H3、M2、M3、M4）。
3. **验证和评价存在循环。** R6用的是构建时的同一批证据；§5没有定义评估域；pilot样本来自测试集（H4、H5、M1）。

---

## 1. 问题总表

| 编号 | 严重度 | 问题 | 方案位置 |
|---|---|---|---|
| H1 | 高 | 冻结估计与接触一致性冲突，"合法小幅候选"没有定义 | 88, 90, 110, 112, 114 |
| H2 | 高 | 冻结的机器人base与A5补出的墙和托盘干涉，且没有回流路径 | 62, 93, 104, 106, 110 |
| H3 | 高 | sim的重力方向没有定义，上游已有两种重力约定 | 88, 102 |
| H4 | 高 | R6几何复核与构建共用同一来源的证据 | 93, 101 |
| H5 | 高 | 互补假设的评价协议没有定义 | 42, 148, 150 |
| H6 | 高 | 混合数据的动作表示、相机来源、观测特权没有定义 | 95, 136, 140 |
| M1 | 中 | 数据划分没有治理，pilot来自 official_test | 87, 133, 142, 148 |
| M2 | 中 | "原K"有歧义；缺OpenCV↔USD相机约定 | 88, 93 |
| M3 | 中 | 同一SceneIR映射到MuJoCo和PhysX时，摩擦组合规则与参数不一致 | 92, 118 |
| M4 | 中 | 没有列出A2机器人模型的动力学缺口 | 91, 104 |
| M5 | 中 | 没有声明质量/惯量的建模方式，也没有度量碰撞近似的偏差 | 91 |
| M6 | 中 | R7失败没有归因，也没有回流路径 | 77–79, 94, 112 |
| M7 | 中 | 对象默认来源写成了SAM3D，与实际不符，且缺审计状态 | 103 |
| M8 | 中 | 技能只有单臂语义，缺执行臂指派和非执行臂策略 | 131, 136, 140 |
| M9 | 中 | 米制证据在时间上稀疏，没有定义事件覆盖和动态pose的来源 | 89, 93, 101 |
| M10 | 中 | 尺度门是二值的，尺度不确定度没有传入物理 | 87, 88 |
| M11 | 中 | 没有定义对象类别范围（可变形体等） | 89, 91 |
| L1 | 低 | "已冻结事实"应改为"冻结估计" | 62 |
| L2 | 低 | 接触标签没有分级 | 47, 50, 95 |
| L3 | 低 | 没有断言USD的单位和上轴 | 92, 118 |
| L4 | 低 | 持物初态缺少允许方法的清单 | 94, 114 |
| L5 | 低 | 缺求解器确定性配置和统计化验收 | 92, 94 |

---

## 2. 高优先级

### H1 冻结估计与接触一致性冲突

**方案位置**
- 第88行R1："不二次缩放深度/mesh"。
- 第90行R3："已有mesh/pose不重新生成/scale/snap"。
- 第110行："改变源pose/scale/camera需回上游"。
- 第112行：默认3个候选版本。
- 第114行："合法小幅候选也要重新检查源重投影/支撑"。

**问题**

方案锁死了源pose和尺度，只给出"回上游"一条路，而第114行的"合法小幅候选"没有可计算的定义。上游估计本身有厘米级的不一致，按现行规则，静置物体在sim初态中会悬空或穿透：

- 悬空的物体开场就会下落，初态因此改变。
- 穿透的物体会被求解器在几步内推出，产生非物理的冲量。

两种情况下，R7的失败都会被错误地归到参考或控制器上。

**依据（pick117）**
- 12个MoGe3深度帧各自拟合出局部桌面。它们相对共享平面的偏差从 −21.1 mm（第150帧）到 +22.6 mm（第300帧），第90帧不可用。各帧锚点距离在 0.327–0.370 m 之间，相对中位数 0.356 m 为 −8.3%/+4.0%。
- `TableEstimate.json` 中 `fit_converged=false`，`status=TABLE_UNRESOLVED`。
- 托盘先例（TASKS.md 第756行）：旧的 initial block 为了贴合CAD内移了13.497 mm，原始重投影误差20.405 px，超过了标注的12 px不确定度。记录还写明"2mm初始间隙是模型施加的"。
- 同一场景的native回放在第157步停止，原因是block与托盘壁穿透2.611924 mm（第561行）。

**注意**：如果只按深度σ（约±2 cm）设平移预算，托盘那次13.5 mm的错误平移也会被放过。所以预算必须同时受像素重投影的约束。

**建议**
1. SceneIR中的源pose始终只读。R3的措辞改为"编译器不静默snap"。
2. 增加一个"接触闭合"派生初态：对静置物体，沿支撑法向做最小范数的刚体平移，使穿透为0、间隙不超过ε。这一步记为具名的 SIM_ASSUMPTION，同时保存原pose、平移量Δ和理由。
3. 接受这个派生初态须同时满足两个条件：
   - |Δ| 不超过对象注册与支撑面的联合不确定度；
   - 平移后，在所有有深度依据的帧上，源重投影误差仍不超过已标注的像素不确定度（pick117为12 px）。

   任何一条不满足，就按第110行回上游，生成新的 ObservationVersion。
4. 用这条定义替换第114行的"合法小幅候选"。

### H2 冻结的机器人base与A5场景干涉

**方案位置**
- 第62行把K、base等列为冻结工件。
- 第93行R6："原K/base/锚点只读"。
- 第104行：沿用base。
- 第106行："不能让未知几何'消失'以改善可达性"。
- 第110行：一次source-scene固定"机器人/tool/base"，但回上游的条件只列了pose/scale/camera。

**问题**

A2的base不是观测量，而是在"名义桌面、无墙、无对象"的模型里搜索出来的设计量。A5按R2补出墙、托盘等任务相关障碍后，pick117冻结的右臂base已经和静态场景干涉。对这种情况，方案既没有合法的修复手段，也没有回上游的路径。

**依据**
- `PlacementV34.json` 中：
  - `installation_mode=INTERNET_FIXED_BASE_SEARCH`
  - `arm_collision_qualification=NOT_EVALUATED`
  - `scope=DECLARED_STATIC_VIRTUAL_MODEL`
  - `physical_installation_qualified=false`
- A2静态IK的 `required_geometry` 只有 `robot_self` 和 `nominal_table_halfspace`。
- 第0帧画面是一个墙角工位：有后墙和右墙，灰托盘靠右墙放置。右臂安装中心在桌面坐标 T(0.338, 0.400)，yaw = −π/2。
- 用A2自己的 reference_camera K/T_WC 和桌面平面，把第0帧中右墙与桌面的交线（像素(590,283)→(680,335)，目测取点，约±1 cm）反投影到桌面上：
  - 右臂中心越过墙线约1.5 cm，足印最深越线约8 cm。
  - 右臂中心投影回第0帧，落在像素(693,337)，正是右墙、桌面和托盘左后角的交汇处。
- 右臂足印约57%（膨胀后的足印约64%）落在 `MultiViewTableModel` 的 ASSUMED_VIRTUAL 补全区。该区属于 `RECTANGULAR_DESIGN_COMPLETION_NOT_OBSERVED_PHYSICAL_EXTENT`，面积0.309 m²；建模区总面积0.654 m²。
- 待抓的小物件位于后墙墙脚附近。A2的接近轨迹是在无墙模型中解出的，也没有验证过。
- 按现行规则，这种干涉会被第104行的"动态资格必须在新scene重验"发现，随后该scope停止（第112行）。它不会被静默地仿真下去，但也没有出路。

**建议**
1. R0把base、安装和关节参考标为上游设计量（`A2_DESIGN`），与K、深度这类观测估计分开管理。
2. 在R0/R4加一道编译期静态干涉门：对A5重建的墙、托盘和背景，检查机器人足印、home位形和参考轨迹扫掠体的碰撞，未知区域先做膨胀。
3. 检查不通过时，发出 `BASE_REPLACEMENT_REQUEST` 回A2，由A2用A5的碰撞几何重新搜索。这条回流单独计版本，不占A5场景的修正额度。
4. 桌面支撑域取"观测到的支撑 ∩ 墙内侧"。设计补全区最多只用来承载固定基座，不作为物体初态或放置区域。

### H3 sim重力方向未定义

**方案位置**
- 第88行R1："固定T_SW"。
- 第102行："继承…A2多视角平面/合法域，A5只加刚性坐标桥，不重定义现实布局"。

**问题**

方案没有规定sim中的重力向量。上游标注的"重力向上"和现有物理场景实际使用的重力不一致，而支撑面法向与两者都相差好几度。

**依据**
- `TableEstimate.json` 的 normal_source 标注为 `GRAVITY_UP_WITH_TABLE_TOP_EVIDENCE`（basis `FROZEN_A1_GRAVITY_AND_VISUALLY_PROMPTED_TABLETOP`），即把A1世界的 +z 当作重力向上。
- 第102行继承的A2多视角平面，法向与 +z 的夹角为3.67°。另一个单帧估计（TableEstimate，未收敛）的夹角为5.58°。两个法向相差3.05°，说明法向本身有约3°的不确定度。
- 同一W坐标系下的现有A4物理场景（`P0/Physics/original_clock_native_20261008_01/Scene.xml`）设定 gravity = (−0.186, −0.457, −9.798)。它与 −z 的夹角为2.88°，与A2平面法向相差2.12°。也就是说，上游现在已经存在两种重力约定。
- 如果取 g = −z_W，A2桌面上的切向重力分量为 9.81·sin3.67° ≈ 0.63 m/s²。
  - tan3.67° ≈ 0.064，远低于常见摩擦系数，所以箱形物体不会滑动。
  - 但圆柱、球、侧放的杯子会滚动。"直立""放平"这类谓词也会因参考方向不同而得出不同结果。

**建议**
1. R1明确写出 g 的方向和来源（例如沿用A1冻结的重力，g = −z_W），作为T_SW的一部分写入SceneIR。同时与A4已有场景对齐，或者显式说明两者的差异。
2. 记录所用支撑面法向与 g 的夹角及其不确定度（约3°），超过阈值（例如1°）时做标记。
3. A5不自行旋转整个源布局，也不自行把桌面调平。确实需要调平时，作为具名 SIM_ASSUMPTION 处理，或者回上游用重力先验重新估计平面。
4. 任务谓词要注明是以重力为参考，还是以支撑面法向为参考。

### H4 R6几何复核与构建共用同源证据

**方案位置**
- 第93行R6："事件中心五问＋全可用帧数值诊断"。
- 第101行：新增帧"只走同一MoGe3来源"。

**问题**

几何由MoGe3深度构建，R6又用同一批深度做重投影和深度一致性检查，几乎按构造就会通过。方案没有区分构建证据和审计证据。

**依据**
- `RefitIntent.json` 中 `heldout_after_refit_is_not_independent=true`；final_all_views 中12个视图组的角色全部是 FIT。
- `MultiViewPlane.json` 中：
  - `holdout_reprojection_pass=false`
  - `rgb_only_observability.rank=0`，`maximum_fit_baseline_m=0.0`
  - 状态为 `DEPTH_PRIOR_WITH_WEAK_RGB_GEOMETRY`

**注意**：只把MoGe3帧切成构建组和留出组，并不能做到独立，因为同一模型的系统偏差在两组之间是共享的。而RGB基线为0，RGB留出也约束不了平面。

**建议**
1. R0对每个几何量分别登记构建证据集和审计证据集。
2. R6中只用同源MoGe3的检查，标为 `NON_INDEPENDENT_CONSISTENCY`。这类检查只用来发现矛盾，不用来签署几何精度。
3. 几何签署只用来源不同的证据，例如：
   - EgoDex官方HDF中接触事件时刻的相机SE3和手关节；
   - 未参与构建的RGB帧；
   - 已知的物体尺寸。
4. 没有这类证据时，状态写 `GEOMETRY_ACCURACY_UNCERTIFIED`，而不是PASS。

### H5 互补假设的评价协议未定义

**方案位置**
- 第42行把互补性列为待检验的假设。
- 第148行："同一批源的robotized-only、sim-only及混合数据，比较实际中间训练价值"。
- 第150行：研究问题。

**问题**

同源比较方案已经有了（第148行），但没有规定评估域、数据量和算力是否对等，也没有规定结论的适用范围。

- 在A5自己的sim里评估，结果会偏向sim分支。
- 只用转换后的robotized参考做离线评估，结果会偏向真实分支。

目前没有真机数据，这是现状，不是方案的约束；但正因为如此，更需要事先把评估设计固定下来。

**建议**

在§5增加一份预注册的评估协议：
1. 三组数据的样本量和训练步数/算力对等。
2. 至少设一个两个分支构建时都没用过的评估，例如：
   - 留出的目标场景ego片段（离线动作预测）；
   - 从留出视频独立构建的sim场景；
   - 条件允许时加真机。
3. 写明结论只适用于所用的评估域。例如结论是"中间训练对动作先验的收益"，而不是"真机收益"。
4. 与M1的数据划分规则一起执行。

### H6 混合数据：动作表示、相机来源、观测特权

**方案位置**
- 第56行：阶段级对应。
- 第95行R8："T命令/T+1状态"。
- 第136行：技能"读取当前对象/机器人状态"。
- 第140行：SkillPackage的"输入观察"。

**已覆盖**：重定时后只保留阶段级对应（第56行）；PTS与控制时间映射（第54行）；型号/TCP/q语义（第104行）。

**还缺三点**
1. **统一的动作表示。** 混合middle train要求两个分支的动作完全同构，包括：用EEF还是q、参考坐标系、控制频率、夹爪表示。"T命令/T+1状态"中的T应写明是控制步，而不是视频帧或物理子步，并通过时钟桥与源PTS关联。
2. **重定时或扩增后的渲染相机。** fixed-source回放可以用源ego的头部轨迹。但技能重定时或换了初态以后，人头轨迹仍按原来的时序看向原来的目标，与新的执行不再对应。需要写明相机轨迹的来源，并标注出来。可选来源有：
   - 按阶段映射原头部轨迹；
   - 固定相机；
   - 机器人挂载相机；
   - 新生成的注视轨迹。
3. **观测特权。** 技能按sim中的精确位姿生成动作，而渲染图里该物体可能被遮挡，模型就会学到图像本身不支持的标签。建议把SkillPackage的"输入观察"分成两类：
   - `privileged_state`：只用于生成标签和评价；
   - `perceived_obs`：策略可以使用。

   第142行中"直接被agent调用"的技能，必须只依赖 `perceived_obs`。

---

## 3. 中优先级

### M1 数据划分（split）未治理

**方案位置**：第87行R0、第133行技能改进、第142行rollout并入middle train、第148行首条示范。

**问题**

方案没有涉及数据划分：
- 仓库里全部EgoDex源组都是 `test/*`。
- pilot pick117 的 `split=official_test`，`source_group_id=test/basic_pick_place/117`；`PreparedManifest` 和 `SceneInputSelection` 都标了 `development_exposed=true`。

A5会在这类样本上做多版本修正、在有限预算内改进技能，并把rollout并入middle train。之后如果在EgoDex test，或者包含这些组的测试上做评估，就会造成数据泄漏。是否真的构成污染，取决于后续用什么评估集。

**建议**
1. R0把 split 和 development_exposed 作为必传的血缘字段。
2. ScenePackage、SkillPackage 和混合数据加载器都按 split 过滤。
3. official_test 样本只作为管线开发样本使用。
4. §5的结论性实验要声明评估集，并排除已暴露的组。

### M2 "原K"有歧义；缺OpenCV↔USD相机约定

**方案位置**：第88、93行。

**依据**
- pick117 至少有4个K：
  - anycalib：fx 865.558 / fy 876.416，非方像素；
  - A1有效K_source：fx = fy = 870.987，即前者的算术平均；
  - K_virtual：960×540，f = 435.494，主点重定到 (479.5, 269.5)；
  - EgoDex官方K。
- 深度在K_virtual体系下。`A_source_to_virtual` 含有 (−0.783, −0.563) px 的平移，不是简单的 ×0.5。
- `00_使用说明.md` 明确警告：960×540的深度"须按其原K_virtual绑定，不能直接错绑1920×1080原K"。
- 深度类型（`Z_DEPTH`）和像素约定（`PIXEL_CENTER_INTEGER`）上游已有记录，R1原样继承即可。

**建议**
1. 第93行的"原K"改为"与depth同源的K_virtual（经A_source_to_virtual关联K_source）"。anycalib和官方K只作为来源记录。
2. sim渲染用K_virtual，与960×540的virtual帧对照，不直接与原始1920×1080视频对照。
3. R1写明两种相机约定之间的轴变换和像素中心约定：OpenCV是x右、y下、z前；USD和MuJoCo相机是看向 −Z、+Y向上。
4. 深度标签用平面深度。Isaac Lab/Replicator中对应 `distance_to_image_plane`。注意OmniGibson的命名与Isaac Lab相反：它的 `depth` 对应 `distance_to_camera`（射线距离），`depth_linear` 才是平面深度。
5. MuJoCo从3.0.0起支持 focal/principal/sensorsize 内参，但只有同时给出 sensorsize 才生效。

### M3 同一SceneIR→MuJoCo/PhysX的参数映射

**方案位置**：第92、118行。

**已覆盖**：第118行已声明两个后端分别验收，不承诺相同的动力学结果。

**问题**

方案没有写参数如何从SceneIR映射到各个后端，而同名参数在两个后端中含义不同：

- **摩擦组合规则。** MuJoCo在两个geom优先级相同时，取两者摩擦的逐元素最大值；PhysX默认 `frictionCombineMode=average`，两个材质的模式不同时取枚举值更高的那个。上游已经出现过"top μ1 / tray μ0.6"这一组参数（EXPERIMENT_LOG 第724行）：MuJoCo得到1.0，PhysX得到0.8，夹持余量相差20%。
- **摩擦参数的形式。** MuJoCo的摩擦是三元组（滑动/扭转/滚动）加condim。PhysX区分静摩擦和动摩擦，没有滚动摩擦；扭转摩擦靠 torsionalPatchRadius 实现，并且依赖穿深，除非设置了 minTorsionalPatchRadius。现有A1X场景的手指用了 condim 6、elliptic锥、impratio 10，这些在PhysX中都没有直接对应项。

**建议**

SceneIR记录材质参数，以及每一对接触的有效摩擦意图。各后端导出时：
- 显式设置组合规则：PhysX用 frictionCombineMode，MuJoCo用 priority 或 `<pair>`；
- 在导出回执中列出 torsional/rolling/condim 的映射方式，或注明缺失。

### M4 A2机器人模型的动力学缺口未列出

**方案位置**：第91行R4、第104行。

**依据**
- `v34_robot/selected/placement/model/RobotConfig.json`：
  - `status=UNQUALIFIED_DUAL_CONTROLLER`，`controller_mode=offline_reference_only`；
  - 夹爪的 `coupling` 写的是"UNKNOWN: URDF has two prismatic joints without mimic; do not infer independent physical channels or symmetric coupling"。
- 但 `ModelJointReferenceV34` 的mimic矩阵设定 finger_joint2 = −finger_joint1，也就是A2已经隐含了对称耦合。第104行"沿用工具语义"会把这个隐含假设一起继承下来。
- `robot_geometry_gaps` 共19项：dual_base 缺 collision，另有18个连杆mesh非水密。
- URDF带有显式惯量和名义effort上限（臂关节27/50/14，夹爪100），所以惯量不算缺失。但effort只是名义值，握力和驱动增益都没有来源；而第112行又禁止"扩大握力"。

**后果**
- 夹爪耦合：MuJoCo用等式约束，PhysX用mimic或两个独立驱动，两者在不对称接触下的力分配不同。如果只驱动 finger1，finger2 会自由滑动。
- dual_base 没有碰撞体，两臂底座之间的互穿检测不到。

**建议**
1. R0对机器人资产单独逐项判定 REUSE/ADAPT/BUILD_MISSING：
   - 运动学链和TCP可以REUSE；
   - 夹爪耦合的实现方式、驱动增益、握力上限、碰撞凸分解，标为 BUILD_MISSING 或 SIM_ASSUMPTION，并纳入物理情景。
2. 两个后端用同一种耦合语义，并记录下来。
3. R7判定握持时，报告实际法向力与假设握力之比。

### M5 质量/惯量建模方式与碰撞近似偏差

**方案位置**：第91行。

**问题**
- 方案没有写惯量怎么得到。如果对闭合mesh按均匀密度积分，杯、盒、托盘这类薄壁件会被当成实心，质量、质心、惯量都会出错。上游已经有薄锥杯，托盘CAD也是按3 mm壁厚建模的。
- 质量是视频观测不到的量。
- 凸分解（如CoACD）会改变几何。第91行规定了"不封闭任务所需洞口"，但没有给出度量。

**建议**
1. R4声明每个对象是按实体还是壳体建模，以及壁厚的来源。
2. 质量、质心、惯量作为物理情景的参数集合，而不是单一值。
3. 碰撞近似要输出与视觉mesh或源mesh的偏差（例如单边Hausdorff距离），并检查开口和内腔是否保留。

### M6 R7失败无归因与回流路径

**方案位置**：第77–79行流程图、第94行R7、第112行。

**问题**

流程图里只有R6→R3这一条修正边。R7暴露的问题（例如托盘壁2.6 mm穿透、抬起约61 mm后滑落）应该走哪条路，方案没有定义。如果允许R7直接驱动改场景，就有"把场景调到让参考成功"的风险。第112行的"先修坐标/几何/接触方式""不用扩大摩擦/握力救错误几何"规定了修正顺序，但没有规定如何归因。

**建议**

R7失败先归因，再按类别回流：

| 归因类别 | 回流去向 |
|---|---|
| 场景几何/注册 | 按第110行回上游，生成新的 ObservationVersion |
| 参考（动力学可行性） | 走第104行的A3/A4修复接口 |
| 控制器 | 作为具名的控制器变体 |
| 物理情景/SIM_ASSUMPTION模型结构 | 生成新的SceneIR版本，重跑R6/R7，计入第112行的版本上限 |

pick117的记录显示关节/速度/effort门都已通过，失败来自托盘壁接触和抓取滑落，正是需要做归因的情形。

### M7 对象默认来源写成SAM3D，缺审计状态

**方案位置**：第103行。

**已覆盖**：R0读取实际producer和资格（第87行）；"未合格注册不能靠A5编译补成合格"（第103行）。

**问题**

第103行把"SAM3D固定模型"写成了默认来源。但pick117等两个场景实际用的是具名的 `MANUAL_CAD_FROM_VIDEO`，记录里明确写了"不冒SAM3D重建"（TASKS.md 第412行）。其中托盘的CAD正在接受源场景审计：真实托盘是曲壁，CAD是5个直壁，h40/t3 mm 是假设值。

**建议**
1. 第103行改为"已有对象模型（按实际producer，如SAM3D或具名MANUAL_CAD_FROM_VIDEO）及已注册pose"。
2. R0的ReuseDecision增加两个字段：对象来源类别和审计状态（QUALIFIED / AUDIT_PENDING / REJECTED）。
3. AUDIT_PENDING 只能作为诊断输入或ADAPT输入，不能REUSE。

### M8 技能只有单臂语义

**方案位置**：第131、136、140行。

**依据**
- 机器人是双臂独立安装的 a1x_dual。A2参考 `required_hands=[left,right]`，分母 604 = 302×2。
- pick117里只有左手在操作，右手整段静置在桌面上。
- 静态IK的 `clearance_m=0.0`，且包含名义桌面半空间，所以右夹爪的参考是贴着名义桌面的。而sim中桌面有约±2 cm的不确定度（见H1）。位置控制下，右夹爪要么悬空，要么压进桌面，产生很大的接触力，甚至推动桌上的物体。

**建议**
1. SkillPackage增加执行臂指派（`arm_assignment`）和非执行臂策略（停放/跟随/避让）两个字段。
2. "人手静置"映射为显式的停放位形，与桌面保持不小于 σ_table 的间隙。
3. 技能验证要覆盖左右臂指派的切换，并检查臂间碰撞。
4. 双手任务另设一种技能类型。

### M9 米制证据时间稀疏，事件覆盖与动态pose来源未定义

**方案位置**：第89、93、101行。

**依据**

pick117只有12帧MoGe3深度：stride 30，约1 Hz，占302帧的4%。第90帧被排除在桌面支撑之外；RGB-only秩为0。抓取、抬起、释放等事件大多落在两个深度样本之间。

**已覆盖**：新增帧只走同源MoGe3的新观察任务（第101行）；改变源pose需回上游（第110行）。

**还缺**：(1) 事件覆盖的准则；(2) 动态pose的来源类型和时间分辨率。

**建议**
1. R0按event_id列出每个事件到最近深度帧的时距。超过阈值（例如2帧）时，在评价冻结前一次性申请同源的事件帧，作为新的 ObservationVersion，并按H4分配到构建集或审计集。R6失败之后不允许再追加。
2. R2给每个动态pose标注来源类型（深度注册 / 手附着推断 / 插值）和时间分辨率。
3. R6只在有深度依据的帧上签署米制几何。

### M10 尺度门是二值的，尺度不确定度未传入物理

**方案位置**：第87、88行。

**依据**
- `InputManifest.json` 中 `world_metric_status=UNKNOWN`。
- 深度是 `ESTIMATED_METRIC`，属于单目先验。
- 桌面 `physical_accuracy_certified=false`。
- A2平面拟合允许 `height_factor_bounds=[0.5,1.5]`。
- 各帧锚点距离的离散为 −8.3%/+4.0%。这个离散包含深度、平面拟合和位姿噪声，所以是尺度误差的上界。另外，anycalib的fx与fy相差1.25%。

在物理中，尺度不是可以忽略的规范自由度，因为机器人CAD、夹爪行程和g都是绝对量。如果上述离散主要来自尺度，那么：
- 物体质量（∝ s³）会变化约 −23% 到 +12%；
- 物体相对夹爪的尺寸会变；
- 可达距离也会变。

**建议**
1. R0把尺度分为四级，并写明每一级允许的产出：

   | 尺度等级 | 允许的产出 |
   |---|---|
   | UNKNOWN | 只做几何诊断 |
   | ESTIMATED_METRIC | 可以做物理执行，但必须带尺度情景 |
   | CROSS_CHECKED、CALIBRATED | 可以签署米制精度 |

2. R1在T_SW旁边记录尺度来源和 σ_s。
3. R4增加尺度敏感度情景：场景整体缩放 s ∈ {1−σ, 1, 1+σ}，机器人不缩放。这只是敏感度情景，不替换主版本。
4. R7报告结果对 s 的敏感度。

### M11 未定义对象类别范围

**方案位置**：第89、91行。

**问题**

第91行只写了"不把未知关节自动降rigid"，全文没有提到可变形体、线缆、颗粒或液体。而EgoDex包含纸张、布料、线缆类操作；仓库里就有 clip_unclip_papers 录制，目前只有离线臂参考，没跑物理。

**建议**

R2/R4增加对象类别门：刚体 / 铰接 / 可变形 / 颗粒 / 液体。超出当前能力的类别只发布几何或静态scope的工件，不进入R7动态执行。

---

## 4. 低优先级 / 表述

- **L1（第62行）**
  - **问题**：第62行的"这些已冻结事实"夸大了上游估计的可信度。上游的标注是 `metric_accuracy=UNVERIFIED_MODEL_ESTIMATE`、`scale_level=ESTIMATED_METRIC`、`physical_accuracy_certified=false`。冻结只是版本纪律，不会提高可信度。
  - **建议**：改为"这些已冻结的上游估计"；R8的标签附上对应的σ。
- **L2（第47、50、95行）**
  - **问题**：接触标签没有分级。在多接触的静不定情形下，刚体接触力不唯一。
    - MuJoCo的软约束凸问题给出唯一解，但这个解依赖 solref/solimp/impratio/锥型/noslip/步长/迭代次数。
    - PhysX则在每个接触补丁内，把法向冲量平均分配到各摩擦锚点。
  - **建议**：R8把"接触对是否存在"（跨后端较稳健）与"逐点接触的数量/位置/力"（与求解器相关）分级标注。
- **L3（第92、118行）**
  - **问题**：方案没有断言USD的单位和上轴。
    - USD没写 metersPerUnit 时回退为0.01（厘米），upAxis 回退为Y。
    - Isaac Sim的应用默认值是1.0 m和Z-up；OmniGibson建stage时也设为1.0和Z。
    - 风险在于：米制资产被引用进厘米stage，或文件没写这些元数据，都会产生100倍的误差，而USD不会自动修正。Kit的metrics assembler还可能自动加上 `unitsResolve` 缩放。
  - **建议**：R5对每个导出的USD断言：metersPerUnit=1、upAxis=Z、没有意外的 unitsResolve 缩放op。否则就违反了"不二次缩放"。
- **L4（第94、114行）**
  - **问题**：方案已经禁止了weld、脚本驱动和自动落桌，但缺少允许方法的清单。
  - **建议**：
    - (a) 把起点前移到持物之前的源帧；
    - (b) 让机器人在关节和力矩限值内闭合夹爪，经过独立的稳定诊断后再开始计时。

    两者都做不到时，该scope标为 NOT_INITIALIZED。mocap、weld、外力都不算合法的初始化，这与 EXPERIMENT_LOG 第473行一致。
- **L5（第92、94行）**
  - **问题**：在冻结的构建、平台和配置下，单次回放是可复现的。但有两个缺口：
    - R5的环境证书没有记录求解器配置，包括CPU/GPU管线、PhysX enhanced determinism、substeps/迭代次数、随机种子、硬件/驱动/版本。跨平台时不保证逐位一致。
    - R7只做单次回放。在厘米级初态不确定度（H1）下，单次成功不能说明结果是稳健的。
  - **建议**：
    - R5记录上述配置。
    - R7在注册σ范围内扰动初态，重复N次，报告成功率和置信区间。
    - 回归测试比较阶段级和谓词级的结果，而不是逐位比较轨迹。

---

## 5. 值得保留的设计

- 区分来源层级，并区分"模拟内精确"与"重建精确"（第47、50行）。
- VLM分数不签物理（第93行）。
- settle不回写原初态，不复用旧场景证书（第92行）。
- 禁止隐藏吸附、weld和对象脚本驱动（第94、114行）。
- "不用扩大摩擦/握力救错误几何"（第112行）。
- 两个后端分别验收，OG预览不算MuJoCo通过（第118行）。
- 技能在未参与搜索的条件上验证，并登记已验证的适用范围（第134、140行）。
- 保留失败母体和原时钟（第95行）。
- LLM不能输出自由关节轨迹，也不能自报物理成功（第144行）。

---

## 6. 按行号的修订清单

| 行 | 建议修改 | 对应意见 |
|---|---|---|
| 62 | "这些已冻结事实"→"这些已冻结的上游估计"；base、安装和关节参考另列为上游设计量 | L1, H2 |
| 77–79 | 增加 R7 → 归因 → 各类回流的边 | M6 |
| 87 | R0增加：split/development_exposed；对象来源类别和审计状态；机器人资产逐项判定；尺度等级；构建/审计证据集；事件到深度帧的时距 | M1, M7, M4, M10, H4, M9 |
| 88 | R1增加：重力向量及来源；相机轴与像素约定；σ_s | H3, M2, M10 |
| 89 | R2增加：动态pose的来源类型与时间分辨率；对象类别门 | M9, M11 |
| 90 | R3："不重新生成/scale/snap"→"编译器不静默snap；接触闭合只作为具名SIM_ASSUMPTION派生初态" | H1 |
| 91 | R4增加：壳体/实体与质量情景；碰撞近似偏差；夹爪耦合、握力与增益；尺度敏感度情景；编译期静态干涉门 | M5, M4, M10, H2 |
| 92 | R5增加：USD单位与上轴断言；后端参数映射回执；求解器配置 | L3, M3, L5 |
| 93 | R6："原K"→"与depth同源的K_virtual"；同源检查标为 NON_INDEPENDENT_CONSISTENCY | M2, H4 |
| 94 | R7增加：失败归因；持物初始化的允许方法；重复与扰动统计 | M6, L4, L5 |
| 95 | R8增加：统一的动作表示与T的定义；相机来源；接触标签分级 | H6, L2 |
| 103 | "SAM3D固定模型"→"已有对象模型（按实际producer）" | M7 |
| 110 | 回上游的条件增加base（BASE_REPLACEMENT_REQUEST） | H2 |
| 114 | "合法小幅候选"按H1给出可计算的定义 | H1 |
| 136, 140 | SkillPackage增加：privileged/perceived观察区分；执行臂指派；非执行臂策略 | H6, M8 |
| 148 | §5增加预注册评估协议和split规则 | H5, M1 |

---

## 附录A 数据核对

路径相对于 `EgoRepair_Studio_视频制作素材_原始文件/`。所有数值都从原文件重新计算或读取过。

| 数值 | 文件 | 字段 |
|---|---|---|
| 逐帧桌面偏差 −0.02106（第150帧）到 +0.02262 m（第300帧），第90帧不可用 | `P1/scene/basic_pick_place_117/pilot_a1x_multiview/final_all_views/estimate/MultiViewPlane.json` | `result.per_frame_local_plane_checks[].difference_from_shared_plane_m` |
| 锚点距离 0.3267–0.3704 m，中位数 0.3563 | 同上 | `anchor_signed_distance_m`、`raw_height_spread_m` |
| holdout_reprojection_pass=false；RGB-only rank=0，基线0.0；12个视图组全部FIT | 同上 | `holdout_reprojection_pass`、`rgb_only_observability`、`frame_group_roles` |
| heldout_after_refit_is_not_independent=true | `P1/scene/basic_pick_place_117/pilot_a1x_multiview/RefitIntent.json` | — |
| fit_converged=false，TABLE_UNRESOLVED，table_thickness=null | `P1/scene/basic_pick_place_117/pilot_scene/observed/TableEstimate.json` | `plane_estimate.fit_converged`、`status` |
| 法向倾角：A2多视角平面3.67°，TableEstimate 5.58°，两者相差3.05° | 上述两个文件 | `plane_W.normal_W` |
| A4物理场景重力 (−0.186, −0.457, −9.798)，与−z夹角2.88° | `P0/Physics/original_clock_native_20261008_01/Scene.xml` | `<option gravity>` |
| anycalib fx 865.558 / fy 876.416 | `P1/scene/basic_pick_place_117/huro_frontend/clips_intr/basic_pick_place_117.json` | — |
| K_source f=870.987；K_virtual f=435.494，c=(479.5, 269.5)；A_source_to_virtual平移 (−0.783, −0.563) | `P1/scene/basic_pick_place_117/pilot_scene/prepared/PreparedManifest.json` | `K_source`、`K_virtual`、`A_source_to_virtual` |
| metric_accuracy=UNVERIFIED_MODEL_ESTIMATE；split=official_test；development_exposed=true | 同上 | — |
| 深度帧0,30,…,300,301（12/302），Z_DEPTH | `P1/scene/basic_pick_place_117/pilot_scene/moge3/DepthManifest.json`、`frames/*.json` | — |
| world_metric_status=UNKNOWN | `P1/scene/basic_pick_place_117/shared_geometry/basic_pick_place_117/frontend/observation/InputManifest.json` | — |
| height_factor_bounds=[0.5, 1.5] | `MultiViewPlane.json` | `result.policy` |
| INTERNET_FIXED_BASE_SEARCH；arm_collision_qualification=NOT_EVALUATED；physical_installation_qualified=false | `P1/scene/basic_pick_place_117/v34_robot/selected/placement/PlacementV34.json` | — |
| STATIC_KINEMATIC_REFERENCE_NOT_COLLISION_OR_EXECUTION_CERTIFIED；MODEL_REFERENCE_NOT_COMMAND；mimic finger2=−finger1；robot_geometry_gaps共19项 | `P1/scene/basic_pick_place_117/v34_robot/selected/joint/ModelJointReferenceV34.json` | `metadata` |
| UNQUALIFIED_DUAL_CONTROLLER；offline_reference_only；coupling UNKNOWN | `P1/scene/basic_pick_place_117/v34_robot/selected/placement/model/RobotConfig.json` | — |
| 托盘内移13.497 mm、20.405 px > 12 px；穿透2.611924 mm；抬约61 mm后滑落；MANUAL_CAD_FROM_VIDEO | `P2/reports/TASKS.md` | 第756、561、412行 |
| top μ1 / tray μ0.6 | `P2/reports/EXPERIMENT_LOG.md` | 第724行 |

计算：
- 9.81·sin3.67° = 0.628 m/s²；tan3.67° = 0.0641；tan5.58° = 0.0977。
- (1−0.083)³ = 0.771；(1+0.040)³ = 1.125。

---

## 附录B 复核中删除或修正的意见

初稿中以下内容经复核后删除或修正，列出来以便追溯。

**删除**
- **"3个候选版本上限容易耗尽"。** 第112行写的是"默认"，同一行还规定额度耗尽时停止该scope；第110行也没有限制一个版本只能改一处。硬上限是有意的设计。
- **"单条视频只有一个杯子，换杯子需要外部资产库"。** 第136行是在禁止夸大泛化，并没有声称支持换杯子；第134、140行已要求登记已验证的适用范围。另外，部分源（例如 stack_unstack_cups_5）本身就含有多个杯子。
- **"时钟桥会累计漂移"。** 第54、88行已要求保存PTS↔仿真时间映射。有这个映射时，非整除的步长只会造成不超过半步的量化误差，不会累积。整除步长可以作为子文档里的实现细节。

**修正**
- 初稿认为§3.4的"合法小幅候选"与R3的"不snap"字面矛盾，这不成立：前者指走版本流程的候选。真正的问题是它没有定义（见H1）。
- 初稿认为"两个桌面法向不知该用哪个"。第102行已指定A2多视角平面，所以改为"法向不确定度约3°，且重力约定不一致"（见H3），并补充了A4场景实际使用倾斜重力的事实。
- 初稿以"人手速度可能超出力矩限"作为R7失败的例子。pick117的记录显示关节/速度/effort门已通过，所以改用托盘壁接触和抓取滑落作例子（见M6）。
- 初稿说逐帧尺度约±6%。实际是相对中位数 −8.3%/+4.0%，而且这个离散包含深度、拟合和位姿噪声，只是尺度误差的上界（见H1、M10）。
- 初稿把"无真机评估"写成方案的约束。方案只是把遥操作排除出必要输入，并没有排除真机评估，所以改为"现状"（见H5）。
- 初稿把Z_DEPTH和像素中心约定列为缺失。上游已有记录，R1继承即可；真正缺的是相机轴变换和"原K"的指代（见M2）。
- 初稿说A4场景用了 solref "0.01 1" 和 friction 0.6。实际上 solref "0.01 1" 只出现在SO101场景中；A1X场景没有设 solref（默认0.02 1），0.6是托盘、铲和块的摩擦，不是手指的。正文只保留已核实的 condim 6、elliptic锥、impratio 10。

---

## 附录C 参考文档

- MuJoCo Modeling – Contact parameters（摩擦和condim的组合规则）：https://mujoco.readthedocs.io/en/stable/modeling.html#contact-parameters
- MuJoCo XML reference – geom friction：https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-geom-friction
- MuJoCo Changelog 3.0.0（相机内参属性）：https://mujoco.readthedocs.io/en/stable/changelog.html#version-3-0-0-october-18-2023
- MuJoCo Computation（软接触与唯一解）：https://mujoco.readthedocs.io/en/stable/computation/index.html
- PhysX PxCombineMode（默认 eAVERAGE）：https://nvidia-omniverse.github.io/PhysX/physx/5.6.1/_api_build/structPxCombineMode.html
- OpenUSD UsdGeom linear units（metersPerUnit 回退为0.01）：https://openusd.org/release/api/group___usd_geom_linear_units__group.html
- OpenUSD UsdGeomCamera（看向 −Z，+Y向上）：https://openusd.org/release/api/class_usd_geom_camera.html
- Omniverse Replicator annotators（distance_to_image_plane / distance_to_camera）：https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator/annotators_details.html
- OpenCV calib3d（像素坐标约定）：https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html
