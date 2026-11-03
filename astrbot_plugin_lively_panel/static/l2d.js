// 〈名字〉的 Live2D 形象：面板正中间是她（只露上半身），以后直播也用这一套
// 通用：这里不写死哪个模型。模型的参数名、表情键、手势、取景都在形象设定 /static/live2d/avatar.json（panel-dev/live2d/avatar.json），换模型只换那份
// 这里只管“她现在什么状态”：动作（act）= 表情记号（marks）+ 手势 + 脸 + 头和身体怎么动；眨眼、呼吸、眼睛跟着鼠标、说话时嘴动都自己来
// 模型、设定、三个库放在 static/live2d/（第三方素材，不随仓库发布，见 README「字体和图片」；panel-dev/live2d/build.sh 做出来）；没放就当没有
// 极客模式不看这张画布，而是每帧叫 L2D.sample() 把她画到一小块贴图上、读回像素，用代码字拼出来
// 要在 geek.js、mind.js 前面载入；对外只有 window.L2D
(() => {
"use strict";
const DIR = "/static/live2d/", LIBV = "1031";
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
const outBack = k => 1 + 2.2 * (k - 1) ** 3 + 1.2 * (k - 1) ** 2;
const smooth = k => k * k * (3 - 2 * k);

// ---------- 动作：她的状态，和模型无关 ----------
// marks 表情记号（模型有的才出来）：gloom 黑脸 tears 落泪 dizzy 圈圈眼 hearts 爱心眼 squint ><眼 smug 屑屑眼 blush 脸红 loading 头上转圈
//   teeth 露牙 basin 钢盆 glasses 黑框眼镜 monocle 单片眼镜 sweat 冷汗；值是 0～1
// g 手势：prop 手里拿个小东西、chest 手按胸口、point 竖食指
// smile 眼睛弯、mouth 嘴型（-1 撇嘴 1 笑）、open 张嘴、brow 眉毛高低、inner 眉头上扬、puff 鼓脸、pucker 撅嘴、tongue 吐舌头、jaw 下巴、eye 睁眼程度
// head 头的角度 [左右, 上下, 歪]（度）、lean 往前倾（负）往后仰（正）（往前倾是凑近镜头、整个人会变大往下沉，-26 时约大 1.4 倍）、look 眼睛往哪看（mouse 跟鼠标、down 低头、up 往上想、away 别过脸、dart 东张西望、shut 闭着）
// sway 身体摇晃幅度、tempo 摇晃快慢、bounce 一下一下地蹦、jolt 吓一跳、chew 嚼东西、mutter 自己嘟囔、shake 摇头晃脑
const ACTS = {
  breathe:{smile:.25, mouth:.35, sway:1},
  hum:{smile:.9, mouth:.8, open:.12, sway:1.7, tempo:1.5, g:"prop", head:[0, 2, 6], mutter:.25},
  float:{smile:.5, mouth:.6, sway:1.4, tempo:.8, head:[0, 4, 4]},
  bubble:{smile:.4, mouth:.2, open:.35, pucker:.6, sway:1.1, look:"up"},
  tail:{marks:{squint:1}, mouth:.6, sway:2, tempo:1.3},
  crab:{smile:.7, mouth:.7, sway:2.4, tempo:2, head:[0, 0, 8]},
  run:{smile:.4, mouth:.5, open:.3, sway:1.6, tempo:2.4, bounce:.6},
  dance:{smile:1, mouth:1, open:.25, sway:2.6, tempo:1.6, g:"prop", shake:1},
  curtsy:{smile:.8, mouth:.8, open:.2, g:"chest", lean:-26, head:[0, -8, 6], sway:.4},
  wave:{smile:.7, mouth:1, open:.55, g:"chest", head:[0, 2, -8], bounce:.25},
  think:{mouth:0, brow:.55, inner:.3, g:"point", look:"up", head:[-10, 8, -9], lean:-6, sway:.5},
  mutter:{mouth:-.1, brow:.2, g:"point", look:"up", head:[-6, 6, -5], mutter:1, sway:.5},
  busy:{marks:{glasses:1}, mouth:.2, brow:.15, look:"down", head:[4, -10, 0], lean:-14, sway:.3, shake:.35},
  file:{marks:{monocle:1}, mouth:.3, brow:.3, g:"point", look:"down", head:[-10, -6, 4], lean:-8, sway:.4},
  cube:{marks:{glasses:1}, mouth:-.2, brow:-.2, look:"down", head:[0, -12, 3], lean:-12, sway:.2, mutter:.4},
  cheer:{marks:{squint:1}, mouth:1, open:.75, g:"prop", bounce:1, shake:.6},
  hop:{marks:{teeth:1}, smile:.6, mouth:1, open:.4, bounce:.7, head:[0, 4, 5]},
  giggle:{marks:{squint:1}, mouth:1, open:.6, shake:1.4, bounce:.3, head:[0, 2, 8]},
  shy:{marks:{blush:1}, mouth:.2, open:.1, pucker:.3, g:"chest", look:"away", head:[-14, -6, -7], lean:-6},
  love:{marks:{hearts:1, blush:1}, smile:.4, mouth:1, open:.3, g:"chest", head:[0, 2, 9], sway:1.2, tempo:.9},
  pout:{puff:1, pucker:.5, mouth:-.6, brow:-.8, look:"away", head:[16, 4, 7]},
  sigh:{marks:{sweat:1}, mouth:-.5, open:.2, inner:1, brow:-.2, eye:.6, look:"down", head:[0, -12, -5], lean:4, sway:.3},
  startle:{marks:{dizzy:1, sweat:1}, mouth:-.2, open:.75, brow:1, head:[0, 6, 0], lean:8, jolt:1},
  drag:{marks:{dizzy:1, sweat:1}, open:.5, brow:1, head:[0, 4, 10], jolt:1, shake:.8},
  sleep:{eye:0, smile:.5, mouth:.2, open:.12, look:"shut", head:[4, -14, 13], lean:-5, sway:.5, tempo:.5},
  yawn:{eye:.15, inner:.8, open:1, jaw:1, head:[0, 12, -6], lean:10, sway:.4},
  stretch:{eye:0, smile:1, mouth:.6, open:.35, look:"shut", head:[0, 14, 4], lean:18},
  look:{mouth:.3, look:"dart", sway:.6},
  rice:{marks:{blush:.6}, smile:.9, mouth:.6, chew:1, head:[0, -2, 5], sway:.6},
  breakfast:{smile:.7, mouth:.5, chew:1, eye:.8, head:[0, -4, 4], sway:.5},
  lunch:{smile:.9, mouth:.6, chew:1, head:[0, -2, 5], sway:.6},
  dinner:{marks:{blush:.5}, smile:.8, mouth:.6, chew:1, head:[0, -2, 6], sway:.6},
  token:{marks:{loading:1}, smile:.6, mouth:.4, chew:1, look:"up", sway:.4},
  load:{marks:{loading:1}, mouth:0, brow:.3, look:"up", head:[-4, 8, -4], sway:.3},
  // 戳她时的小反应
  pat:{marks:{blush:1}, smile:1, mouth:.9, look:"shut", head:[0, -6, 10], lean:-4},
  cheek:{marks:{squint:1}, puff:1, pucker:.4, head:[10, 0, 8], shake:.5},
  ear:{marks:{squint:1}, mouth:1, open:.5, shake:1.6, head:[0, 0, -9]},
  basin:{marks:{basin:1, sweat:1, dizzy:1}, open:.4, brow:1, jolt:1},
  smug:{marks:{smug:1}, mouth:.7, head:[8, 4, 6], lean:-4},
  tease:{marks:{squint:1}, tongue:1, mouth:1, open:.45, head:[8, 0, 10], shake:.5},
  cry:{marks:{gloom:1, tears:1}, mouth:-.8, inner:1, look:"down", head:[0, -10, -4], sway:.3},
};

// ---------- 加载：读形象设定，再依次载入三个库和模型 ----------
const loadScript = src => new Promise((ok, no) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => no(new Error("载入失败 " + src)); document.head.appendChild(s); });
let AV = null, PM = {}, app = null, model = null, im = null, core = null, host = null, paperOn = true, raf = 0, last = 0, rt = null;
let KEYS = [], GP = [], GSW = new Set(), HAS = new Set();
const api = {ok:false};
api.ready = (async () => {
  if(!window.WebGLRenderingContext) return false;
  // 设定会改，不能用长快取：每次都问一下服务器变没变
  AV = await fetch(DIR + "avatar.json", {credentials:"same-origin", cache:"no-cache"}).then(r => r.ok ? r.json() : null).catch(() => null);
  if(!AV) return false;
  try{
    for(const f of ["live2dcubismcore.min.js", "pixi.min.js", "cubism4.js"]) await loadScript(`${DIR}lib/${f}?v=${LIBV}`);
    const L = PIXI.live2d;
    L.CubismConfig.supportMoreMaskDivisions = true;  // 遮罩多的模型（DeepSeek-chan 有 49 组）默认只放得下 36 组
    app = new PIXI.Application({width:2, height:2, backgroundAlpha:0, antialias:true, autoStart:false, sharedTicker:false,
      resolution:Math.min(2, devicePixelRatio || 1), autoDensity:true});
    app.ticker.stop();
    model = await L.Live2DModel.from(DIR + AV.model, {autoUpdate:false, autoInteract:false});
    im = model.internalModel; core = im.coreModel;
    if(AV.mask_buffer) im.renderer.setClippingMaskBufferSize(AV.mask_buffer);  // 遮罩贴图大一点，眼睛、头发的边才不糊
    im.eyeBlink = undefined;          // 眨眼、呼吸、看哪儿都自己来
    im.breath = undefined;
    im.focusController = {update(){}, focus(){}, x:0, y:0};
    if(AV.idle_motion) model.motion(AV.idle_motion, 0).catch(() => {});  // 模型自带的待机动画（眼里的星星、泪光这些小特效）
    // 只拨模型里真有的参数
    const ids = new Set(core.getModel().parameters.ids);
    PM = Object.fromEntries(Object.entries(AV.params || {}).filter(([, id]) => ids.has(id)));
    KEYS = [...new Set(Object.values(AV.marks || {}).flatMap(o => Object.keys(o)))].filter(id => ids.has(id));
    GP = [...new Set(Object.values(AV.gestures || {}).flatMap(o => Object.keys(o)))].filter(id => ids.has(id));
    GSW = new Set(AV.gesture_switches || []);
    HAS = new Set([...Object.keys(AV.marks || {}), ...Object.keys(AV.gestures || {})]);
    im.on("afterMotionUpdate", apply);
    app.stage.addChild(model);
    api.ok = true; api.avatar = AV;
    return true;
  }catch(e){
    console.warn("[l2d]", e);
    return false;
  }
})();

// ---------- 每帧算目标值、平滑过去 ----------
const cur = {}, want = {}, tau = {};
let act = ACTS.breathe, actName = "breathe", extra = {}, extraUntil = 0, t = 0;
let gCur = null, gP = 0;                          // 手势：现在是哪个、举到几成
let jolt = 0, bounceT = 0, talkUntil = 0, talkSeed = 0, lip = -1, loading = false;
let blinkAt = 2, blinkK = 1;
const mouse = {x:0, y:0, at:-1e9};
let wander = {x:0, y:0, at:0}, gazeAt = null;
const DARTS = [[-.8, .1], [.7, 0], [-.3, -.3], [.6, .3], [0, 0]];
const put = (role, v, tc) => { const id = PM[role]; if(id){ want[id] = v; if(tc != null) tau[id] = tc; } };
function target(dt){
  const A = act, now = t;
  // 表情记号：动作带的 + 外面临时加的（express）+ 数据慢时头上转圈
  const mk = Object.assign({}, A.marks || {}, now < extraUntil ? extra : {}); if(loading) mk.loading = 1;
  const kv = {};
  for(const [name, v] of Object.entries(mk)) for(const [id, x] of Object.entries(AV.marks[name] || {})) kv[id] = Math.max(kv[id] || 0, x * v);
  for(const id of KEYS){ want[id] = kv[id] || 0; tau[id] ??= .12; }
  // 眼睛往哪看：默认跟鼠标（或外面给的 look()），鼠标停了就自己慢慢看来看去
  let gx = 0, gy = 0;
  const look = REDUCED && A.look === "dart" ? "mouse" : A.look || "mouse";
  if(look === "mouse"){
    if(gazeAt){ gx = gazeAt[0]; gy = gazeAt[1]; }
    else if(!REDUCED && now - mouse.at < 4){ gx = mouse.x; gy = mouse.y; }
    else if(!REDUCED){ if(now > wander.at) wander = {x:(Math.random() - .5) * .9, y:(Math.random() - .5) * .5, at:now + 2 + Math.random() * 3}; gx = wander.x; gy = wander.y; }
  } else if(look === "down"){ gx = Math.sin(now * .7) * .25; gy = -.75; }
  else if(look === "up"){ gx = .45; gy = .7; }
  else if(look === "away"){ gx = -.85; gy = -.25; }
  else if(look === "dart"){ const d = DARTS[Math.floor(now / 1.3) % DARTS.length]; gx = d[0]; gy = d[1]; }
  const shut = look === "shut", h = A.head || [0, 0, 0], sw = REDUCED ? 0 : (A.sway ?? 1), tp = A.tempo || 1;
  const shake = REDUCED ? 0 : (A.shake || 0) * Math.sin(now * 7.5) * 4;
  const swayX = Math.sin(now * .55 * tp) * 4 * sw, swayZ = Math.sin(now * .43 * tp + 1) * 3.5 * sw;
  put("head_x", clamp(h[0] + (shut ? 0 : gx * 22) + swayX * .6, -30, 30), .16);
  put("head_y", clamp(h[1] + (shut ? 0 : gy * 14) + Math.sin(now * .31 * tp) * 2 * sw, -30, 30), .16);
  put("head_z", clamp(h[2] + swayZ + shake, -30, 30), .16);
  put("gaze_x", shut ? 0 : clamp(gx, -1, 1), .1);
  put("gaze_y", shut ? 0 : clamp(gy, -1, 1), .1);
  // 身体：左右晃、蹦、往前倾
  let by = 0;
  if(A.bounce && !REDUCED){ bounceT += dt * 2.6; by = Math.abs(Math.sin(bounceT * Math.PI)) * 10 * A.bounce; }
  put("body_x", swayX * 1.4 + shake * .4, .32);
  put("body_y", by + jolt * 14, .32);
  put("body_z", swayZ * .8, .32);
  put("lean", A.lean || 0, .32);
  put("breath", (1 - Math.cos(now / 4.8 * Math.PI * 2)) / 2, 0);
  // 脸
  put("eye_smile", A.smile || 0, .16);
  put("mouth_form", A.mouth ?? .3, .1);
  put("brow_l", A.brow || 0, .1); put("brow_r", A.brow || 0, .1);
  put("brow_inner", A.inner || 0, .1);
  put("puff", A.puff || 0, .1);
  put("pucker", A.pucker || 0, .1);
  put("tongue", A.tongue || 0, .1);
  put("jaw", A.jaw || 0, .1);
  let open = A.open || 0;
  if(A.chew && !REDUCED) open = Math.max(0, Math.sin(now * 9)) * .45;
  if(lip >= 0) open = Math.max(open, lip);  // 外面接着声音时按音量张嘴
  else if(!REDUCED && (now < talkUntil || (A.mutter && Math.sin(now * .9) > 1 - A.mutter * 1.2))){
    const n = Math.sin(now * 17 + talkSeed) * .5 + Math.sin(now * 23.7) * .5; open = Math.max(open, .15 + Math.max(0, n) * .55);
  }
  put("mouth_open", open, .06);
  // 眨眼：闭着眼、><、圈圈眼的时候不眨
  const eye = A.eye ?? 1, noBlink = REDUCED || eye < .3 || mk.squint || mk.dizzy;
  if(!noBlink && now > blinkAt){ blinkK = Math.max(0, 1 - (now - blinkAt) / .07); if(now - blinkAt > .16){ blinkAt = now + 2 + Math.random() * 4.5; if(Math.random() < .2) blinkAt = now + .25; } }
  else blinkK = Math.min(1, blinkK + dt / .08);
  const e = eye * (now - blinkAt > .07 && now - blinkAt < .16 ? 0 : blinkK);
  put("eye_l", e, 0); put("eye_r", e, 0);
  // 手势：先把手放下来，再举起新的（举起时带一点回弹）
  const gw = A.g && AV.gestures[A.g] ? A.g : null;
  if(gCur !== gw){ gP -= dt / .38; if(gP <= 0){ gP = 0; gCur = gw; } }
  else if(gCur) gP = Math.min(1, gP + dt / .55);
  const G = gCur ? AV.gestures[gCur] : {}, ge = gw === gCur ? outBack(gP) : smooth(gP);
  for(const id of GP){ want[id] = (G[id] || 0) * (GSW.has(id) ? clamp(gP * 1.4, 0, 1) : ge); tau[id] = 0; }
  jolt *= Math.exp(-dt * 6);
}
function step(dt){
  target(dt);
  for(const p in want){
    const w = tau[p] ?? .1, c = cur[p] ?? want[p];
    cur[p] = w ? c + (want[p] - c) * (1 - Math.exp(-dt / w)) : want[p];
  }
}
function apply(){ for(const p in cur) core.setParameterValueById(p, cur[p]); }

// ---------- 画：纸面时画到桌面上，极客模式只在 sample() 时画 ----------
let size = [0, 0];
function frame(fr, W, H){
  const oh = im.originalHeight, ow = im.originalWidth, s = H / ((fr.bot - fr.top) * oh);
  model.scale.set(s); model.x = W / 2 - ow * s / 2; model.y = -fr.top * oh * s;
}
function resize(){
  const r = host.getBoundingClientRect(), w = Math.round(r.width), h = Math.round(r.height);
  if(!w || !h || (w === size[0] && h === size[1])) return;
  size = [w, h]; app.renderer.resize(w, h);
}
function tick(now){
  raf = requestAnimationFrame(tick);
  if(document.hidden) return;
  const dt = Math.min(.1, last ? (now - last) / 1000 : 0); last = now; t += dt;
  step(dt);
  if(!paperOn || !host) return;
  resize(); frame(AV.frame, size[0], size[1]);
  model.update(dt * 1000);
  app.renderer.render(app.stage);
}

// ---------- 对外 ----------
// 放进一个元素里（画布跟着元素大小走）；眼睛跟着整页的鼠标
api.mount = el => {
  host = el; el.appendChild(app.view);
  app.view.setAttribute("aria-hidden", "true");
  if(AV.credit) app.view.title = AV.credit;
  addEventListener("pointermove", e => {
    // 以她的脸为中心（大约在画布上方三成），离得越远转得越多
    const r = host.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height * .3, R = Math.max(innerWidth, innerHeight) * .45;
    mouse.x = clamp((e.clientX - cx) / R, -1, 1); mouse.y = clamp(-(e.clientY - cy) / R, -1, 1); mouse.at = t;
  }, {passive:true});
  if(!raf) raf = requestAnimationFrame(tick);
};
// 极客模式：把她按 fr 的取景（默认 frame_geek）画进 w×h 的小贴图，读回 RGBA（行从上往下）
// 模型的时间（物理、自带的待机动画）要在这里往前走：转头、身体晃、前倾、手势、头发都是物理带的，时间不走就全停着
let sampledAt = 0;
api.sample = (w, h, fr) => {
  if(!api.ok) return null;
  if(!rt || rt.width !== w || rt.height !== h){ rt?.destroy(true); rt = PIXI.RenderTexture.create({width:w, height:h, resolution:1}); }
  frame(fr || AV.frame_geek || AV.frame, w, h);
  const now = performance.now();
  model.update(paperOn || !sampledAt ? 0 : Math.min(100, now - sampledAt));  // 纸面开着时 tick 已经走过了；隔很久才取一次（切回来）最多补 0.1 秒
  sampledAt = now;
  app.renderer.render(model, {renderTexture:rt, clear:true});
  const px = app.renderer.extract.pixels(rt);
  app.renderer.renderTexture.bind(null);
  return px;
};
api.paper = v => { paperOn = !!v; };      // 纸面关掉（极客模式）时不画大画布，省显卡
api.acts = () => Object.keys(ACTS);
api.has = c => !!ACTS[c];
// 换动作（名字见上面 ACTS）
api.act = c => { const A = ACTS[c]; if(!A) return false; if(c !== actName && A.jolt) jolt = 1; act = A; actName = c; return true; };
// 临时加几个表情记号，ms 毫秒后撤掉：express({blush:1}, 3000)
api.express = (marks, ms=3000) => { extra = marks || {}; extraUntil = t + ms / 1000; };
api.marks = () => [...HAS];
// 说话：talk(字数) 按字数动一阵嘴；lip(0～1) 外面按声音音量直接给张嘴程度，lip(-1) 交还给 talk
api.talk = n => { talkUntil = t + Math.min(6, .35 + n * .06); talkSeed = Math.random() * 9; };
api.lip = v => { lip = v == null || v < 0 ? -1 : clamp(v, 0, 1); };
// 接一个 <audio>/<video>：播放时按音量对口型（以后直播、语音用），返回一个停掉的函数
api.listen = media => {
  const AC = window.AudioContext || window.webkitAudioContext; if(!AC) return () => {};
  const ac = new AC(), src = ac.createMediaElementSource(media), an = ac.createAnalyser(), buf = new Uint8Array(an.fftSize = 512);
  src.connect(an); an.connect(ac.destination);
  let on = true;
  (function loop(){ if(!on) return; an.getByteTimeDomainData(buf); let s = 0; for(const v of buf) s += (v - 128) ** 2;
    const rms = Math.sqrt(s / buf.length) / 128; api.lip(media.paused ? -1 : clamp((rms - .02) * 6, 0, 1)); requestAnimationFrame(loop); })();
  return () => { on = false; api.lip(-1); ac.close(); };
};
// 让她看某个方向（-1～1，x 往右、y 往上）；look(null) 交还给鼠标
api.look = (x, y) => { gazeAt = x == null ? null : [clamp(x, -1, 1), clamp(y || 0, -1, 1)]; };
api.load = v => { loading = !!v; };
api.bounce = () => { if(!REDUCED) jolt = Math.max(jolt, .6); };
// 戳在哪：head 头顶、face 脸、ear 耳朵、body 身上（按纸面的取景）
api.zone = (x, y) => {
  if(!host) return "body";
  const Z = AV.zones || {}, F = AV.frame, r = host.getBoundingClientRect();
  const fy = F.top + (y - r.top) / r.height * (F.bot - F.top), dx = (x - r.left - r.width / 2) / r.height;
  if(Z.head && fy < Z.head) return "head";
  if(Z.face && fy < Z.face) return Z.ear_dx && Math.abs(dx) > Z.ear_dx ? "ear" : "face";
  return "body";
};
window.L2D = api;
})();
