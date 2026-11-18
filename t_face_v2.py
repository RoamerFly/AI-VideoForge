# -*- coding: utf-8 -*-
"""面部修好版测试：接入头肩特写参考图（<Picture 2>）+ 重写表情段。

对比现状（只有全身定妆图当参考、脸在参考图里只有几十像素）
用法: python t_face_v2.py [steps] [turbo 1/0] [label]
"""
import json, sys, time

sys.path.insert(0, "E:/Agent/projects/freetime_AI_Video_Comfyui")
import run_h3_swap_full as R
import ab_face_test as A

VIDEO = "role_swap_20261112/ab_124f.mp4"
FRAMES = 124

PROMPT_V2 = """画面风格：写实摄影质感，纯白摄影棚背景，全身构图，保持与原片一致的机位、景别、焦距、光线方向，镜头全程固定不移动。

人物身份：把舞者替换为 <Picture 1> 中的角色——深棕红色长发、头戴浅色竹编斗笠并系带、蓝紫色无袖高开衩和服配白色内衬、黑色宽腰带外缠麻绳、黑色长筒袜与过肘护臂、腰侧挂褐色葫芦。脸型、五官、肤色、体型严格沿用 <Picture 1>，不得残留原舞者的白发或黑色紧身衣。

脸部细节：面部的骨相与五官比例严格参照 <Picture 2> 的头肩照——同一张脸、同一个人：眉形、双眼皮褶皱、绿灰色瞳孔、鼻梁高度、唇形厚薄、下颌线全部与 <Picture 2> 一致。眼睛是睁开的、瞳孔有高光有焦点，视线跟着身体动作走；双唇自然微张跟唱，唇形随节奏开合变化；表情随舞蹈自然起伏，发力时专注、放松时轻快，眨眼自然。皮肤是真人皮肤：有毛孔、细纹、血色与次表面散射，眼周和唇部有自然湿润感。

动作：完整复刻原片的舞蹈动作——重心左右转移、胯部与肩部同步摆动、手臂上举与收回、转身与回正，节奏与时间轴逐帧对齐，不加速、不减速、不改变方向。

服装动态：和服下摆与宽袖随舞动自然甩动，斗笠系带与长发同步摆动，布料褶皱、遮挡关系与脚踩地面的接触点物理可信。

背景：纯白摄影棚背景与地面反光保持不变，不添加任何场景元素。

不要文字，不要 logo，不要水印。"""


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    turbo = (sys.argv[2] if len(sys.argv) > 2 else "1") not in ("0", "false")
    label = sys.argv[3] if len(sys.argv) > 3 else f"v2_s{steps}{'t' if turbo else 'f'}"

    oi = R.load(R.OI)
    api = R.to_api(R.load(R.WF), oi)
    api = A.build(api, label, steps, turbo, 1.00)

    # 关键改动 1：接上第二张参考图（头肩特写）— 节点 139 LoadImage
    api["136"]["inputs"]["ref_images.ref_image_1"] = ["139", 0]
    # 关键改动 2：重写提示词，脸部以 <Picture 2> 为准
    api["138"]["inputs"]["value"] = PROMPT_V2
    # 关键改动 3：分辨率与源片段一致（ab_124f 是 768x1344 切出来的，这里保持 640x1120）
    api["136"]["inputs"]["ref_image_size"] = "match"
    print(f"测试组 {label}: steps={steps} turbo={turbo} refs=2 (front+head)", flush=True)

    res = A.post(api)
    if "error" in res:
        print("提交失败:", str(res["error"])[:2000], flush=True)
        return 1
    pid = res["prompt_id"]
    print("prompt_id", pid, flush=True)
    t0 = time.time()
    while True:
        time.sleep(10)
        h = R.get(f"/history/{pid}")
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                print("执行报错:", json.dumps(st, ensure_ascii=False)[:2000], flush=True)
                return 2
            files = [it["filename"] for node in h[pid].get("outputs", {}).values()
                     for v in node.values() if isinstance(v, list)
                     for it in v if isinstance(it, dict) and it.get("filename")]
            print(f"完成 {(time.time()-t0)/60:.1f} 分钟 {files}", flush=True)
            return 0
        if int(time.time() - t0) % 120 < 10:
            try:
                q = R.get("/queue")
                print(f"  [{label}] {(time.time()-t0)/60:.1f} 分钟 running={len(q.get('queue_running', []))}", flush=True)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
