# 参赛交付定义与第三方许可清单

版本：A4X_REVIEW_V5_20261005。响应Claude P1-4/P2-7。完整M0–M10研究方案保留；用户明确要求的软件平台＋仿真任务＋后训练对比不被自行删去。

## 1. 10月8日目标具体是什么

软件名仍为**EgoRepair Studio**，发布profile为`CONTEST_T1_SO101_V1`；它限定公开演示任务／型号，不把完整研究改成仅建议重跑的MVP。目标是SO101的T1取放，合法自采/自生成素材、一条真实可追溯处理链，以及ACT后训练对照。完整研究仍有T1–T5、A1X、ACT/DP、EgoPHI、PPO、DPPO及全部消融。

| 交付件 | 明确验收 | 当前状态 |
|---|---|---|
| 可运行Web平台和自研源码 | 导入、查询、修复、回放、导出、训练结果页面；至少一次请求实际执行；完整启动说明、锁文件、错误状态和日志读回 | NOT_IMPLEMENTED |
| 本地空间专家＋DeepSeek调度 | 实际模型输出、引用原帧、结构化派单；原RGB不外发，报告外传也须具相应数据权限 | NOT_RUN |
| 学习修复 | 条件残差扩散真实训练/加载、与确定性B4对照；原/新/投影工件可读回 | NOT_RUN |
| T1模拟闭环 | SO101资产/控制验收，同初态原轨迹与候选无辅助回放；包含失败/拒绝，不只播放动画 | NOT_RUN |
| 机器人后训练 | 同π0的raw、filter、repair至少三组ACT实际训练和同留出初态评价；记录训练重复和全分母，不把Jev分类当此结果 | NOT_RUN |
| 数据版本与材料 | writer→reader证据、PDF、3截图、≤5分钟MP4、模型/AI辅助说明、许可包和公网校外访问回执 | NOT_PREPARED |

自采ego若未完成重建桥，展示的是EGO_REFERENCE；合成仿真和后训练必须在页面/视频明确标SYNTHETIC_SIM，不能拼成“这条真实ego已实现物理提升”。若具备合法重建桥才可展示EGO_RECONSTRUCTED_SIM对应结果。

`ReleaseManifest`逐项记录method_id、模块/权重/代码revision、数据线、观察profile、任务/机器人、真实运行ID、许可、完整源码可运行性和未完成项。**FULL只能在所有必需模块实际运行后使用**；M3许可或PPO未齐只能标相应具名消融，不能暗删依赖继续叫FULL。若上述用户要求的三类交付没有齐，结论为RELEASE_TARGET_NOT_MET，不把缺后训练的v0称为已完成目标，也不承诺三天足以完成。

10月5日锁依赖/输入/接口；10月6日目标为单任务真实链；10月7日目标为后训练读回、公网校外访问和材料一致性；10月8日按实际状态提交。以上是排程目标，当前无生产代码、训练、部署或提交的完成声明。本轮只修方案，不启动这些任务；是否达到日期由实际执行证据决定。

## 2. 许可清单：代码、模型、数据、派生物分别记录

| 材料 | 本次核实的一手证据 | 内部研究与提交／公网策略 |
|---|---|---|
| EgoDex数据 | [官方README](https://github.com/apple-aiml-research/ml-egodex)写CC-by-NC-ND；与repo代码许可分开，README没有在该行写明具体版本 | 不把已下载等同用途授权；内部按实际取得的完整条款使用。未获得相应授权/依据前，原RGB及叠加/改编视频、标注截图、数据派生包不进入提交/公网素材白名单 |
| CC NC-ND解释 | [CC官方说明](https://creativecommons.org/licenses/by-nc-nd/4.0/)限制分享改编作品，例外和纯技术格式修改另论 | 不一概断言任何数值特征/标注一定构成法律上的改编；赛事是否商业用途也不凭“学生比赛”推定。这里只采用不分发未核派生物的项目政策，需具体条款/权利依据才能加入白名单 |
| EgoPHI代码／权重 | **2026-10-06更正**：锁定commit `b3de0ce4f128664770cfd695704bbac559e8e79f` 的[官方README](https://github.com/eth-siplab/EgoPHI)明确声明项目使用MIT；GitHub metadata仍为license:null，不能据此否认README声明 | 代码记录为 `MIT_DECLARED_IN_PINNED_README`，可继续隔离获取与适配；保留声明/作者归属。权重、MANO/ARCTIC等第三方资产仍分别核版本/用途，不能把代码声明自动扩为所有数据的再分发许可。旧LICENSE_UNRESOLVED总括判断已纠正；M3真实运行缺口另列 |
| ARCTIC数据／软件／mesh | [官方条款](https://arctic.is.tue.mpg.de/license.html)限非商业研究等用途，含不得向第三方分发/提供的限制 | 不随源码包带数据、mesh或受限软件；研究许可不自动覆盖公网托管／参赛分发 |
| MANO模型／软件 | [官方条款](https://mano.is.tue.mpg.de/license.html)为非商业用途个人不可转让许可，另有分发限制 | 模型资产、参数包与工具输出逐类核查；不能仅因我们有adapter就把上游模型放到评委包 |
| SenseNova-SI-1.3 | [官方权重](https://huggingface.co/sensenova/SenseNova-SI-1.3-InternVL3-8B)和代码Apache-2.0 | 保留实际revision、LICENSE/NOTICE及第三方说明；权重不因可用就算本项目自研 |
| SO101 Menagerie模型 | [模型目录](https://github.com/google-deepmind/mujoco_menagerie/tree/main/robotstudio_so101)本次读到Apache-2.0 LICENSE | 锁完整资产/source、保留notice，仍核依赖mesh/转换后版本；不是robosuite原生已验机器人 |
| Qwen/Jev、HuRo、MuJoCo/robosuite、ACT/DP/DPPO、SAM/ProxyPose等 | 用到哪个源码／权重／数据版本，就读取其对应条款；已有来源锁不替代用途许可 | 逐项写`ThirdPartyManifest`；本次没有重新完整核完所有传递依赖，未核项保持UNVERIFIED，不声称全栈许可已清 |
| 自采ego／自生成模拟 | 需素材权利人、人物/场景和使用范围；模拟资产纹理也各有来源 | 默认公开素材来源。自采不自动等于已获公开许可，先以已有权利依据确认；合成来源在页面显式标注 |

每项许可回执字段：`component_id, artifact_kind, source_revision, license_url/text_sha, internal_use, hosted_inference, redistribution, derivative_outputs, authority_basis, status`。未知是UNKNOWN，不当ALLOW；论文开放、GitHub公开、license:null各自不能取代实际许可证。对公开输出追溯输入数据／模型／mesh依赖，拒绝把原RGB改成overlay就绕过素材权限。

## 3. “只交adapter”能解决什么

自研源码可以单独提交并注明第三方来源；这解决代码归属，**不能自动解决依赖许可，也不能保证评委可运行完整软件**。发布包必须在允许使用的依赖集上完成干净环境启动、真实请求和reader回归。若必需依赖需评委另行申请且无法取得，标REPRODUCTION_BLOCKED，不能声称已经满足完整可运行源码要求。

公网页面可以只使用合规合成样本和具名方法臂；正式材料如实列没有启用的组件。没有许可不授权我们私自发邮件／替用户接受条款，本轮也不发消息、不部署。合法素材、账号和实际发布是后续执行依赖，不是这轮文档修订的阻塞。

2026-10-06核验依据：`runs/implementation_20261005/egophi_source_recheck_20261006T041106_158157Z/Receipt.json`；官方API读取锁定README（Git blob `4b5c6e3e61a79bc6198f98d640f1c143230d6687`），与当前main同commit。更正此前只查看LICENSE文件/API metadata的片面结论；未更改历史审查工件。此前许可询问中有关代码的缺项已由公开官方依据补齐，权重/依赖仍待各自实际依据。
