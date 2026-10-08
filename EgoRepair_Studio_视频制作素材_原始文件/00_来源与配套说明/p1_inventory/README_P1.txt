所有被选文件原字节，不转码/重采样/改NPZ/修改URDF或XML。新增仅清单和说明。
scene所有302帧相机与mask属于同recording；深度文件原来就在960×540虚拟相机体系（每30帧及末帧采样），原尺寸不改。K_source 1920×1080与K_virtual及变换有显式记录，不能误绑原视频。
桌面support GeoJSON嵌在原始MultiViewTableModel JSON中，保observed/modeled/assumed区分，世界尺度与SLAM模型来源并非实测认证。
A1X ROS package URI读取时，将models/A1X/mobiman设作mobiman资源根。SO101 URDF和MJCF均与assets/相对路径一致；13同名共有STL经SHA一致验证只收一次。
F7B历史读回宣称161引用；本次对现存引用按SHA核验，11个活动源码文件后来已变更且未找到精确旧字节，拒收并单列SOURCE_SHA_MISMATCH；旧实验输出与resume父绑定原样保留。最后链15阶段按历史记录EXECUTED，scope仅NO_EDIT连接消融，repair_benefit NOT_CLAIMED。整理阶段没有重跑。
P2当前TASKS/EXPERIMENT_LOG保留原字节和历史段落；其中AI60-70%为旧估计，61.5s为旧网站固定展示回放时长，均不能写成模型实测推理速度或新的性能结果。DEMO_CASES_20261007是真实1PASS/7FAIL+另1UNKNOWN，固定仿真和估计模型范围。
F7原scene.xml使用绝对meshdir=/home/xklv/ego_robot/a4_experiment/vendor/mujoco_menagerie/robotstudio_so101/assets。包内模型STL齐全在P1/models/SO101/assets；重渲染应配置资源路径映射。原XML未改，不能承诺脱离原目录直接解析。
F7C真实专家云模型工作流与F10B18calls是独立episode/实验，不作为F7B链上模型调用证据。没有保存或生成隐藏思维。
ledger原SQLite是已归档历史snapshot；未触碰仍用的authority数据库。
F10B只使用归档审计脱敏Result/Start。reasoning字段是API参数与usage统计，没有输出type:reasoning块。

缺项/限制:
[
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/cli.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "75087c093b101acfaac3ec589513d75a41278d21547f66cf08d2e85b9aceef7a",
    "actual": "fd0e06a37503d6b85d9552bc5e72630ab6f99b09ccf62716bf854670a1d54e7a",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/pipeline/candidate.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "64e10d2fb5cc7ae7554b51fb79ce9c10cb785842774f12610fbda85efb6b7456",
    "actual": "543ef2ff724ffbcf67601845bc16e6fc0e1990305ddb8c28f8176e1b0c3fc4d7",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/pipeline/handlers.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "c4c65a68a417297b5d3baff2afcaf61c35ef296d17dc2ca198e12b87939aa2f5",
    "actual": "fd983b9ecde84a74ed0629be91cd03006ead99ddb41921b0ad5e2983fb1e61a8",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/pipeline/packages.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "1b65affd789b86ef86dc69c336db78350efb1ce62b47d75110db03af0cba7dd8",
    "actual": "94569eb14505ca3583afd346f60c9114979d0ddf7fd77c8bf389a55063bfa7d9",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/pipeline/project.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "b4afc4e886c63f5b734c8a8413658f3fa42889fbd81e9277628b32a0247fedb5",
    "actual": "9b99c751c1cc1e2d640d15add06efc29d460031cf2767021dc16f9ffd7c2166c",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/pipeline/provider.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "9f228c413d06be6b75e49e299dbd0cad8f0a3f56e57d654328e863f6a7388089",
    "actual": "5c28c9c3cb2b8136df3795633d6fb6d29e8276e0c9a3e83facfb4452338150a9",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/pipeline/repair.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "10cea415c97fc6ad16ff1d1dd7ad2e0751c1cd99b068537a10aedfcf782a3209",
    "actual": "4449ad49db98aa38d44463e65b3f34fb2980ee274aed905dc0d0f5222f86a70d",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/pipeline/source_registry.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "f6405b26ecb632e5c81b0641c8974215187c089413423bef244739d97ab8ee09",
    "actual": "89d7521f43504d40a924b5baa1f87da0a87ae5bbfeee3631e6afadebb64c0528",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/workers/budget_scope.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "d8ec9e7bf1493b8082af4c185a3e6026683ff96b4a6293b01c474758710c9666",
    "actual": "2f601c931dc985cf8bf68f645170f13f2d79b851922aca7377d7a38f060f1ca6",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/workers/entry.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "6dbe3a0472dbdf840a6ed7df0f5fe8282461cf4105f08e2b5dbe22d0e0c2043b",
    "actual": "5bf9a9c7a0ac8285a5ef4dc35a395cdc47ebb3c5c00d77f700c3dcf201bc7d68",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "/home/xklv/ego_robot/a4_experiment/src/a4x/workers/registry.py",
    "status": "SOURCE_SHA_MISMATCH",
    "expected": "28ed6305c90a8bb54da4142ff4db23fc9e3706a41344d5387eb4cafdee43b344",
    "actual": "5a0ab05aa937c5d535687d205ff7bed2fa4535abc5c358f70719ca0b8ebe50a3",
    "bundle_id": "f7b_episode"
  },
  {
    "item": "pick117 all302frame MoGe3 depth",
    "status": "NOT_AVAILABLE_FULL_FRAME",
    "available": "12 original sampled depth frames only; no new interpolation/inference"
  },
  {
    "item": "pick117 standalone tabletop .geojson",
    "status": "AVAILABLE_EMBEDDED",
    "available": "pilot_a1x_multiview/final_all_views/table/MultiViewTableModel.json.result observed_support_T_geojson/modeled_support_T_geojson/assumed_completion_T_geojson; files unchanged"
  },
  {
    "item": "A1X full BSD license text",
    "status": "NOT_FOUND",
    "available": "Original A1X package.xml declares BSD; no independent license text identified"
  },
  {
    "item": "F7B cloud/local SpatialEvidenceReport in same episode",
    "status": "NOT_FOUND",
    "available": "F7C narrow_prism is a distinct source episode and bundled separately"
  },
  {
    "item": "F7B CoordinationDecision named artifact",
    "status": "NOT_FOUND_AS_NAMED_FILE",
    "available": "FullCPUChain embeds coordinator and results; EvidenceGraph and original process stages provided"
  },
  {
    "item": "F7B HELP/NEUTRAL/HARM candidate label triplet",
    "status": "NOT_FOUND_AS_COMPARATIVE_TRIPLET",
    "available": "NO_EDIT connectivity ablation original/candidate dataset versions and qualification kept; not pretend optimization gain"
  },
  {
    "item": "F7B neural model checkpoints excluded",
    "status": "OUT_OF_VIDEO_ASSET_SCOPE",
    "available": "Readback retains original weight refs; model checkpoints are not media assets"
  }
]