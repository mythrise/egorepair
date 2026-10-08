# 两段真实 EgoDex 任务：当前状态

更新UTC：2026-10-07T18:56:51.870831+00:00。当前完整任务成功 **0/2**，没有发布新的成功演示。旧倒水视频搭配合成单臂夹块的展示不作为这两段结果。

| 原任务 | 完整源数据 | 当前执行进度 |
|---|---|---|
| basic_pick_place/117：左手把灰托盘中的木块移入紫色铲盘 | 302帧源轨迹、RGB、各独立mask及A3基线LeRobot已接受 | 多轮真实抓取失败保留；正在独立审查唯一有限接触面6D摩擦模型变体 |
| stack_unstack_cups/5：左手扶外杯、右手依次拆出五杯、左手最后放外杯 | 270帧源轨迹、RGB、各独立mask及A3基线LeRobot已接受 | 已找到合法远基座和双指外杯接触；完整270帧双臂IK/名义场景规划工程正在独立审查，尚无双臂动态 |

已可读取的真实工件：

- [完整原始参考审查](../../ownreview/egodex_source_independent_20261007_01/ReviewFinal.json)、[实际A3基线执行审查](../../ownreview/egodex_a3_baseline_20261007_01/ReviewFinal.json)。A3 K/C/N改进效果不能由基线执行冒充。
- [真实失败轨迹的完整LeRobot/500Hz表](../../runs/egodex_linear_failed_full_lerobot_review_20261008_01/)：174实际行、8683实际积分步、175边界，原302帧中128未执行后缀明确标记；含对应RGB、原PTS和全部原mask。[独立全行核验](../../ownreview/egodex_linear_full_data_20261008_01/retest03/ActualReport.md)已通过；数据导出通过不代表任务成功。
- [抓持失败近景与真实STL核验](../../runs/egodex_linear_grasp_geometry_debug_20261008_02/)：4个记录姿态，静态渲染，无新动态或成功标签。
- [独立物理诊断](../../reports/astra_grasp_forensics_20261008_01/Report.md)：记录显示木块偏转、接触移向对角边缘并楔开夹爪，有限接触面模型只是下一待验证假设。
- [双臂选定夹口静态核验](../../ownreview/egodex_cups_selected_aperture_20261008_01/Report.md)：82.83358mm，两侧夹指均碰外杯，未碰内杯/桌/另一臂；尚未验证握持力与持续时间。

边界：source video与对应官方HDF人体参考分清，后者不冒A1模型预测。CAD/尺度/安装为明确模型估计，指导轨迹为专家修正。原source世界、原始位置/旋转mask及全部母体保留；新安装与接触数值变体各自留档。规划中的预期物体位置只用于静态检查，真实物理回放从原初态自由物体开始，不用脚本物体位姿、焊接或外力扶持。全部新增写入仅a4_experiment。
