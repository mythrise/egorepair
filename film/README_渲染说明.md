# EgoRepair 发布片 · 4K 渲染包

输出：`out/EgoRepair_Launch_Film_4K.mp4` —— 3840×2160 · 30fps · H.264 + AAC · ≤145 MB · 时长 4:49

## 1. 环境（Linux x86_64）
- **Node.js ≥ 18**（推荐 22）和 npm
- **ffmpeg / ffprobe**（需含 libx264、aac）
- **python3**（只用标准库）
- 第一次运行需要联网：自动安装 Playwright 1.56.1 和 Chromium（约 150 MB）。
  如果已有 Chrome/Chromium，可以设置 `CHROME_PATH=/path/to/chrome`，这样就不用下载 Chromium。
- Ubuntu/Debian 缺系统库时执行一次：`sudo .pw/node_modules/.bin/playwright install-deps chromium`

## 2. 一条命令渲染
```bash
unzip EgoRepair_Film_Render.zip && cd EgoRepair_Film_Render
JOBS=16 bash run.sh          # JOBS ≈ CPU 核数 / 4
```
完成后文件在 `out/EgoRepair_Launch_Film_4K.mp4`。

## 3. 原理与耗时
- 13 个场景切成每段 6 秒的分块（约 50 块），`JOBS` 个无头 Chromium 并行逐帧渲染（CPU 渲染器 SwiftShader，结果稳定）。
- 分块按场景无损拼接，再按 145 MB 预算做两遍 H.264 编码，并混入原创配乐。
- 实测：4 核机器 4K 约 1.7 秒/帧，全片 8,670 帧。每个 Chromium 大约占 3–4 核。
  例如 64 核、`JOBS=16`：渲染约 15–25 分钟，编码约 15–30 分钟。
- 中途中断后重跑同一命令，会跳过已完成的分块（`out/chunks/*.ok`）。

## 4. 常用参数
| 变量 | 默认 | 说明 |
|---|---|---|
| `JOBS` | 核数/4 | 并行渲染进程数 |
| `MB` | 145 | 成片体积上限（十进制 MB），码率自动计算 |
| `W` `H` `OUT` | 3840 2160 out/4k | 例如 `W=1920 H=1080 MB=60 OUT=out/1080 bash run.sh` 先出 1080p 快速版 |
| `SCENES` | 全部 | 只渲染部分场景，例如 `SCENES="s08_agents"`（配合 `SKIP_FINAL=1`） |
| `CHUNK` | 6 | 每个分块的秒数 |
| `CHROME_PATH` | — | 使用已安装的 Chrome/Chromium |
| `CHROME_GL` | SwiftShader | 有 GPU 时可以试 `CHROME_GL="--use-angle=vulkan"`（更快，但请目视检查画面） |

单帧预览：`PLAYWRIGHT_PATH=$PWD/.pw/node_modules/playwright node engine/render.mjs --scene s08_agents --w 1920 --h 1080 --stills 10,30 --fmt jpeg`

## 5. 目录
- `engine/` 渲染引擎（three.js 场景 + DOM 字幕，逐帧确定性驱动），字体已内置
- `scenes/` 13 个镜头（见 `STORYBOARD.md`）；`timeline.json` 是剪辑与配乐共用的时间线
- `assets/` 已生成的素材：EgoDex 原始 1080p 帧、EEF 参考视频帧、A1X 规划轨迹、MuJoCo 回放帧、Studio 2× 截图、HDF5 手腕位姿、手部追踪与光流数据、点云重建、配乐（`audio/score.m4a`，320 kbps；也可用 tools/score.py 重新合成）
- `tools/` 素材生成脚本、配乐合成（`score.py`）、分块渲染（`render_server.sh`）、合成编码（`assemble.py`）
