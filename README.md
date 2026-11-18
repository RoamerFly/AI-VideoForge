# AI-VideoForge

本项目是本地视频角色替换与场景重拍工具，基于 ComfyUI 和 MiniMax H3 工作流，提供桌面端 H3 影栈程序与可复用的 API 工作流模板。

## 当前能力

- MiniMax H3 Ref2VA 角色替换
- 角色参考图和场景参考图输入
- AddGuide 动作、镜头和时间节奏引导
- 自然语言指定目标人物与时间范围
- 原视频音轨复用
- H3、SCAIL-2、Wan-Animate 实验路线
- ComfyUI API 工作流模板和桌面端界面

## 目录说明

- `app/` 桌面程序源码、前端界面和工作流模板
- `app/templates/` ComfyUI API 工作流 JSON
- `experiments/` 实验脚本和验证记录
- `*.md` 方案、交接、进度和部署说明
- `release/` 本地发布目录，模型和 EXE 不纳入 Git

模型权重、ComfyUI 运行时、生成视频、构建产物和本地虚拟环境均不提交到仓库。请按项目文档将模型配置到本地 ComfyUI 的 `models` 目录，并使用 `extra_model_paths.yaml` 挂接。

## 本地开发环境

建议使用项目约定的 Python 3.10 环境，并安装 `app/` 目录所需依赖。源码启动入口为：

```powershell
python app/server.py
```

构建 Windows 单文件程序：

```powershell
app\.venv\Scripts\python.exe -m PyInstaller app\H3影栈.spec --clean --noconfirm
```

运行前请确认本机 ComfyUI 已启动，并且 H3 模型、VAE、文本编码器和 LoRA 已按文档配置完成。

## 说明

当前自然语言替换默认使用角色优先的 H3 Ref2VA + AddGuide 路线。若同时上传角色参考图和场景参考图，角色参考图会优先用于人物身份，场景参考图用于环境重建。严格锁定背景时仍建议使用分阶段生成和人物遮罩合成。
