#!/bin/bash
# MiniMax H3 模型下载（ModelScope 源，断点续传，可重复执行）
# 顺序已按"换人路线优先"排好：TE → ref2va → VAE → turbo LoRA → fl2va(文生)
# 用法：bash download_h3_models.sh

COMFY="E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI"
SRC="https://modelscope.cn/models/Comfy-Org/MiniMax-H3/resolve/master"
LOG="$COMFY/../h3_download.log"

declare -a ITEMS=(
"text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors|15687142551"
"diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors|20970379616"
"vae/minimax_h3_video_vae_int8_convrot.safetensors|2811065184"
"vae/minimax_h3_audio_vae_fp32.safetensors|605254808"
"loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors|1956192992"
"diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors|20970379616"
"loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors|1956193000"
"loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors|1956192992"
)

echo "===== START $(date '+%F %T') =====" >> "$LOG"

for item in "${ITEMS[@]}"; do
  rel="${item%%|*}"; want="${item##*|}"
  dest="$COMFY/models/$rel"
  mkdir -p "$(dirname "$dest")"
  have=0
  [ -f "$dest" ] && have=$(stat -c %s "$dest" 2>/dev/null || echo 0)

  if [ "$have" -ge "$want" ]; then
    echo "[SKIP] $rel 已完成 ($((have/1048576)) MB)" >> "$LOG"
    continue
  fi

  echo "[GET ] $rel  $((have/1048576))/$((want/1048576)) MB  $(date '+%T')" >> "$LOG"
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
    curl -sSL -C - --no-progress-meter \
         --retry 10 --retry-delay 5 --retry-all-errors \
         --speed-limit 3000 --speed-time 90 --connect-timeout 20 \
         -o "$dest" "$SRC/$rel"
    have=$(stat -c %s "$dest" 2>/dev/null || echo 0)
    echo "     try$attempt -> $((have/1048576)) MB  $(date '+%T')" >> "$LOG"
    [ "$have" -ge "$want" ] && break
    sleep 3
  done

  if [ "$have" -ge "$want" ]; then
    echo "[DONE] $rel" >> "$LOG"
  else
    echo "[FAIL] $rel ($((have/1048576))/$((want/1048576)) MB) 重跑脚本可续传" >> "$LOG"
  fi
done

echo "===== END $(date '+%F %T') =====" >> "$LOG"
du -sh "$COMFY/models/diffusion_models" "$COMFY/models/text_encoders" "$COMFY/models/vae" "$COMFY/models/loras" >> "$LOG" 2>/dev/null
