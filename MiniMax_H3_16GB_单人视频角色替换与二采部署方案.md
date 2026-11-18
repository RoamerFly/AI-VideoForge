# MiniMax H3 本地部署：16GB 显存单人视频角色替换与二采优化方案

> 方案版本：v1.0｜编写日期：2026-11-12｜目标平台：Windows 11 + RTX 5060 Ti 16GB + 32GB RAM  
> 用途：提供**原始单人动作视频**与**写实真人／真人 Cosplay 角色参考图**，尽可能保留原视频的动作、镜头、背景和音频，将画面中的整个人替换为指定角色，并控制脸型、服装、配色在时间上的漂移。  
> **状态说明：这是依据项目官方文档、开源仓库与公开实测整理的可执行部署方案，尚未在本人的这台电脑上实测；不能承诺零变脸、零偏色、15 秒一次成功。**

## 0. 先说结论

你的 5060 Ti **16GB 显存可以尝试本地 MiniMax H3**。关键是：16GB 显存不等于“只允许载入 16GB 文件”，部分权重可从 32GB 系统内存和 NVMe 虚拟内存交换；代价是速度可能大幅下降、严重时卡死或内存不足。官方介绍建议系统内存 32–64GB；专门的一键换人项目 Openjutsu 用 **RTX 4060 Ti 16GB + 64GB RAM** 测试过，不能把它的速度和成功率直接套到当前 32GB RAM 上。

**最终建议按顺序走三条路线：**

1. **A / 首选：MiniMax H3 Ref2VA + Character Swap LoRA v1.1（纯 ComfyUI）**。先拿 2–3 秒片段验证脸、衣服、背景和动作，再逐步拉长。这是“整人替换”最贴近目标、安装链相对短的起点。
2. **B / 画质进阶：H3 Director 的 `rv2v` / `二采_加速` 工作流**，或 A 工作流自带的可选 LMS 二采。低分辨率一采→放大 latent→少量精修采样→最后单独超分；**二采用于补画质，不等于锁住人物身份**。
3. **C / 精细局部替换：Openjutsu（SAM 3.1 人体跟踪蒙版 + H3 + 修脸/调色）**。如果 A 经常改背景、人物边界出错，就转 C；但它对内存更苛刻，32GB RAM 可能需要升级至 64GB 或接受重度换页。

请勿把“8GB 显存可跑 15 秒 720p”的普通生成视频教程，当成“8GB 可高质量逐帧替换全身 Cosplay 角色”的证明：两种工作负荷并不相同。

## 1. 对你提供的 B 站 v1.5 视频的核实结果

- 视频：[【MiniMax-H3】v1.5版本 8G显存+16G内存也能15秒720p 低配二采工作流分享](https://www.bilibili.com/video/BV1pmxQ6pEUq/)。
- 搜索到相近标题的 v1.5 转载，声称“8GB 显存 + 16GB 内存、720p、修复音频问题”；**无法直接打开视频读取完整节点图、模型权重、每段耗时、峰值内存与 JSON**，因而本方案**不冒称已经复现该 v1.5**。
- 可核查的独立开源实现：
  - [AIMixer / ComfyUI_MiniMaxH3_Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director)：提供 `minimax_h3_director_二采_加速.json`，有 `refine/upscale/latent_upscale` 三种模式，另有 `rv2v`（原视频＋角色图）入口。
  - [YixuAn / minimax-h3-comfyui-all-in-one](https://github.com/YixuAn-13/minimax-h3-comfyui-all-in-one)：作者报告 8GB 卡 0.82MP 二采成功，1.22MP 在 RAM 紧张时很慢，2.09MP OOM；**这些是作者实验条件下的记录，不是你电脑的实测**。
  - [FlowForgeLabAi / MiniMax-H3-8GB-Workflows](https://github.com/FlowForgeLabAi/MiniMax-H3-8GB-Workflows)：解释低内存的 pinned memory、量化、帧数、采样和掉速陷阱。

## 2. 先分清四个概念

| 技术 | 输入 | 能做什么 | 对你是否关键 |
|---|---|---|---|
| H3 **FL2VA** | 文本，首帧/尾帧 | 文/图生视频，原生音频 | 一般视频测试可以；**不是整人替换主力** |
| H3 **Ref2VA** | 图片、视频、音频参考 | 用原视频指导动作，用角色图指导外观 | **主力模型** |
| Character Swap LoRA / SAM 跟踪 | Ref2VA、角色图；可加人物蒙版 | 提高“仅换人、背景不变、身份稳定”的倾向 | **最值得先试** |
| 二次采样（`refine`） | 一采 latent、分辨率、噪声调度 | 细节、纹理、清晰度改善 | 画质达标后再上；也可能**重新画坏脸、改色** |

MiniMax 官方将 H3 Base 的本地产出定位在最高约 **768p 短边**；官方宣传的完整 **2K Regenerate** 是额外的云端/API 流水线，不等于下载 H3 Base 就能在 16GB 上免费跑官方 2K 模块。不要把普通 ESRGAN 超分混同于官方 2K 再生成。

## 3. 你的设备与资源规划

| 项目 | 配置与建议 |
|---|---|
| 显卡 | NVIDIA RTX 5060 Ti 16GB，Blackwell；有条件使用专为 RTX 50 的 NVFP4 压缩权重 |
| 系统内存 | 32GB：是能尝试的下限，**复杂 SAM / H3 多阶段可能不够**；若经常换页/蓝屏/系统无响应，未来升 64GB 比继续堆复杂加速节点更实用 |
| 硬盘 | NVMe：预留至少 **100–150GB**（模型、临时视频帧、缓存、虚拟内存）；大型试验建议更多 |
| 操作系统 | Windows 11；显卡驱动、ComfyUI、PyTorch/CUDA 环境必须支持 RTX 50 系显卡 |
| 测试视频 | 先 2–3s、24fps、竖屏 **448×768 或 416×736**；正式再 5s、10–15s |
| 虚拟内存 | 可在 NVMe 所在盘设置 Windows 系统管理大小；若经常出现提交限制不足，可试**自定义初始 32GB / 最大 64GB**，需硬盘空间足够。它不是 RAM/显存升级的替代物 |

**部署隔离原则**：不要直接升级/破坏笔记本旧 ComfyUI-aki 的环境。新台式机建议建一个独立目录，例如 `E:\AI\ComfyUI-H3\`；若你已经有可用的台式机 ComfyUI，先备份它的 `user/`、`custom_nodes/` 与 `extra_model_paths.yaml`。

## 4. 核心下载地址与模型摆放路径

以下路径均相对于实际的 `ComfyUI` **程序根目录**（即含 `main.py` 的目录），不是便携包外层目录；`models/` 下不存在的文件夹可新建。

### 4.1 先装最少必需件（A 路线）

| 优先级 | 文件 / 软件 | 下载地址 | 目标路径 / 备注 |
|---|---|---|---|
| 必需 | ComfyUI（建议新版，后续 Openjutsu 要求 ≥0.41.2） | [ComfyUI 官方 GitHub](https://github.com/comfyanonymous/ComfyUI) / [桌面安装](https://www.comfy.org/download) | `E:\AI\ComfyUI-H3\ComfyUI\`（示例） |
| **必需、首选低显存** | `MiniMax-H3_Ref2VA-NVFP4.safetensors`，约 **10.86GiB**，第三方 Blackwell 量化 | [DmitryDB 直接下载](https://huggingface.co/DmitryDB/MiniMax-H3-ComfyUI-Quants/resolve/main/Ref2VA/MiniMax-H3_Ref2VA-NVFP4.safetensors?download=true) | `models/diffusion_models/`；这不是官方原版，**需要对 LoRA/工作流兼容性实测** |
| 备选、画质比较 | `MiniMax-H3_Ref2VA-NVFP4-HQ.safetensors`，约 **13.60GiB** | [DmitryDB HQ 直接下载](https://huggingface.co/DmitryDB/MiniMax-H3-ComfyUI-Quants/resolve/main/Ref2VA/MiniMax-H3_Ref2VA-NVFP4-HQ.safetensors?download=true) | `models/diffusion_models/`；更容易挤爆 16GB 显存，不要初装就都下载 |
| 备选、原工作流兼容基线 | `minimax_h3_ref2va_pruned_int8_convrot.safetensors`，约 **21GB 文件** | [Comfy-Org 直接下载](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors?download=true) | `models/diffusion_models/`；占系统 RAM/换页更重。Openjutsu 默认用它 |
| 必需 | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`，约 **15.7GB 文件** | [Comfy-Org 直接下载](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors?download=true) | `models/text_encoders/`；它是 **H3 专用文本编码器**，不是普通 Qwen 聊天模型 |
| 必需 | `minimax_h3_video_vae_int8_convrot.safetensors`，约 **2.81GB** | [Comfy-Org 直接下载](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_int8_convrot.safetensors?download=true) | `models/vae/`；更省内存，**工作流支持的加载器必须匹配** |
| 兼容备选 | `minimax_h3_video_vae_fp16.safetensors`，约 **5.21GB** | [Comfy-Org 直接下载](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors?download=true) | `models/vae/`；如果某个工作流未测试 int8 VAE，先用原作者指定的 fp16 版做兼容验证 |
| 必需 | `minimax_h3_audio_vae_fp32.safetensors`，约 **605MB** | [Comfy-Org 直接下载](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors?download=true) | `models/vae/` |
| **必需、换人** | `minimax_h3_character_swap_v1.1_ref2va_fro.safetensors`，约 **80.7MB** | [Alissonerdx 直接下载](https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI/resolve/main/loras/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors?download=true) | `models/loras/`；作者建议 strength 1.0，声称 v1.1 比 v1.0 更贴近脸、头发、身形、衣服 |
| **必需、换人工作流** | `minimax_h3_character_swap_workflow_native_nodes_v1.1.json` | [直接下载 JSON](https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI/resolve/main/workflows/minimax_h3_character_swap_workflow_native_nodes_v1.1.json?download=true) | `user/default/workflows/` 或拖入 ComfyUI；此图还引用 Turbo LoRA、描述图像的 VLM，**照节点 Notes 下载，缺模型时可先改手工提示词** |
| 可选、分镜 | `minimax_h3_character_swap_workflow_v1.1.json` | [分镜工作流 JSON](https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI/resolve/main/workflows/minimax_h3_character_swap_workflow_v1.1.json?download=true) | 依赖 [ComfyUI-BFSNodes ≥1.113.0](https://github.com/alisson-anjos/ComfyUI-BFSNodes) |

**重要：下载策略**：第一轮只选一个 Ref2VA DiT 和一个 video VAE，不要同时下载 10GB、14GB、21GB 三种主模型。第三方 NVFP4 模型的文件体积只是**模型权重大小，不是运行时显存峰值**。

上表第三方模型、角色 LoRA、作者工作流各自更新频繁；若工作流下拉菜单找不到模型，要在相应 Loader 中**重新选择实际文件名**，不要通过强制改名伪装模型结构。

### 4.2 二采所需额外项目（B 路线）

1. [AIMixer / ComfyUI_MiniMaxH3_Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director)，内置路径 `example_workflows/minimax_h3_director_二采_加速.json`。
2. 同仓：`example_workflows/minimax_h3_director_rv2v.json`；此图是**源视频＋角色图**入口，比纯 T2V 二采更贴合要求。
3. **如需 H3 latent upscaler**：按 Director `Refine` 下拉框与示例 JSON 提示下载相容的 3D latent-upscale 文件，放 `models/latent_upscale_models/`。上游权重名称随实现版本变化；**不在此猜测一个可能不存在的文件名**。
4. A 路线也可试 [Alissonerdx v1.1 官方说明](https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI/blob/main/docs/character-swap.md) 自带的 LMS/latent-upscaler 分支；**A 的二采和 B 的 Director 二采是两个不同实现，不要未经验证直接交叉拼节点**。

### 4.3 Openjutsu 进阶所需文件（C 路线）

源码：[D3voz/openjutsu](https://github.com/D3voz/openjutsu)。仓库当前说明列出的模型：

| 模型 | 位置 | 作用 |
|---|---|---|
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `models/diffusion_models/` | H3 Ref2VA 主模型，建议先**按该项目原始模型验证** |
| `minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors` | `models/loras/` | 项目自带速度配置所需 LoRA；从项目 README 的模型来源获取 |
| `qwen3vl_32b_minimax_h3_int4_convrot.safetensors` | `models/text_encoders/` | 该项目当前推荐的 H3 编码器，**与 A 默认 nvfp4 名称不同** |
| `qwen3vl_8b_int8_convrot.safetensors` | `models/text_encoders/` | 描述人物、场景所用 VLM |
| `minimax_h3_video_vae_int8_convrot.safetensors`、`minimax_h3_audio_vae_fp32.safetensors` | `models/vae/` | 音视频解码 |
| `sam3.1_multiplex_fp16.safetensors` | `models/checkpoints/` | 人物逐帧跟踪和蒙版 |
| 可选脸修复所需 YOLO、SAM、InsightFace | 参看仓库 README 中的 `ultralytics/`、`sams/` 和 `insightface/` | 后处理，仅修脸阶段安装 |

**C 路线不是 A 的“打开一个开关”**：其节点包多、下载较大、系统内存需求高。官方 README 的测试机是 4060 Ti 16GB + 64GB RAM，32GB RAM 可作为实验，但不能保证可完整部署。

## 5. Windows 11 安装步骤（从零到 A 路线首片）

### 步骤 1：更新基础环境

1. 从 [NVIDIA 官方驱动](https://www.nvidia.com/Download/index.aspx) 安装支持 RTX 5060 Ti 的新驱动；重启。
2. 安装新版 [ComfyUI](https://github.com/comfyanonymous/ComfyUI)；Windows 便携版通常含独立 Python，**用它自带的 Python 装节点依赖，勿混用系统 Python**。
3. 若 RTX 50 系提示 `no kernel image available`、`sm_120` 之类，先核对 [PyTorch 官方安装说明](https://pytorch.org/get-started/locally/) 与 ComfyUI 的 CUDA/torch 构建；不要反复盲目换旧版 Torch。
4. 打开 PowerShell 运行只读硬件检查：

```powershell
nvidia-smi
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-Volume | Select-Object DriveLetter, FileSystemLabel, SizeRemaining
```

至少核对：`nvidia-smi` 能显示 5060 Ti 16GB；实际可用的 NVMe 有足够空间。

### 步骤 2：放置模型（只下载 A 必需项）

按第 4.1 节表格把模型放进对应目录。完整树示意：

```text
E:\AI\ComfyUI-H3\ComfyUI\                     ← 示例，改为你的真实根目录
  main.py
  models\
    diffusion_models\
      MiniMax-H3_Ref2VA-NVFP4.safetensors
    text_encoders\
      qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
    vae\
      minimax_h3_video_vae_int8_convrot.safetensors
      minimax_h3_audio_vae_fp32.safetensors
    loras\
      minimax_h3_character_swap_v1.1_ref2va_fro.safetensors
  user\default\workflows\
    minimax_h3_character_swap_workflow_native_nodes_v1.1.json
```

注意：原作者的 v1.1 JSON 可能默认使用不同 VAE、Turbo LoRA、描述模型。**加载后有红色缺节点/缺模型提示时，按节点注释逐一安装；不要默认这个“最小树”足以原样点击 Queue。** 若资源不足，用手写角色描述代替额外的描述 VLM，并在修改节点连接后才运行。

### 步骤 3：先让 ComfyUI 正常启动

如果使用独立 Python 环境，启动示例（具体运行方式以你的安装版本为准）：

```powershell
cd 'E:\AI\ComfyUI-H3\ComfyUI'
python main.py --listen 127.0.0.1 --port 8188
```

便携包应使用其自带 `run_nvidia_gpu.bat`，不要把上面的 `python` 当成通用命令。打开 `http://127.0.0.1:8188`。

**优先用默认内存策略**。遇到 CUDA OOM 时，先降画布/帧数、关其他 GPU 程序，再考虑 `--lowvram`。遇到系统 RAM 被 pinned memory 占满/不断换页时，试独立启动参数 `--disable-pinned-memory`；该参数在某些超低内存 H3 环境非常重要，但不能保证所有版本都有相同行为。

**不要为 H3 直接加** `--fast`、`--fp16-unet`、`--force-fp16` 来赌速度；社区低显存复现报告过与 H3 BF16 计算路径不匹配、黑帧的问题。50 系是否启用 Sage/Flash/Sol Attention，也先以当前 ComfyUI 及节点版本的真实兼容性为准。

### 步骤 4：在 ComfyUI 执行角色替换

1. 把 `minimax_h3_character_swap_workflow_native_nodes_v1.1.json` 拖进画布。
2. 在 `Load Diffusion Model` 指向 **Ref2VA** 模型；`Text Encoder` 指向 Qwen3-VL H3 版本；`VAE`、`LoRA` 逐个核对；缺少辅助的 DMD Turbo LoRA 则按工作流 Notes 补齐。**工作流中的 8 步必须匹配相应加速 LoRA，不能只改 `steps=8` 就当作 Turbo 生效。**
3. 将**原视频**接到 `MiniMaxH3AddGuide`，原作者建议 `frame_idx=0`；将角色图接到 H3 图片参考 `<Picture 1>`。
4. 选一段最有代表性的 2–3 秒测试，保留原始画面宽高比，输出帧数遵循 `17n+5`（例如 73 帧 ≈3.04 秒；124 帧 ≈5.17 秒，按 24fps）。
5. 最初不开二采、不插帧、不锐化，先得到 **baseline.mp4**。同时保存视频首、中、尾帧截图。

### 步骤 5：参考图与提示词（决定脸/衣服是否漂）

你此前的蓝衣长袖、斗笠、葫芦、扇子等配饰属于**结构复杂的 Cosplay**；只有单张正面参考时，袖子翻转、遮挡、帽子背面和服饰细节都可能被模型凭空补全。因此推荐准备：

- `ref_front.png`：全身正面、包含鞋靴，脸清楚，无强滤镜。
- `ref_side.png`：同一角色 45–90°，衣服背侧与帽檐结构清楚。
- `ref_back.png`：同一服饰背面/披风细节，可选。
- `ref_face.png`：面部特写，可选。
- 四张图必须尽量是**同一个人、同一套服装、同一套颜色**，不能只靠提示词拼出不存在的背面。

最初测试只提供 v1.1 工作流能稳定消费的 1 张主参考图；多参考必须正确映射到 `<Picture 2>` 等槽位并重写 `subject_definitions`，**不是把四张图拼在一张画布就一定更好**。

可从以下英文模板起步（不是保证精确遵循的“锁脸指令”）：

```text
body_swap: subject_definitions: <Subject 1> is the same adult woman shown in <Picture 1>.
Identity: preserve the exact facial structure, dark reddish-brown hair, hairstyle, skin tone and body proportions from <Picture 1>.
Costume: deep muted indigo-blue kimono-style cosplay outfit, black waist corset,
tan rope belt, black arm sleeves, straw hat, hanging gourds, and the exact props shown in <Picture 1>.
The guide video provides the original environment, camera, framing, timing and performance.
Replace only the main person in the guide video with <Subject 1>.
Keep one consistent person and one consistent costume in every frame.
No clothing redesign, no color shifts toward bright purple, no changing face shape,
no missing props, no added decorations, no background repainting, no temporal flicker.
```

**严格色彩建议**：不用单一“blue outfit”概括全部蓝色衣料，可将主衣服定为深靛蓝、腰带黑色、绳带浅棕、帽子草黄色，按参考图逐件描述。不同模型不一定能听懂 HEX；真正的跨帧色彩匹配需要后处理/统一调色，而不是只靠负面词。

## 6. 为什么你之前会从蓝色逐渐漂成紫色、脸不一致

这里应拆成四个相互独立的误差源，分别处理：

1. **人物身份漂移**：模型每段重新生成细节；换镜头、扭头、遮挡、长袖挡脸后更容易变脸。处理：先短段、一致参考图；使用 Character Swap LoRA；分段时重用同一角色参考而非连续拿上段误差结果当唯一依据。
2. **服装配色漂移**：亮度、色温、布料反射及模型重绘共同导致蓝→紫。处理：原始参考图固定色域；减少二采重绘强度；对合成后的人体区域做统一色彩映射；以参考服装关键区域为校准点。
3. **细节模糊**：低分辨率本身、VAE、快速采样、视频压缩和过激平滑。处理：低分辨率首轮只测动作；确保二采使用相容 latent upscaler；成片经时序一致的视频超分而非粗暴每帧独立“画脸”。
4. **背景/动作不准确**：Ref2VA 本身有创造性，不是像素级视频编辑器。处理：需要保背景时上人物分割蒙版并仅重绘人物；需要动作极近似时提高源视频引导分辨率、必要时加入 pose/normal 结构控制。

**建议质量优先级**：① 人物和衣装是否对 → ② 动作跟随 → ③ 背景不变 → ④ 清晰度 → ⑤ 超分/插帧。前三级失败时，即使升到 2K 也只是把错误放大。

## 7. B 路线：在能稳定换人后做 H3 二采

### 7.1 使用 Director 自带可复现的 JSON

安装：

```powershell
# 将路径改成你实际的 ComfyUI 根目录后运行
cd 'E:\AI\ComfyUI-H3\ComfyUI\custom_nodes'
git clone https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director.git

# 便携版必须使用其 python_embeded/python.exe，以下只是普通 venv 的示例
# python -m pip install -r '.\ComfyUI_MiniMaxH3_Director\requirements.txt'
```

更适合初学者的方式：ComfyUI Manager → **Install via Git URL** → 输入仓库地址 → 重启；打开插件目录自带 `example_workflows/minimax_h3_director_rv2v.json` 或 `minimax_h3_director_二采_加速.json`。

Director 的操作方式：

1. 主模型选择 **Ref2VA**；选择 `rv2v`（原视频＋参考人物图）。不要用 `fl2v` 误以为那是保动作整人替换。
2. 原视频分镜可按时间轴切分；固定同一张角色图、同一角色定义。每段开始/结束尽量避开快速遮挡动作。
3. 添加 **MiniMax H3 Director Refine**，把其输出接到导演台的 `refine` 输入。
4. `mode=upscale`：先增大视频 latent 再二次采样；`mode=refine`：同分辨率再采；`mode=latent_upscale`：只放大 latent，**不二次采样**。
5. `mode=upscale/refine` 时必须连接 `BasicScheduler` 或 `ManualSigmas` 至 `Refine.sigmas`；要与二采模型匹配。不要额外给 Refine 手工叠加一次 `SigmaShift`。
6. `confirm_first_pass` 可以第一轮只出一采并缓存、第二轮再二采；分别保留 `images_pre_refine` 与 `images` 作对照。

### 7.2 适合 16GB VRAM + 32GB RAM 的试验参数

| 阶段 | 先试参数 | 说明 |
|---|---|---|
| 一采测试 1 | 竖屏 `416×736` 或横屏 `736×416`；73 帧；速度 LoRA 对应的步数 | 先评估脸/衣服/动作，低成本排错 |
| 一采测试 2 | 5s（124 帧），短边仍约 416–480 | 先稳定一采，不急于二采 |
| 二采测试 1 | 比例放大约 **1.25×**，只 `passes=1` | 先检验速度、显存和脸是否被二次重画 |
| 二采测试 2 | 目标 720p 级分辨率（例如 `720×1280` 竖屏，前提是节点按 32 对齐） | 只有上一档不 OOM、外观不漂时再做；H3 原生训练分辨率约束须遵守 |
| 正式生成 | 原始 24fps，按场景切成约 3–5s 段，质量优先再拼接 | 15s 单段可能减少切段缝，但显存、时长和人物一致性风险更高 |

**特别注意**：`720×1280` 两个数并非都能被 32 整除（720 不是 32 的倍数），实际输入务必按节点要求**取邻近 32 倍数**（如 `704×1248`、`736×1280`；保原始画面比例并避免过度裁掉帽子/鞋子）。也不要超出 MiniMax Base 的训练分辨率条件。

如二采让脸变形、服装蓝色变紫：先在一采前后对照帧上找到问题起点；尝试更低的二采去噪强度（若工作流有可调项）、减少 passes、换更保守的精修模型；必要时**舍弃二采，改成一采定稿＋视频超分**。

## 8. C 路线：Openjutsu 精细整人替换（可选）

这是**更接近“只改人、不动背景”的工具形态**：视频导入后 SAM 3.1 跟踪主体，预览蒙版，H3 只生成被替换区域；作者提供 `Fix faces` 与 `Fix colours`。源代码、安装说明、工作流 JSON 均在 [D3voz/openjutsu](https://github.com/D3voz/openjutsu)。

### 安装建议

1. ComfyUI 升级至 Openjutsu README 所需的 **0.41.2+**，确认 GPU/PyTorch 适配。
2. 安装 [Node.js ≥22.6](https://nodejs.org/en/download) 与 Git；先检查 `node --version`、`npm --version`、`git --version`。
3. 在独立目录克隆：

```powershell
cd 'E:\AI'
git clone https://github.com/D3voz/openjutsu.git
cd '.\openjutsu'
```

4. 照仓库 README 在 ComfyUI 中安装它列出的 **11 个左右节点包**；安装模型时严格以 Openjutsu 的模型表为准（见本方案 §4.3），别假设前面的 v1.1 JSON 或任一 NVFP4 量化无需适配就能用。
5. 先启动 ComfyUI `http://127.0.0.1:8188`；Windows 下该仓库要求 ComfyUI 启动时设置环境变量 `AIOHTTP_NOSENDFILE=1`，例如 `PowerShell: $env:AIOHTTP_NOSENDFILE = '1'` 后再启动。
6. 双击 `openjutsu\start_openjutsu.bat`。项目 README 称其会安装代理/依赖并构建 Next.js 应用；网页一般打开 `http://127.0.0.1:3000`，真实端口和失败日志以该版本 README 为准。
7. 先选 **Simple motion transfer** → 2–3s 原视频 → 单张角色参考图 → `Check mask`。如果帽子被旧角色带回，可试 `Hat fix`；如果蒙版漏掉袖子/腿，调整 `Mask margin`。
8. 通过蒙版验证后再 Generate → 对完成的短片依次做 `Fix faces` / `Fix colours`，每次保存单独结果以便比较。

README 明确指出：镜面反射/橱窗倒影可能把原角色带回；某些张口、微表情由 H3 重新推断；局部服装改造可能继承旧服装的轮廓。它比“整帧重画”更适合背景保护，但也**不能保证脸恒定**。

### 为什么 32GB RAM 不该一开始就选 C？

Openjutsu 开发者测试硬件是 RTX 4060 Ti 16GB + **64GB RAM**，高精度 INT8 主模型和多个辅助模型靠 RAM 流式卸载；用户的 32GB RAM 还有 Windows、浏览器和 ComfyUI 本体占用。因此 C 应作为 **A/B 成功后的进阶试验**。先做 `Check mask` 单独阶段、保存跟踪结果，再释放 SAM / VLM 内存、运行 H3；一旦长时间停在加载/换页，**不要误认作“正在计算”而一直等待**。

## 9. 进一步优化：锁脸、锁衣服、锁颜色

**这部分比单纯增加采样次数更重要。**

### 9.1 锁脸

- 先保证角色参考图有清晰面部（五官无遮挡），且人物在视频中足够大；低分辨率里只占几十像素的人脸无法仅靠提示词恢复真实细节。
- 参考图尽量同身份、同妆容、同发型；避免从两个不同人物照片“混出一张脸”。
- 保存完整输出，**最后做单独人脸修复**。Openjutsu 的 `Fix faces` 提供偏向“像参考图”与偏向“跟随原视频嘴型”的不同模式；二者存在取舍，嘴型与身份不能无条件同时完全一致。
- 一旦出现眼睛数/手指畸变，先排查源视频遮挡、动作速度和低分辨率；不要盲目加 Face LoRA。

### 9.2 锁服装和道具

- 把斗笠、袖子、腰带、葫芦、扇子等拆成独立观察点，做首/中/尾帧对照。
- 重要配饰必须在参考图能看见；超出画面或长期被遮挡时模型可能删除它。
- 对漂移最严重的 1–2 秒单独重采；多镜头拼接时固定角色描述、参考图、色彩参数。
- 正向提示词尽量精准（深蓝/黑色/草编黄/浅棕绳带），避免宽泛“漂亮 Cosplay”；不依赖泛泛的负面词来保证细节。

### 9.3 锁颜色

最优顺序是：**先确定一采帧是否色准 → 再决定是否二采 → 最后统一调色**。如果第 0 秒就偏紫，说明不是“后面逐渐漂”的问题，而是模型风格/参考控制不足。

在 Openjutsu 的 `Fix colours` 中先试较温和的默认配置；如果蓝衣依然偏紫，可在剪辑软件（DaVinci Resolve 免费版、FFmpeg 滤镜或你已有视频软件）按人物蒙版定向调校蓝/紫色相，保持背景颜色不变。不要直接对整帧强行换色，这会把背景灰色与肤色也染坏。

### 9.4 清晰度

- 不要在角色还漂时用 Topaz、SeedVR2、Real-ESRGAN 做高清化；先锁住人物再超分。
- 先导出高质量中间文件，避免每个阶段重复 H.264 低码率编码。
- 需要 30fps/60fps 时最后再插帧，动作快速与袖摆交叠处要逐帧检查残影。
- 本地二采提高 latent 细节、视频超分提高视觉清晰度，两者可以并行比较，不保证叠加一定更好。

## 10. 逐步验收：用最少算力筛掉无效方案

| 试验 | 只改变什么 | 观察重点 | 通过后做什么 |
|---|---|---|---|
| T0 | 3s、Ref2VA、**不加任何角色 LoRA** | H3 是否跑通、动作/音频是否正常 | 排除部署问题 |
| T1 | T0 + Character Swap LoRA v1.1 | 人脸、服装、斗笠、葫芦与原背景 | 与 T0 固定种子对比 |
| T2 | 只更换角色参考图/提示词 | 脸/蓝衣一致性是否改善 | 选稳定参考组合 |
| T3 | 一采不变，打开低倍率二采 | 高清化是否带来变脸、变紫 | 成功再放大画布 |
| T4 | 用 SAM 蒙版限人物区（若转 C） | 背景、地面、人物边缘 | 合成/修脸 |
| T5 | 固定最终模型与参考图，延长至 5–15s | 是否随时间漂移、拼接处跳变 | 最后超分和插帧 |

建议每个 T 试验都保存：`workflow.json`、`seed`、主模型文件名、量化精度、LoRA 列表及强度、分辨率、帧数、步骤数、用时、峰值显存、系统 RAM 峰值、首中尾帧和最终 MP4。**相同 Seed 也不等于跨量化/跨节点版本严格可复现**。

**推荐的主观及客观验收**（人工先审）：

- 身份：5 个间隔取样帧能否一眼判断为同一张脸。
- 服装：深蓝是否稳定为同类蓝色；袖摆、腰带、腿部、斗笠和配饰不能前后“长出/消失”。
- 动作：出拳/转头/抬手的关键时间点是否和原片同秒；有无莫名额外动作。
- 背景：原片灰背景色和相机运动是否保留；无大片涂抹。
- 清晰度：眼口轮廓、纹理不过度锐化；快速动作无明显时序闪烁。
- 音频：保留原片音轨和时间同步；如需只替换画面、保持原声，优先后期直接复用原音轨。

## 11. 典型问题排查

| 症状 | 最可能原因 | 优先处理 |
|---|---|---|
| `CUDA out of memory` | 主模型+编码器+VAE+视频 latent 同时占显存 | 73 帧/低分辨率、逐阶段卸载、关闭其它 GPU 应用，必要时 `--lowvram`；更小 DiT 量化 |
| RAM 28–32GB，系统/采样几乎不动 | 多阶段模型争抢 RAM、Windows 换页 | 检查任务管理器“已提交”、磁盘占用；先关闭 SAM/额外 VLM、重启 ComfyUI，降低任务长度；考虑 64GB RAM |
| 加载后模型找不到 | 下载位置不对，或工作流记录的是别人的模型名 | 核对 ComfyUI 根目录、Loader 下拉菜单，重新选择实际名称 |
| 节点红框/执行错误 | 第三方节点、加速 LoRA 不齐、版本不匹配 | 先按工作流 Notes 完整装依赖，再用单采、不开额外组件测试 |
| 全黑帧、Nan | 错误 dtype、加速器内核不兼容 | 去掉强制 FP16/实验性 Attention，回到官方兼容配置 |
| 人物脸越来越陌生 | 参考图覆盖不足、长片漂移、二采过重 | 缩短窗口，固定主参考，关二采先查，最终单独修脸 |
| 蓝衣越来越紫 | 色彩映射漂移与风格重绘 | 固定深蓝细节描述，减二采强度，末尾按人物蒙版统一调色 |
| 帽子/手上的道具被截断 | 蒙版边缘过紧或主体检测遗漏 | Openjutsu 的 `Check mask` 调 margin、`Hat fix`、手工扩蒙版 |
| 输出 720p 但仍模糊 | 低采样质量、VAE/视频压缩、超分并不增加真实身份信息 | 先检查无压缩中间帧，评估二采与时序视频超分，勿盲目加锐化 |
| 不能从 8GB 视频复现角色替换 | 原视频案例可能用 FL2VA/T2V、不用 SAM/Ref2VA | 对照其真实 JSON、量化类型、输入素材与硬件条件 |

## 12. 明确的限制与合规前提

1. **无法保证面部绝对不变形**，只能逐阶段提高一致性；一帧成功不能推出 15s 成功。
2. **16GB VRAM + 32GB RAM 可试，但无法保证复现 Openjutsu 的 64GB RAM 实测。** 单个量化权重约 10.86GB 并不代表整个生成只要 10.86GB 显存。
3. **MiniMax H3 并不是无地区限制的开源许可。** 官方 FAQ 提到当前社区权重许可**不包含美国、英国、欧盟、韩国**等地区；使用或分发前应核对最新许可及所在地适用条件，不能通过本方案绕过限制。法律和商业条款请以模型许可原文为准。
4. 真人肖像替换要取得当事人许可，并确认来源视频、角色形象、Cosplay 衣装的使用权；发布时避免误导观众以为是真实拍摄。
5. 第三方量化权重、角色 LoRA、节点的兼容性和安全性均以各仓库实际版本为准，**不要随便下载不明来源的 exe/整合包**；优先官方 GitHub/Hugging Face 链接，并验证校验和。

## 13. 可直接给 Codex 执行的任务单

> 以下任务单**不授权 Codex 自动删改已有 ComfyUI、重装 Python/显卡驱动或修改整个 Windows 全局环境**。若涉及管理员操作、模型许可、系统虚拟内存或大体积下载，先让我确认。

```text
目标：在 Windows 11 RTX 5060 Ti 16GB / 32GB RAM 的新台式机上，
为 MiniMax H3 Ref2VA 建立一个独立可回滚的 ComfyUI 单人整人替换实验环境。
输入：原始单人动作视频、固定真人 Cosplay 角色参考图。
输出：可执行 ComfyUI JSON、3秒对比视频、日志、显存/RAM指标、首中尾帧对照表。

阶段一（只读）：
  1. 识别现有 ComfyUI 安装、Python/Torch/CUDA、NVIDIA 驱动、盘符和剩余空间；
  2. 核验模型许可与目录，列出已有模型，不重复下载，不覆盖旧环境；
  3. 如果仓库版 JSON、第三方 NVFP4 主模型和 LoRA 不匹配，先报告具体节点及依赖。

阶段二（经确认才写入）：
  4. 在独立目录部署新版 ComfyUI，先完成官方 H3 Ref2VA 最小跑通；
  5. 下载 H3 量化模型/TE/VAE、Character Swap LoRA v1.1 与 native workflow；
  6. 优先使用 10.86GiB NVFP4 DiT；若不兼容，提出 INT8 回退计划并计算 RAM 成本；
  7. 用 73 帧低分辨率源片测试，记录显存、RAM、速度和准确性；
  8. 调整人物参考、LoRA、手工提示词，避免同时引入二采/复杂 SAM。

阶段三（首片通过后）：
  9. 试 Director rv2v + 二采工作流，保存一采/二采两个版本；
 10. 若背景或人物边缘仍有问题，再单独部署 Openjutsu，优先 Check mask；
 11. 仅在脸和衣服已稳定时使用 Fix faces、Fix colours 与视频超分；
 12. 交付 workflow、版本/权重表、日志、前后对比、失败复现方式；
 13. 不把模型下载大小当作显存峰值，不把推测耗时写成实测耗时。
```

## 14. 一手资料与开源项目索引

### 官方 / 核心资料

1. [MiniMax 官方 H3 开源仓库](https://github.com/MiniMax-AI/MiniMax-H3)（FL2VA / Ref2VA、输入数量、时长、许可）。
2. [MiniMax 官方 H3 介绍与 FAQ](https://design.minimaxi.com/h3)（32–64GB RAM 建议、Base 768p 与云端 2K 区别、地区限制）。
3. [MiniMax 官方维护的社区集成索引](https://github.com/MiniMax-AI/awesome-minimax-h3-integration)（量化/VRAM/节点路线总表）。
4. [ComfyUI 官方 MiniMax H3 教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)。
5. [Comfy-Org MiniMax-H3 模型仓](https://huggingface.co/Comfy-Org/MiniMax-H3)（主模型、TE、VAE）。

### 与本任务最相关的开源项目

6. [Alissonerdx / MiniMax H3 Character Swap LoRA v1.1](https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI/blob/main/docs/character-swap.md)（纯原生节点版 JSON、换人 LoRA、可选二采）。
7. [AIMixer / MiniMaxH3 Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director)（rv2v 时间轴 / `minimax_h3_director_二采_加速.json`）。
8. [D3voz / Openjutsu](https://github.com/D3voz/openjutsu)（SAM 人体跟踪、换人蒙版、修脸、调色；公开实测 16GB VRAM + 64GB RAM）。
9. [DmitryDB / MiniMax-H3-ComfyUI-Quants](https://huggingface.co/DmitryDB/MiniMax-H3-ComfyUI-Quants)（RTX 50 系 NVFP4 Ref2VA 10.86GiB / 13.60GiB 主模型）。
10. [FlowForgeLabAi / MiniMax-H3-8GB-Workflows](https://github.com/FlowForgeLabAi/MiniMax-H3-8GB-Workflows)（低内存陷阱）。
11. [YixuAn / minimax-h3-comfyui-all-in-one](https://github.com/YixuAn-13/minimax-h3-comfyui-all-in-one)（参考模式与 8GB 二采实测）。

---

**本方案最重要的一句话：先用 H3 Ref2VA + Character Swap LoRA 在 3 秒内把“人、脸、衣服、颜色”做对；只有这一步稳定后，二采和超分才有意义。**
