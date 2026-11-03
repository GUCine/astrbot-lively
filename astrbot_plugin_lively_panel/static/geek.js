// 极客模式：整页换成黑底代码风，正中间是代码流拼成的大肥鱼（成年形态的她，只到上半身，两边可以被纸盖住）
// 打开时代码从按钮里溢出来盖满整页，换好皮再退开，四周的代码汇到中间拼成她；换脑区时一道斜光扫过、她一行行重新编译一遍（像女神异闻录的菜单）
// 开没开、蓝还是绿只记在这个浏览器里（读不到就当没开）
// 她的样子：Live2D（l2d.js）每帧把她画成一小块贴图、读回来，按格子拼字——转头、身体晃、前倾、手势、眨眼、说话、表情都跟着动，亮的地方（脸、白围裙）字亮，五官的边更亮
// Live2D 还在载（第一次要下十几 MB）时中间用字拼“载入中”，载好了字飞过去拼成她；没放模型或载不出来就只有代码雨
// 要在 mind.js 前面载入：mind.js 一开始就会切到第一个脑区（发 lively:region 事件）
(() => {
"use strict";
const $ = s => document.querySelector(s);
const root = document.documentElement;
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const PAL = {blue:{a:"#4d6bfe", hi:"#e3e9ff"}, green:{a:"#00ff41", hi:"#eaffef"}};
const BG = "#020409";
const store = {
  get(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } },
  set(k, v){ try{ localStorage.setItem(k, v); }catch(e){} },
};
const rnd = n => Math.floor(Math.random() * n);
const clamp = v => v < 0 ? 0 : v > 1 ? 1 : v;
const outQuart = k => 1 - (1 - k) ** 4, inQuart = k => k ** 4;
const inOutExpo = k => k <= 0 ? 0 : k >= 1 ? 1 : k < .5 ? 2 ** (20 * k - 10) / 2 : (2 - 2 ** (-20 * k + 10)) / 2;

// 代码雨用的字：一段她自己的代码里的字，加一点半角片假名
const CHARS = [...new Set(("const R=REGIONS.find(r=>r.id===id);if(!same){Water.tint(R.id);Pet.bloop()}await get('/api/heart');"
  + "return{ok:true,data:rows.map(p=>[p.qq,p.score|0])};0x4D6BFE;#!/usr/bin/env;$%&*+-<>[]{}?@^_~|0123456789"
  + "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ").replace(/[\s'".,:;|!^~`_-]/g, ""))];  // 细的字拼不出实心的样子
const NC = CHARS.length;
const CW = 8, CH = 10, FS = 10.5;  // 她身上一格多大（CSS 像素）
const BREATH = 4800;  // 一次呼吸多久（毫秒）

let on = root.classList.contains("geek"), color = store.get("lively.geek.c") === "green" ? "green" : "blue";
let target = null;  // 正在变成哪个：wait 载入中、live 她
root.dataset.gc = color;

// ---------- 右上角的开关 ----------
const hud = $(".hud");
hud.insertAdjacentHTML("afterbegin",
  `<button class="pill geek-btn" id="geekBtn" type="button" aria-pressed="${on}" title="极客模式（按 G）"><code>&lt;/&gt;</code><span>极客</span></button>`
  + `<button class="pill geek-pal" id="geekPal" type="button" title="换颜色：蓝 / 绿" aria-label="换颜色"><i></i></button>`);
const btn = $("#geekBtn"), pal = $("#geekPal");

// ---------- 画她的画布：在水光上面、纸下面 ----------
const cv = document.createElement("canvas");
cv.id = "geek"; cv.setAttribute("aria-hidden", "true");
document.body.insertBefore(cv, $("body > header"));
const ctx = cv.getContext("2d");
const scan = document.createElement("div");
scan.className = "geek-scan"; scan.setAttribute("aria-hidden", "true");
document.body.appendChild(scan);

// 左上角的标志：深色圆角小屏，代码雨只下在探头的她身上（icon-geek.png 是纸面版图标的剪影）
const mk = document.createElement("canvas");
const mkSil = new Image(); mkSil.src = "/static/icon-geek.png?v=1102";
mk.className = "geek-mark"; mk.setAttribute("aria-hidden", "true");
$(".brand-mark")?.appendChild(mk);
const MK = {S:48, C:3};  // 多大、一格几像素
let mkAtl = null, mkChars = null, mkDrops = [];
function markLayout(){
  const n = MK.S / MK.C;
  mk.width = mk.height = Math.round(MK.S * dpr);
  mkAtl = atlas([Math.round(MK.C * dpr), Math.round(MK.C * dpr)], 5 * dpr);
  mkChars = new Uint8Array(n * n).map(() => rnd(NC));
  mkDrops = Array.from({length:n}, () => ({y:Math.random() * n * 2 - n, v:5 + Math.random() * 9, len:3 + rnd(6)}));
}
function markDraw(dt){
  if(!mkAtl) return;
  const x = mk.getContext("2d"), n = MK.S / MK.C, s = Math.round(MK.C * dpr);
  x.globalAlpha = 1; x.clearRect(0, 0, mk.width, mk.height);
  x.globalAlpha = .5; x.fillStyle = PAL[color].a; x.fillRect(0, 0, mk.width, mk.height);
  for(let c = 0; c < n; c++){
    const d = mkDrops[c]; d.y += d.v * dt; if(d.y - d.len > n){ d.y = -rnd(n); d.v = 5 + Math.random() * 9; }
    for(let r = 0; r < n; r++){
      const i = r * n + c, k = d.y - r, on = k >= 0 && k < d.len;
      if(on && k < 1 && Math.random() < .5) mkChars[i] = rnd(NC);
      x.globalAlpha = on ? Math.min(1, .5 + (1 - k / d.len) * .6) : .55;
      x.drawImage(mkAtl, mkChars[i] * s, on ? s : 0, s, s, c * s, r * s, s, s);
    }
  }
  if(!mkSil.complete || !mkSil.naturalWidth) return;
  x.globalAlpha = 1; x.globalCompositeOperation = "destination-in";
  x.drawImage(mkSil, 0, 0, mk.width, mk.height);
  x.globalCompositeOperation = "source-over";
}
// 网页标签的小图标跟着换：极客模式用深色小屏那张，分蓝绿
function syncIcon(){
  const l = document.querySelector('link[rel="icon"]');
  if(l) l.href = on ? `/static/favicon-geek-${color}.png?v=1102` : "/static/favicon.png?v=1102";
}

// 水光：极客模式时不画（被盖住了还画白费显卡）；卡册那边的暂停照旧算数
let waterWant = false;
if(window.Water){
  const pause = Water.pause.bind(Water);
  Water.pause = v => { waterWant = !!v; pause(waterWant || on); };
}
const syncWater = () => window.Water && Water.pause(waterWant);

let W = 0, H = 0, dpr = 1, gw = 0, gh = 0, box = null, cols = 0, rows = 0, ATL = null;
let grids = {}, glows = {}, chars = null, loose = null, drops = [];
function atlas(size, font){
  const c = document.createElement("canvas"), P = PAL[color];
  c.width = NC * size[0]; c.height = size[1] * 2;
  const x = c.getContext("2d"), mono = `px ui-monospace,"SF Mono",Menlo,Consolas,monospace`;
  x.font = font + mono; x.textAlign = "center"; x.textBaseline = "middle";
  [P.a, P.hi].forEach((col, k) => { x.fillStyle = col; CHARS.forEach((ch, i) => x.fillText(ch, i * size[0] + size[0] / 2, k * size[1] + size[1] / 2)); });
  return c;
}
// “载入中”三个字：一格一个像素画出来（格子比字高，竖着压扁一点，屏幕上才是方的），透明度当覆盖率
function waitGrid(){
  const c = document.createElement("canvas"); c.width = cols; c.height = rows;
  const x = c.getContext("2d", {willReadFrequently:true}), fs = Math.min(cols / 3.4, rows / 4);
  x.setTransform(1, 0, 0, CW / CH, 0, 0);
  x.fillStyle = "#fff"; x.textAlign = "center"; x.textBaseline = "middle";
  x.font = `900 ${fs}px "PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif`;
  x.fillText("载入中", cols / 2, rows * .34 * CH / CW);
  const px = x.getImageData(0, 0, cols, rows).data, val = new Float32Array(cols * rows);
  for(let i = 0; i < val.length; i++) val[i] = px[i * 4 + 3] / 255;
  return cells(val);
}
// 覆盖率（和 Live2D 时的亮度）→ 哪格有字、哪格是轮廓、往外是哪个方向、身后那团光；into 给了就重复用里面的数组和画布（Live2D 每帧都算）
function cells(val, lum, into){
  const n = cols * rows, G = into || {};
  const st = G.st && G.st.length === n ? G.st.fill(0) : new Uint8Array(n);
  for(let i = 0; i < n; i++) st[i] = val[i] > .42 ? 1 : 0;
  // 手臂和身体之间那几道黑缝缩小以后常常只占半格，按覆盖率看不出来：比上下左右最亮的那格暗一截的也当缝，不画字，动作才看得清
  for(let r = 0; r < rows; r++) for(let c2 = 0; c2 < cols; c2++){
    const i = r * cols + c2; if(!st[i] || val[i] >= .86) continue;
    const nb = Math.max(c2 ? val[i - 1] : 0, c2 < cols - 1 ? val[i + 1] : 0, r ? val[i - cols] : 0, r < rows - 1 ? val[i + cols] : 0);
    if(nb - val[i] > .1) st[i] = 0;
  }
  const list = [], out = G.out && G.out.length === n * 2 ? G.out : new Float32Array(n * 2);
  for(let r = 0; r < rows; r++) for(let c2 = 0; c2 < cols; c2++){
    const i = r * cols + c2; if(!st[i]) continue;
    const L = !c2 || !st[i - 1], R = c2 === cols - 1 || !st[i + 1], U = !r || !st[i - cols], D = r < rows - 1 && !st[i + cols];
    if(L || R || U || D){
      st[i] = 2;  // 轮廓亮一点
      // 往外是哪个方向：边上飘出去的字顺着它走
      let dx = R - L, dy = D - U; const m = Math.hypot(dx, dy);
      if(m){ dx /= m; dy /= m; } else { const a = Math.random() * 6.283; dx = Math.cos(a); dy = Math.sin(a); }
      out[i * 2] = dx; out[i * 2 + 1] = dy;
    }
    list.push(i);
  }
  // 身后那团光：覆盖率当透明度涂上主色，缩得很小再放大，自然就糊了（遮罩图本身不透明，不能拿它的透明度）
  const full = G.full || document.createElement("canvas"); full.width = cols; full.height = rows;
  const fx = full.getContext("2d"), id = fx.createImageData(cols, rows), rgb = PAL[color].a.match(/\w\w/g).map(h => parseInt(h, 16));
  for(let i = 0; i < n; i++){ id.data.set(rgb, i * 4); id.data[i * 4 + 3] = val[i] * 255; }
  fx.putImageData(id, 0, 0);
  const gc = G.glow || document.createElement("canvas"); gc.width = Math.ceil(cols / 4); gc.height = Math.ceil(rows / 4);
  gc.getContext("2d").drawImage(full, 0, 0, gc.width, gc.height);
  // Live2D 时：亮度、五官的边（比上下左右的平均亮或暗一截）
  let feat = G.feat;
  if(lum){
    feat = feat && feat.length === n ? feat : new Float32Array(n);
    for(let r = 0; r < rows; r++) for(let c2 = 0; c2 < cols; c2++){
      const i = r * cols + c2; if(!st[i]){ feat[i] = 0; continue; }
      const nb = ((c2 ? lum[i - 1] : lum[i]) + (c2 < cols - 1 ? lum[i + 1] : lum[i]) + (r ? lum[i - cols] : lum[i]) + (r < rows - 1 ? lum[i + cols] : lum[i])) / 4;
      feat[i] = clamp(Math.abs(lum[i] - nb) * 4);
    }
  }
  return Object.assign(G, {val, st, list, out, glow:gc, full, lum, feat});
}
// ---------- Live2D：每帧把她画进 cols×rows 格（每格 4×5 个像素，和字的宽高比一样），读回来算覆盖率和亮度 ----------
const SX = 4, SY = 5, live = () => !!(window.L2D && L2D.ok);
let liveVal = null, liveLum = null;
function liveGrid(){
  // 「只看她」放大缩小时，拼字用的取景也跟着变（mind.js 的 Solo 算）
  const fr = window.Solo?.on ? Solo.frameFor(L2D.avatar.frame_geek || L2D.avatar.frame) : undefined;
  const w = cols * SX, h = rows * SY, px = L2D.sample(w, h, fr);
  if(!px) return null;
  const n = cols * rows;
  if(!liveVal || liveVal.length !== n){ liveVal = new Float32Array(n); liveLum = new Float32Array(n); }
  liveVal.fill(0); liveLum.fill(0);
  for(let y = 0; y < h; y++){
    const r = (y / SY) | 0, row = y * w * 4;
    for(let x = 0; x < w; x++){
      const o = row + x * 4, a = px[o + 3]; if(!a) continue;
      const i = r * cols + ((x / SX) | 0);
      liveVal[i] += a; liveLum[i] += px[o] * .3 + px[o + 1] * .55 + px[o + 2] * .15;  // 预乘过透明度的，下面除回去
    }
  }
  for(let i = 0; i < n; i++){ const a = liveVal[i]; liveLum[i] = a ? Math.min(1, liveLum[i] / a) : 0; liveVal[i] = a / (255 * SX * SY); }
  return cells(liveVal, liveLum, grids.live);
}
function layout(){
  dpr = Math.min(2, devicePixelRatio || 1); W = innerWidth; H = innerHeight;
  cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  gw = Math.round(CW * dpr); gh = Math.round(CH * dpr);
  ATL = atlas([gw, gh], FS * dpr);
  const top = W <= 1100 ? 64 : 88;
  let h = (H - top) * 1.1, w = h * 2 / 3;  // 她只画到胸口，比屏幕高一点；两边的头发被功能框盖住一点，手势露在中间
  if(w > W * .96){ w = W * .96; h = w * 1.5; }
  cols = Math.floor(w / CW); rows = Math.floor(h / CH);
  box = {x:Math.round((W - cols * CW) / 2), y:top};
  chars = new Uint8Array(cols * rows).map(() => rnd(NC));
  // 每个字离开格子歪一点（少数歪得远），自己慢慢晃；亮度各不一样；有的叠着第二个字
  loose = new Float32Array(cols * rows * 5);
  for(let i = 0; i < cols * rows; i++){
    const far = Math.random() < .06, r = far ? .9 + Math.random() * 1.5 : Math.random() * .45, a = Math.random() * 6.283;
    loose.set([Math.cos(a) * r, Math.sin(a) * r * .8, Math.random() * 6.283, .6 + Math.random() * .7, Math.random() < .09 ? 1 + rnd(NC - 1) : 0], i * 5);
  }
  drops = Array.from({length:cols}, () => [drop(true), drop(true)]);
  grids = {wait:waitGrid()};
  anim = null;
  markLayout();
  if(typeof vfSync === "function") vfSync();
}
function drop(scatter){ return {y:scatter ? Math.random() * rows * 1.4 - rows * .4 : -Math.random() * rows * .5, v:7 + Math.random() * 16, len:5 + rnd(16)}; }
const cx = i => (box.x + (i % cols) * CW) * dpr, cy = i => (box.y + Math.floor(i / cols) * CH) * dpr;
// 歪过以后的“家”；Live2D 时歪得少，五官才拼得出来
let LZ = 1;
const hx = i => cx(i) + loose[i * 5] * gw * LZ, hy = i => cy(i) + loose[i * 5 + 1] * gh * LZ;
// 再加一点从右上打来的光（ASCII Logo 的打光）：靠右上的格子亮一点，有立体感
const lit = i => .18 * ((i % cols) / cols - Math.floor(i / cols) / rows);
const base = (g, i) => g.lum ? (g.st[i] === 2 ? .45 : .03 + .95 * g.lum[i] ** 1.6 + .55 * g.feat[i] + lit(i))  // Live2D：照她身上的明暗（头发暗、脸和围裙亮），五官的边亮
  : g.st[i] === 2 ? .62 : .26 + .22 * g.val[i];  // “载入中”：轮廓稍亮一点，字形才看得出来
// 一个格子在某一段时间里的随机数：字时有时无、偶尔亮一下都靠它，不用每帧存状态
const hash = n => { n = Math.imul(n ^ (n >>> 16), 0x45d9f3b); n = Math.imul(n ^ (n >>> 16), 0x45d9f3b); return ((n ^ (n >>> 16)) >>> 0) / 4294967296; };

// ---------- 动画：拼起来（四周汇到中间）、换动作（变形＋一道斜光） ----------
let running = false, raf = 0, last = 0, shown = null, anim = null, slash = 0, sweep = 0, glitchUntil = 0, calmAt = 0;
const SWEEP = 900;  // 换脑区时从脚到头扫一遍要多久（毫秒）
let rowDy = new Float32Array(0), colDx = new Float32Array(0), breath = 0, calm = 0;
function parts(now){
  // 现在画面上每个字在哪：动画中途换脑区，就从半路接着变
  if(anim){
    const out = [];
    for(let j = 0; j < anim.n; j++){
      const o = j * 7, k = anim.ease(clamp((now - anim.t0 - anim.p[o + 4]) / anim.p[o + 5]));
      out.push([anim.p[o] + (anim.p[o + 2] - anim.p[o]) * k, anim.p[o + 1] + (anim.p[o + 3] - anim.p[o + 1]) * k, anim.p[o + 6]]);
    }
    return out;
  }
  const g = grids[shown];
  return g ? g.list.map(i => { const q = at(i, now); return [q[0], q[1], chars[i]]; }) : [];
}
// 停着时一个字画在哪：歪过的家＋慢慢晃（刚落定时从 0 加上去）＋呼吸
const q2 = [0, 0];
function at(i, now){
  const o = i * 5, w = calm * (.22 + .1 * loose[o + 3]) * (LZ < 1 ? .5 : 1), ph = loose[o + 2];
  q2[0] = hx(i) + colDx[i % cols] + Math.sin(now * .00055 * loose[o + 3] + ph) * w * gw;
  q2[1] = hy(i) + rowDy[Math.floor(i / cols)] + Math.cos(now * .0004 * loose[o + 3] + ph * 1.3) * w * gh;
  return q2;
}
function animate(kind, next, now){
  // kind：in 拼起来（四周汇过来）、morph 换脑区（带一道斜光）
  const g = grids[next]; if(!g) return;
  target = next;
  const src = kind === "in" ? null : parts(now), list = g.list, n = list.length, p = new Float32Array(n * 7);
  for(let j = 0; j < n; j++){
    const o = j * 7, i = list[j];
    let fx, fy, ch = chars[i];
    if(src){ const s = src[Math.floor(j * src.length / n)] || [hx(i), hy(i), ch]; fx = s[0]; fy = s[1]; ch = s[2]; }
    else {  // 从屏幕四边飞进来
      const side = rnd(4), m = 30 * dpr;
      fx = side < 2 ? Math.random() * cv.width : side === 2 ? -m : cv.width + m;
      fy = side >= 2 ? Math.random() * cv.height : side === 0 ? -m : cv.height + m;
    }
    const r = Math.floor(i / cols) / rows;
    p.set([fx, fy, hx(i), hy(i), kind === "in" ? Math.random() * 650 + r * 250 : r * 170 + Math.random() * 80,
      kind === "in" ? 800 + Math.random() * 650 : 380 + Math.random() * 140, ch], o);
  }
  anim = {kind, next, p, n, t0:now, ease:kind === "in" ? outQuart : inOutExpo, end:Math.max(...Array.from({length:n}, (_, j) => p[j * 7 + 4] + p[j * 7 + 5]))};
  if(kind === "morph") slash = now;
}
function frame(now){
  if(!running){ raf = 0; return; }
  raf = requestAnimationFrame(frame);
  if(now - last < 1000 / 48) return;  // 代码雨 48 帧就够，省电
  const dt = Math.min(.1, (now - last) / 1000); last = now;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  ctx.clearRect(0, 0, cv.width, cv.height);
  if(!box) return;
  waves(now);
  markDraw(dt);
  breathe(now);
  LZ = shown === "live" ? .22 : 1;
  if(shown === "live" && live()) grids.live = liveGrid() || grids.live;
  if(anim) drawAnim(now); else if(grids[shown]) figure(grids[shown], dt, now, 1);
  if(slash) drawSlash(now);
  if(window.ORACLE_ON) oracleCorrupt(now);   // 神谕：整副剪影混着红色错误代码
  if(sweep && now - sweep > SWEEP) sweep = 0;
}
// 呼吸：越往上的行抬得越多（像从腰往上吸一口气），胸口那几列往两边撑一点；都挪整像素，字不会糊
// 刚变完动作时从 0 慢慢加上去，免得一落定就跳一下
function breathe(now){
  if(rowDy.length !== rows){ rowDy = new Float32Array(rows); colDx = new Float32Array(cols); }
  const k = (now % BREATH) / BREATH, amp = REDUCED || anim ? 0 : clamp((now - calmAt) / 900);  // Live2D 时她自己会呼吸，这里只用来让字慢慢开始晃
  calm = amp;
  breath = shown === "live" ? 0 : (1 - Math.cos(k * Math.PI * 2)) / 2 * amp;
  const up = rows * gh * .014 * breath, out = cols * gw * .006 * breath;
  for(let r = 0; r < rows; r++) rowDy[r] = -Math.round(up * (1 - r / rows));
  for(let c = 0; c < cols; c++) colDx[c] = Math.round(out * ((c + .5) / cols - .5) * 2);
}
// 背景（Wavefield）：几条发光的波纹线横过去，游标附近往游标那边弯；先画一道宽的淡光，再画一道细的亮线
let mx = 0, my = 0;
addEventListener("pointermove", e => { mx = e.clientX / innerWidth - .5; my = e.clientY / innerHeight - .5; }, {passive:true});
const WAVES = 5, WAVE_TINT = {blue:"#9e73ff", green:"#3fd7c4"};
function waves(now){
  const t = REDUCED ? 8 : now / 1000, P = PAL[color], step = 14 * dpr, cw = cv.width, ch = cv.height, u = ch;
  ctx.save(); ctx.globalCompositeOperation = "lighter"; ctx.lineCap = "round";
  for(let f = 0; f < WAVES; f++){
    ctx.beginPath();
    for(let X = -step; X <= cw + step; X += step){
      const px = (X - cw / 2) / u;
      let y = -.32 + f * .16 + .09 * Math.sin(px * (1.6 + f * .35) + t * .45 + f * 1.9) + .05 * Math.sin(px * 3.1 - t * .3 + f);
      y += .12 * Math.exp(-(((px - mx * 1.6) * 2.2) ** 2)) * my * (1 - f * .12);
      const Y = ch / 2 + y * u;
      X < 0 ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y);
    }
    const col = f < 2 ? P.a : f < 4 ? WAVE_TINT[color] : P.hi;
    ctx.strokeStyle = col;
    ctx.globalAlpha = .07; ctx.lineWidth = 9 * dpr; ctx.stroke();
    ctx.globalAlpha = .45; ctx.lineWidth = 1.1 * dpr; ctx.stroke();
  }
  ctx.restore();
}
// 她：一格一个字，但都不在格子上：歪着、慢慢晃、时有时无、深浅不一，边上偶尔有字飘出去；代码雨从上往下流过
function figure(g, dt, now, fade){
  const ox = box.x * dpr, oy = box.y * dpr, glitch = now < glitchUntil;
  ctx.globalAlpha = (.14 + .08 * breath) * fade;  // 光淡一点，不然把缝填满了
  ctx.drawImage(g.glow, ox + colDx[0], oy + rowDy[0], cols * gw + colDx[cols - 1] * 2, rows * gh - rowDy[0]);
  const live = REDUCED ? 0 : calm;  // 刚落定时字全在，慢慢才开始缺
  // 换脑区（Venus & David 的等高线）：从下往上扫，没扫到的那几行先是一层层发光的等高线，扫过的才变回字
  const band = sweep ? rows + 6 - (now - sweep) / SWEEP * (rows + 12) : -1e9;
  if(band > -1e8) contours(g, now, band, fade);
  for(let c = 0; c < cols; c++){
    const D = drops[c];
    for(const d of D){ d.y += d.v * dt; if(d.y - d.len > rows) Object.assign(d, drop(false)); }
    for(let r = 0; r < rows; r++){
      const i = r * cols + c, s = g.st[i]; if(!s) continue;
      if(oy + r * gh > cv.height) break;
      const o = i * 5, ph = loose[o + 2], lu = loose[o + 3];
      // 每个字自己的节奏：一段时间一换，换的时候决定这段时间在不在、亮不亮、要不要飘出去
      const per = 700 + lu * 900, slot = Math.floor((REDUCED ? 0 : now + ph * 400) / per), hs = hash(i * 7919 + slot);
      let b = base(g, i) * lu * (.86 + .12 * Math.sin(now * .002 + ph) + .08 * breath), head = false;
      for(const d of D){ const k = d.y - r; if(k >= 0 && k < d.len){ b += (1 - k / d.len) * .45; if(k < 1) head = true; } }
      if(!head && hs > 1 - live * (s === 2 ? .12 : g.lum ? .45 * (1 - g.lum[i]) : .3)) continue;  // 里面缺得多，边上少缺一点；Live2D 时暗的地方（头发）缺、亮的地方（脸）不缺
      if(head ? Math.random() < .5 : Math.random() < .003) chars[i] = rnd(NC);
      const q = at(i, now); let x = q[0], y = q[1];
      if(s === 2 && live && hs < .07){  // 这段时间这个字飘出去：顺着往外的方向走，越走越淡
        const k = (now + ph * 400) % per / per, far = (1.5 + hs * 40) * k;
        x += g.out[i * 2] * far * gw; y += g.out[i * 2 + 1] * far * gh; b *= 1 - k * .8;
      }
      if(hs > .3 && hs < .37 && live){  // 零星几个突然亮一下，还跑开一点，像飞在半路（这段随机数在缺字那段之外）
        const a = hs * 900; b = .95; x += Math.cos(a) * (hs - .29) * 18 * gw * live; y += Math.sin(a) * (hs - .29) * 12 * gh * live;
      }
      if(glitch){ b += .25; if(r % 7 === (now >> 5) % 7) x += (rnd(7) - 3) * gw; }
      if(r < band - 1) continue;  // 还没扫到：这一行是等高线
      const dz = Math.abs(r - band);
      if(dz < 5){  // 刚扫过的那几行：字乱换、亮一下、往旁边错开一点，再照新的样子落定
        const k = 1 - dz / 5; b += .7 * k; if(Math.random() < .5 * k) chars[i] = rnd(NC);
        x += (hs - .5) * 2.4 * k * gw;
      }
      ctx.globalAlpha = Math.min(1, b) * fade;
      ctx.drawImage(ATL, chars[i] * gw, head || (g.lum && g.lum[i] > .78) ? gh : 0, gw, gh, x, y, gw, gh);  // 最亮的地方用高光色
      if(loose[o + 4]){  // 叠着的第二个字
        ctx.globalAlpha = Math.min(1, b) * .55 * fade;
        ctx.drawImage(ATL, (chars[i] + loose[o + 4]) % NC * gw, 0, gw, gh, x + (loose[o] > 0 ? -.45 : .45) * gw, y + .3 * gh, gw, gh);
      }
    }
  }
}
function contours(g, now, band, fade){
  const P = PAL[color], top = Math.min(rows, Math.ceil(band)), k = clamp(1 - band / rows), y0 = box.y * dpr, x0 = box.x * dpr;
  ctx.save(); ctx.lineWidth = 1.2 * dpr; ctx.strokeStyle = P.a; ctx.shadowColor = P.a; ctx.shadowBlur = 6 * dpr;
  for(let r = 0; r < top; r += 2){
    ctx.globalAlpha = (.35 + .55 * r / rows) * fade; ctx.beginPath();
    let on = false;
    for(let c = 0; c <= cols; c++){
      const a = c < cols && g.st[r * cols + c], X = x0 + c * gw, Y = y0 + r * gh + gh / 2 + rowDy[r] + Math.sin(c * .3 + k * 9) * 1.5 * dpr * (1 - k);
      if(a && !on){ ctx.moveTo(X, Y); on = true; } else if(a) ctx.lineTo(X, Y); else if(on){ ctx.lineTo(X, Y); on = false; }
    }
    ctx.stroke();
  }
  ctx.shadowBlur = 0; ctx.globalAlpha = .9 * fade; ctx.fillStyle = P.hi;
  if(band > 0 && band < rows) ctx.fillRect(x0 - 20 * dpr, y0 + band * gh, cols * gw + 40 * dpr, 1.5 * dpr);  // 扫到哪一行的那道白线
  ctx.restore();
}
function drawAnim(now){
  const a = anim, t = now - a.t0, g = grids[a.next];
  if(a.kind !== "in"){  // 两团光交叉淡换
    const k = clamp(t / 450), old = grids[shown];
    ctx.globalAlpha = .14 * (1 - k); if(old) ctx.drawImage(old.glow, box.x * dpr, box.y * dpr, cols * gw, rows * gh);
    ctx.globalAlpha = .14 * k; ctx.drawImage(g.glow, box.x * dpr, box.y * dpr, cols * gw, rows * gh);
  }
  for(let j = 0; j < a.n; j++){
    const o = j * 7, k = a.ease(clamp((t - a.p[o + 4]) / a.p[o + 5]));
    const x = a.p[o] + (a.p[o + 2] - a.p[o]) * k, y = a.p[o + 1] + (a.p[o + 3] - a.p[o + 1]) * k;
    const fly = k > 0 && k < 1;
    ctx.globalAlpha = fly ? .95 : k ? .3 : a.kind === "in" ? .1 : .5;
    ctx.drawImage(ATL, a.p[o + 6] * gw, 0, gw, gh, x, y, gw, gh);
  }
  if(t > a.end + 30){
    for(let j = 0; j < a.n; j++) chars[g.list[j]] = a.p[j * 7 + 6];
    shown = a.next; anim = null;
    if(shown !== target) animate("morph", target, now);  // 中途又换了脑区
    else calmAt = now;
  }
}
// 换动作时一道斜着扫过去的光（女神异闻录菜单那种）
function drawSlash(now){
  const k = (now - slash) / 340; if(k >= 1){ slash = 0; return; }
  const e = outQuart(k), w = cols * gw, h = rows * gh;
  ctx.save();
  ctx.translate((box.x * dpr) + w / 2, (box.y * dpr) + h * .42); ctx.rotate(-.5);
  const x = -w + e * w * 2.2, bw = 46 * dpr * (1 - k * .6);
  ctx.globalAlpha = .32 * (1 - k); ctx.fillStyle = PAL[color].a; ctx.fillRect(x - bw, -h, bw, h * 2);
  ctx.globalAlpha = .9 * (1 - k); ctx.fillStyle = PAL[color].hi; ctx.fillRect(x, -h, 3 * dpr, h * 2);
  ctx.restore();
}
// ---------- 神谕：整副剪影崩坏，红色错误代码混在里面 ----------
const ERR_TOKENS = ["0x00","SEGV","ERR","null","NaN","死","void","??","0xFF","#","&","}","{",";","1","0"];
function oracleCorrupt(now){
  if(!window.ORACLE_ON || !box) return;
  const g = grids[shown]; if(!g || !g.list || !g.list.length) return;
  const slot = Math.floor(now / 180), n = g.list.length;
  ctx.save();
  ctx.textBaseline = "top";
  ctx.font = `${Math.round(9 * dpr)}px ui-monospace,Menlo,monospace`;
  ctx.shadowColor = "rgba(255,20,60,.95)"; ctx.shadowBlur = 7 * dpr;
  // ① 身上抽一批格子换成红色错误代码（每 180ms 换一次，看起来在抖）
  const cnt = Math.min(420, Math.max(90, (n * .05) | 0));
  for(let k = 0; k < cnt; k++){
    const h = hash(k * 977 + slot), i = g.list[(h * n) | 0];
    if(!i || !g.st[i]) continue;
    const h2 = hash(i * 31 + slot * 7);
    if(h2 > .62) continue;
    const q = at(i, now), tok = ERR_TOKENS[((h2 * ERR_TOKENS.length * 3.7) | 0) % ERR_TOKENS.length];
    ctx.globalAlpha = .35 + .6 * hash(i + slot);
    ctx.fillStyle = h2 < .18 ? "#ff2a44" : h2 < .4 ? "#c40f26" : "#8f0a1c";
    ctx.fillText(tok, q[0] + (hash(i + 3) - .5) * gw * .6, q[1] + (hash(i + 5) - .5) * gh * .4);
  }
  // ② 红色断层：横着一整段亮红，像画面撕裂
  ctx.shadowBlur = 8 * dpr;
  for(let k = 0; k < 3; k++){
    const h = hash(k * 131 + Math.floor(now / 140)), r = (h * rows) | 0;
    ctx.globalAlpha = .45 + .45 * hash(k + Math.floor(now / 90));
    ctx.fillStyle = k % 2 ? "#ff1f3a" : "#ff4a63";
    ctx.fillRect(box.x * dpr + (h * .3 + .15) * cols * gw, box.y * dpr + r * gh,
                 cols * gw * (.18 + h * .3), Math.max(1.5 * dpr, gh * .35));
  }
  // ③ 几条往下淌的红线，散在身上各处
  ctx.shadowBlur = 10 * dpr;
  for(let k = 0; k < 6; k++){
    const h = hash(k * 733 + Math.floor(now / 400)), c = (h * cols) | 0;
    const x = box.x * dpr + c * gw, y0 = box.y * dpr + h * rows * gh;
    const fall = (now * .06 + k * 97) % (rows * gh);
    for(let j = 0; j < 5; j++){
      ctx.globalAlpha = .7 - j * .13;
      ctx.fillStyle = "#ff2a44";
      ctx.fillText(ERR_TOKENS[(j + k) % ERR_TOKENS.length], x + Math.sin(now * .003 + j) * 2 * dpr, y0 + fall + j * gh);
    }
  }
  ctx.restore();
}

function start(entry){
  running = true;
  window.L2D?.paper(false);
  if(!box) layout();
  const now = performance.now();
  // Live2D 已经载好就直接拼她；还在载就先拼“载入中”，载好了字飞过去拼成她
  const go = p => {
    if(p === "live") grids.live = liveGrid();
    shown = target = grids[p] ? p : null;
    if(shown && entry && !REDUCED) animate("in", shown, now);
    else calmAt = now;
    if(!raf){ last = 0; raf = requestAnimationFrame(frame); }
  };
  if(live()) return go("live");
  go(window.L2D ? "wait" : null);
  window.L2D?.ready.then(ok => {
    if(!running || shown === "live") return;
    if(!ok){ shown = target = null; anim = null; return; }
    grids.live = liveGrid(); if(!grids.live) return;
    if(REDUCED){ shown = target = "live"; anim = null; return; }
    if(anim) target = "live";  // 正在拼“载入中”，拼完接着变
    else animate(shown ? "morph" : "in", "live", performance.now());
  });
}
function stop(){
  running = false; anim = null; ctx.clearRect(0, 0, cv.width, cv.height);
  window.L2D?.paper(true);
}

// ---------- 打开、关掉：代码从按钮溢出来盖满整页，换好皮再退开 ----------
function flood(from, mid){
  return new Promise(done => {
    const c = document.createElement("canvas"); c.className = "geek-flood"; c.setAttribute("aria-hidden", "true");
    document.body.appendChild(c);
    const d = Math.min(1.5, devicePixelRatio || 1), S = 16, s = Math.round(S * d);
    c.width = Math.round(innerWidth * d); c.height = Math.round(innerHeight * d);
    const x = c.getContext("2d"), A = atlas([s, s], 12 * d);
    const fc = Math.ceil(innerWidth / S), fr = Math.ceil(innerHeight / S), n = fc * fr;
    const tc = new Float32Array(n), tu = new Float32Array(n), ch = new Uint8Array(n);
    let cover = 0, endu = 0;
    for(let i = 0; i < n; i++){
      const dx = (i % fc + .5) * S - from[0], dy = (Math.floor(i / fc) + .5) * S - from[1];
      // 往下淌得快、往上慢：像从按钮里溢出来流下去
      tc[i] = Math.hypot(dx, dy > 0 ? dy * .55 : dy * 1.6) / 2.6 + Math.random() * 110; cover = Math.max(cover, tc[i]);
      ch[i] = rnd(NC);
    }
    cover += 60;
    for(let i = 0; i < n; i++){
      const dx = (i % fc + .5) * S - innerWidth / 2, dy = (Math.floor(i / fc) + .5) * S - innerHeight / 2;
      tu[i] = cover + 120 + (Math.hypot(innerWidth, innerHeight) / 2 - Math.hypot(dx, dy)) / 3.4 + Math.random() * 120; endu = Math.max(endu, tu[i]);
    }
    let flipped = false; const t0 = performance.now();
    (function f(now){
      const t = now - t0;
      x.clearRect(0, 0, c.width, c.height);
      for(let i = 0; i < n; i++){
        if(t < tc[i]) continue;
        const u = t - tu[i]; if(u > 140) continue;
        const X = (i % fc) * s, Y = Math.floor(i / fc) * s;
        if(u < 0){
          const k = t - tc[i];
          x.globalAlpha = 1; x.fillStyle = BG; x.fillRect(X, Y, s + 1, s + 1);
          if(k < 160 || (i * 7 + (t / 90 | 0)) % 6 === 0) x.globalAlpha = k < 160 ? 1 : .45;
          else x.globalAlpha = .16;
          if(Math.random() < .04) ch[i] = rnd(NC);
          x.drawImage(A, ch[i] * s, k < 160 ? s : 0, s, s, X, Y, s, s);
        } else {  // 退开的那一下闪一下
          x.globalAlpha = 1 - u / 140; x.drawImage(A, ch[i] * s, s, s, s, X, Y, s, s);
        }
      }
      if(!flipped && t > cover){ flipped = true; mid(); }
      if(t > endu + 160){ c.remove(); done(); return; }
      requestAnimationFrame(f);
    })(t0);
  });
}
let busy = false;
function apply(v, entry){
  const was = on; on = v;
  root.classList.toggle("geek", v); root.dataset.gc = color;
  btn.setAttribute("aria-pressed", v);
  syncWater(); syncIcon();
  if(v){ if(!was || !running) start(entry); } else stop();
  vfSync();
}
async function toggle(){
  if(busy) return; busy = true;
  const want = !on; store.set("lively.geek", want ? "1" : "0");
  if(REDUCED){ apply(want, false); busy = false; return; }
  scramble(btn.querySelector("span"), "极客");
  const r = btn.getBoundingClientRect();
  await flood([r.left + r.width / 2, r.top + r.height / 2], () => apply(want, true));
  busy = false;
}
// 按钮上的字先乱跳一下再落回来
function scramble(el, to){
  if(!el) return; let n = 0;
  const id = setInterval(() => { el.textContent = n++ < 8 ? Array.from(to, () => CHARS[rnd(NC)]).join("") : to; if(n > 8) clearInterval(id); }, 45);
}
function recolor(){
  color = color === "blue" ? "green" : "blue"; store.set("lively.geek.c", color); root.dataset.gc = color; syncIcon();
  if(box){ ATL = atlas([gw, gh], FS * dpr); grids.wait = waitGrid(); markLayout(); }
  glitchUntil = performance.now() + 300;
}
btn.addEventListener("click", toggle);
pal.addEventListener("click", recolor);
addEventListener("keydown", e => {
  if(e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable) return;
  if(e.key === "g" || e.key === "G") toggle();
});
// 换脑区：她自己换动作（mind.js 叫 L2D），这里从脚到头扫一遍等高线
addEventListener("lively:region", () => {
  if(!running || REDUCED || shown !== "live") return;
  sweep = performance.now();
});
// ---------- 取景框（random-eyes）：只在「只看她」时出现（两边有卡片时太挤）；圆弧和刻度框住她，上面是读数，左边一列动作（点了她就做），右上一个时钟 ----------
const VF_ACTS = [["breathe", "待机"], ["think", "想事"], ["busy", "忙"], ["hum", "哼歌"], ["giggle", "笑"]];
const vf = document.createElement("div"); vf.id = "vf"; vf.hidden = true;
const ticks = Array.from({length:72}, (_, i) => { const a = i / 72 * 6.283, l = i % 6 ? 1.5 : 4;
  return `<line x1="${50 + Math.cos(a) * 47}" y1="${50 + Math.sin(a) * 47}" x2="${50 + Math.cos(a) * (47 - l)}" y2="${50 + Math.sin(a) * (47 - l)}"/>`; }).join("");
vf.innerHTML = `<svg viewBox="0 0 100 100" aria-hidden="true"><g class="vf-t">${ticks}</g><circle class="vf-o" cx="50" cy="50" r="49.5"/>
    <g class="vf-r"><path d="M50 3 A47 47 0 0 1 89 26"/><path d="M50 97 A47 47 0 0 1 11 74"/></g>
    <path class="vf-b" d="M36 30h-4v4M64 30h4v4M36 52h-4v-4M64 52h4v-4"/></svg>
  <div class="vf-rd vf-l"></div><div class="vf-rd vf-rt"></div>
  <div class="vf-acts" role="group" aria-label="让她做个动作">${VF_ACTS.map(([a, n], i) => `<button type="button" data-a="${a}" aria-pressed="${!i}"><i></i>${n}</button>`).join("")}</div>`;
document.body.appendChild(vf);
// 右下角的开关：取景框收起来就只剩她；收没收记着
const vfBtn = Object.assign(document.createElement("button"), {id:"vfBtn", type:"button", hidden:true, title:"收起 / 放出取景框"});
document.body.appendChild(vfBtn);
let vfOff = store.get("lively.vf.off") === "1";
vfBtn.addEventListener("click", () => { vfOff = !vfOff; store.set("lively.vf.off", vfOff ? "1" : ""); vfSync(); });
let vfAct = "breathe";
function vfSync(){
  const can = on && root.classList.contains("solo") && W > 760;
  vfBtn.hidden = !can; vfBtn.textContent = vfOff ? "显示取景框" : "隐藏取景框"; vfBtn.setAttribute("aria-pressed", String(!vfOff));
  vf.hidden = !can || vfOff;
  if(vf.hidden || !box) return;
  const r = Math.max(140, Math.min(rows * CH * .42, W * .3, 340)), cx = W / 2, cy = box.y + rows * CH * .4;
  Object.assign(vf.style, {left:cx - r + "px", top:cy - r + "px", width:r * 2 + "px", height:r * 2 + "px"});
  vfText();
}
function vfText(){
  if(vf.hidden) return;
  const n = new Date(), hm = n.toTimeString().slice(0, 8);
  vf.querySelector(".vf-l").textContent = `LIVE2D ${window.L2D?.ok ? "ON" : "--"}\nACT ${vfAct.toUpperCase()}`;
  vf.querySelector(".vf-rt").textContent = `${hm}\n${W}×${H}`;
}
setInterval(vfText, 1000);
vf.querySelector(".vf-acts").addEventListener("click", e => {
  const b = e.target.closest("button"); if(!b || !window.L2D?.ok) return;
  vfAct = b.dataset.a; L2D.act(vfAct); vf.querySelectorAll(".vf-acts button").forEach(x => x.setAttribute("aria-pressed", x === b)); vfText();
});
addEventListener("lively:solo", vfSync);

// 戳她：字抖一下
$("#pet")?.addEventListener("click", () => { if(on) glitchUntil = performance.now() + 380; });
let rt;
addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if(box) layout(); vfSync(); }, 160); });

if(on){ syncWater(); syncIcon(); start(true); }
window.Geek = {toggle, get on(){ return on; }, get live(){ return shown === "live"; }};
})();
