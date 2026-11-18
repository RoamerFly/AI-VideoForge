# MiniMax H3 高质量视频工作流 · 部署说明（本地推理版）

> 目标环境：`E:\Agent\projects\freetime_AI_Draw\AI_Draw\ComfyUI-aki\ComfyUI-aki-v3`
> 部署时间：2026-11-12　状态：模型下载中 · 工作流已生成并通过结构校验

---

## 一、先更正一个结论：H3 在本地是能跑的

上一版说明里写的"H3 是闭源商业模型、没有权重、只能调 API"**已经过期**。实测这台机器上的 ComfyUI **0.45.0** 里：

| 组成 | 实机状态 |
|---|---|
| `Ref2VA` / `Fl2VA` 本地推理节点 | ✅ 内置，`comfy_extras/nodes_minimax_h3.py`（1000+ 行，含 AV 双流扩散） |
| 官方工作流模板 | ✅ 5 套（`video_minimax_h3_t2v / i2v / r2v`、`api_minimax_h3_*`） |
| 16G 显存优化 | ✅ `MiniMaxLowVRAMAttention`、`MiniMaxChunkFeedForward`（KJNodes）已装 |
| 视频 IO（`LoadVideo` / `GetVideoComponents` / `CreateVideo`） | ✅ 内置 |
| 云端 API 节点（要 comfy.org 额度） | ✅ 也在，但我们**不用这条路** |

所以部署重点是 **权重 + 工作流 + 显存调优**，不需要 API Key、不需要新建环境、不需要装第三方节点包。

---

## 二、模型清单（ModelScope 源，5–6 MB/s）

| 顺序 | 文件 | 体积 | 放在 | 用途 |
|---|---|---|---|---|
| 1 | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 15.7 GB | `models/text_encoders/` | 文本/图像编码器，**所有路线都要** |
| 2 | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 21.0 GB | `models/diffusion_models/` | **换人 / 参考生视频**主模型 |
| 3 | `minimax_h3_video_vae_int8_convrot.safetensors` | 2.8 GB | `models/vae/` | 视频解码 |
| 4 | `minimax_h3_audio_vae_fp32.safetensors` | 0.6 GB | `models/vae/` | 音频解码（H3 是音视频同时生成） |
| 5 | `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | 2.0 GB | `models/loras/` | 4 步加速，试构图用 |
| 6 | `minimax_h3_character_swap_v1.1_ref2va_fro.safetensors` | 80 MB | `models/loras/` | **换人 LoRA**（社区 v1.1，动作保留+身份替换） |
| 7 | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 21.0 GB | `models/diffusion_models/` | 文生 / 图生 / 首尾帧主模型（可选） |
| 8 | `fl2v_turbo_8step` / `fl2v_turbo_4step_768p` | 各 2.0 GB | `models/loras/` | 文生加速（可选） |

前 6 项约 **42 GB**，跑通换人只需这部分。第 7–8 项是文生/图生路线，按需再下。

下载脚本（断点续传、可反复执行、换人优先排序）：

```bash
cd E:/Agent/projects/freetime_AI_Video_Comfyui
bash download_h3_models.sh
```

日志：`ComfyUI-aki-v3/h3_download.log`

> 补充：官方还有一档 `pruned_w6a8`（15.98 GB）比 int8 更省显存、但量化更狠；社区 `DmitryDB` 的 NVFP4 只有 11.7 GB，**只在 HuggingFace**，本机直连 HF 超时、镜像只有 0.3–1.6 MB/s，所以不作为首选。

---

## 三、工作流清单

目录：`ComfyUI/user/default/workflows/MiniMax_H3_本地/`

| 文件 | 干什么 | 依赖模型 |
|---|---|---|
| `01_H3本地_文生视频_768p高质量` | 纯提示词出片 | fl2va |
| `02_H3本地_图生视频_768p高质量` | 一张图当首帧 | fl2va |
| `03_H3本地_首尾帧_768p高质量` | 两图锁首尾，中间补运镜 | fl2va |
| `04_H3本地_参考生视频_角色一致性` | 最多 3 图 + 参考视频，`<Picture i>` 指代 | ref2va |
| `05_H3本地_源视频换人_单人` | **源视频驱动换人**（本次重点） | ref2va + swap LoRA |
| `98_作者原版_换人工作流_v1.1_需补3个文件` | 社区原版，仅作参考 | 缺 3 个文件，跑不起来 |

选哪个：

- 只要一段好看的空镜 → 01
- 有定妆图想让人动起来 → 02 / 03
- 想让**自己的角色**出现在**指定场景/指定动作**里 → 04
- 有一段现成视频，只想**把里面的人换成别人** → 05

---

## 四、05 换人工作流怎么用

### 结构

```
LoadVideo ─┐
           └→ GetVideoComponents ─┬─ images ─┐
                                  └─ audio ──┤
                                             ▼
LoadImage(新角色) ──→ MiniMaxH3ReferenceToVideo ──→ Add Guide ──→ BasicGuider
                          (positive + LATENT)        (锚定第0帧)
UNETLoader(ref2va) → swap LoRA → LowVRAM Attention → Chunk FF → turbo 开关 → Sampler
```

三个关键点：

1. **Ref2VA 吃"新的人"**：`ref_image_0` = 新角色定妆图，提示词里写 `<Picture 1>`
2. **Add Guide 吃"旧视频"**：把源视频的画面 + 原声整体锚定在第 0 帧，模型据此复刻动作、运镜、光影，提示词里写 `<Video 1>`
3. **swap LoRA 强度 1.0**：社区 v1.1 的作用就是"保留运动、替换身份"，与上面两个配合，比单用任一都稳

### 当前预设（申鹤依赖摇 → 侠隐照美冥）

| 节点 | 预设值 |
|---|---|
| Load Video | `role_swap_20261112/zhaomei_dance_5s_24fps.mp4`（768×1344，120 帧，5.0s，带原声） |
| Load Image(137) | `role_swap_20261112/zhaomei_front.png`（全身正面定妆） |
| Primitive Float | `5`（= 源视频秒数） |
| Resolution Selector | `9:16 (Portrait)` · 0.98MP → 768×1344 |

换 10 秒：Load Video 选 `zhaomei_dance_10s_24fps.mp4`，Primitive Float 改 `10`。

### ⚠ 原片必须裁段转码，不能直接喂

`E:/Agent/projects/AI视频模板/申鹤依赖摇.mp4` 实测 **1080×1920 / 60fps / 34.4 秒 / AV1**，三个硬伤：

1. H3 训练区间只有 **124–362 帧（5.2–15.1 秒）**，34 秒超出上限
2. 帧网格按 **24fps** 算，60fps 直接给会变成 **0.4 倍慢动作**
3. `Get Video Components` 会把整段解码成图像批次：2063 帧 1080p ≈ 50 GB 内存，必崩

已裁好转码（原片未动），放在 `ComfyUI/input/role_swap_20261112/`：

```bash
ffmpeg -i "申鹤依赖摇.mp4" -t 10 \
       -vf "fps=24,scale=768:1344:flags=lanczos" \
       -c:v libx264 -crf 16 -pix_fmt yuv420p -c:a aac -b:a 128k zhaomei_dance_10s_24fps.mp4
```

### 提示词里只能用 `<Picture 1>`

源视频是走 `Add Guide` 做 latent 锚定的，**没有进 Ref2VA 的参考槽**，所以不存在 `<Video 1>` 这个 token。
提示词已改为"复刻原片的舞蹈动作"这类自然语言描述。若以后把视频接进 `ref_videos`，才可以用 `<Video 1>`（会显著变慢）。

### 排错顺序

| 现象 | 处理 |
|---|---|
| 报 `frame_idx ... does not fit` | `Primitive Float` 加 1 秒（帧数吸附到 17k+5 网格） |
| 帽子丢了 / 变回申鹤白发 | swap LoRA 1.0 → 1.15；提示词已写死斗笠、蓝紫和服、红棕长发 |
| 脸不像 | `Ref2VA` 的 `ref_image_size` 由 `match` 改 `max`（更准，慢数倍） |
| 动作速度不对 | 先查源视频是不是 24fps |
| 手部/裙摆穿模 | 舞蹈幅度大是 H3 弱项，砍到 3–5 秒取动作最稳的一段 |
| 动作不跟 | 确认 Add Guide 的 `image` 接的是 `Get Video Components.images` |
| 出片比源视频短 | 网格裁尾，正常 |

---

## 五、16G 显存 / 32G 内存怎么调

真正的瓶颈是**内存**，不是显存：21G 主模型 + 15.7G 编码器不可能同时驻留。

1. **系统虚拟内存**：初始 32 GB / 最大 64 GB，放 E 盘（现有 1.3T 空间）。不设会在换入换出时卡死。
2. 工作流里两个补丁节点保持开启：
   - `MiniMax H3 Low VRAM Attention`（`head_chunks=4`）：把 attention 拆头组，**数学等价**，只降峰值
   - `MiniMax H3 Chunk Feed Forward`（`chunks=2`，`seq_threshold=4096`）：SwiGLU 按 token 分块
   显存富裕（24G+）时右键 Bypass 这两个节点可以提速。
3. 分辨率：`Resolution Selector` 保持 0.98 MP 档（竖屏 768×1344 / 横屏 1344×768）。再往上 16G 卡必然换页。
4. 启动参数（需要时在 `main.py` 后加）：
   - `--reserve-vram 0.6`：给系统留 0.6G，避免爆显存导致整机卡顿
   - `--cache-none`：每次执行不缓存中间结果，省内存，但重复跑会变慢
   - `--use-sage-attention`：装了 sageattention 时可用，降低 attention 显存

参考出片时间（RTX 5060 Ti 16G）：20 步质量模式 8 秒视频约 12–20 分钟；开 turbo（4 步）约 3–5 分钟。首次运行因为要读 36 GB 权重进内存，会明显更慢。

---

## 六、校验记录

| 项目 | 结果 |
|---|---|
| 节点是否注册 | `/object_info` 实测：H3 相关节点 27 个，含全部关键件 |
| 工作流 widget 顺序 | 逐个比对服务器 schema，4 套通用工作流的 widget 数量/顺序一致 |
| 图结构完整性 | 6 个 JSON 全部通过自研校验器（连线双向一致、槽位类型匹配、无孤儿 link） |
| 模型文件 | 下载中，未做端到端出片验证 |

校验脚本（可重复执行）：

```bash
PY="E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/python/python.exe"
$PY _validate_swap.py     # 6 个工作流的图结构
$PY check_h3_ready.py     # 9 个模型文件：缺失 / 下载中百分比 / safetensors 头是否可解析
```

---

## 七、已知限制

1. **许可**：MiniMax H3 权重有地区与商用限制，商用前自行确认；换真人脸需本人授权。
2. **二采（重渲染到 2K）**：社区方案依赖 `minimax_h3_lms_v1.0_r64`（1.24 GB）和 `dmd_ref2va_8step_turbo`，来源未核实，本次**未部署**。先用 20 步 + 768p 出片，二采以后再说。
3. **作者原版工作流**（`98_...`）还缺 `qwen3.5_9b_w4a8_gptq`（自动描述参考图的 VLM）等 3 个文件，仅作结构参考，不要直接跑。
4. 16G 显存 + 32G 内存在这套模型上属于**下限配置**：能跑，但同时开浏览器/剪辑软件会明显拖慢。
