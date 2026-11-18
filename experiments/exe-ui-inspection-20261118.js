/* H3 影栈 —— 前端逻辑 */
const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => { const n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; };

const ICON = {
  text: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 11h11M4 16h7"/><circle cx="18" cy="16.5" r="2.6"/></svg>`,
  image: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4.5" width="18" height="15" rx="3"/><circle cx="8.6" cy="9.6" r="1.6"/><path d="m4 17 5-4.6 3.6 3.2L16 12l4 4.4"/></svg>`,
  film: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M7.5 4v16M16.5 4v16M3 9h4.5M3 15h4.5M16.5 9H21M16.5 15H21"/></svg>`,
  swap: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="3"/><path d="M2.8 19c0-2.9 2.3-5 5.2-5s5.2 2.1 5.2 5"/><path d="M16 8h5.2M18.6 5.3 21.2 8l-2.6 2.7"/><path d="M16 16h5.2M18.6 13.3 21.2 16l-2.6 2.7"/></svg>`,
  pose: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="4.6" r="2"/><path d="M12 6.6v6M12 8.6 7.4 11M12 8.6 16.6 11M12 12.6 8.4 18M12 12.6 15.6 18"/></svg>`,
};

/* 画质词：默认折叠，用户想改再展开 */
const Q = {
  base:
    "写实摄影质感，皮肤有真实纹理与血色，毛孔和细小绒毛可见，不磨皮、不过曝。\n" +
    "全身构图完整，头脚不出画，机位稳定不抖动，焦距和景别前后一致。\n" +
    "光线柔和均匀，明暗过渡自然，色调统一不偏色。\n" +
    "服装颜色与款式稳定，不漂移、不变形，衣料褶皱随动作自然垂坠。\n" +
    "面部清晰不糊，眼睛睁开有焦点，会自然眨眼，表情放松自然。\n" +
    "手指与四肢结构正确，不多手多脚、不穿模、不粘连。\n" +
    "画面干净，背景不杂乱，无噪点、无水印、无文字。",
  ref:
    "写实摄影质感，皮肤有真实纹理与血色，毛孔和细小绒毛可见，不磨皮、不过曝。\n" +
    "动作节奏连贯，关键动作不打折、不错位，动作之间自然过渡。\n" +
    "全身构图完整，头脚不出画，机位稳定，焦距和景别前后一致。\n" +
    "光线柔和均匀，人物与环境的光线方向一致，色调统一不偏色。\n" +
    "服装颜色与款式稳定，不漂移、不变形，衣料褶皱随动作自然垂坠。\n" +
    "面部清晰不糊，眼睛睁开有焦点，会自然眨眼，表情放松自然。\n" +
    "手指与四肢结构正确，不多手多脚、不穿模、不粘连。\n" +
    "画面干净，背景不杂乱，无噪点、无水印、无文字。",
  swap:
    "写实摄影质感，皮肤有真实纹理与血色，毛孔和细小绒毛可见，不磨皮、不过曝。\n" +
    "背景、机位、景别、镜头运动与原片保持一致，只替换人物身份与穿着。\n" +
    "人物边缘干净，与背景衔接自然，不出现重影、拖影和穿帮。\n" +
    "面部清晰不糊，眼睛睁开有焦点，表情与动作节奏贴合原片。\n" +
    "服装颜色与款式稳定，不漂移、不变形，衣料褶皱随动作自然垂坠。\n" +
    "手指与四肢结构正确，不多手多脚、不穿模、不粘连。\n" +
    "画面干净，无噪点、无水印、无文字。",
};

const ADV_WH = [
  { k: "steps", label: "步数", ph: "4" },
  { k: "seed", label: "种子", ph: "随机" },
];
const ADV_TIP = "步数留空用上面的精细度预设（4 步带加速 LoRA）。种子填同一个值可以复现同一段画面。";

const MODES = {
  "01": {
    no: "①", name: "文生视频", icon: ICON.text, badge: "", hot: false, family: "fl2v",
    desc: "只写一段文字描述，AI 从零画出画面。不需要准备任何素材，最适合先试试手感。",
    facts: ["约 11 分钟出片", "单次 5 秒", "无需素材"],
    fields: [
      { k: "prompt", t: "text", label: "画面描述", rec: true, rows: 5,
        ph: "她是谁、在哪、做什么。例如：一位红褐色长发的年轻女性，站在木质洗手间里，缓缓转身看向镜头，抬手挥了挥",
        tip: "这里只写人和动作，画质要求已经收进下面的「质量词」，不用重复写。" },
      { k: "ratio", t: "seg", label: "画面比例", def: "竖屏", opts: [["竖屏", "640×1120"], ["竖屏高清", "768×1344"], ["横屏", "1120×640"], ["方形", "896×896"]] },
      { k: "duration", t: "seg", label: "时长", def: "5 秒", opts: [["5 秒", "最稳"], ["10 秒", "更久"], ["15 秒", "上限"]] },
      { k: "quality", t: "seg", label: "精细度", def: "标准", opts: [["标准", "4 步 · 快"], ["高质", "20 步 · 慢"]], tip: "4 步已经接近这条模型的上限，12 步只是稍稳一点，耗时约 2.5 倍。" },
      { k: "qt", t: "text", label: "质量词", rows: 8, fold: true, def: Q.base },
      { k: "adv", t: "adv", label: "高级参数", items: ADV_WH, tip: ADV_TIP },
    ],
  },
  "02": {
    no: "②", name: "图生视频", icon: ICON.image, badge: "推荐", hot: true, family: "fl2v",
    desc: "第 1 张放角色、第 2 张放场景，让她在场景里做你描述的动作。只放 1 张时，就直接以它当视频第 1 帧。",
    facts: ["约 11 分钟出片", "单次 5 秒", "角色图 + 场景图"],
    fields: [
      { k: "chars", t: "upload", narrow: true, kind: "image", multi: 4, label: "角色图", rec: true,
        addText: "添加角色图",
        hint: "这些都是同一个角色的不同角度/部位，越全越像。",
        tip: "第 1 张放全身正面（定长相、发型、服装），第 2 张可以放头肩特写（定五官、妆容）。" },
      { k: "scenes", t: "upload", narrow: true, kind: "image", multi: 3, label: "场景图",
        addText: "添加场景图",
        hint: "这些是背景/环境参考，决定她站在哪里、光从哪来。",
        tip: "放场景图＝让她进到这张图的环境里做动作；不放就只以角色图为首帧动起来。" },
      { k: "prompt", t: "text", label: "动作描述", rec: true, rows: 4, def: "",
        ph: "她做什么？例如：她坐在马桶上，双手抱膝抬头看镜头，然后慢慢站起来转身走出去",
        tip: "这里只写动作，别写画质——画质词已经收在下面的「质量词」里。" },
      { k: "ratio", t: "seg", label: "画面比例", def: "竖屏", opts: [["竖屏", "640×1120"], ["竖屏高清", "768×1344"], ["横屏", "1120×640"], ["方形", "896×896"]] },
      { k: "duration", t: "seg", label: "时长", def: "5 秒", opts: [["5 秒", "最稳"], ["10 秒", "更久"], ["15 秒", "上限"]] },
      { k: "quality", t: "seg", label: "精细度", def: "标准", opts: [["标准", "4 步 · 快"], ["高质", "20 步 · 慢"]] },
      { k: "qt", t: "text", label: "质量词", rows: 8, fold: true, def: Q.ref },
      { k: "adv", t: "adv", label: "高级参数", items: ADV_WH, tip: ADV_TIP },
    ],
  },
  "03": {
    no: "③", name: "视频参考", icon: ICON.film, badge: "", family: "ref2v",
    desc: "上传一段参考视频，AI 照着它的动作节奏和构图重新画一遍。动作会「像」，但不是逐帧一致。",
    facts: ["约 12 分钟出片", "1 段视频 + 可选角色图", "动作相似而非相同"],
    fields: [
      { k: "video", t: "upload", kind: "video", label: "参考视频", rec: true, tip: "建议 2–15 秒、24fps 的短视频，太长要先切段。" },
      { k: "chars", t: "upload", narrow: true, kind: "image", multi: 4, label: "角色图", addText: "添加角色图",
        hint: "同一个角色的不同角度，越全越像。",
        tip: "第 1 张放角色，第 2 张可以补头肩特写。不放就沿用原片里那个人。" },
      { k: "scenes", t: "upload", narrow: true, kind: "image", multi: 3, label: "场景图", addText: "添加场景图",
        hint: "背景/环境参考，决定她站在哪里、光从哪来。",
        tip: "第 1 张放场景，决定成片的背景环境与光线；不放就沿用原片的背景。" },
      { k: "prompt", t: "text", label: "动作补充（一般留空）", rows: 3, def: "",
        ph: "动作已经跟随参考视频，这里一般留空；想强调某个瞬间可以写一句" },
      { k: "ratio", t: "seg", label: "画面比例", def: "竖屏", opts: [["竖屏", "640×1120"], ["竖屏高清", "768×1344"], ["横屏", "1120×640"], ["方形", "896×896"]] },
      { k: "duration", t: "seg", label: "时长", def: "5 秒", opts: [["5 秒", "最稳"], ["10 秒", "更久"]] },
      { k: "quality", t: "seg", label: "精细度", def: "标准", opts: [["标准", "4 步 · 快"], ["高质", "20 步 · 慢"]] },
      { k: "keep_audio", t: "seg", label: "音频", def: "使用原音频",
        opts: [["使用原音频", "跟原片一致"], ["模型生成", "AI 配音"]],
        tip: "使用原音频：生成完把源视频的音轨盖回去，口型节奏最贴原片；模型生成则用 H3 自己配的声音。" },
      { k: "refsize", t: "seg", label: "参考图精度", def: "match", opts: [["match", "快"], ["max", "更像 · 慢"]],
        tip: "max 用 2048 短边跑参考图，身份更准，但慢数倍。" },
      { k: "qt", t: "text", label: "质量词", rows: 8, fold: true, def: Q.ref },
      { k: "adv", t: "adv", label: "高级参数", items: ADV_WH, tip: ADV_TIP },
    ],
  },
  "04": {
    no: "④", name: "角色替换", icon: ICON.swap, badge: "主打", hot: true, family: "ref2v",
    desc: "上传一段视频和几张角色图，把视频里的舞者整段换成你的角色。动作逐帧跟随原片，完成后自动拼回原音轨。",
    facts: ["约 26 分钟/段", "长片自动分段", "保留原声"],
    fields: [
      { k: "video", t: "upload", kind: "video", label: "源视频", rec: true, tip: "整段传进来就行，程序会自动按 10 秒切段、逐段生成、最后拼回原音轨。" },
      { k: "chars", t: "upload", narrow: true, kind: "image", multi: 4, min: 1, label: "角色图", rec: true, addText: "添加角色图",
        hint: "同一个角色的不同角度，越全越像。",
        tip: "第 1 张放全身正面（定长相、发型、服装），第 2 张可以放头肩特写（定五官、妆容）。" },
      { k: "scenes", t: "upload", narrow: true, kind: "image", multi: 3, label: "场景图", addText: "添加场景图",
        hint: "背景/环境参考，决定背景与光线。",
        tip: "第 1 张放场景；不放就沿用原片的背景环境。" },
      { k: "quality", t: "seg", label: "精细度", def: "标准", opts: [["标准", "4 步 · 快"], ["高质", "20 步 · 慢"]] },
      { k: "prompt", t: "text", label: "补充描述（一般留空）", rows: 3, fold: true, def: "",
        ph: "动作跟随原片，这里一般留空；想额外强调什么再写" },
      { k: "refsize", t: "seg", label: "参考图精度", def: "match", opts: [["match", "快"], ["max", "更像 · 慢"]],
        tip: "max 用 2048 短边跑参考图，身份更准，但慢数倍。" },
      { k: "qt", t: "text", label: "质量词", rows: 8, fold: true, def: Q.swap },
      { k: "adv", t: "adv", label: "高级参数", items: ADV_WH, tip: ADV_TIP },
    ],
  },
  "05": {
    no: "⑤", name: "姿态控制", icon: ICON.pose, badge: "实验", family: "fl2v",
    desc: "把源视频里的人整段换成你的角色：动作、运镜、原生音频跟源视频走；不传场景图就沿用原片背景，传了就换成你的场景。",
    facts: ["动作逐帧复刻", "可换场景", "原生音频"],
    fields: [
      { k: "video", t: "upload", kind: "video", label: "动作来源视频", rec: true,
        tip: "程序会从里面提取人体骨架。建议 5–10 秒、单人、全身入镜。" },
      { k: "chars", t: "upload", narrow: true, kind: "image", multi: 3, label: "角色图", addText: "添加角色图", rec: true,
        hint: "同一个角色的不同角度。",
        tip: "第 1 张放角色正面全身图。" },
      { k: "scenes", t: "upload", narrow: true, kind: "image", multi: 2, label: "场景图", addText: "添加场景图",
        hint: "可选：换成这个场景。",
        tip: "不放就沿用原片的背景；放了会按参考图重建背景（动作仍然跟原片）。" },
      { k: "engine", t: "seg", label: "生成引擎", def: "SCAIL-2 · 角色替换",
        opts: [["SCAIL-2 · 角色替换", "动作最准 · 推荐"],
               ["H3 · 原声", "24fps · 原生音频"],
               ["Wan · 实验", "可能有构图问题"]],
        tip: "SCAIL-2：专门的角色替换模型，SAM3 自动跟踪人物，动作和构图都跟原片，5 分钟/4 秒（推荐）；H3：原生 24fps + 自带音轨，动作靠参考；Wan-Animate：实验性，会把画面拉成特写。" },
      { k: "prompt", t: "text", label: "补充描述（一般留空）", rows: 3, fold: true, def: "",
        ph: "动作和场景都由素材决定，这里一般留空" },
      { k: "ratio", t: "seg", label: "画面比例", def: "竖屏", opts: [["竖屏", "640×1120"], ["竖屏高清", "768×1344"], ["横屏", "1120×640"], ["方形", "896×896"]] },
      { k: "duration", t: "seg", label: "时长", def: "5 秒",
        opts: [["5 秒", "最稳"], ["10 秒", "更久"], ["整段", "自动分段"]],
        tip: "「整段」= 按原片时长自动切段（每段 10 秒、重叠 2 秒），逐段生成后拼接并挂回原音轨。" },
      { k: "express", t: "seg", label: "表情跟随", def: "开启",
        opts: [["开启", "表情/眼神跟着原片"], ["关闭", "动作优先 · 更快"]],
        tip: "开启后整段源视频参与参考，表情、眼神、嘴型会跟着原片变化；关闭则只锚定首帧（动作准但脸容易定格）。" },
      { k: "keep_audio", t: "seg", label: "音频", def: "使用原音频",
        opts: [["使用原音频", "跟原片一致"], ["模型生成", "AI 配音"]],
        tip: "使用原音频：生成完把源视频的音轨盖回去（推荐）；模型生成则用 H3 自己配的声音。" },
      { k: "quality", t: "seg", label: "精细度", def: "高质",
        opts: [["标准", "4 步 · 快"], ["高质", "20 步 · 更像"]],
        tip: "4 步加速画面会糊一点，20 步清晰度和身份都更稳（约 18 分钟/5 秒）。" },
      { k: "qt", t: "text", label: "质量词", rows: 8, fold: true, def: Q.ref },
      { k: "adv", t: "adv", label: "高级参数", items: ADV_WH, tip: ADV_TIP },
    ],
  },
};

const RATIO = { "竖屏": [640, 1120], "竖屏高清": [768, 1344], "横屏": [1120, 640], "方形": [896, 896] };
const DURATION = { "5 秒": 124, "10 秒": 243, "15 秒": 362 };
const QUALITY = { "标准": [4, true], "高质": [20, false] };


/* 尺寸/帧数吸附到模型网格：宽高 32 的倍数，帧数 17k+5 */
function geom(v) {
  let [w, h] = RATIO[v.ratio] || RATIO["竖屏"];
  if (+v.width > 0) w = Math.max(32, Math.round(+v.width / 32) * 32);
  if (+v.height > 0) h = Math.max(32, Math.round(+v.height / 32) * 32);
  let frames = DURATION[v.duration] || 124;
  if (+v.seconds > 0) frames = Math.max(5, Math.round((+v.seconds * 24 - 5) / 17) * 17 + 5);
  return { w, h, frames };
}

/* 比例 / 时长都允许手填，手填优先于预设 */
Object.values(MODES).forEach((m) => {
  m.fields.forEach((f) => {
    if (f.k === "ratio") {
      const [pw, ph] = RATIO[f.def] || RATIO["竖屏"];
      f.hint = "点选预设，或直接填宽高";
      f.nums = [{ k: "width", label: "宽", ph: () => String(pw) }, { k: "height", label: "高", ph: () => String(ph) }];
      f.tip = "留空就用预设；填了会吸附到 32 的倍数（16G 显存建议 ≤ 768×1344）。";
    }
    if (f.k === "duration") {
      const ps = Math.round((DURATION[f.def] || 124) / 24 * 10) / 10;
      f.hint = "点选预设，或直接填秒数";
      f.nums = [{ k: "seconds", label: "时长（秒）", ph: () => String(ps) }];
      f.tip = "留空就用预设；秒数会吸附到模型的 17k+5 帧网格（4.9 秒≈124 帧）。";
    }
  });
});

const S = {
  mode: "02",
  values: {},          // mode -> {field: value}
  assets: {},          // mode -> {field: {path, name, dataUrl, meta}}
  online: false,
  starting: false,
  engine: null,
  tasks: [],
  busy: false,
  models: null,
  currentPlay: null,
};

/* ---------------------------------------------------------------- 状态 */
async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (j && j.ok === false) throw new Error(j.error || "请求失败");
  return j;
}

function toast(msg, kind = "") {
  const t = el("div", "toast " + kind, msg);
  $("#toastWrap").appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; t.style.transition = ".3s"; }, 2800);
  setTimeout(() => t.remove(), 3200);
}

function fmtDur(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  if (sec < 60) return sec + " 秒";
  const m = Math.floor(sec / 60), s = sec % 60;
  if (m < 60) return s ? `${m} 分 ${String(s).padStart(2, "0")} 秒` : `${m} 分钟`;
  const h = Math.floor(m / 60);
  return `${h} 小时 ${m % 60} 分`;
}

/* ---------------------------------------------------------------- 侧栏 */
function renderModes() {
  const box = $("#modeList");
  box.innerHTML = "";
  Object.entries(MODES).forEach(([k, m]) => {
    const item = el("div", "mode-item" + (k === S.mode ? " on" : ""));
    item.innerHTML = `
      <div class="m-icon">${m.icon}</div>
      <div class="m-txt">
        <div class="m-name">${m.name}${m.badge ? `<span class="m-badge ${m.exp ? "exp" : "hot"}">${m.badge}</span>` : ""}</div>
        <div class="m-desc">${m.desc.slice(0, 20)}</div>
      </div>`;
    item.onclick = () => { S.mode = k; renderModes(); renderStage(); };
    box.appendChild(item);
  });
}

/* ---------------------------------------------------------------- 中区 */
function vals(mode) {
  if (!S.values[mode]) S.values[mode] = {};
  const v = S.values[mode];
  MODES[mode].fields.forEach((f) => {
    if (v[f.k] === undefined) v[f.k] = f.def !== undefined ? f.def : "";
  });
  if (!S.assets[mode]) S.assets[mode] = {};
  return v;
}

function renderStage() {
  const m = MODES[S.mode];
  const v = vals(S.mode);

  const head = $("#modeHead");
  head.innerHTML = `
    <div class="mh-top"><span class="mh-no">${m.no}</span><div class="mh-title">${m.name}</div></div>
    <div class="mh-desc">${m.desc}</div>
    <div class="mh-facts">${m.facts.map((f) => `<div class="fact"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.5 1.5" stroke-linecap="round"/></svg>${f}</div>`).join("")}</div>`;

  const form = $("#formArea");
  form.innerHTML = "";

  let pairBox = null;
  m.fields.forEach((f) => {
    if (f.t === "text") {
      const box = el("div", "sect" + (f.fold ? " foldable" : ""));
      if (f.fold) {
        box.innerHTML = `<div class="sect-h fold-h"><b>${f.label}</b><span class="fold-tag">可选</span>
          <button class="fold-btn">展开<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 9l6 6 6-6"/></svg></button></div>`;
      } else {
        box.innerHTML = `<div class="sect-h"><b>${f.label}</b>${f.rec ? '<em>建议填写</em>' : ""}</div>`;
      }
      const body = el("div", f.fold ? "fold-body" : "");
      const ta = el("textarea");
      ta.rows = f.rows || 4;
      ta.value = v[f.k] || "";
      ta.placeholder = f.ph || "用中文描述你想要的画面…";
      ta.oninput = () => { v[f.k] = ta.value; };
      body.appendChild(ta);
      if (f.tip) body.appendChild(el("small", "f-tip", f.tip));
      box.appendChild(body);
      if (f.fold) {
        const btn = box.querySelector(".fold-btn");
        btn.onclick = () => {
          const open = box.classList.toggle("open");
          btn.firstChild.textContent = open ? "收起" : "展开";
          if (open) ta.focus();
        };
      }
      form.appendChild(box);
    } else if (f.t === "adv") {
      const box = el("div", "sect foldable");
      box.innerHTML = `<div class="sect-h fold-h"><b>${f.label}</b><span class="fold-tag">高级</span>
        <button class="fold-btn">展开<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 9l6 6 6-6"/></svg></button></div>`;
      const body = el("div", "fold-body");
      const row = el("div", "adv-row");
      f.items.forEach((it) => {
        const cell = el("label", "adv-cell");
        cell.innerHTML = `<span>${it.label}</span>`;
        const inp = el("input");
        inp.type = "number";
        inp.placeholder = it.ph || "";
        inp.value = v[it.k] || "";
        inp.oninput = () => { v[it.k] = inp.value; };
        cell.appendChild(inp);
        row.appendChild(cell);
      });
      body.appendChild(row);
      if (f.tip) body.appendChild(el("small", "f-tip", f.tip));
      box.appendChild(body);
      const btn = box.querySelector(".fold-btn");
      btn.onclick = () => {
        const open = box.classList.toggle("open");
        btn.firstChild.textContent = open ? "收起" : "展开";
      };
      form.appendChild(box);
    } else if (f.t === "seg") {
      const box = el("div", "sect");
      box.innerHTML = `<div class="sect-h"><b>${f.label}</b>${f.nums ? `<span class="hint-mini">${f.hint || "点选预设，或在下面直接填"}</span>` : ""}</div>`;
      const row = el("div", "seg");
      f.opts.forEach(([name, sub]) => {
        const b = el("button", "seg-item" + (v[f.k] === name ? " on" : ""),
          `<span>${name}</span><small>${sub}</small>`);
        b.onclick = () => {
          v[f.k] = name;
          if (f.nums) { f.nums.forEach((n) => { v[n.k] = ""; }); }
          renderStage();
        };
        row.appendChild(b);
      });
      box.appendChild(row);

      if (f.nums) {
        const numRow = el("div", "adv-row nums-row");
        f.nums.forEach((it) => {
          const cell = el("label", "adv-cell");
          cell.innerHTML = `<span>${it.label}</span>`;
          const inp = el("input");
          inp.type = "number";
          inp.placeholder = it.ph ? it.ph() : "";
          inp.value = v[it.k] || "";
          inp.min = it.min || 1;
          inp.oninput = () => { v[it.k] = inp.value; };
          if (it.suffix) cell.appendChild(el("i", "unit", it.suffix));
          cell.appendChild(inp);
          numRow.appendChild(cell);
        });
        box.appendChild(numRow);
      }
      if (f.tip) box.appendChild(el("small", "f-tip", f.tip));
      form.appendChild(box);
    } else if (f.t === "upload") {
      const node = uploadBox(f, v);
      if (f.narrow) {
        // 角色图 / 场景图并排成一行，省纵向空间
        if (!pairBox) { pairBox = el("div", "sect-pair"); form.appendChild(pairBox); }
        pairBox.appendChild(node);
      } else {
        pairBox = null;
        form.appendChild(node);
      }
    }
  });

  if (!m.exp) form.appendChild(modelBox(m));

  const hint = $("#submitHint");
  hint.textContent = estimateText();

  const btn = $("#btnGenerate");
  btn.disabled = S.busy;
  btn.querySelector("span").textContent = S.busy ? "正在生成…" : "开始生成";
}

/* 模型选择：让用户看到并切换引擎真正加载的文件 */
function modelBox(m) {
  const sel = (S.models && S.models.selected) || {};
  const files = (S.models && S.models.files) || {};
  const fam = m.family || "fl2v";
  const hintKw = fam === "fl2v" ? "fl2va" : "ref2va";

  const pick = (kind, famKw) => {
    const all = (files[kind] || []).filter((f) => /minimax_h3/i.test(f.name));
    const base = all.length ? all : (files[kind] || []);
    const match = base.filter((f) => f.name.toLowerCase().includes(famKw));
    return match.length ? match : base;
  };

  const rows = [
    { key: "unet_" + fam, label: "主模型", kind: "unet", kw: hintKw,
      tip: fam === "fl2v" ? "文生视频 / 图生视频用的主模型" : "视频参考 / 角色替换用的主模型" },
    { key: "lora_" + fam, label: "加速 LoRA", kind: "lora", kw: "", tip: "4 步出片靠它，删掉就要跑 20 步" },
  ];
  if (S.mode === "04") rows.push({ key: "lora_swap", label: "换人 LoRA", kind: "lora", kw: "swap", tip: "只替换人物身份用的适配层" });

  const box = el("div", "sect");
  box.innerHTML = `<div class="sect-h"><b>模型</b>
      <button class="mrefresh">刷新列表</button></div>
    <div class="sect-sub">下面是引擎这次真正会加载的文件。换模型只影响之后的生成，正在跑的任务不受影响。</div>`;
  box.querySelector(".mrefresh").onclick = (e) => { e.preventDefault(); loadModels(true); };

  const grid = el("div", "model-grid");
  rows.forEach((r) => {
    let list = (files[r.kind] || []);
    if (r.kw) {
      const hit = list.filter((f) => f.name.toLowerCase().includes(r.kw));
      if (hit.length) list = hit;
    } else if (r.kind === "unet") {
      list = pick("unet", hintKw);
    } else {
      const h3 = list.filter((f) => /minimax_h3/i.test(f.name));
      if (h3.length) list = h3;
    }
    const cur = sel[r.key] || "";
    const eff = (S.models && S.models.effective) ? (S.models.effective[r.key] || "") : "";
    const curFile = list.find((f) => f.name === cur) || list.find((f) => f.name === eff);

    const row = el("div", "mrow");
    row.innerHTML = `<div class="f-label"><span>${r.label}</span>
        <span class="msize">${curFile ? curFile.gb.toFixed(2) + " GB" : (cur ? "文件不在库里" : "跟随工作流默认")}</span></div>`;
    const s = el("select", "mselect");
    s.appendChild(el("option", "", "跟随工作流默认"));
    s.lastChild.value = "";
    list.forEach((f) => {
      const o = el("option", "", f.name);
      o.value = f.name;
      s.appendChild(o);
    });
    if (cur && !list.some((f) => f.name === cur)) {
      const o = el("option", "", cur + "（不在当前目录）");
      o.value = cur;
      s.appendChild(o);
    }
    s.value = cur;
    s.onchange = () => saveModel(r.key, s.value);
    row.appendChild(s);
    if (r.tip) row.appendChild(el("small", "f-tip", r.tip));
    grid.appendChild(row);
  });
  box.appendChild(grid);
  return box;
}

async function saveModel(key, value) {
  const sel = Object.assign({}, (S.models && S.models.selected) || {});
  sel[key] = value;
  try {
    const r = await api("/api/models", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ models: sel }),
    });
    S.models = r;
    toast(value ? "已切换模型，下次生成生效" : "已恢复工作流默认模型", "ok");
    renderStage();
  } catch (e) {
    toast("保存失败：" + e.message, "err");
  }
}

async function loadModels(notify = false) {
  try {
    S.models = await api("/api/models");
    if (notify) toast("模型列表已刷新", "ok");
    renderStage();
  } catch (e) {
    if (notify) toast("读取模型列表失败：" + e.message, "err");
  }
}

function assetList(mode, f) {
  const v = S.assets[mode] && S.assets[mode][f.k];
  if (!v) return [];
  return Array.isArray(v) ? v : [v];
}

function setAssets(mode, f, arr) {
  if (!S.assets[mode]) S.assets[mode] = {};
  if (!arr || !arr.length) delete S.assets[mode][f.k];
  else S.assets[mode][f.k] = f.multi ? arr : arr[0];
}

function hasAsset(mode, f) {
  return assetList(mode, f).length > 0;
}

function uploadBox(f, v) {
  const arr = assetList(S.mode, f);
  const isVid = f.kind === "video";
  const multi = !isVid && f.multi > 1;
  const box = el("div", "sect");
  box.innerHTML = `<div class="sect-h"><b>${f.label}</b>${f.rec ? "<em>必填</em>" : ""}` +
    `${multi ? `<span class="cnt">${arr.length} / ${f.multi}</span>` : ""}</div>`;

  const zone = el("div", "drop" + (arr.length ? " has" : "") + (multi && arr.length ? " multi" : ""));

  if (multi) {
    if (arr.length) {
      const grid = el("div", "thumb-grid");
      arr.forEach((a, i) => {
        const t = el("div", "thumb");
        t.innerHTML = `<img src="${a.dataUrl || ""}" alt=""><span class="thumb-no">${i + 1}</span>
          <button class="thumb-x" title="移除这张">×</button>`;
        t.querySelector(".thumb-x").onclick = (e) => {
          e.stopPropagation();
          const next = arr.slice();
          next.splice(i, 1);
          setAssets(S.mode, f, next);
          renderStage();
        };
        grid.appendChild(t);
      });
      if (arr.length < f.multi) {
        const add = el("button", "thumb-add", `+<small>继续加</small>`);
        add.onclick = (e) => { e.stopPropagation(); input.click(); };
        grid.appendChild(add);
      }
      zone.appendChild(grid);
      zone.appendChild(el("div", "drop-txt multi-txt",
        f.narrow
          ? `<span>${arr.length} 张已就绪 · ${f.hint || "点 + 继续加"}</span>`
          : `<b>${arr.length} 张已就绪${f.min && arr.length < f.min ? `（建议至少 ${f.min} 张）` : ""}</b>` +
            `<span>${f.hint || (f.slot === "fl2v"
              ? "第 1 张是角色（也是首帧）；点 + 继续加，点 × 移除。"
              : "第 1 张是角色，第 2 张是场景，再往后当角色补充角度；点 + 继续加，点 × 移除。")}</span>`));
    } else {
      zone.classList.add("add-row");
      zone.innerHTML = `<div class="add-plus">+</div>
        <div class="drop-txt"><b>${f.addText || "点击添加参考图"}</b>
          <span>${f.narrow ? `最多 ${f.multi} 张，可陆续加` : `可以一张一张陆续添加，最多 ${f.multi} 张`}</span></div>`;
    }
  } else {
    const a = arr[0];
    zone.innerHTML = `
      ${a && !isVid ? `<img class="drop-thumb" src="${a.dataUrl || ""}">` : `<div class="drop-ico">${isVid ? ICON.film : ICON.image}</div>`}
      <div class="drop-txt">
        <b>${a ? a.name : (isVid ? "点击选择视频，或把文件拖进来" : "点击选择图片，或把图片拖进来")}</b>
        <span>${a ? (a.meta || "已就绪") : (isVid ? "支持 mp4 / mov，长视频会自动分段" : "支持 png / jpg，可一次选多张")}</span>
      </div>
      <button class="drop-clear"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>`;
    zone.querySelector(".drop-clear").onclick = (e) => {
      e.stopPropagation();
      setAssets(S.mode, f, []);
      renderStage();
    };
  }

  const input = el("input");
  input.type = "file";
  input.accept = isVid ? "video/*" : "image/*";
  input.multiple = multi;
  input.style.display = "none";
  input.onchange = () => { addFiles(input.files, f); input.value = ""; };
  zone.appendChild(input);

  zone.onclick = (e) => {
    if (e.target.closest(".drop-clear") || e.target.closest(".thumb-x") || e.target.closest(".thumb")) return;
    input.click();
  };
  zone.ondragover = (e) => { e.preventDefault(); zone.classList.add("over"); };
  zone.ondragleave = () => zone.classList.remove("over");
  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    addFiles(e.dataTransfer.files, f);
  };
  box.appendChild(zone);
  if (f.tip) box.appendChild(el("small", "f-tip", f.tip));
  return box;
}

function readAsDataUrl(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = () => rej(new Error("读取文件失败"));
    r.readAsDataURL(file);
  });
}

async function uploadOne(file, f) {
  const isVid = f.kind === "video";
  const dataUrl = await readAsDataUrl(file);
  const res = await api("/api/upload", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: file.name, data: dataUrl }),
  });
  let meta = `${(file.size / 1048576).toFixed(1)} MB`;
  if (isVid) {
    try {
      const info = await api("/api/probe?path=" + encodeURIComponent(res.path));
      meta = `${info.width}×${info.height} · ${info.duration.toFixed(1)} 秒 · ${info.frames} 帧`;
    } catch (e) { }
  }
  return { path: res.path, name: file.name, dataUrl: isVid ? "" : dataUrl, meta };
}

async function addFiles(files, f) {
  const list = Array.from(files || []);
  if (!list.length) return;
  const isVid = f.kind === "video";
  const cur = assetList(S.mode, f);
  const limit = isVid ? 1 : (f.multi || 1);
  const room = Math.max(0, limit - cur.length);
  if (room <= 0) {
    toast(isVid ? "这里只需要一段视频，先点 × 移除旧的再换" : `最多 ${limit} 张，先移除多余的再添加`, "");
    return;
  }
  const use = list.slice(0, room);
  if (list.length > room) toast(`超出上限，只添加了前 ${room} 个`, "");
  toast(use.length > 1 ? `正在上传 ${use.length} 个文件…` : "正在读取…");
  const added = [];
  for (const file of use) {
    if (isVid && file.size > 600 * 1024 * 1024) { toast("视频太大了，请控制在 600MB 内", "err"); continue; }
    try {
      added.push(await uploadOne(file, f));
    } catch (e) {
      toast("上传失败：" + e.message, "err");
    }
  }
  if (added.length) {
    setAssets(S.mode, f, cur.concat(added));
    renderStage();
    toast(isVid ? "视频已就绪" : `已添加 ${added.length} 张参考图`, "ok");
  }
}

function estimateText() {
  const v = vals(S.mode);
  const m = MODES[S.mode];
  if (m.exp) return "该模式还需要补一个控制模型文件，暂时无法运行";
  const need = m.fields.filter((f) => f.t === "upload" && f.rec).filter((f) => !hasAsset(S.mode, f));
  if (need.length) return "还需要上传：" + need.map((f) => f.label).join("、");
  if (S.mode === "05" && (v.engine || "").indexOf("SCAIL") === 0) {
    const a = assetList("05", { k: "video" })[0];
    const m = a && a.meta && a.meta.match(/(\d+) 帧/);
    const f24 = m ? parseInt(m[1]) : 0;
    if (!f24) return "上传源视频后会自动计算分段与耗时";
    const f16 = Math.round(f24 / 24 * 16);
    const segs = Math.max(1, Math.ceil((f16 - 5) / 60));
    const per = v.quality === "高质" ? 9 : 5;
    return `SCAIL-2 将切成 ${segs} 段 · 每段约 ${per} 分钟 · 共约 ${Math.round(segs * per)} 分钟`;
  }
  if (S.mode === "05" && v.duration === "整段") {
    const a05 = assetList("05", { k: "video" })[0];
    const i05 = a05 && a05.meta && a05.meta.match(/(\d+) 帧/);
    const total05 = i05 ? parseInt(i05[1]) : 0;
    if (!total05) return "上传源视频后会自动计算分段与耗时";
    const segs05 = Math.max(1, Math.ceil((total05 - 49) / 194));
    return `将自动切成 ${segs05} 段 · 每段约 40 分钟 · 共约 ${Math.round(segs05 * 40)} 分钟`;
  }
  if (S.mode === "04") {
    const a = assetList("04", { k: "video" })[0];
    const info = a && a.meta && a.meta.match(/(\d+) 帧/);
    const frames = info ? parseInt(info[1]) : 0;
    if (frames) {
      const segs = Math.max(1, Math.ceil((frames - 49) / 194));
      return `将自动切成 ${segs} 段 · 每段约 26 分钟 · 共约 ${Math.round(segs * 26)} 分钟`;
    }
    return "上传源视频后会自动计算分段与耗时";
  }
  const { w, h, frames } = geom(v);
  const [steps] = QUALITY[v.quality] || QUALITY["标准"];
  const px = (w * h) / (640 * 1120);
  const mins = Math.max(2, 11 * Math.pow(px, 0.85) * (frames / 124) * Math.pow(steps / 4, 0.72));
  return `预计 ${Math.round(mins)} 分钟左右出片`;
}

/* ---------------------------------------------------------------- 提交 */
async function generate() {
  if (S.busy) return;
  const m = MODES[S.mode];
  const v = vals(S.mode);

  const missing = m.fields.filter((f) => f.t === "upload" && f.rec && !hasAsset(S.mode, f));
  if (missing.length) return toast("请先上传：" + missing.map((f) => f.label).join("、"), "err");
  if (m.exp) return toast("这个模式还缺一个控制模型文件，暂时跑不了。等把 FunControl 权重放进 models/model_patches 就能用。", "err");
  const promptField = m.fields.find((f) => f.k === "prompt");
  if (promptField && promptField.rec && !promptField.fold && !(v.prompt || "").trim())
    return toast("请先写一句她要做什么动作", "err");

  const [qSteps, qTurbo] = QUALITY[v.quality] || QUALITY["标准"];
  const manual = +v.steps > 0 ? Math.min(60, Math.max(1, Math.round(+v.steps))) : 0;
  const steps = manual || qSteps;
  const turbo = manual ? steps <= 6 : !!qTurbo;
  const { w, h, frames } = geom(v);
  const params = { prompt: v.prompt || "", quality: v.qt || "", turbo: !!turbo, steps };
  const vidField = m.fields.find((f) => f.t === "upload" && f.kind === "video");
  const vid = vidField ? assetList(S.mode, vidField)[0] : null;
  const scailEngine = (v.engine || "").indexOf("SCAIL") === 0;
  const wanEngine = (v.engine || "").indexOf("Wan") === 0;
  if (S.mode === "05" && scailEngine) {
    params.engine = "scail";
    params.frames = 65;
    params.width = w; params.height = h;
    params.video_abs = vid ? vid.path : "";
    params.video = vid ? vid.name : "";
    params.steps = v.quality === "高质" ? 12 : 6;
    params.segment = true;
  } else if (S.mode === "05" && wanEngine) {
    params.engine = "wan";
    params.frames = 81;
    params.width = w; params.height = h;
    params.video_abs = vid ? vid.path : "";
    params.video = vid ? vid.name : "";
    params.steps = v.quality === "高质" ? 10 : 6;
    params.turbo = true;
  } else if (S.mode === "05" && v.duration === "整段") {
    params.frames = 243;
    params.width = w; params.height = h;
    params.video_abs = vid ? vid.path : "";
    params.video = vid ? vid.name : "";
    params.segment = true;
  } else if (S.mode === "04") {
    params.frames = frames || 243;
    params.width = w; params.height = h;
    params.video_abs = vid ? vid.path : "";
    params.video = vid ? vid.name : "";
  } else {
    params.width = w; params.height = h;
    params.frames = frames;
    if (vid) params.video = vid.path;
  }
  if ((v.seed || "").trim()) params.seed = parseInt(v.seed, 10);
  if (v.refsize) params.ref_size = v.refsize;
  if (v.express) params.express = (v.express === "开启");
  if (v.keep_audio) params.keep_audio = (v.keep_audio !== "模型生成");

  // 图序：角色图在前、场景图在后，后端按 char_count 拆开指认
  const chars = assetList(S.mode, { k: "chars" }).map((x) => x.path);
  const scenes = assetList(S.mode, { k: "scenes" }).map((x) => x.path);
  const imgs = chars.concat(scenes);
  if (imgs.length) {
    params.images = imgs;
    params.char_count = chars.length;
  }

  S.busy = true;
  renderStage();
  try {
    const res = await api("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: S.mode, title: m.name, params }),
    });
    if (res.autostart) {
      toast("引擎还没启动，已自动开始拉起 ComfyUI（约 1 分钟）", "");
    } else {
      toast("已加入队列，右栏可以看到进度", "ok");
    }
    pollTasks();
    pollState();
  } catch (e) {
    toast(e.message, "err");
  } finally {
    S.busy = false;
    renderStage();
  }
}

/* ---------------------------------------------------------------- 任务 */
function renderTasks() {
  const box = $("#taskList");
  const active = S.tasks.filter((t) => t.status === "running" || t.status === "queued").length;
  $("#dockCount").textContent = active;
  if (!S.tasks.length) {
    box.innerHTML = `<div class="task-empty">还没有任务<br>左边选一个玩法，点「开始生成」</div>`;
    return;
  }
  box.innerHTML = "";
  S.tasks.slice(0, 12).forEach((t) => {
    const card = el("div", "task");
    const tagMap = { queued: ["排队", ""], running: ["生成中", "run"], done: ["完成", "ok"], error: ["失败", "err"], canceled: ["已取消", ""] };
    const [txt, cls] = tagMap[t.status] || ["", ""];
    const pct = t.status === "done" ? 100 : Math.round(t.progress || 0);
    const meta = [];
    if (t.status === "running" || t.status === "queued") {
      if (t.elapsed > 5) meta.push(`已用 ${fmtDur(t.elapsed)}`);
      if (t.eta > 0) meta.push(`剩约 ${fmtDur(t.eta)}`);
      if (S.tasks.filter((x) => x.status === "queued").length > 1 && t.status === "queued")
        meta.push(`队列中`);
    }
    card.innerHTML = `
      <div class="task-top">
        <div class="task-name">${t.title || t.mode}</div>
        <span class="task-tag ${cls}">${txt}</span>
      </div>
      <div class="task-stage"><span>${t.stage || ""}</span><span>${pct}%</span></div>
      <div class="bar"><i style="width:${Math.min(100, pct)}%"></i></div>
      ${meta.length ? `<div class="task-meta">${meta.map((x) => `<em>${x}</em>`).join("")}</div>` : ""}`;
    if (t.status === "done" && t.files && t.files.length) {
      const acts = el("div", "task-act");
      const p = el("button", "tlink", "播放");
      p.onclick = () => playFile(t.files[0]);
      const o = el("button", "tlink", "打开位置");
      o.onclick = () => api("/api/reveal", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: t.files[0].path }) });
      acts.appendChild(p); acts.appendChild(o);
      card.appendChild(acts);
    } else if (t.status === "running" || t.status === "queued") {
      const acts = el("div", "task-act");
      const c = el("button", "tlink dim", "取消");
      c.onclick = () => api("/api/cancel/" + t.id, { method: "POST" });
      acts.appendChild(c);
      card.appendChild(acts);
    } else if (t.status === "error") {
      card.appendChild(el("div", "task-err", (t.error || "未知错误").slice(0, 300)));
    }
    box.appendChild(card);
  });
}

function playFile(f) {
  S.currentPlay = f;
  const card = $("#playerCard");
  card.classList.add("has");
  card.innerHTML = `<video id="vid" src="/media?path=${encodeURIComponent(f.path)}" controls autoplay playsinline></video>
    <div class="player-bar">
      <button class="mini-btn" id="pbReveal"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h4l1.8 2H19a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>打开位置</button>
      <button class="mini-btn" id="pbName">${f.name}</button>
    </div>`;
  $("#pbReveal").onclick = () => api("/api/reveal", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: f.path }) });
  $("#pbName").onclick = () => toast(f.name);
}

/* ---------------------------------------------------------------- 引擎 */
function renderEngine(eng) {
  S.engine = eng;
  S.online = !!(eng && eng.online);
  S.starting = !!(eng && eng.starting);

  const pill = $("#pillEngine");
  const main = $("#engMain"), sub = $("#engSub");
  let cls = "engine-pill", text = "引擎未启动", subText = "点击这里启动 ComfyUI";
  if (S.online) {
    const q = (S.queueRunning || 0) + (S.queuePending || 0);
    if (q > 0) { cls += " busy"; text = "引擎工作中"; subText = `队列 ${q} 个任务`; }
    else { cls += " on"; text = "引擎就绪"; subText = "ComfyUI " + (eng.version || ""); }
  } else if (S.starting) {
    cls += " starting";
    text = "正在启动引擎 " + (eng.start_elapsed || 0) + " 秒";
    subText = "首次启动约需 1 分钟";
  } else {
    cls += " off";
    if (eng && eng.error) subText = "启动失败，点开看原因";
  }
  pill.className = cls;
  main.textContent = text;
  sub.textContent = subText;

  const state = $("#epState");
  state.className = S.online ? "on" : (S.starting ? "busy" : "off");
  state.textContent = S.online ? "在线" : (S.starting ? "启动中" : "离线");

  const rows = [];
  rows.push(["版本", eng && eng.version ? "ComfyUI " + eng.version : "—"]);
  rows.push(["端口", "127.0.0.1:" + ((eng && eng.port) || 8188)]);
  rows.push(["队列", `${(S.queueRunning || 0)} 运行 / ${(S.queuePending || 0)} 等待`]);
  if (eng && eng.gpu) rows.push(["显存", `${eng.gpu.used} / ${eng.gpu.total} GB`]);
  if (eng && eng.watch) rows.push(["进度通道", eng.watch.connected ? "已连接" : (eng.watch.alive ? "未连接" : "线程异常")]);
  $("#epRows").innerHTML = rows.map(([k, v]) => `<div class="ep-row"><span>${k}</span><b>${v}</b></div>`).join("");

  const msg = $("#epMsg");
  const text2 = (eng && (eng.error || eng.msg)) || "";
  if (text2) { msg.className = "ep-msg show" + (eng.error ? " err" : ""); msg.textContent = text2; }
  else msg.className = "ep-msg";

  $("#btnEngStart").disabled = S.online || S.starting;
  $("#btnEngStop").disabled = !S.online && !S.starting;
  $("#btnEngStart").textContent = S.starting ? "启动中…" : (S.online ? "已在运行" : "启动引擎");
}

function bindEngine() {
  const wrap = document.querySelector(".engine-wrap");
  $("#pillEngine").onclick = (e) => { e.stopPropagation(); wrap.classList.toggle("open"); };
  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) wrap.classList.remove("open");
  });
  $("#btnEngStart").onclick = async (e) => {
    e.stopPropagation();
    toast("正在拉起 ComfyUI，首次启动约 1 分钟…");
    try {
      await api("/api/comfy/start", { method: "POST" });
      pollState();
    } catch (err) { toast(err.message, "err"); }
  };
  $("#btnEngStop").onclick = async (e) => {
    e.stopPropagation();
    const running = S.tasks.some((t) => t.status === "running" || t.status === "queued");
    if (running && !confirm("还有任务在跑，关闭引擎会中断它们。确定关闭？")) return;
    toast("正在关闭引擎…");
    try {
      const r = await api("/api/comfy/stop", { method: "POST" });
      toast(r.msg || "已关闭", "ok");
      pollState();
    } catch (err) { toast(err.message, "err"); }
  };
  $("#btnEngOpen").onclick = () => api("/api/comfy/open", { method: "POST" });
  $("#btnEngLog").onclick = async () => {
    $("#modalLog").classList.add("on");
    $("#logPre").textContent = "读取中…";
    try {
      const r = await api("/api/comfy/log");
      $("#logPre").textContent = r.log || "（日志为空）";
    } catch (e) { $("#logPre").textContent = "读取失败：" + e.message; }
  };
  $("#btnCloseLog").onclick = () => $("#modalLog").classList.remove("on");
}

/* ---------------------------------------------------------------- 轮询 */
let lastDone = "";
async function pollState() {
  try {
    const s = await api("/api/state");
    S.queueRunning = (s.queue && s.queue.running) || 0;
    S.queuePending = (s.queue && s.queue.pending) || 0;
    renderEngine(s.engine || { online: s.online });
    if (s.gpu) {
      $("#pillGpu").querySelector("span").textContent = `${s.gpu.used} / ${s.gpu.total} GB 显存`;
    } else {
      $("#pillGpu").querySelector("span").textContent = "显卡 —";
    }
  } catch (e) { }
}

async function pollTasks() {
  try {
    const d = await api("/api/tasks");
    S.tasks = d.tasks || [];
    renderTasks();
    const done = S.tasks.find((t) => t.status === "done" && t.finished);
    if (done && done.id !== lastDone) {
      lastDone = done.id;
      if (done.files && done.files.length) {
        playFile(done.files[0]);
        toast("生成完成：" + done.files[0].name, "ok");
        pollHistory();
      }
    }
    const err = S.tasks.find((t) => t.status === "error" && t.finished && t.id !== S.seenErr);
    if (err) {
      S.seenErr = err.id;
      toast("任务失败：" + (err.error || "").slice(0, 60), "err");
    }
  } catch (e) { }
}

/* ---------------------------------------------------------------- 作品 */
const HIST = { batch: false, sel: new Set() };

function _updSelCount() {
  $("#selCount").textContent = String(HIST.sel.size);
}

async function _deleteFiles(paths) {
  let ok = 0, fail = 0;
  for (const p of paths) {
    try {
      const r = await api("/api/delete", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: p }),
      });
      if (r && r.ok === false) fail++; else { ok++; HIST.sel.delete(p); }
    } catch (e) { fail++; }
  }
  if (fail) toast(`完成：成功 ${ok} 个，失败 ${fail} 个`, fail && !ok ? "err" : "ok");
  else toast(`已删除 ${ok} 个文件`, "ok");
  pollHistory();
}

async function pollHistory() {
  try {
    const d = await api("/api/history");
    const box = $("#historyList");
    if (!d.items || !d.items.length) {
      box.innerHTML = `<div class="hist-empty">${HIST.batch ? "（批量模式）" : "还没有作品"}</div>`;
      return;
    }
    // 批量模式：点条目 = 勾选；正常模式：点条目 = 播放
    box.classList.toggle("batch", HIST.batch);
    box.innerHTML = "";
    d.items.slice(0, 20).forEach((it) => {
      const n = el("div", "hist-item", `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3.5 19 12 5 20.5z"/></svg><span class="hist-name">${it.name}</span><button class="hist-del" title="删除这个文件">✕</button>`);
      n.title = it.name;
      if (HIST.batch) {
        const cb = el("input", "hist-check");
        cb.type = "checkbox";
        cb.checked = HIST.sel.has(it.path);
        n.classList.toggle("sel", cb.checked);
        const toggle = () => {
          if (HIST.sel.has(it.path)) HIST.sel.delete(it.path);
          else HIST.sel.add(it.path);
          cb.checked = HIST.sel.has(it.path);
          n.classList.toggle("sel", cb.checked);
          _updSelCount();
        };
        cb.onclick = (ev) => { ev.stopPropagation(); toggle(); };
        n.insertBefore(cb, n.firstChild);
        n.onclick = toggle;
      } else {
        n.onclick = () => playFile(it);
      }
      const del = n.querySelector(".hist-del");
      del.onclick = async (ev) => {
        ev.stopPropagation();
        if (!confirm(`确定删除「${it.name}」？\n（文件会从磁盘上移除，不可恢复）`)) return;
        try {
          const r = await api("/api/delete", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: it.path }),
          });
          if (r && r.ok === false) toast("删除失败：" + (r.error || ""), "err");
          else { toast("已删除 " + it.name, "ok"); pollHistory(); }
        } catch (e) { toast("删除失败", "err"); }
      };
      box.appendChild(n);
    });
    _updSelCount();
  } catch (e) { }
}

function _setBatchMode(on) {
  HIST.batch = on;
  $("#btnBatchMode").hidden = on;
  $("#batchBar").hidden = !on;
  if (!on) HIST.sel.clear();
  _updSelCount();
  pollHistory();
}

function bindBatch() {
  $("#btnBatchMode").onclick = () => _setBatchMode(true);
  $("#btnBatchExit").onclick = () => _setBatchMode(false);
  $("#btnSelAll").onclick = async () => {
    const d = await api("/api/history");
    const items = (d.items || []).slice(0, 20);
    if (!items.length) return;
    const allSel = items.every((it) => HIST.sel.has(it.path));
    if (allSel) items.forEach((it) => HIST.sel.delete(it.path));
    else items.forEach((it) => HIST.sel.add(it.path));
    _updSelCount();
    pollHistory();
  };
  $("#btnBatchDel").onclick = () => {
    const paths = [...HIST.sel];
    if (!paths.length) { toast("先勾选要删除的作品", "err"); return; }
    if (!confirm(`确定删除选中的 ${paths.length} 个作品？\n（文件会从磁盘上移除，不可恢复）`)) return;
    _deleteFiles(paths);
  };
}

/* ---------------------------------------------------------------- 设置 */
async function openSettings() {
  const cfg = await api("/api/config");
  $("#cfgRoot").value = cfg.comfy_root || "";
  $("#cfgOut").value = cfg.out_dir || "";
  $("#cfgPort").value = cfg.port || 8188;
  $("#cfgAuto").checked = !!cfg.auto_start_comfy;
  $("#modalSettings").classList.add("on");
}

async function saveSettings() {
  await api("/api/config", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      comfy_root: $("#cfgRoot").value.trim(),
      out_dir: $("#cfgOut").value.trim(),
      port: parseInt($("#cfgPort").value) || 8188,
      auto_start_comfy: $("#cfgAuto").checked,
    }),
  });
  $("#modalSettings").classList.remove("on");
  toast("已保存，重启程序后生效", "ok");
  pollState();
}

/* ---------------------------------------------------------------- 绑定 */
function bind() {
  $("#btnGenerate").onclick = generate;
  $("#btnSettings").onclick = openSettings;
  $("#btnCloseSettings").onclick = () => $("#modalSettings").classList.remove("on");
  $("#btnSaveSettings").onclick = saveSettings;
  $("#btnFolder").onclick = () => api("/api/open", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  bindBatch();
  $("#btnMount").onclick = async () => {
    try {
      const r = await api("/api/mount", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comfy_root: $("#cfgRoot").value.trim() }),
      });
      if (r && r.ok === false) toast(r.error || "挂接失败", "err");
      else toast("模型已挂接：" + r.msg, "ok");
    } catch (e) { toast("挂接失败", "err"); }
  };
  bindEngine();
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") generate();
    if (e.key === "Escape") {
      $("#modalSettings").classList.remove("on");
      $("#modalLog").classList.remove("on");
      document.querySelector(".engine-wrap").classList.remove("open");
    }
  });
}

/* ---------------------------------------------------------------- 启动 */
// 支持用 #03 这类锚点直接打开某个模式，方便排查和截图
const bootMode = (location.hash || "").replace("#", "").trim();
if (MODES[bootMode]) S.mode = bootMode;

renderModes();
renderStage();
bind();
pollState();
pollTasks();
pollHistory();
loadModels();
setInterval(pollState, 2000);
setInterval(pollTasks, 1500);
setInterval(pollHistory, 8000);
