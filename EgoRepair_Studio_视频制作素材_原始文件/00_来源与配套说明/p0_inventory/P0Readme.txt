P0 原素材核验说明

P0Inventory.json / P0Inventory.csv 是逐文件原字节清单；source 为打包读取路径，dest 为建议ZIP路径，source_resolved 为软链接真实来源，size/sha256来自实际原文件读取。来源均只读，本任务未转码、缩放、降帧、推理、训练或仿真。

1. 十个 EgoDex 配对
官方原archive：/data/xklv_data/raw/egodex_official_20260928/test.zip
原ZIP现有摘要sidecar为0218a1368e34495dbae166ebca7b237d52560ff422e42434b4481da9758dcc7f（该17.3GB archive本轮未重新整体hash；每个选中video/HDF5 member均实际读取hash）。
HDF5按Source.json声明的原source_member同stem精确提取，ZIP库校验CRC，输出内容与原member字节一致；只复制重命名以使MP4与HDF5同名。10个MP4也与同ZIP原member重新读出的SHA完全一致，均1920×1080/30fps。
短名映射：legos_33→assemble_disassemble_legos_33；fold_paper_10→fold_unfold_paper_basic_10；screw_allen_10→screw_unscrew_allen_fixture_10；bagging_10→insert_remove_bagging_10；clip_papers_1→clip_unclip_papers_1；box_4→open_close_insert_remove_box_4。
帧数：basic_pick_place117=302；pour32=214；stackcups5=270；sortbeads1=300；legos33=362；foldpaper10=317；screwallen10=1960；bagging10=337；clippapers1=953；box4=323。
HDF5保留camera/intrinsic(3,3)、transforms/camera、左右手/各手指/身体transforms(N,4,4)、confidences(N)。所有时序dataset帧轴均与完整原video解码帧数一致；静态内参矩阵不计入帧轴。HDF5无单独timestamp数组，不新造时间或6DoF数据。

2. 绝对EEF
输入alias共7条，但eef_data_actions.npz SHA仅4个不同原数据组：pick_place117、sort_beads1、stackcups5、pour32。相同SHA明确列sha_aliases；历史/v34路径没有伪称7套独立数据。
四组视频实际640×360/30fps；原数据source_frame_id/source_time_s与视频帧数逐一相符。eef_state/eef_state_available/eef_state_training_mask、model_opening_desired_m/model_opening_realized_m及各available/exact_mask、human_geometric_opening_m、render_tool_mask等保留原字段。开度人手几何值与模型夹爪值分开，validity/显示/训练mask不互换。

3. 机器人视频
原档案视频清单137项全部保留原字节，原体积438,940,825字节。模型参考、EEF展示、planning、synthetic sim展示、encoder fixture按原scope及fixture字段分列。三视图常见1920×360，robot_hybrid常见640×360；既有低分辨率原片保持真实尺寸。PlanningDemo302是规划呈现，不是物理成功。

4. 原生状态与物理素材
original_clock_native_20261008_01/Execution.json.gz原6400092字节：native_states2973项及qpos_full/time_s，稀疏states180项；原302帧计划未完整执行，不能宣称完整任务通过。
pregrasp_prefix_v4_native_20261008_01/PrefixExecution.json.gz原13103862字节：states5001项、commands5000项，原prefix101/302帧，whole_task_success=NOT_ACCEPTED_PREFIX_ONLY。
两组原Scene.xml及其实际mesh refs已保留。原XML含绝对file路径，原字节不改。P0/Physics/source_tree/ 保留每个引用的原绝对路径结构；迁移后需以manifest中的original_xml_reference→dest映射在渲染加载时重绑定，不能声称原XML开箱即用或改原文件来掩盖这件事。没有新增qpos NPZ，qpos_full/time仍位于完整原gzip JSON。
root_demo_fixed8_closure是八候选合成场景研究的Closure，而非视频目录。八个result.json.gz及资格报告、原模型资产保留；原qpos_full/time原生快照嵌在record.commands[].substep_contacts[]中，完整JSON内容未拆取/截取，不能把contact archive改名成独立qpos文件。
三个指定run没有找到已有MP4，尤其没有可确认>=1280×720的物理原片。缺项详见Missing.json。RecordedPolicy_F是另一份合成场景模型的已录制政策展示，来源与上述两个EgoDex native run分开。
额外提供F既有141帧JPEG（deployment_v2/site/assets/frames/f000.jpg...f140.jpg），每帧1280×800，原大小5831124字节，保持文件名和序列。它们是原MuJoCo展示图像，不冒充MP4或指定三个run视频。

5. 旧成片
五版原成片全部保留、全帧解码读回：v1=211s/12660帧；launch=41.95s/2517帧；v2=250s/15000帧；v3=193s/11580帧；v5=145s/8700帧。均1920×1080/60fps。未能唯一认定用户所说“两分钟问题”的版本；保留候选原时长及SHA。旧字幕/旧结论不作为最新资格事实。

核验命令：
PYTHONDONTWRITEBYTECODE=1 /data/xklv_data/egorobot_a2/envs/a2_v322_runtime_20260928/bin/python work/p0_inventory/inventory.py
PYTHONDONTWRITEBYTECODE=1 /data/xklv_data/egorobot_a2/envs/a2_v322_runtime_20260928/bin/python work/p0_inventory/augment.py
PYTHONDONTWRITEBYTECODE=1 a4_experiment/.venv-data/bin/python work/p0_inventory/add_frames.py
inventory脚本读取所有原SHA与container，十原视频/七EEF/五成片解码全部原帧；augment校验同ZIP视频SHA、HDF5schema/时序轴、四唯EEF组与fixed8原生快照；add_frames逐帧读原图尺寸。说明路径为本次run/work相对路径；重跑必须新run，避免重复append141帧。

独审后补充（20261008T142155_600617Z）：不再仅依旧档案137视频表。实扫additional_arms原recordings树及v34/egodex_batch_01全部原MP4，共149条原路径；新增180条source记录，其中95条视频。原source即使相同SHA也全部登记，由打包器无损alias去重。新增所有有EEF参考视频的robot root配原actions NPZ及schema/RenderSummary/ResultManifest，包含cups SO101及fold SO101两组。配对详情见RawRecordingsSupplement.json。
HDF5对齐口径：frame index + 原MP4 PTS；HDF5没有timestamp dataset，未核过HDF内部timestamps。camera/hand Nx及全部时序轴与原帧数验证保持。原先4唯一EEF是最初指定input aliases的四组；补充批次按真实robot root另列，不用四组计数覆盖新增原数组。
