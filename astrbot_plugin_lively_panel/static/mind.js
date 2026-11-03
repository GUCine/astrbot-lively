// 〈名字〉的脑内：正中间是她，底下一排脑区泡泡；选一个脑区，水换颜色、她换动作、身边飘出对应的日记纸
// 数据来自面板的接口（main.py）；会改东西的操作走 POST，必须带 X-Lively: 1 头，按钮要点两下才算
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const p2 = x => String(x).padStart(2, "0");
const fmtT = ts => { if(!ts) return "—"; const d = new Date(ts*1000), n = new Date(), hm = p2(d.getHours())+":"+p2(d.getMinutes());
  return d.toDateString() === n.toDateString() ? hm : (d.getMonth()+1)+"-"+d.getDate()+" "+hm; };
const ago = ts => { if(!ts) return "—"; const s = Date.now()/1000 - ts; if(s < 3600) return Math.max(1, Math.round(s/60))+" 分钟前";
  if(s < 86400) return Math.round(s/3600)+" 小时前"; return Math.round(s/86400)+" 天前"; };
const ME = window.LIVELY_ME || {}, OWNER = String(ME.owner || ""), BOT = String(ME.bot_qq || "");
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const ic = id => `<svg class="ic" aria-hidden="true"><use href="#${id}"/></svg>`;
const av = (qq, s=100) => `<img src="https://q1.qlogo.cn/g?b=qq&nk=${esc(qq)}&s=${s}" alt="" referrerpolicy="no-referrer" loading="lazy" onerror="this.onerror=null;this.src='/api/avatar/${esc(qq)}'">`;
const N = v => `<span class="n">${esc(v)}</span>`;
// 悬停时的小纸条（内容是 HTML）；手绘的圈、下划线、荧光笔（纸展开后才画）
const tip = html => ` data-tip="${esc(html)}"`;
const mark = (html, type="underline", c="#e7799b") => `<span data-mark="${type}" data-mc="${c}">${html}</span>`;

// 心情、感受的颜色（和后台一致）；每种感情一种颜色（信任、依赖 10-27 并进亲近，留着给旧数据）
const MOOD = {平常:"#8f9cbd",开心:"#eaa92a",害羞:"#ec7fa3",得意:"#e0a630",感动:"#2b9a6e",吃醋:"#8fbf3f",担心:"#5b7bc4",嫌弃:"#8a97b8",小生气:"#e9724f",生气:"#d8506f",
  委屈:"#6f86d6",难过:"#5b7bc4",期待:"#f2a65a",好奇:"#3fb0c9",怀念:"#b58cd6",释然:"#6cc69a",心疼:"#e58fb0",无奈:"#a3a9c0",失望:"#7f8fb8",警惕:"#d9a13a",不屑:"#9a8f7a",愧疚:"#9b7fc6"};
const mc = m => MOOD[m] || "#8a97b8";
const DIM_C = {亲近:"#ec6f9a",信任:"#2f5fd0",逗趣:"#f2a03f",牵挂:"#a77de0",欣赏:"#27a8c4",依赖:"#4cbf86",芥蒂:"#9aa6c2",反感:"#d8506f"};
const BAD = new Set(["芥蒂","反感"]);
const ATTS = ["正常","冷淡","戒备","冷处理","封闭"];

// ---------- 数据：同一个接口在一段时间内只拉一次 ----------
const cache = {};
function get(url, ttl=55000){
  const c = cache[url];
  if(c && Date.now() - c.t < ttl) return c.p;
  // 网不好或后台忙时别一直等着：20 秒没回来就算读不到（不然换脑区会一直卡在这一步）
  const p = fetch(url, {credentials:"same-origin", signal:AbortSignal.timeout?.(20000)}).then(r => r.json()).then(j => j.ok ? j.data : Promise.reject(new Error(j.error || "读不到")));
  cache[url] = {t:Date.now(), p}; p.catch(() => delete cache[url]);
  return p;
}
const soft = p => p.catch(() => null);

// ---------- 她：Live2D（l2d.js）；没放模型（开源版不带）或载不出来就不放形象，只留对话框 ----------
const Pet = (() => {
  const host = $("#pet");
  // 载好之前记着该做哪个动作，载好了直接做
  let L2 = null, clip = null, base = "breathe", back;
  window.L2D?.ready.then(ok => {
    if(!ok) return;
    L2 = L2D; L2.mount(host); L2.act(L2.has(clip) ? clip : L2.has(base) ? base : "breathe");
  });
  function play(c){ clip = c; L2?.act(L2.has(c) ? c : base); }
  return {
    play, bloop(){ L2?.bounce(); },
    set base(c){ base = c; clearTimeout(back); play(c); }, get base(){ return base; },
    // 做一个小反应，过一会儿回到这个脑区的动作
    react(c, ms=3600){ clearTimeout(back); play(c); back = setTimeout(() => play(base), ms); },
    // 思考泡泡打字时嘴跟着动、数据慢时头上转圈、戳到哪
    talk(n){ L2?.talk(n); }, load(v){ L2?.load(v); },
    zone(x, y){ return L2 ? L2.zone(x, y) : null; },
  };
})();

// ---------- 头顶的思考泡泡：一句句打出来 ----------
const Thought = (() => {
  const el = $("#thought"); let q = [], i = 0, tNext;
  const type = line => { if(window.Privacy?.on) line = Privacy.line(line); Pet.talk(line.t.length); FX.thought(el, `<span class="tt">${line.h || esc(line.t)}</span>` + (line.s ? `<small>${esc(line.s)}</small>` : "")); };
  function next(){ if(!q.length) return; const l = q[i++ % q.length]; type(l); clearTimeout(tNext); tNext = setTimeout(next, Math.max(5600, l.t.length * 190 + 2400)); }
  return {
    set(lines){ q = lines.filter(Boolean).map(l => typeof l === "string" ? {t:l} : l); i = 0; next(); },
    say(text){ clearTimeout(tNext); type({t:text}); tNext = setTimeout(next, 4800); },
    again(){ if(q.length){ i = Math.max(0, i - 1); next(); } },  // 隐私模式一开一关，当前这句按新状态重打
  };
})();

// ---------- 脑区 ----------
// 11-02 重新归类：内容页只看；要主人拍板的都进「待你裁决」（id 还是 mail），开关都进「设定」，记录合成「记录」一条时间线（id 还是 body）
const REGIONS = [
  {id:"now",    name:"此刻",     ic:"i-bowl",      render:renderNow},
  {id:"mail",   name:"待你裁决", ic:"i-bell",      render:renderMail},
  {id:"people", name:"心里的人", ic:"i-heartcard", render:renderPeople},
  {id:"memory", name:"记忆",     ic:"i-book",      render:renderMemory},
  {id:"groups", name:"群里",     ic:"i-bubbles",   render:renderGroups},
  {id:"bill",   name:"饭钱",     ic:"i-yen",       render:renderBill},
  {id:"meme",   name:"表情包",   ic:"i-smile",     render:renderMeme},
  {id:"body",   name:"记录",     ic:"i-clock",     render:renderBody},
  {id:"set",    name:"设定",     ic:"i-switch",    render:renderSet},
];
$("#dock").innerHTML = REGIONS.map((r, i) => `<button class="orb" data-r="${r.id}" title="${r.name}（按 ${i + 1}）" aria-keyshortcuts="${i + 1}"><i>${ic(r.ic)}</i><span>${r.name}</span></button>`).join("");
const dockTo = FX.dock($("#dock"), REGIONS.map(() => 0));
$$("#dock .orb").forEach(b => b.onclick = () => go(b.dataset.r));

let region = null, nav = 0;
const PEOPLE_PAGES = [];  // 心里的人底下不是某个人的子页（点进去不选中泡泡、地址栏直接打开也认）
const stageCenter = () => { const r = $("#stage").getBoundingClientRect(); return [r.left + r.width/2, r.top + r.height*.55]; };
const head = () => { const r = $("#stage").getBoundingClientRect(); return [r.left + r.width/2, r.top + r.height*.36]; };

// 后点的那一下算数：前面还没读回来的不再排队等，读回来也直接丢掉
function go(id, sub){ return enter(id, sub, ++nav).catch(e => console.error(e)); }
async function enter(id, sub, my){
  const R = REGIONS.find(r => r.id === id) || REGIONS[0], same = region === R.id;
  region = R.id;
  dispatchEvent(new CustomEvent("lively:region", {detail:R.id}));  // 极客模式里的大剪影跟着换动作
  $$("#dock .orb").forEach(b => b.setAttribute("aria-current", b.dataset.r === R.id));
  history.replaceState(null, "", "#" + R.id + (sub && !window.Privacy?.on ? "/" + sub : ""));  // 隐私模式不把 QQ 号写进地址栏
  if(!same){ Water.tint(R.id); const [x, y] = stageCenter(); Water.burst(x, y); Pet.bloop(); dockTo($(`#dock .orb[data-r="${R.id}"]`)); }
  // 数据慢（网不好、后台忙）时先让她吱一声，别像卡住了
  const slow = setTimeout(() => { if(my === nav){ Thought.say("等〈我〉翻一下……"); Pet.load(true); } }, 1200);
  const [out] = await Promise.all([R.render(sub), columnsOut()]).finally(() => { clearTimeout(slow); Pet.load(false); });
  if(my !== nav) return;
  Field.show(R.id === "people");
  if(R.id === "people") Field.pick(sub && !PEOPLE_PAGES.includes(sub) ? sub : null);
  document.documentElement.style.setProperty("--col", R.id === "people" ? "320px" : "");
  fill(out);
  setKpi(out.title || R.name, out.sub, out.kpi);
  if(out.clip) Pet.base = out.clip;
  if(out.thoughts) Thought.set(out.thoughts);
}
// 换两侧的纸：旧的缩回泡泡被她吸回去，新的从她头上冒成泡泡飘出来再展开
const cols = () => [[...$("#left").children], [...$("#right").children]];
function columnsOut(){ FX.hideTip(); return FX.cardsOut(cols(), head()); }
function fill(out){
  for(const side of ["left", "right"]){
    const col = $("#" + side); col.innerHTML = (out[side] || []).join(""); col.scrollTop = 0;
    // 每一列只在第一张纸上贴纸胶带，当作这一列的记号
    const first = col.querySelector(":scope > .card");
    if(first){ first.insertAdjacentHTML("afterbegin", `<i class="tp" aria-hidden="true"></i>`); if(side === "right") first.classList.add("b"); }
  }
  FX.cardsIn(cols(), head());
  out.after?.();
  More.check(); setTimeout(More.check, 1200);
}
// 一列纸放不下时，底下冒一个「往下还有」，点一下往下翻；翻到底就收起来
const More = (() => {
  const el = {};
  for(const side of ["left", "right"]){
    const b = document.createElement("button"); b.className = "more"; b.dataset.side = side; b.hidden = true;
    b.innerHTML = `往下还有${ic("i-down")}`;
    b.onclick = () => { const c = $("#" + side); c.scrollBy({top:c.clientHeight * .7, behavior:REDUCED ? "auto" : "smooth"}); };
    document.body.appendChild(b); el[side] = b;
    $("#" + side).addEventListener("scroll", () => check(side), {passive:true});
  }
  function check(side){ const c = $("#" + side); el[side].hidden = innerWidth <= 1100 || c.scrollHeight - c.scrollTop - c.clientHeight < 40; }
  const all = () => { check("left"); check("right"); };
  addEventListener("resize", all);
  return {check:all};
})();
// 脑区抬头：名字、一句话、几个一眼看懂的数（[标签, 数, 单位, 语气, 悬停说明]）
function setKpi(name, sub, kpi){
  $("#kpiName").textContent = name; $("#kpiSub").textContent = sub || "";
  $("#kpis").innerHTML = (kpi || []).filter(Boolean).map(([l, v, u, tone, t]) =>
    `<div class="kpi ${tone || ""}"${t ? tip(t) : ""}><small>${esc(l)}</small><b>${esc(v)}${u ? `<i>${esc(u)}</i>` : ""}</b></div>`).join("");
  FX.kpi($("#kpi"));
}

// ---------- 组件：卡片、分页、数字块、刻度条、排行条、分类条、时间线 ----------
// card(标题, 正文, {ic 图标, note 说明, meta 右上角, cls, foot 底下的按钮, raw 正文自己带外框（分页用）})
const card = (title, body, o={}) => `<section class="card ${o.cls || ""}">
  <header class="card-h"><span class="card-ic">${ic(o.ic || "i-tail")}</span><div class="card-t"><h2>${title}</h2>${o.note ? `<p>${o.note}</p>` : ""}</div>${o.meta ? `<span class="card-m">${o.meta}</span>` : ""}</header>
  ${o.raw ? body : `<div class="card-b">${body}</div>`}${o.foot ? `<footer class="card-f">${o.foot}</footer>` : ""}</section>`;
// 分页：[[名字, 内容, 角标], ...]，空的页不显示；只剩一页就不出切换条
let tabSeq = 0;
function tabs(panes){
  panes = panes.filter(p => p && p[1]);
  if(!panes.length) return "";
  if(panes.length === 1) return `<div class="card-b">${panes[0][1]}</div>`;
  const id = "t" + (++tabSeq);
  return `<div class="seg" role="tablist">${panes.map(([n, , c], i) => `<button role="tab" aria-selected="${!i}" aria-controls="${id}-${i}">${n}${c != null && c !== "" ? `<em>${esc(c)}</em>` : ""}</button>`).join("")}</div>`
    + panes.map(([, h], i) => `<div class="card-b pane" role="tabpanel" id="${id}-${i}"${i ? " hidden" : ""}>${h}</div>`).join("");
}
const stat = (label, value, desc="", tone="") => `<div class="stat ${tone}"><small>${label}</small><b>${value}</b>${desc ? `<p>${desc}</p>` : ""}</div>`;
const meter = (name, frac, num, desc, warm) => `<div class="meter"><b>${name}</b><span class="bar ${warm ? "warm" : ""}"><i style="width:${Math.max(3, Math.min(1, frac) * 100)}%"></i></span><em>${esc(num)}</em>${desc ? `<p>${esc(desc)}</p>` : ""}</div>`;
// 排行条：rows = [{lb 名字(HTML), v 数, w 0～1 条长, c 颜色, qq 点了去看这个人, attr 别的点击用的属性, img 头像, sub 小字}]
// 右边的数单独一栏、按这一列最长的那个定宽，条只画到这一栏前面；太短的条不画（看数就行）
const numW = s => Math.ceil([...String(s)].reduce((a, c) => a + (/[.,:]/.test(c) ? .5 : c === " " ? .8 : c.charCodeAt(0) > 0x2000 ? 1.6 : 1), 0) * 10);
const blist = (rows, rank=false) => `<ol class="blist" style="--nw:${Math.max(0, ...rows.map(r => numW(r.v ?? "")))}px">${rows.map((r, i) => { const tag = r.qq || r.attr ? "button" : "div", w = Math.min(1, r.w ?? 0);
  return `<li><${tag} class="row"${r.qq ? ` data-qq="${esc(r.qq)}"` : ""}${r.attr || ""} style="--c:${r.c || "var(--tip)"}"${r.tip ? tip(r.tip) : ""}><i class="bf" style="--w:${w < .05 ? 0 : w.toFixed(3)}"></i>${rank ? `<span class="rk">${i + 1}</span>` : ""}${r.img || ""}<span class="lb">${r.lb}${r.sub ? `<small>${r.sub}</small>` : ""}</span><em>${esc(r.v)}</em></${tag}></li>`; }).join("")}</ol>`;
// 分类条：parts = [[名字, 数, 颜色, 悬停说明]]
const cbar = (parts, legend=true) => { const tot = parts.reduce((a, p) => a + p[1], 0) || 1;
  return `<div class="cbar">${parts.map(([k, n, c, t]) => `<i style="--m:${c};flex:${n}"${tip(t || `<b>${esc(k)}</b> ${n}（${Math.round(n / tot * 100)}%）`)}></i>`).join("")}</div>
    ${legend ? `<div class="legend">${parts.map(([k, n, c]) => `<span style="--m:${c}">${esc(k)} <b>${n}</b></span>`).join("")}</div>` : ""}`; };
// 时间线：items = [{m 点的颜色, cls, h 抬头(HTML), t 时间, p 正文(HTML), s 小字(HTML), x 其他(HTML)}]
const tl = items => `<ol class="tl">${items.map(it => `<li class="${it.cls || ""}"${it.m ? ` style="--m:${it.m}"` : ""}${it.attr || ""}>
  <div class="tl-h">${it.h || ""}${it.t ? `<time>${it.t}</time>` : ""}</div>${it.p ? `<p>${it.p}</p>` : ""}${it.s ? `<small>${it.s}</small>` : ""}${it.x || ""}</li>`).join("")}</ol>`;
// TA 是 bot：名字后面一个小机器人（关系读口的 bot，诅咒名单、人的页面上标）
// bot 是哪家做的：有那家的标志就画标志（static/brands，公开版不带，没有就退回小机器人）
const VENDORS = {deepseek:"DeepSeek", openai:"OpenAI · ChatGPT", anthropic:"Anthropic · Claude", google:"Google · Gemini", qwen:"通义千问",
  doubao:"豆包", kimi:"Kimi", zhipu:"智谱 GLM", other:"别家"};
const botFace = r => (VENDORS[r.bot_vendor] && r.bot_vendor !== "other" ? `<img src="/static/brands/${r.bot_vendor}.png" alt="" onerror="this.remove()">` : "") + ic("i-bot");
const botTip = r => "TA 是 bot" + (VENDORS[r.bot_vendor] ? `（${VENDORS[r.bot_vendor]}${r.bot_model ? " · " + r.bot_model : ""}）` : "");
const botMark = r => `<span class="botm" title="${esc(botTip(r))}" aria-label="${esc(botTip(r))}">${botFace(r)}</span>`;
const bm = r => r && r.bot ? botMark(r) : "";
const tagM = (text, color) => `<span class="tag dot" style="--m:${color}">${esc(text)}</span>`;
const avs = (qqs, n=6) => `<span class="avs">${qqs.slice(0, n).map(q => av(q, 40)).join("")}${qqs.length > n ? `<em>+${qqs.length - n}</em>` : ""}</span>`;
// 没东西时贴一张表情包（表情包不随仓库发布，没放进来就只有字）
const memeImg = k => ME.meme === false ? "" : `<img src="/static/meme/${k}.webp" alt="" loading="lazy" onerror="this.remove()">`;
const empty = (k, text) => `<div class="empty">${memeImg(k)}<p>${text}</p></div>`;
const fail = what => empty("dead", `读不到${what}～`);
// 卡片里的分页切换
document.addEventListener("click", e => {
  const b = e.target.closest(".seg [role=tab]"); if(!b) return;
  const seg = b.parentElement, cardEl = seg.parentElement;
  seg.querySelectorAll("[role=tab]").forEach(x => x.setAttribute("aria-selected", x === b));
  cardEl.querySelectorAll(":scope > .pane").forEach(p => { const on = p.id === b.getAttribute("aria-controls"); p.hidden = !on; if(on) FX.decorate(p); });
  More.check();
});

// ---------- 动手：POST 带 X-Lively 头（跨站页面带不了自定义头），改完把缓存清掉 ----------
async function post(url, body, {quiet=false}={}){
  Pet.play("busy");
  try{
    const r = await fetch(url, {method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json", "X-Lively":"1"}, body:JSON.stringify(body)});
    let j; try{ j = await r.json(); }catch{ throw new Error(r.status === 403 ? "没有权限" : "服务器回了 HTTP " + r.status); }
    if(!j.ok) throw new Error(j.error || "HTTP " + r.status);
    for(const k in cache) delete cache[k];
    Pet.react("cheer"); if(!quiet) Thought.say(j.msg ? j.msg + "～" : "办好啦～");
    badges();
    return j;
  }catch(e){ Pet.react("startle"); Thought.say("没办成：" + e.message + "～"); throw e; }
}
// 改完重新画一遍现在这页（同一个人的页面也留在原地）
// 地址栏里的中文会被编成 %E5…，记忆线上的「事和梗」名字要解回来
const hashSub = () => { try{ return decodeURIComponent(location.hash.split("/").slice(1).join("/")) || undefined; }catch{ return undefined; } };
const reload = () => go(region, hashSub());
// 会改东西的按钮点两下才算：第一下变成「确定…？」，三秒半内不点第二下就复原
function sure(b){
  if(b.dataset.armed){ clearTimeout(b._t); delete b.dataset.armed; b.innerHTML = b._h; return true; }
  b._h = b.innerHTML; b.dataset.armed = 1; b.textContent = `确定${b.textContent.trim()}？`;
  b._t = setTimeout(() => { delete b.dataset.armed; b.innerHTML = b._h; }, 3500);
  return false;
}
async function doing(b, f){
  b.disabled = true; b.classList.add("wait");
  try{ return await f(); }catch{ return null; }finally{ b.disabled = false; b.classList.remove("wait"); }
}
// 两侧纸上的按钮（data-act）和开关（data-set）都在这里接
const ACT = {
  // 回提案时顺手写的做法（说好）或为什么不要，跟在指令后面记在提案上；改做法只改已经同意了的
  prop: b => sure(b) && doing(b, () => post("/api/evolve", {action:"proposal", n:b.dataset.n, ok:b.dataset.ok === "1", note:($("#propNote" + b.dataset.n)?.value || "").trim()})).then(r => r && go("mail")),
  propnote: b => { const v = ($("#propNote" + b.dataset.n)?.value || "").trim();
    if(!v){ Thought.say("先写要改成什么做法～"); $("#propNote" + b.dataset.n)?.focus(); return; }
    return sure(b) && doing(b, () => post("/api/evolve", {action:"proposal", n:b.dataset.n, ok:true, note:v})).then(r => r && go("mail")); },
  note: b => sure(b) && doing(b, () => post("/api/evolve", {action:"del_note", i:+b.dataset.i})).then(r => r && go("memory")),
  ask: b => sure(b) && doing(b, () => post("/api/asks", {action:"del", id:+b.dataset.id})).then(r => r && go("memory")),
  selfnote: b => sure(b) && doing(b, () => post("/api/selfnotes", {action:"del", id:+b.dataset.id})).then(r => r && go("memory")),
  notes: b => sure(b) && doing(b, () => post("/api/evolve", {action:b.dataset.a})),
  req: b => sure(b) && doing(b, () => post("/api/pending", {what:"request", key:b.dataset.key, action:b.dataset.a})).then(() => go("mail")),
  qz: b => { const a = b.dataset.a;
    if(a !== "write" && !sure(b)) return;
    if(a === "write" || a === "rewrite") Thought.say("〈我〉在想写什么，十几秒～");
    return doing(b, () => post("/api/pending", {what:"qzone", action:a, text:$("#qzText")?.value, topic:$("#qzTopic")?.value || ""})).then(r => r && go("mail")); },
  // 点评〈我〉想做的事：点 ✓/✗，再点一次同一个就撤掉；✗ 之后可以写一句哪里不对
  mrv: b => doing(b, async () => { const row = b.closest(".mact"), was = b.getAttribute("aria-pressed") === "true";
    const ok = was ? null : b.dataset.ok === "1";
    await post("/api/mind/review", {beat:row.dataset.beat, i:+row.dataset.i, ok, note:""}, {quiet:true});
    row.querySelectorAll("[data-act=mrv]").forEach(x => x.setAttribute("aria-pressed", String(ok !== null && x === b)));
    row.querySelector(".rv-note").hidden = ok !== false;
    Thought.say(ok === null ? "撤掉啦～" : ok ? "嘿嘿，〈我〉想对了～" : "记下了，下次改～"); if(ok === false) row.querySelector(".rv-note").focus(); }),
  pcday: b => doing(b, async () => { const d = await soft(get("/api/pclog?day=" + encodeURIComponent(b.dataset.day))); const el = $("#pcLog"); if(el && d){ el.innerHTML = pcBody(d); FX.decorate?.(el); More.check(); } }),
  mindbeat: b => sure(b) && doing(b, async () => { Thought.say("〈我〉拿起手机看一眼～");
    const r = await post("/api/mind/beat", {}, {quiet:true}); Thought.say(r.beat.thought || (r.beat.result === "ok" ? "看了一眼，没什么想做的～" : r.beat.result + "～")); go("body"); }),
  wbsave: b => doing(b, async () => {
    const r = await post("/api/brain", {action:"api", base:$("#wbBase")?.value || "", key:$("#wbKey")?.value || "", model:$("#wbModel")?.value || ""}, {quiet:true});
    Thought.say(r.msg || "存好啦～"); if($("#wbKey")) $("#wbKey").value = ""; reload(); }),
  wbprobe: b => doing(b, async () => {
    const r = await post("/api/brain", {action:"probe"}, {quiet:true});
    Thought.say(r.msg || "通了～"); }),
  // 记一笔投喂：先在纸上查一下有没有写 QQ 和钱，再点两下才记
  feed: b => { const f = b.closest(".feedf"), q = f.querySelector(".ff-qq"), qq = f.dataset.qq || q?.value.trim(), amt = +f.querySelector(".ff-amt").value;
    if(!/^\d{5,12}$/.test(qq || "")){ Thought.say("先写是谁投喂的（QQ 号）～"); q?.focus(); return; }
    if(!(amt > 0)){ Thought.say("写一下投喂了多少钱～"); f.querySelector(".ff-amt").focus(); return; }
    if(!sure(b)) return;
    return doing(b, () => post("/api/feeds", {action:"add", qq, amount:amt, date:f.querySelector(".ff-date").value, note:f.querySelector(".ff-note").value.trim()})).then(r => r && reload()); },
  feeddel: b => sure(b) && doing(b, () => post("/api/feeds", {action:"del", id:b.dataset.id})).then(r => r && reload()),
  memepref: b => sure(b) && doing(b, () => post("/api/memepref", {action:"del", qq:b.dataset.qq, file:b.dataset.file})).then(r => r && reload()),
  // 表情包那页：换分类、拿下来（进隔离区）、放回、撤回刚才那一下
  mgmove: b => { const to = $("#mgTo")?.value; if(!to){ Thought.say("先选换到哪一类～"); $("#mgTo")?.focus(); return; } return sure(b) && mgDo(b, {action:"move", to}); },
  mgout: b => sure(b) && mgDo(b, {action:"out"}),
  mgback: b => sure(b) && mgDo(b, {action:"back", to:$("#mgTo")?.value || ""}),
  mgundo: b => sure(b) && doing(b, () => post("/api/memes", {action:b.dataset.a, files:[b.dataset.f], to:b.dataset.to || ""})).then(r => r && mgReload()),
  // 记忆线：去看一个点（空的回到全貌）、看一条的原话和前后、改（记一条新的取代它）、忘掉、找回、认人
  mlgo: b => go("memory", b.dataset.id || undefined),
  mlperson: b => go("people", b.dataset.qq),
  tlplace: b => { TL.place = b.dataset.p; TL.page = 0; tlRedraw(); },
  tlpage: b => { TL.page = Math.max(0, TL.page + +b.dataset.d); tlRedraw(); },
  mlpt: b => { const box = $("#mlp" + b.dataset.id); if(!box) return;
    if(!box.hidden && box.dataset.k === "src"){ box.hidden = true; More.check(); return; }
    return doing(b, async () => { const d = await get("/api/memline/point?id=" + b.dataset.id, 20000).catch(e => { Thought.say("没翻到：" + e.message + "～"); });
      if(!d) return; box.innerHTML = mlDetail(d); box.dataset.k = "src"; box.hidden = false; FX.decorate?.(box); More.check(); }); },
  mledit: b => { const box = $("#mlp" + b.dataset.id); if(!box) return;
    box.innerHTML = `<div class="ml-edit"><textarea id="mlt${b.dataset.id}" rows="3" maxlength="200" aria-label="改成什么">${esc(b.dataset.t)}</textarea><div class="ml-btns"><button class="btn sm" data-act="mlfix" data-id="${b.dataset.id}">保存</button><small class="muted">旧的留着</small></div></div>`;
    box.dataset.k = "edit"; box.hidden = false; $("#mlt" + b.dataset.id)?.focus(); More.check(); },
  mlfix: b => { const v = ($("#mlt" + b.dataset.id)?.value || "").trim();
    if(!v){ Thought.say("先写改成什么～"); $("#mlt" + b.dataset.id)?.focus(); return; }
    return sure(b) && doing(b, () => post("/api/memline", {action:"fix", id:+b.dataset.id, text:v})).then(r => r && reload()); },
  mlforget: b => sure(b) && doing(b, () => post("/api/memline", {action:"forget", id:+b.dataset.id})).then(r => r && reload()),
  mlrestore: b => sure(b) && doing(b, () => post("/api/memline", {action:"restore", id:+b.dataset.id})).then(r => r && reload()),
  mlclaim: b => { const to = b.dataset.to || ($("#mlq" + b.dataset.k)?.value || "").trim();
    if(!/^\d{5,12}$/.test(to) && to !== "thing"){ Thought.say("写 TA 的 QQ 号～"); $("#mlq" + b.dataset.k)?.focus(); return; }
    return sure(b) && doing(b, () => post("/api/memline", {action:"claim", node:b.dataset.node, to})).then(r => r && reload()); },
  // 记录那条时间线：按来源打开、收起
  annf: b => { const on = b.getAttribute("aria-pressed") !== "true"; b.setAttribute("aria-pressed", on); on ? ANN_OFF.delete(b.dataset.k) : ANN_OFF.add(b.dataset.k);
    const ls = $$(`#annBox li[data-src="${b.dataset.k}"]`); ls.forEach(l => l.hidden = !on);
    if(on && !REDUCED) gsap.from(ls.slice(0, 40), {autoAlpha:0, x:-8, duration:.35, stagger:.012, ease:"power2.out", clearProps:"all"});
    More.check(); },
  report: b => doing(b, async () => { const box = $("#report"); box.innerHTML = `<p class="loading">〈我〉在写，十几秒～</p>`; Thought.say("〈我〉在写汇报～");
    try{ const r = await post("/api/report", {}, {quiet:true}); box.innerHTML = `<div class="report-text">${esc(r.text)}</div>`; Thought.say("写好啦，主人看看～"); }
    catch(e){ box.innerHTML = `<p class="loading">没写成：${esc(e.message)}</p>`; } }),
};
for(const side of ["#left", "#right"]){
  $(side).addEventListener("keydown", async e => { const el = e.target.closest(".rv-note"); if(!el || e.key !== "Enter") return;
    const row = el.closest(".mact");
    try{ await post("/api/mind/review", {beat:row.dataset.beat, i:+row.dataset.i, ok:false, note:el.value.trim()}, {quiet:true}); Thought.say("记下啦～"); el.blur(); }catch{} });
  $(side).addEventListener("click", e => { const b = e.target.closest("[data-act]"); if(b && !b.disabled) ACT[b.dataset.act]?.(b); });
  $(side).addEventListener("change", async e => { const el = e.target.closest("[data-set]"); if(!el) return;
    const [plugin, key] = el.dataset.set.split(".");
    // 「不主动找 TA」这种按人的开关：勾上是 block，取消是 unblock，值是 QQ
    const body = el.dataset.qq ? {plugin, key:el.checked ? "block" : "unblock", value:el.dataset.qq} : {plugin, key, value:el.type === "checkbox" ? el.checked : el.value};
    try{ const r = await post("/api/settings", body, {quiet:true}); Thought.say(el.type === "checkbox" ? (el.checked ? "打开啦～" : "关掉啦～") : "改好啦～");
    }
    catch{ if(el.type === "checkbox") el.checked = !el.checked; } });
}
const toggle = (set, on, title, desc, extra="", cls="") => `<label class="sw${cls ? " " + cls : ""}"><span>${title}${desc ? `<small>${desc}</small>` : ""}</span><input type="checkbox" role="switch" data-set="${set}" ${extra} ${on ? "checked" : ""}><i aria-hidden="true"></i></label>`;
const choose = (set, val, opts, title, desc) => `<label class="sw"><span>${title}${desc ? `<small>${desc}</small>` : ""}</span><select data-set="${set}">${Object.entries(opts).map(([k, v]) => `<option value="${esc(k)}"${k === val ? " selected" : ""}>${esc(v)}</option>`).join("")}</select></label>`;

// ---------- 此刻 ----------
function hourClip(h){
  if(h < 6) return "sleep";
  if(h === 7 || h === 8) return "breakfast";
  if(h === 12) return "lunch";
  if(h === 18) return "dinner";
  return Math.random() < .5 ? "breathe" : "hum";
}
const todayOf = ov => { const t = ov?.today || {}, g = t["各群"] || {};
  return {t, g, m:t["模型回复"] || {}, gmsg:Object.values(g).reduce((a, x) => a + (x["群消息"] || 0), 0), replies:Object.values(g).reduce((a, x) => a + (x["〈我〉回复"] || 0), 0)}; };
async function renderNow(){
  const [ov, ppl, hr, bill, mi, pa] = await Promise.all([soft(get("/api/overview")), soft(get("/api/people")), soft(get("/api/heart")), soft(get("/api/billing")),
    soft(get("/api/mind?only=thoughts")), pendingAll()]);
  const h = new Date().getHours();
  const hello = h < 5 ? "这么晚还不睡呀" : h < 11 ? "早上好呀" : h < 14 ? "中午好呀" : h < 18 ? "下午好呀" : "晚上好呀";
  const left = [], right = [], thoughts = [];
  const {t, g, m, gmsg, replies} = todayOf(ov);
  if(qqDown(ov)){ left.push(offlineCard(ov.offline_since)); thoughts.push({t:"QQ 掉线了，〈我〉现在收不到也发不出消息……"}); }

  // 身体感受：把今天的数字换成她自己的感觉
  const rows = [];
  let eat = null;
  if(bill){
    // 今天余额实际掉了多少（和「平常一天」同一个算法）；还没有余额记录才用按 token 算的
    const d = bill.days[bill.days.length-1] || {}, per = (bill.accounts || [])[0]?.per_day || 0;
    eat = d.actual != null ? +d.actual : Object.values(d.keys || {}).reduce((a, k) => a + (k.total || 0), 0);
    const frac = Math.max(.15, (Date.now() - new Date().setHours(0, 0, 0, 0)) / 864e5), full = per ? Math.min(1, eat / (per * frac)) : .4;
    rows.push(["肚子", full, `¥${eat.toFixed(2)}`, `今天${d.actual != null ? "扣了" : "吃了"} ${eat.toFixed(2)} 元${per ? `，平常一天 ${per.toFixed(2)}` : ""}${full > .95 ? "，吃得比平常快～" : full < .4 ? "，还饿～" : "～"}`]);
  }
  if(ov){
    const rate = gmsg ? replies / gmsg : 0;
    rows.push(["嗓子", Math.min(1, rate * 3), `${Math.round(rate*100)}%`, `群里 ${gmsg} 条，〈我〉插嘴了 ${replies} 句`]);
    const sec = m["中位耗时秒"];
    rows.push(["脑子", sec ? Math.min(1, sec / 8) : 0, sec != null ? `${sec}s` : "—", `想一句要 ${sec ?? "?"} 秒，回了 ${m["次数"] || 0} 次${m["失败"] ? `，卡壳 ${m["失败"]} 次` : ""}`, m["失败"]]);
    const s = ov.system || {}, mem = s.mem || {}, used = mem.total ? (mem.total - mem.available) / mem.total : 0, ld = (s.load?.[0] ?? 0) / (s.cpus || 1);
    const tired = Math.max(used, Math.min(1, ld));
    rows.push(["累不累", tired, `${Math.round(tired*100)}%`, tired > .8 ? "喘不过气了～" : tired > .55 ? "有点累～" : "身体很轻松～", tired > .65]);
  }
  left.push(card("〈我〉现在的身体", rows.length ? rows.map(r => meter(...r)).join("") : fail("身体状况"), {ic:"i-pulse", note:"把今天的数字换成〈我〉自己的感觉"}));

  // 心情：一根按人数分段的条，下面是每种心情对着谁
  if(ppl){
    const known = ppl.filter(r => r.qq !== BOT && String(r.impression || "").trim());
    const by = {}; known.forEach(r => (by[r.mood || "平常"] ||= []).push(r));
    const ks = Object.keys(by).filter(k => k !== "平常").sort((a, b) => by[b].length - by[a].length);
    const n = ks.reduce((a, k) => a + by[k].length, 0);
    left.push(card("〈我〉对大家的心情", ks.length
      ? cbar(ks.map(k => [k, by[k].length, mc(k), `<b>${esc(k)}</b> ${by[k].length} 人<br>${esc(by[k].slice(0, 6).map(r => r.name || r.qq).join("、"))}${by[k].length > 6 ? " 等" : ""}`]))
        + `<div class="mrows">${ks.slice(0, 4).map(k => `<div class="mrow">${tagM(k, mc(k))}${avs(by[k].map(r => r.qq))}<span class="mrow-n">${esc(by[k].slice(0, 2).map(r => r.name || r.qq).join("、"))}${by[k].length > 2 ? " 等" : ""}</span></div>`).join("")}</div>`
      : empty("great", "对谁都心平气和～"), {ic:"i-heart", cls:"pink", meta:n ? `<b>${n}</b> 人` : "", note:`对 ${n} 个人有点小情绪，其他 ${known.length - n} 人都平常`}));
    const sp = ks[0]; if(sp) thoughts.push({t:`现在对 ${by[sp].map(r => r.name).slice(0,2).join("、")} 有点${sp}～`});
  }

  // 要主人拍板的事都在「待你裁决」，这里只放一行总数，点了过去
  if(pa.n){
    right.push(card("等主人管的事", `<div class="todo"><button data-go="mail">${ic("i-bell")}<span><b>有 ${pa.n} 件事等主人裁决</b><small>${esc(pa.sum)}</small></span><em aria-hidden="true">›</em></button></div>`,
      {ic:"i-bell", cls:"pink", meta:`<b>${pa.n}</b> 件`}));
    thoughts.push({t:`有 ${pa.n} 件事等主人看一眼～`});
  }
  // 刚才在想：看 QQ 时（自主心跳）想的，12 小时内最近 4 次；每晚回味出的回忆在「记忆深处」
  if(mi){
    const bs = (mi.thoughts || []).filter(b => Date.now()/1000 - b.ts < 12 * 3600).slice(0, 4);
    right.push(card("刚才在想的事", bs.length ? tl(bs.map(b => ({m:"var(--blush)", h:`<b>看 QQ 时想的</b>`, t:fmtT(b.ts), p:esc(b.text)})))
      : empty("sleep", mi.sleeping ? "〈我〉睡着了，醒了再想～" : "这半天还没拿起手机想事～"),
      {ic:"i-spark", meta:bs[0] ? ago(bs[0].ts) : "", note:"大约 15 分钟看一眼手机，看完想的；睡觉时不看"}));
  }
  if(hr?.ready) (hr.recent || []).slice(0, 3).forEach(mo => thoughts.push({t:`想起 ${mo.name}：${mo.text}`, s:`${fmtT(mo.ts)} · ${mo.feeling}`}));
  // 今天的日记
  const mt = ov?.mind?.thought, fresh = mt?.text && Date.now()/1000 - mt.ts < 3 * 3600;
  if(ov){
    const L = [];
    L.push({h:`<b>今天的群</b>`, p:`${Object.keys(g).length} 个群冒出 ${N(gmsg)} 条消息，〈我〉插嘴了 ${N(replies)} 句～`});
    const users = ov.hourly.users.map((v, i) => v + ov.hourly.bot[i]), peak = users.indexOf(Math.max(...users));
    if(users[peak]) L.push({h:`<b>最热闹</b>`, p:`${mark(N(peak + "点"))}，一个小时 ${N(users[peak])} 条～`});
    const fr = (t["关系"] || {})["新认识"] || [];
    if(fr.length) L.push({m:"var(--good)", h:`<b>新朋友</b>`, p:`新认识了 ${N(fr.length)} 个人～`});
    const dn = (t["关系"] || {})["好感掉了"] || [];
    if(dn.length) L.push({cls:"bad", h:`<b>有点不高兴</b>`, p:`${esc(dn.slice(0,2).map(x => x.replace(/\s*-[\d.]+$/, "")).join("、"))}今天惹〈我〉不高兴了，哼～`});
    right.push(card("今天的日记", tl(L), {ic:"i-book"}));
    thoughts.unshift({t:`主人${hello}～今天回了 ${replies} 句话～`});
  }
  if(fresh) thoughts.unshift({t:mt.text, s:`${fmtT(mt.ts)} · 看 QQ 时想的`});
  if(h < 6) thoughts.unshift({t:"呼……zzz……（〈我〉睡着了，在回味白天的事）"});
  setOnline(ov?.online, ov?.offline_since, ov && !qqDown(ov));
  const kpi = [ov && ["今天的群消息", gmsg, "条"], ov && ["〈我〉回了", replies, "句"], eat != null && ["今天吃了", "¥" + eat.toFixed(2)],
    hr?.ready ? ["记得的回忆", hr.moments, "段"] : ppl && ["心里的人", ppl.length, "个"]];
  return {left, right, thoughts, kpi, sub:`主人${hello}～${h < 6 ? "〈我〉在睡觉" : "这是〈我〉现在的样子"}`, clip:hourClip(h)};
}
// 一段回忆放进时间线：点的颜色是当时的感受
function momentItem(mo){
  const imp = Object.entries(mo.impacts || {}).map(([k, v]) => `<span class="imp${(BAD.has(k) ? v > 0 : v < 0) ? " neg" : ""}"${tip(`这件事让〈我〉对 ${esc(mo.name)} 的<b>${esc(k)}</b> ${v > 0 ? "多了" : "少了"} ${Math.abs(v)}`)}>${esc(k)} ${v > 0 ? "+" : ""}${v}</span>`).join("");
  return {m:mc(mo.feeling), h:`${tagM(mo.feeling, mc(mo.feeling))}<b>${esc(mo.name)}</b>`, t:fmtT(mo.ts), p:esc(mo.text),
    s:`${mo.private ? `<span class="lock">${ic("i-lock")}私聊</span>` : esc(mo.where)}${imp}`};
}

// ---------- 心里的人：一圈圈围着她转 ----------
const closeness = r => { const f = r.feelings || {};
  return (f["亲近"]||0) + .6*(f["信任"]||0) + .35*((f["逗趣"]||0) + (f["欣赏"]||0) + (f["依赖"]||0) + (f["牵挂"]||0)) - (f["芥蒂"]||0) - (f["反感"]||0)
    + (r.familiarity||0) * .4 + (r.favor||0) * .3; };
const topDim = f => Object.entries(f || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1])[0];
const Field = (() => {
  const root = $("#field");
  root.innerHTML = `<svg class="ties" aria-hidden="true"><ellipse class="orbit"/><ellipse class="orbit"/><ellipse class="orbit"/><path id="tie" d="M0 0" fill="none" stroke="#fff" stroke-width="2" stroke-dasharray="3 7" stroke-linecap="round" opacity="0"/></svg>`;
  const orbits = [...root.querySelectorAll(".orbit")];  // 三圈轨道，纸面时看不见（极客模式才画）
  let okey = "";
  // 后半圈的人在她身后（层级比她低），前半圈的人在她身前；两层直接挂在 body 下，才能夹住她
  const layer = z => { const d = document.createElement("div"); d.className = "ring-layer"; d.style.zIndex = z; document.body.appendChild(d); return d; };
  const back = layer(5), front = layer(9);
  root.style.zIndex = 4;
  let items = [], on = false, vis = false, raf, last = 0, paused = false, sel = null, frozen = false, hov = null, G = null, gAt = 0;
  // 鼠标在哪：整圈跟着轻轻偏一点（景深）
  let mx = 0, my = 0;
  addEventListener("pointermove", e => { mx = e.clientX / innerWidth - .5; my = e.clientY / innerHeight - .5; }, {passive:true});
  const RINGS = [{k:.6, sp:1/70}, {k:.8, sp:-1/110}, {k:1, sp:1/160}];  // 最里一圈也要绕开她的身子
  function build(rows){
    const list = rows.filter(r => r.qq !== BOT && (r.moments || String(r.impression || "").trim() || r.qq === OWNER))
      .sort((a, b) => (b.qq === OWNER) - (a.qq === OWNER) || closeness(b) - closeness(a)).slice(0, 54);
    const caps = [7, 17, 99], per = [[], [], []];
    list.forEach((r, i) => { const ring = r.attitude > 0 ? 2 : i < caps[0] ? 0 : i < caps[0] + caps[1] ? 1 : 2; per[ring].push(r); });
    items = [];
    back.innerHTML = front.innerHTML = "";
    per.forEach((rs, ri) => rs.forEach((r, j) => {
      const el = document.createElement("button");
      const dim = topDim(r.feelings), owner = r.qq === OWNER;
      el.className = "ppl" + (r.attitude > 0 ? " att" : "") + (owner ? " owner" : "");
      el.style.setProperty("--s", Math.round(30 + Math.min(1, (r.familiarity || 0) / 60) * 26 + (ri === 0 ? 6 : 0)) + "px");
      el.style.setProperty("--c", owner ? "#e0a630" : r.attitude > 0 ? "#9aa6c2" : dim ? DIM_C[dim[0]] : "#c9d3ea");
      if(r.attitude > 0) el.dataset.att = ATTS[r.attitude];
      el.setAttribute("aria-label", `${r.name || r.qq}${dim ? `，最深的感情是${dim[0]}` : ""}`);
      el.innerHTML = av(r.qq) + `<span class="nm">${esc(r.name || r.qq)}</span>` + (r.bot ? `<span class="bt" aria-hidden="true">${botFace(r)}</span>` : "");
      const top3 = Object.entries(r.feelings || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 3);
      el.dataset.tip = `<div class="tp-who"><b>${esc(r.name || r.qq)}</b>${bm(r)}${r.attitude > 0 ? `<span class="att-stamp sm">${ATTS[r.attitude]}</span>` : ""}</div>`
        + (top3.length ? `<div class="tp-bars">${top3.map(([k, v]) => `<span>${k}</span><i style="--c:${DIM_C[k]};--w:${v}%"></i><em>${v}</em>`).join("")}</div>` : "")
        + (r.impression ? `<p class="tp-q">${esc(String(r.impression).slice(0, 42))}</p>` : "") + `<small>熟悉 ${r.familiarity ?? 0} · 点一下看〈我〉怎么称 TA</small>`;
      el.style.pointerEvents = "auto";
      el.onclick = e => { e.stopPropagation(); FX.pickFrom(el); go("people", r.qq); };
      const it = {el, r, ring:ri, a:(j / rs.length) * Math.PI * 2 + ri * .7, depth:0, k:1, o:1, h:0, ph:Math.random() * 6.28, pe:""};
      // 停在一颗上：整圈停下，这一颗弹大一点、浮到最前面、不再变淡
      el.onmouseenter = () => { paused = true; hov = it; gsap.to(it, {h:1, duration:.45, ease:"back.out(2.4)"}); };
      el.onmouseleave = () => { paused = !!sel; if(hov === it) hov = null; gsap.to(it, {h:0, duration:.35, ease:"power2.out"}); };
      items.push(it);
      back.appendChild(el);
    }));
  }
  // 圈只占她身边那块空地：左右两列纸之间、上面那排数字下面、底下对话框上面，别压到纸和字（11-02）
  // 量这些框要读布局，不每帧量：隔 400 毫秒、或者窗口变了再量
  const PAD = 34;
  function box(){
    if(innerWidth <= 1100){ const r = $("#stage").getBoundingClientRect(), rx = Math.max(120, r.width / 2 - PAD);
      return {cx:r.left + r.width / 2, cy:r.top + r.height * .5, rx, ry:Math.min(rx * .62, r.height / 2 - PAD)}; }
    const L = $("#left").getBoundingClientRect(), R = $("#right").getBoundingClientRect(), K = $("#kpi").getBoundingClientRect(), T = $("#thought").getBoundingClientRect();
    const lb = L.width && L.right < innerWidth / 2 ? L.right : 0, rb = R.width && R.left > innerWidth / 2 ? R.left : innerWidth;
    const tb = Math.max(K.bottom, 70), bb = window.Geek?.on || !T.height || T.top < innerHeight / 2 ? innerHeight - parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--bottom") || 116) : T.top;
    const rx = Math.max(150, (rb - lb) / 2 - PAD), ry = Math.max(90, Math.min(rx * .62, (bb - tb) / 2 - PAD));
    const [, sy] = stageCenter();
    return {cx:(lb + rb) / 2, cy:Math.max(tb + PAD + ry, Math.min(bb - PAD - ry, sy - 20)), rx, ry};
  }
  function geom(now){
    if(!G || now - gAt > 400){ G = box(); gAt = now; }
    return {cx:G.cx + mx * 14, cy:G.cy + my * 8, rx:G.rx, ry:G.ry};
  }
  function tick(now){
    const dt = Math.min(60, now - (last || now)) / 1000; last = now;
    const g = geom(now), key = `${g.cx | 0},${g.cy | 0},${g.rx | 0},${g.ry | 0}`, t = now / 1000;
    if(key !== okey){ okey = key; orbits.forEach((o, i) => { o.setAttribute("cx", g.cx); o.setAttribute("cy", g.cy); o.setAttribute("rx", g.rx * RINGS[i].k); o.setAttribute("ry", g.ry * RINGS[i].k); }); }
    for(const it of items){
      const R = RINGS[it.ring];
      if(!paused && !REDUCED) it.a += R.sp * Math.PI * 2 * dt;
      // it.k：出场时从她心口一圈圈旋出来（0 → 1）；每颗自己上下浮一点
      const s = Math.sin(it.a), bob = REDUCED ? 0 : Math.sin(t * 1.3 + it.ph) * 3 * it.k;
      const x = g.cx + g.rx * R.k * it.k * Math.cos(it.a), y = g.cy + g.ry * R.k * it.k * s + bob;
      const sc = (.72 + .28 * (s + 1) / 2) * (.35 + .65 * it.k) * (1 + .32 * it.h);
      it.el.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px) scale(${sc.toFixed(3)})`;
      const d = s > 0 ? 1 : -1;
      if(d !== it.depth){ it.depth = d; (d > 0 ? front : back).appendChild(it.el); }
      // 在她身前经过时变淡、点不到（不挡她的脸，也能戳到她）；后半圈暗一点；选了一个人时别的都淡下去
      const near = Math.min(1, Math.abs(x - g.cx) / (g.rx * .42));
      let o = d > 0 ? .22 + .78 * near * near : .8;
      if(sel) o = it.r.qq === sel ? 1 : Math.min(o, .28);
      if(it.h > .01) o = Math.max(o, it.h);
      it.el.style.opacity = (o * it.o).toFixed(3);
      it.el.style.zIndex = it.h > .01 ? 5 : "";
      const pe = it.o < .5 || o < .45 ? "none" : "";
      if(pe !== it.pe){ it.pe = pe; it.el.style.pointerEvents = pe; }
      it.x = x; it.y = y;
    }
    const tie = $("#tie"), it = sel && items.find(i => i.r.qq === sel);
    if(it){ const [px, py] = stageCenter(), sy = py - 60, mx = (px + it.x) / 2, my = Math.min(sy, it.y) - 70;
      tie.setAttribute("d", `M${px.toFixed(0)} ${sy.toFixed(0)} Q${mx.toFixed(0)} ${my.toFixed(0)} ${it.x.toFixed(0)} ${it.y.toFixed(0)}`); tie.setAttribute("opacity", ".8"); }
    else tie.setAttribute("opacity", "0");
    if(on) raf = requestAnimationFrame(tick);
  }
  addEventListener("resize", () => { G = null; });
  return {
    build, has:() => items.length > 0,
    // 卡册铺满屏幕时停下来（被挡住还每帧挪 50 多颗泡泡，很吃显卡），合上再接着转
    freeze(v){
      if(v){ if(on){ on = false; cancelAnimationFrame(raf); frozen = true; } }
      else if(frozen){ frozen = false; if(vis && !on){ on = true; last = 0; tick(performance.now()); } }
    },
    show(v){
      if(v === vis) return; vis = v;
      root.classList.toggle("on", v);
      gsap.killTweensOf(items);
      G = null;
      if(v){
        // 一个个从她心口旋出来（位置、透明度每帧由 tick 写，GSAP 只推 it.k 和 it.o）
        items.forEach(it => { it.depth = 0; it.k = REDUCED ? 1 : 0; it.o = REDUCED ? 1 : 0; it.h = 0; it.pe = null; });
        if(!on){ on = true; last = 0; tick(performance.now()); }
        if(!REDUCED){
          gsap.to(items, {k:1, duration:1.6, ease:"expo.out", stagger:.014, delay:.2});
          gsap.to(items, {o:1, duration:.5, stagger:.014, delay:.2});
        }
      } else {
        // 收回她心口里，收完再停帧、拿掉
        gsap.to(items, {k:0, duration:REDUCED ? 0 : .45, ease:"power2.in", stagger:.004});
        gsap.to(items, {o:0, duration:REDUCED ? 0 : .4, delay:REDUCED ? 0 : .1, onComplete:() => { if(vis) return; on = false; cancelAnimationFrame(raf); items.forEach(it => it.el.remove()); }});
      }
    },
    pick(qq){
      sel = qq || null; paused = !!sel;
      root.classList.toggle("picked", !!sel);
      [back, front].forEach(c => c.classList.toggle("picked", !!sel));
      items.forEach(it => it.el.classList.toggle("sel", it.r.qq === sel));
    },
  };
})();
// 点空白处放下这个人
$("#field").addEventListener("click", () => { if(region === "people" && location.hash.includes("/")) go("people"); });
addEventListener("keydown", e => { if(e.key === "Escape" && region === "people" && location.hash.includes("/")) go("people"); });

// 「TA 是 bot」不走 /api/settings：拦在两侧纸的 change 前面（捕获阶段）
for(const side of ["#left", "#right"]) $(side).addEventListener("change", async e => {
  const el = e.target.closest("[data-bot]"); if(!el) return;
  e.stopImmediatePropagation();
  try{ await post("/api/bot", {qq:el.dataset.bot, on:el.checked}, {quiet:true}); Thought.say(el.checked ? "记下了，TA 是 bot～" : "好，TA 不是 bot～"); go("people", el.dataset.bot); }
  catch{ el.checked = !el.checked; }
}, true);

// 哪家做的、什么型号：〈主人〉在这里标的算数，〈我〉自己记的会被盖掉
const botWho = (qq, p) => `<div class="bot-who" data-botw="${esc(qq)}">
    <select class="bw-v" aria-label="哪家做的"><option value="">不知道哪家</option>${Object.entries(VENDORS).map(([k, v]) => `<option value="${k}"${p.bot_vendor === k ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
    <input class="bw-m" maxlength="40" value="${esc(p.bot_model || "")}" placeholder="型号（可不写）" aria-label="型号">
    <button class="btn sm alt" data-act="botwho">${ic("i-bot")}记下</button>
    ${p.bot_by ? `<small class="muted">${esc(p.bot_by)}</small>` : ""}</div>`;
ACT.botwho = async b => {
  const w = b.closest("[data-botw]");
  if(!await doing(b, () => post("/api/bot", {qq:w.dataset.botw, on:true, vendor:w.querySelector(".bw-v").value, model:w.querySelector(".bw-m").value.trim()}))) return;
  Thought.say("记下了是哪家的 bot～"); go("people", w.dataset.botw);
};

// ---------- 记忆线（〈我〉自己的记忆，记忆插件）共用的小工具 ----------
const short = (s, n) => { const a = [...String(s ?? "")]; return a.length > n ? a.slice(0, n).join("") + "…" : a.join(""); };
const ML_KIND = {person:"人", group:"群", thing:"事和梗", unknown:"待认的名字", me:"〈我〉"};

async function renderPeople(qq){
  const more = [];
  const [rows, hr, cu] = await Promise.all([soft(get("/api/people")), soft(get("/api/heart")), ...more]);
  if(!rows) return {left:[card("心里的人", fail("人物表"), {ic:"i-users"})], right:[], clip:"float"};
  if(!Field.has()) Field.build(rows);
  if(qq) return renderPerson(qq, rows, hr);
  Field.pick(null);
  const list = rows.filter(r => r.qq !== BOT && (r.moments || String(r.impression || "").trim()));
  const by = d => list.filter(r => (r.feelings || {})[d] > 0).sort((a, b) => b.feelings[d] - a.feelings[d]);
  const badOf = r => ((r.feelings || {})["芥蒂"] || 0) + ((r.feelings || {})["反感"] || 0);
  const grudge = list.filter(r => r.attitude > 0 || badOf(r) > 0).sort((a, b) => (b.attitude || 0) - (a.attitude || 0) || badOf(b) - badOf(a));
  const close = by("亲近"), fun = by("逗趣"), trust = by("信任");
  const rk = (rs, d) => rs.length ? blist(rs.slice(0, 8).map(r => ({qq:r.qq, img:av(r.qq, 40), lb:esc(r.name || r.qq) + bm(r), v:r.feelings[d], w:r.feelings[d] / 100, c:DIM_C[d]})), true) : "";
  const left = [card("排一排", tabs([["最亲近", rk(close, "亲近"), close.length], ["最逗趣", rk(fun, "逗趣"), fun.length], ["最信任", rk(trust, "信任"), trust.length],
      ["有芥蒂", grudge.length ? blist(grudge.slice(0, 8).map(r => ({qq:r.qq, img:av(r.qq, 40), lb:esc(r.name || r.qq) + bm(r), sub:r.attitude > 0 ? ATTS[r.attitude] : "", v:r.attitude > 0 ? ATTS[r.attitude] : badOf(r), w:Math.min(1, badOf(r) / 100), c:"#d8506f"})), true) : "", grudge.length]])
      || empty("great", "还没有排得上的人～"), {ic:"i-chart", raw:true, note:"点一行看〈我〉怎么称这个人"}),
    card("这一圈怎么看", `<p class="small muted" style="margin:0 0 10px">离〈我〉越近越亲近，泡泡越大越熟，颜色是对 TA 最深的那种感情；灰色带章的在闹别扭，转在最外圈。</p>
      <div class="legend">${Object.entries(DIM_C).map(([k, c]) => `<span style="--m:${c}">${k}</span>`).join("")}<span style="--m:#e0a630">主人</span></div>`, {ic:"i-info"})];
  // 手里捏五张：最亲近的在正中间压在最上面，往两边依次排
  const top5 = [...list].sort((a, b) => (b.qq === OWNER) - (a.qq === OWNER) || closeness(b) - closeness(a)).slice(0, 5);
  const hand = [top5[3], top5[1], top5[0], top5[2], top5[4]].filter(Boolean);
  const right = [`<div class="deck bare"><h2 class="deck-h">〈我〉手里的〈卡〉<small>最亲近的 ${hand.length} 张</small></h2>
       <div class="hand">${hand.map(miniCard).join("")}</div>
       <button class="album-btn" id="albumBtn">翻开整本〈卡〉册 · ${list.length} 张</button></div>`];
  // 卡下面：最近心里记下谁的事（每人只留最新一条），和这周新认识的人
  const seen = new Set(), lately = (hr?.recent || []).filter(mo => mo.qq && !seen.has(mo.qq) && seen.add(mo.qq)).slice(0, 5);
  if(lately.length) right.push(card("最近在想的人", `<ul class="thinkof">${lately.map(mo => `<li><button data-qq="${esc(mo.qq)}" style="--m:${mc(mo.feeling)}">${av(mo.qq, 64)}<span class="to-h"><b>${esc(mo.name || mo.qq)}</b><i>${esc(mo.feeling || "平常")}</i><time>${ago(mo.ts)}</time></span><span class="to-t">${esc(mo.text || "")}</span></button></li>`).join("")}</ul>`,
    {ic:"i-heart", note:"心里刚记下的事，每人一条", foot:`<button class="btn alt sm" data-go="memory/feel">${ic("i-heart")}看全部回味</button>`}));
  const WEEK = Date.now() / 1000 - 7 * 86400, fresh = rows.filter(r => r.qq !== BOT && r.first_met > WEEK).sort((a, b) => b.first_met - a.first_met);
  if(fresh.length) right.push(card("这周新认识的", `<div class="newfaces">${fresh.slice(0, 12).map(r => `<button data-qq="${esc(r.qq)}"${tip(`<b>${esc(r.name || r.qq)}</b> 认识于 ${fmtT(r.first_met)}${r.impression ? `<br>${esc(r.impression)}` : ""}`)}>${av(r.qq, 64)}<span>${esc(r.name || r.qq)}</span></button>`).join("")}</div>`,
    {ic:"i-users", note:`7 天里 ${fresh.length} 个`}));
  const th = [{t:`〈我〉心里住着 ${list.length} 个人～`}];
  if(close[0]) th.push({t:`最亲近的是 ${close[0].name}，亲近 ${close[0].feelings["亲近"]}～`});
  if(fun[0]) th.push({t:`最会逗〈我〉笑的是 ${fun[0].name}～`});
  if(grudge[0]) th.push({t:`哼，还在跟 ${grudge[0].name} 闹别扭～`});
  const kpi = [["住在心里", list.length, "人"], hr?.ready && ["一起的回忆", hr.moments, "段"], close.find(r => r.qq !== OWNER) && ["最亲近", close.find(r => r.qq !== OWNER).name],
    ["在闹别扭", list.filter(r => r.attitude > 0).length, "人", list.some(r => r.attitude > 0) ? "warn" : ""]];
  return {left, right, thoughts:th, kpi, sub:"点一颗泡泡，看〈我〉心里怎么称这个人", clip:"float", after:() => { bindRank(); $("#albumBtn").onclick = () => Album.open(list); }};
}
function bindRank(){ $$(".blist button[data-qq],.hand .mcard,.newfaces button,.thinkof button").forEach(b => b.onclick = () => { FX.pickFrom(b.querySelector("img")); go("people", b.dataset.qq); }); }


// 整本卡册：铺满屏幕的一层，卡一张张发出来；点一张就合上卡册去看这个人
const Album = (() => {
  const el = document.createElement("div"); el.id = "album"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", "〈卡〉册"); el.hidden = true;
  el.innerHTML = `<div class="al-head"><h2>〈卡〉册</h2><span id="alCount"></span>
      <div class="al-sort" role="group" aria-label="排序">${[["close", "最亲近"], ["favor", "好感"], ["fam", "最熟"], ["recent", "最近聊过"], ["grudge", "有芥蒂"]].map(([k, t], i) => `<button data-k="${k}" aria-pressed="${!i}">${t}</button>`).join("")}</div>
      <input id="alFind" type="search" placeholder="找名字、QQ、印象" aria-label="找人">
      <button class="al-x" aria-label="合上卡册">${ic("i-close")}</button></div>
    <div class="al-grid" id="alGrid"></div>`;
  document.body.appendChild(el);
  let rows = [], key = "close";
  const SORT = {close:closeness, favor:r => r.favor || 0, fam:r => r.familiarity || 0, recent:r => r.last_talk || 0,
    grudge:r => (r.attitude || 0) * 100 + ((r.feelings || {})["芥蒂"] || 0) + ((r.feelings || {})["反感"] || 0)};
  function draw(deal){
    const q = $("#alFind").value.trim();
    const rs = rows.filter(r => !q || [r.name, r.qq, r.impression].some(x => String(x || "").includes(q))).sort((a, b) => SORT[key](b) - SORT[key](a));
    $("#alCount").textContent = `${rs.length} 张`;
    $("#alGrid").innerHTML = rs.map(miniCard).join("") || `<p class="muted">没找到这个人～</p>`;
    $$("#alGrid .mcard").forEach(b => b.onclick = () => { FX.pickFrom(b.querySelector("img")); close(); go("people", b.dataset.qq); });
    FX.deal($$("#alGrid .mcard"), deal ? head() : null);
  }
  let gen = 0;  // 刚合上又马上打开时，别让合上那一下的收尾把新打开的藏掉
  function open(list){
    gen++; rows = list; el.hidden = false; $("#alFind").value = "";
    Field.freeze(true); Water.pause(true);
    FX.albumIn(el); draw(true); Pet.react("file", 2600); Thought.say("这是〈我〉的〈卡〉册，每张都是〈我〉心里的一个人～");
  }
  function close(){ if(el.hidden) return; const g = ++gen; Field.freeze(false); Water.pause(false);
    FX.albumOut(el).then(() => { if(g === gen) el.hidden = true; }); }
  el.querySelector(".al-x").onclick = close;
  el.addEventListener("click", e => { if(e.target === el) close(); });
  $$("#album .al-sort button").forEach(b => b.onclick = () => { key = b.dataset.k; $$("#album .al-sort button").forEach(x => x.setAttribute("aria-pressed", x === b)); draw(false); });
  $("#alFind").oninput = () => draw(false);
  addEventListener("keydown", e => { if(e.key === "Escape" && !el.hidden){ e.stopImmediatePropagation(); close(); } }, true);
  return {open, close};
})();

// ---------- 〈卡〉（印象卡）----------
// 正面跟群友要卡时收到的那张差不多，只多一个态度章（面板只有〈主人〉看；群友收到的卡不带，被冷落的人自己看不出来）；点一下翻过来，是只有〈我〉知道的心里话
// 關係只放第一段（主人那句「主人，最亲的人，……」只留「主人」），整句滑上去看
const shortStage = s => (s || "").split(/[，,；;（(]/)[0].trim();
const tierOf = r => r.qq === OWNER || /主人/.test(r.stage || "") ? ["t-owner", "主人"]
  : (r.favor || 0) >= 70 ? ["t-love", "喜欢"] : (r.favor || 0) >= 13 ? ["t-close", "亲近"] : (r.favor || 0) >= -13 ? ["t-mid", "普通"] : ["t-hate", "讨厌"];
const qlogo = (qq, s) => `<img src="https://q1.qlogo.cn/g?b=qq&nk=${esc(qq)}&s=${s}" alt="" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='/api/avatar/${esc(qq)}'"`;
// 定做了虚拟形象的群友：〈卡〉和卡册放那张（大图是卡面图，圆圈是裁出的脸），跟 QQ 里发的印象卡一样；人泡泡、名单这些小头像照旧是 QQ 头像
const faceOf = (r, s, ring) => r.made_av ? `<img src="/api/madeav/${esc(r.qq)}?w=${s}${ring ? "&face=1" : ""}&v=${r.made_av.v}" alt="" onerror="this.onerror=null;this.src='/api/avatar/${esc(r.qq)}'"` : qlogo(r.qq, s);
// 好感度怎么来的：回忆算出的 + 〈我〉自己的偏心 + 回味后聊天时的加减 + 〈主人〉手调的；13 以上按认识多久封顶；每天只往目标追一部分
const scoreParts = p => { const s = p.score_parts; if(!s || p.qq === OWNER) return "";
  const sg = v => (v > 0 ? "+" : "") + v;
  const capped = s.raw != null && Math.abs(s.raw - p.favor) >= 0.1 ? `<br>不限速的话是 ${s.raw}（每天只往这个数追一部分：最多涨 4、跌 10）` : "";
  const grow = s.grow_cap ? `<br>认识了大约 ${s.grow_cap.known_days} 天，现在最多到 ${s.grow_cap.cap}（认识越久能到越高）` : "";
  return `<br>回忆 ${s.base}${s.lean ? `，〈我〉的偏心 ${sg(s.lean)}${s.lean_why ? `（${esc(s.lean_why)}）` : ""}` : ""}，回味后聊天 ${sg(s.live)}${s.adjust ? `，手调 ${sg(s.adjust)}` : ""}${grow}${capped}`; };
// 投喂过的：bond 关系读口给的档位（1～5），〈卡〉换成这一档的背景画＋雾面玻璃，跟 QQ 里发的那张一样
const ROMAN = ["", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"];
const fedOf = r => { const f = r && r.fed, t = f ? +f.tier || 0 : 0; return t >= 1 ? {...f, tier:Math.min(5, t)} : null; };
const fedArt = (t, w, blur) => `url('/api/feedbg/${t}?w=${w}${blur ? "&blur=1" : ""}')`;
// 〈卡〉正面用哪张画：有专属背景的用那张（香槟金，玻璃亮暗跟着画），投喂过的用这一档的画，都没有就是普通的卡
const artOf = r => { const fd = fedOf(r), cb = r && r.card_bg;
  if(cb) return {fd, cls:` fed own${cb.dark ? " dk" : ""}`, deep:cb.deep, url:(w, b) => `url('/api/cardbg/${r.qq}?w=${w}&v=${cb.v}${b ? "&blur=1" : ""}')`};
  return fd ? {fd, cls:` fed f${fd.tier}`, url:(w, b) => fedArt(fd.tier, w, b)} : null; };
const fedTip = f => `投喂档位 <b>${ROMAN[f.tier]} ${esc(f.tier_name || "")}</b>（${f.tier_count || 5} 档里的第 ${f.tier} 档）<br>累计 ¥${+(+f.total || 0).toFixed(2)}`
  + (f.next_name ? `，再 ¥${+(f.next_amount - f.total).toFixed(2)} 到「${esc(f.next_name)}」` : "，已经是最高一档");
// 好感度刻度上的两道线：过了各能做什么
const UNLOCK = "到 <b>13</b>：〈我〉会主动找 TA、能给 TA 配擦边表情包<br>到 <b>70</b>：TA 能叫〈我〉画图";
const TICKS = [13, 70].map(v => `<b class="tk" style="left:${(v + 80) / 1.6}%"></b>`).join("");
// 〈卡〉正面的三格：熟不熟、直接聊过几句、记得几件事；各管什么写在悬停里
function statsHtml(p, H){
  const kd = p.known_days, st = shortStage(p.stage) || "认识";
  const fam = `熟悉 <b>${p.familiarity ?? 0}</b>：6 以下还不太认识、6～20 眼熟、20 以上熟人，〈我〉跟 TA 说话时看到的就是这个关系`
    + (kd != null ? `<br>认识 ${Math.round(kd)} 天：有回忆的日子，越久前的算得越少（60 天减半）；好感度 13 以上按它封顶，认识越久能到越高` : "");
  const talk = `TA 直接跟〈我〉说过的话（群里叫〈我〉、私聊）<br>聊过 1 句以上，TA 加好友〈我〉自己就通过；2 句以上，看 QQ 时会把 TA 列进可以主动找的人`;
  const mem = `每晚回味从聊天里拆出的和 TA 的事<br>好感度、感情都是从这些回忆算出来的，〈我〉自己挑的专属回忆也从这里来`;
  return `<div class="fc-stats"><div${tip(fam)}><b>${esc(st)}</b><small>${kd != null ? `认识 ${Math.round(kd)} 天` : `熟悉 ${p.familiarity ?? 0}`}</small></div>`
    + `<div${tip(talk)}><b>${p.talks ?? 0}<i>句</i></b><small>直接聊过</small></div>`
    + `<div${tip(mem)}><b>${H ? H.moment_count : 0}<i>件</i></b><small>记得的事</small></div></div>`;
}
function fishCard(qq, p, H, events, hf, st){
  const [tc, tn] = tierOf({...p, qq}), name = p.name || qq, fv = Math.max(-80, Math.min(80, p.favor || 0)), fd = fedOf(p), art = artOf({...p, qq});
  // 感情换成的短字（和她说话时看到的同一套，到了门槛才有），分数放在悬停里；旧后端没给就退回最深三种带分数
  const feel = p.feel ? p.feel.chips : Object.entries(H?.feelings || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => [k, `${k} ${v}`, v]);
  const list = (v, cls="") => (v || []).map(x => `<span class="chip ${cls}">${esc(x)}</span>`).join("");
  const facts = [["叫 TA", hf["称呼"] && esc(hf["称呼"])], ["喜好", list(hf["喜好"])], ["雷区", list(hf["雷区"], "no")],
    ["梗", (hf["梗"] || []).map(g => typeof g === "object" ? `<div class="geng"><span class="chip">${esc(g["梗"])}</span>${g["来历"] ? `<small>${esc(g["来历"])}</small>` : ""}</div>` : `<span class="chip">${esc(g)}</span>`).join("")],
    ["最近", hf["最近"] && esc(hf["最近"])], ["语气", hf["语气"] && esc(hf["语气"])], ["牵挂", list(hf["牵挂"])]].filter(([, v]) => v);
  const pv = hf["私下"] || {}, pvs = [...(pv["心事"] || []), ...(pv["牵挂"] || [])];
  // 专属回忆：〈我〉自己挑的和 TA 的几件事（最多 6 条，新的在后面），新的放上面；面板只有〈主人〉看，私聊的照样列
  const mems = (Array.isArray(hf["回忆"]) ? hf["回忆"] : []).filter(m => m && m["事"]).slice().reverse();
  // 印象怎么变的：最近 4 条，一样的只留最新那条（聊天时记的印象也会进心里的 TA 的印象史）
  const hist = (events.filter(e => e.kind === "impression").reverse().map(e => [e.note, fmtT(e.ts)]).concat((hf["印象史"] || []).map(x => [x["印象"], `用到 ${x["到"]}`])))
    .filter(([t], i, a) => t && a.findIndex(x => x[0] === t) === i).slice(0, 4);
  // 心里的 TA 改过的：她聊天时自己动手改的（heart_edit），每晚回味时发现对不上改掉的（heart_fix）；最近 3 条
  const fixes = events.filter(e => e.kind === "heart_edit" || e.kind === "heart_fix").slice(-3).reverse();
  const att = st.attitude > 0 ? `<span class="att-stamp fc-att-st"${tip(`态度：<b>${ATTS[st.attitude]}</b>${st.reason ? `<br>${esc(st.reason)}` : ""}`)}>${ATTS[st.attitude]}</span>` : "";
  const mood = p.mood ? `<span class="fc-mood" style="--m:${mc(p.mood)}">${esc(p.mood_word || p.mood)}</span>` : "";
  const mid = `<div class="fc-meter"${tip(`好感度 <b>${p.favor ?? 0}</b>（-80 到 80）${scoreParts(p)}<br>${UNLOCK}`)}>${TICKS}<i style="left:${(fv + 80) / 1.6}%"></i></div>
        <div class="fc-meter-l"><span>讨厌</span><span>喜欢</span></div>
        ${statsHtml(p, H)}
        ${feel.length ? `<div class="fc-feel">${feel.map(([k, w, v]) => `<span style="--c:${DIM_C[k]}"${tip(`<b>${k}</b> ${v} 分`)}>${esc(w)}</span>`).join("")}</div>` : ""}
        <div class="fc-quote"><small>〈我〉觉得</small><p>${esc(hf["印象"] || p.impression || "还没有印象～")}</p></div>`;
  // 投喂过的、有专属背景的正面：上面只放画，下面雾面玻璃（玻璃底下那层是后端先糊好的同一张画，卡上不用 filter）；投喂四、五档有一道光扫过，五档还有光点往上飘
  const front = art ? `<div class="fc-face fc-front" style="--art:${art.url(720)};--artb:${art.url(720, 1)}${art.deep ? `;--deep:${art.deep}` : ""}">
      <span class="fc-scene" aria-hidden="true"></span><span class="fc-frost" aria-hidden="true"></span>${fd && fd.tier >= 5 ? `<span class="fc-motes" aria-hidden="true">${"<i></i>".repeat(8)}</span>` : ""}
      <div class="fc-art"><span class="fc-tags">${att}</span><span class="fc-fav">${p.favor ?? 0}</span></div>
      <div class="fc-body">
        <div class="fc-id"><span class="fc-ring">${faceOf({...p, qq}, 320, 1)} data-fly></span>
          <div class="fc-idt"><h2 class="fc-name">${esc(name)}${bm(p)}</h2><p class="fc-sub">${[p.stage && `<span title="${esc(p.stage)}">${esc(shortStage(p.stage))}</span>`, esc(p.favor_desc || tn), mood].filter(Boolean).map((t, i) => `<span>${i ? "· " : ""}${t}</span>`).join("")}</p></div>
          ${fd ? `<span class="fc-rank"${tip(fedTip(fd))}><b>${ROMAN[fd.tier]}</b><small>${esc(fd.tier_name || "")}</small></span>` : ""}</div>
        ${mid}
        <div class="fc-foot"><span>QQ ${esc(qq)} · 认识于 ${fmtT(p.first_met)}</span><span>最近聊天 ${ago(p.last_talk)}</span></div>
      </div>${fd && fd.tier >= 4 ? `<span class="fc-sheen" aria-hidden="true"></span>` : ""}
    </div>` : `<div class="fc-face fc-front">
      <div class="fc-top"><span>QQ ${esc(qq)}</span><span class="fc-tier">${esc(p.favor_desc || tn)}</span></div>
      <div class="fc-art">${faceOf({...p, qq}, 640)} data-fly><span class="holo"></span><span class="fc-tags">${att}${mood}</span><span class="fc-fav">${p.favor ?? 0}</span></div>
      <div class="fc-body">
        <h2 class="fc-name">${esc(name)}${bm(p)}</h2>${p.stage ? `<span class="fc-stage" title="${esc(p.stage)}">${esc(shortStage(p.stage))}</span>` : ""}
        ${mid}
        <div class="fc-foot"><img src="/static/fish.webp" alt=""><span>认识于 ${fmtT(p.first_met)}</span><span>最近聊天 ${ago(p.last_talk)}</span></div>
      </div>
      <span class="holo frame"></span>
    </div>`;
  return `<div class="fc-wrap"><article class="fcard ${tc}${art ? art.cls : ""}" tabindex="0" aria-label="${esc(name)} 的〈卡〉，点一下翻面">
    ${front}
    <div class="fc-face fc-back">
      <div class="fc-top"><span>只有〈我〉知道的</span><span class="fc-tier">${ic("i-lock")}</span></div>
      <div class="fc-back-in">
        ${st.attitude > 0 ? `<p class="fc-att"><span class="att-stamp">${ATTS[st.attitude]}</span>${st.reason ? esc(st.reason) : ""}</p>` : ""}
        ${facts.length ? `<dl class="dl">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>` : `<p class="muted small">还没摸清 TA 的喜好～</p>`}
        ${pvs.length ? `<div class="privbox"><span class="lock">${ic("i-lock")} 私下知道的</span>（私聊里知道的，群里提不提〈我〉自己掂量）<br>${pvs.map(esc).join("；")}</div>` : ""}
        ${mems.length ? `<h3 class="fc-h"${tip("〈我〉自己挑的；TA 跟〈我〉说话时单独一行带给〈我〉，群里也带，私聊那条标着群里别人不知道")}>专属回忆</h3><ol class="fc-hist fc-mem">${mems.map(m => `<li><p>${esc(m["事"])}</p><small>${esc(m["哪天"] || "")}${m["私聊"] ? ` · <span class="lock">${ic("i-lock")}私聊里</span>` : " · 群里"}</small></li>`).join("")}</ol>` : ""}
        ${unsentHtml(H?.unsent)}
        ${fixes.length ? `<h3 class="fc-h">〈我〉改过的</h3><ol class="fc-hist">${fixes.map(e => `<li><p>${esc(e.note)}</p><small>${fmtT(e.ts)} · ${e.kind === "heart_fix" ? "回味时发现对不上" : "聊天时自己改的"}</small></li>`).join("")}</ol>` : ""}
        ${hist.length ? `<h3 class="fc-h">印象怎么变的</h3><ol class="fc-hist">${hist.map(([t, w]) => `<li><p>${esc(t)}</p><small>${esc(w)}</small></li>`).join("")}</ol>` : ""}
      </div>
      <span class="holo frame"></span>
    </div>
  </article><p class="fc-hint">点卡片翻面</p></div>`;
}
// 心里的 TA 说话时按栏位挑（260 字以内），放不下的整栏不带；这里标出这次没带给她的
function unsentHtml(u){
  if(!u) return "";
  const g = u.group || [], d = u.dm || [];
  if(!g.length && !d.length) return "";
  const t = (w, xs) => xs.length ? `${w}没带：${xs.map(esc).join("、")}` : "";
  return `<p class="small muted fc-unsent">${ic("i-info")} 这几项放不下，跟 TA 说话时没带给〈我〉：${[t("群里", g), t("私聊", d)].filter(Boolean).join("；")}</p>`;
}
// 一手扇形的小卡（心里的人总览）；整本卡册在 Album 里
const miniCard = r => { const [tc] = tierOf(r), fd = fedOf(r), art = artOf(r);
  return `<button class="mcard ${tc}${art ? art.cls : ""}" data-qq="${esc(r.qq)}" aria-label="${esc(r.name || r.qq)} 的〈卡〉"${art ? ` style="--art:${art.url(280)}"` : ""}><span class="mc-in"><span class="mc-art">${faceOf(r, 160, !!art)} loading="lazy">${fd ? `<span class="mc-rank">${ROMAN[fd.tier]}</span>` : ""}<span class="holo"></span><span class="mc-fav">${r.favor ?? 0}</span></span>
    <span class="mc-body"><span class="mc-name">${esc(r.name || r.qq)}${bm(r)}</span>${r.stage ? `<span class="mc-stage" title="${esc(r.stage)}">${esc(shortStage(r.stage))}</span>` : ""}<span class="mc-impr">${esc(r.impression || "还没有印象～")}</span></span></span><span class="holo frame"></span></button>`; };

// 一段回忆现在还有多重：按每种感情各自的半衰期淡去（和 bond 的 heart.py 一样的算法）
function weigh(mo, hl){
  const age = Math.max(0, Date.now()/1000 - mo.ts) / 86400;
  let pos = 0, neg = 0, now = 0, init = 0;
  for(const [d, v] of Object.entries(mo.impacts || {})){
    const h = (BAD.has(d) ? 1 : (.6 + .8 * (mo.weight || .4))) * (hl[d] || 45), k = Math.pow(.5, age / h), val = Math.abs(v) * k;
    now += val; init += Math.abs(v);
    // 芥蒂、反感加了是坏事、减了（道歉、和好）是好事；其他感情反过来
    if(BAD.has(d) === (v > 0)) neg += val; else pos += val;
  }
  if(!init) init = 1, now = Math.pow(.5, age / 45);
  return {pos, neg, fresh:now / init, left:now};
}
async function renderPerson(qq, rows, hr){
  Field.pick(qq);
  const [d, ml] = await Promise.all([soft(get("/api/person/" + qq, 20000)), soft(get("/api/memline/node?id=qq:" + qq, 20000))]);
  if(!d) return {left:[card("读不到这个人", fail("档案"), {ic:"i-users"})], right:[], clip:"sigh"};
  const p = d.profile || {}, H = d.heart, hf = H?.heart || {}, f = H?.feelings || {}, st = H?.stance || {}, hl = H?.meta?.half_life || {};
  const row = rows.find(r => r.qq === qq) || {}, name = p.name || qq, dim = topDim(f), color = qq === OWNER ? "#e0a630" : dim ? DIM_C[dim[0]] : "#c9d3ea";
  const moms = (H?.moments || []).map(m => ({...m, w:weigh(m, hl)}));
  // 秤上的总数和倾斜由后端从感情加总算（每天上限、主人规则、芥蒂 ×2、反感 ×4 都套上了）；旧后端没给就退回前端自己加
  const B = H?.balance, pos = B ? B.good : moms.reduce((a, m) => a + m.w.pos, 0), neg = B ? B.bad : moms.reduce((a, m) => a + m.w.neg, 0);
  const tilt = B ? B.tilt : 100 * (pos - neg) / (pos + neg + .5);

  // 左：这张〈卡〉，下面是〈我〉对 TA 的规矩
  const left = [fishCard(qq, p, H, d.events || [], hf, st)];
  const rules = [];
  if(qq !== BOT){
    if(qq !== OWNER) rules.push(`<div class="group">${toggle("proactive.block", d.proactive_blocked, "不要主动找 TA 聊天", "打开后〈我〉不会主动私聊这个人", `data-qq="${esc(qq)}"`)}</div>`);
    if(qq !== OWNER) rules.push(`<div class="group">${toggle("bond.bot", !!p.bot, `TA 是 bot ${ic("i-bot")}`, "程序在说话，不是真人：〈卡〉、印象卡、人泡泡上画小机器人，〈我〉跟 TA 说话时也知道", `data-bot="${esc(qq)}"`)}${p.bot ? botWho(qq, p) : ""}</div>`);
    if(rules.length) left.push(card("〈我〉对 TA 的规矩", rules.join(""), {ic:"i-switch", note:"拨一下马上生效；「设定」里按人那张表是同一个开关"}));
    const fs = d.feeds || [], fed = fs.reduce((a, f) => a + f.amount, 0), fd = fedOf(p);
    if(qq !== OWNER || fs.length) left.push(card("投喂", (fs.length ? `<p class="fed-sum">TA 投喂过〈我〉 <b>¥${+fed.toFixed(2)}</b>（${fs.length} 笔）</p>`
        + (fd ? `<p class="small muted fed-tier">投喂档位 <b>${ROMAN[fd.tier]} ${esc(fd.tier_name || "")}</b>（${fd.tier_count || 5} 档里的第 ${fd.tier} 档）${fd.next_name ? `，再 ¥${+(fd.next_amount - fd.total).toFixed(2)} 到「${esc(fd.next_name)}」` : "，已经是最高一档"}；${p.card_bg ? "〈卡〉用的是专属背景，右上角标着档位" : "〈卡〉换成这一档的样子"}</p>` : "") + feedItems(fs, false)
        : `<p class="small muted" style="margin:0 0 8px">TA 还没投喂过〈我〉</p>`) + feedForm(qq),
      {ic:"i-yen", meta:fs.length ? `<b>¥${+fed.toFixed(2)}</b>` : "", note:"钱在主人那里，这里只记账"}));
    const mp = d.meme_prefs || [];
    if(mp.length) left.push(card("表情包", memePrefs(mp, qq),
      {ic:"i-tail", note:"〈我〉聊天时自己记的：TA 不喜欢的不再给 TA 配，喜欢的给 TA 配时更容易挑到（会慢慢淡）"}));
  }

  // 右：心（天平、形状）+ 回忆（压在心上的、记得的、TA 说的）
  const scale = scaleSvg(moms, pos, neg, tilt) +
    `<div class="scale-cap"><span>好的回忆<b>${pos >= neg && pos > 0 ? mark(pos.toFixed(1), "circle", "#2f5fd0") : pos.toFixed(1)}</b></span><span class="neg">芥蒂和反感<small>（含玩笑那种）</small><b>${neg > pos ? mark(neg.toFixed(1), "circle", "#d8506f") : neg.toFixed(1)}</b></span></div>
     <p class="small muted" style="margin:10px 0 0">好感度照这杆秤算：一件芥蒂抵两件好事，反感抵四件，时间越久越轻；玩笑那种、〈我〉心疼 TA 时记的芥蒂也在秤上，只是不算进〈我〉看到的那句。秤盘里是分量最重的几件事。</p>`;
  const dims = H?.meta?.dims || Object.keys(DIM_C), line = p.feel?.line;
  const said = `<div class="card-b feel-line">${line ? `<p>${esc(line)}</p>` : `<p class="muted">还没有到门槛的感情，这句不带</p>`}<small>〈我〉跟 TA 说话时看到的就是这句（芥蒂、反感会带上为的是哪件事）</small></div>`;
  const right = [card("〈我〉的心", said + tabs([["天平", scale], ["心的形状", radarSvg(f, color, dims, H?.feelings_all) + `<p class="small muted" style="margin:6px 0 0">${dims.length} 种感情，越往外越深；和〈我〉看到的那句是同一份；虚线是全部的芥蒂（含玩笑那种、〈我〉心疼 TA 时记的，好感度照它算）；悬停看分数</p>`]]),
    {ic:"i-heart", cls:"pink", raw:true, meta:dim ? `最深是 <b>${dim[0]}</b>` : ""})];
  const heavy = [...moms].sort((a, b) => b.w.left - a.w.left);
  const MT = {day:"日记忆", week:"周记忆", month:"月记忆", quarter:"季记忆"}, mems = d.memories || [], tiered = mems.filter(m => m.tier).sort((a, b) => (b.ts||0) - (a.ts||0)), raw = mems.length - tiered.length;
  const plain = m => String(m.where || "").replace(/^.+?记忆（.+?）・/, "");
  const heavyH = heavy.length ? tl(heavy.slice(0, 10).map(m => ({attr:` style="--m:${mc(m.feeling)};--fresh:${m.w.fresh.toFixed(2)}"`, cls:"fade",
      h:`${tagM(m.feeling, mc(m.feeling))}<span class="muted small">${esc(m.kind)}</span><span class="age"${tip(`这段回忆还剩 <b>${Math.round(m.w.fresh*100)}%</b> 的分量`)}><i style="width:${Math.round(m.w.fresh*100)}%"></i></span>`,
      t:fmtT(m.ts), p:esc(m.text), s:m.private ? `<span class="lock">${ic("i-lock")}私聊</span>` : esc(m.where)}))) : "";
  const memH = (tiered.length ? tl(tiered.slice(0, 8).map(m => ({h:`<span class="tag blue">${esc(MT[m.tier] || m.tier)}</span>`, t:esc(m.label || fmtT(m.ts)), p:`<span class="clamp"${tip(esc(m.text))}>${esc(m.text)}</span>`, s:esc(plain(m))}))) : "")
    + (raw ? `<div class="callout" style="margin-top:10px">${ic("i-info")}<span>还有 ${raw} 段零碎记忆没压，每天 03:30 合成日记忆</span></div>` : "");
  const saidH = (d.messages || []).length ? tl(d.messages.slice(0, 10).map(m => ({t:fmtT(m.ts), h:`<span class="muted small">${esc(m.where)}</span>`, p:`<span class="clamp2"${tip(esc(m.text))}>${esc(m.text)}</span>`}))) : "";
  right.push(card("和 TA 的事", tabs([["压在心上", heavyH, H?.moment_count || ""], ["记得的事", memH, tiered.length || ""], ["TA 说的话", saidH, (d.messages || []).length || ""]])
    || empty("sleep", "还没回味到和 TA 的事～"), {ic:"i-spark", raw:!!(heavyH || memH || saidH), note:heavy.length ? "回忆按现在还剩多少分量排" : ""}));

  if(ml) right.push(card("〈我〉的记忆线上的 TA", ml.points.length ? tl(ml.points.slice(0, 6).map(x => mlPoint(x, {bare:true}))) : empty("sleep", "记忆线上还没有 TA～"),
    {ic:"i-spark", meta:`<b>${ml.count?.active || 0}</b> 条`, note:"〈我〉自己的记忆里跟 TA 有关的，最新的在上面",
     foot:`<button class="btn alt sm" data-act="mlgo" data-id="qq:${esc(qq)}">看 TA 的记忆</button>`}));
  const th = [{t:`${name}……〈我〉觉得 TA ${hf["印象"] || p.impression || "还不太熟"}`}, {t:`给 TA 的〈卡〉是「${tierOf({...p, qq})[1]}」那一档，翻过来是〈我〉的心里话～`}];
  if(dim) th.push({t:`对 TA 最深的感情是${dim[0]}，有 ${dim[1]} 分～`});
  if(heavy[0]) th.push({t:`最忘不掉的是：${heavy[0].text}`, s:`${fmtT(heavy[0].ts)} · ${heavy[0].feeling}`});
  if(st.attitude > 0) th.push({t:`哼，〈我〉现在对 TA 还在${ATTS[st.attitude]}～`});
  const clip = st.attitude > 0 ? "pout" : qq === OWNER ? "love" : (f["亲近"]||0) >= 50 ? "hop" : "think";
  const kpi = [["好感度", p.favor ?? 0, "", (p.favor || 0) < -13 ? "bad" : "", "-80 到 80" + scoreParts(p)], ["熟悉", p.familiarity ?? 0, "", "", "6 以下还不太认识、6～20 眼熟、20 以上熟人" + (p.known_days != null ? `<br>认识 ${Math.round(p.known_days)} 天（有回忆的日子）` : "")],
    ["聊过", p.talks ?? 0, "句", "", "TA 直接跟〈我〉说过的话<br>1 句以上加好友自动通过；2 句以上会被列进可以主动找的人"],
    ["回忆", H ? H.moment_count : 0, "段", "", "每晚回味拆出的和 TA 的事；好感度、感情都从这里算"],
    st.attitude > 0 && ["态度", ATTS[st.attitude], "", "warn", esc(st.reason || "")]];
  // 名字是 QQ 昵称；在群里的群名片不一样的列在这（最多 3 个）
  const gc = (p.group_cards || []).slice(0, 3).map(c => `${esc(c.group)}叫「${esc(c.card)}」`).join("、");
  return {left, right, thoughts:th, clip, kpi, title:name, sub:`${p.stage ? shortStage(p.stage) + " · " : ""}${gc ? "群名片：" + gc + " · " : ""}最近聊天 ${ago(p.last_talk)} · Esc 或点空白处回到一圈人`};
}
// 天平：横梁按轻重倾斜，两边秤盘里放着一颗颗回忆
function scaleSvg(moms, pos, neg, tilt){
  const ang = Math.max(-16, Math.min(16, -tilt * .18));
  const balls = side => moms.filter(m => side ? m.w.neg > .05 : m.w.pos > .05).sort((a, b) => (side ? b.w.neg - a.w.neg : b.w.pos - a.w.pos)).slice(0, 9)
    .map((m, i) => { const r = 4 + Math.min(6, (side ? m.w.neg : m.w.pos) * 3); const row = Math.floor(i / 3), colx = (i % 3 - 1) * 15 + (row % 2) * 5;
      return `<circle cx="${colx}" cy="${-r - row * 10}" r="${r.toFixed(1)}" fill="${mc(m.feeling)}" stroke="#fff" stroke-width="1.2"${tip(`<span class="pill-m" style="--m:${mc(m.feeling)}">${esc(m.feeling)}</span> ${esc(m.text)}<br><small>${fmtT(m.ts)} · 还记得 ${Math.round(m.w.fresh * 100)}%</small>`)}/>`; }).join("");
  return `<svg class="scale" viewBox="0 0 300 170" data-ang="${ang.toFixed(2)}" aria-label="好的回忆 ${pos.toFixed(1)}，芥蒂和反感 ${neg.toFixed(1)}">
    <path d="M150 158 L150 44" stroke="#5a6a96" stroke-width="3" stroke-linecap="round"/>
    <path d="M118 162 Q150 146 182 162 Z" fill="#c9d6ee"/>
    <g class="beam"><line x1="40" y1="40" x2="260" y2="40" stroke="#1c2b66" stroke-width="4" stroke-linecap="round"/>
      <circle cx="150" cy="40" r="7" fill="#e7799b" stroke="#fff" stroke-width="2"/></g>
    <g class="pan L"><line x1="0" y1="0" x2="-26" y2="56" stroke="#8a97b8"/><line x1="0" y1="0" x2="26" y2="56" stroke="#8a97b8"/>
      <g transform="translate(0,56)">${balls(0)}</g><path d="M-34 56 Q0 78 34 56 Z" fill="#8ec9f2" opacity=".85"/></g>
    <g class="pan R"><line x1="0" y1="0" x2="-26" y2="56" stroke="#8a97b8"/><line x1="0" y1="0" x2="26" y2="56" stroke="#8a97b8"/>
      <g transform="translate(0,56)">${balls(1)}</g><path d="M-34 56 Q0 78 34 56 Z" fill="#f3a3bd" opacity=".85"/></g>
  </svg>`;
}
// 感情的雷达（几种由 bond 给，10-27 起六种）：形状由 FX 从中心长出来
// f 是给她看的那份；all 是全部的（含玩笑、她心疼 TA 时记的芥蒂，好感度照这个算），不一样的那几轴画一圈虚线
function radarSvg(f, color, dims, all){
  const ks = dims || Object.keys(DIM_C), n = ks.length, C = 150, Y = 116, R = 76;
  const pt = (i, v) => { const a = -Math.PI/2 + i * 2*Math.PI/n; return [C + Math.cos(a) * R * v, Y + Math.sin(a) * R * v]; };
  const ring = v => ks.map((_, i) => pt(i, v).map(x => x.toFixed(1)).join(",")).join(" ");
  return `<svg class="radar" viewBox="0 0 300 232" data-radar="${esc(JSON.stringify(ks.map(k => f[k] || 0)))}" data-cx="${C}" data-cy="${Y}" data-r="${R}" style="--c:${color}"
      aria-label="${esc(ks.map(k => k + " " + (f[k] || 0)).join("，"))}">
    ${[.25, .5, .75, 1].map(v => `<polygon class="rd-grid" points="${ring(v)}"/>`).join("")}
    ${ks.map((k, i) => { const [x, y] = pt(i, 1), [lx, ly] = pt(i, 1.24), cs = Math.cos(-Math.PI/2 + i * 2*Math.PI/n);
      return `<line class="rd-axis" x1="${C}" y1="${Y}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"/><text class="rd-l${BAD.has(k) ? " bad" : ""}" x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="${cs > .3 ? "start" : cs < -.3 ? "end" : "middle"}" dominant-baseline="middle">${k}<tspan dx="4">${f[k] || 0}</tspan>${all && (all[k] || 0) !== (f[k] || 0) ? `<tspan class="rd-all" dx="2">/${all[k] || 0}</tspan>` : ""}</text>`; }).join("")}
    ${all && ks.some(k => (all[k] || 0) !== (f[k] || 0)) ? `<path class="rd-ghost" d="M${ks.map((k, i) => pt(i, Math.min(1, (all[k] || 0) / 100)).map(x => x.toFixed(1)).join(",")).join("L")}Z"/>` : ""}
    <polygon class="rd-shape"/>
    ${ks.map(k => { const a = all && (all[k] || 0) !== (f[k] || 0) ? all[k] || 0 : null;
      return `<circle class="rd-dot" r="4.5" fill="${DIM_C[k]}"${tip(`<b>${k}</b> ${f[k] || 0} 分` + (a != null ? `<br>全部是 ${a} 分（虚线）：玩笑那种、〈我〉在心疼 TA 时记的不算进给〈我〉看的这份，好感度照全部的算` : ""))}/>`; }).join("")}
  </svg>`;
}

// ---------- 记忆深处 ----------
// 相处经验：〈我〉每晚从大家的反应里记下的几件事，聊天时会带上；要跟着最新的人设和主人定的规矩走
function notesCard(ev){
  const ns = ev.notes || [], last = (ev.changes || [])[0];
  const items = ns.map((n, i) => ({m:"var(--brand)", h:`<b>${i + 1}</b>`, t:fmtT(n.ts), p:esc(n.text),
    s:n.from ? `依据：${esc(n.from)}` : "", x:`<button class="btn sm danger" data-act="note" data-i="${i}" style="margin-top:4px">删掉</button>`}));
  const rules = (ev.rules || []).length ? `<p class="small muted" style="margin:8px 0 0">主人定的规矩：${ev.rules.map(esc).join("；")}</p>` : "";
  const state = ev.busy ? "〈我〉正在整理……" : ev.aligned ? "跟现在的人设、规矩对过了" : "人设或规矩改过了，一分钟内会按最新的重整";
  return card("相处经验", (ns.length ? tl(items) : empty("sleep", "还没记下什么～")) + rules
      + (last ? `<p class="small muted" style="margin:8px 0 0">上次${last.kind === "notes_align" ? "按新人设重整" : "每晚复盘"}（${fmtT(last.ts)}）：${esc(last.text || "")}${(last.dropped || []).length ? `；删改了 ${last.dropped.length} 条：${last.dropped.map(d => esc(d.text) + (d.why ? `（${esc(d.why)}）` : "")).join("；")}` : ""}</p>` : ""),
    {ic:"i-book", meta:`<b>${ns.length}</b> 条`, note:`每晚 4:30 从昨天大家的反应里记的，聊天时会带上（只是参考，人设和分寸为准）。${state}`,
     foot:`<button class="btn alt sm" data-act="notes" data-a="align">重整</button><button class="btn alt sm" data-act="notes" data-a="rewrite">重写</button>`});
}
// 〈主人〉交代的事：她用 lively_owner_rule 记的，挂在某个人、某个群身上的到那儿才带，到哪都算的每轮都带；主人能删
function asksCard(as){
  const items = as.map(a => ({m:"var(--brand)", h:`<b>交代${esc(a.id)}</b> <span class="small muted">${esc(a.where)}</span>`, t:fmtT(a.ts),
    p:esc(a.text), s:`${esc(a.src)}交代的${a.updated > a.ts + 60 ? ` · ${fmtT(a.updated)} 改过` : ""}`,
    x:`<button class="btn sm danger" data-act="ask" data-id="${esc(a.id)}" style="margin-top:4px">删掉</button>`}));
  return card("〈主人〉交代的事", as.length ? tl(items) : empty("sleep", "〈主人〉还没交代过什么～"),
    {ic:"i-list", meta:as.length ? `<b>${as.length}</b> 条` : "", note:"〈主人〉交代、〈我〉记在随身本子上的：挂在谁身上的，TA 说话、被提到时带着；挂在群上的在那个群带；到哪都算的每轮都带"});
}
// 〈我〉自己的事：她用 lively_self_note 记的，每一轮、每个聊天都带；谁说的都能记，不是〈主人〉说的标出来；主人能删
function selfNotesCard(ns){
  const n = ns.reduce((a, x) => a + (x.text || "").length, 0);
  const items = ns.map(x => ({m:x.owner ? "var(--brand)" : "var(--warn)", h:`<b>S${esc(x.id)}</b> <span class="small muted">${esc(x.who)}</span>`, t:fmtT(x.ts),
    p:esc(x.text), s:[x.where ? `在${esc(x.where)}记的` : "", x.updated > x.ts + 60 ? `${fmtT(x.updated)} 改过` : ""].filter(Boolean).join(" · "),
    x:`<button class="btn sm danger" data-act="selfnote" data-id="${esc(x.id)}" style="margin-top:4px">删掉</button>`}));
  return card("〈我〉自己的事", ns.length ? tl(items) : empty("sleep", "〈我〉还没记自己的事～"),
    {ic:"i-book", meta:ns.length ? `<b>${ns.length}</b> 条 · ${n}/800 字` : "", note:"〈我〉自己记在随身本子上的：住在哪、手上有什么、最近自己变了什么。每一轮、每个聊天都带着；不是〈主人〉说的标了黄色"});
}
// 记忆线的纸：一条记忆点（谁说的、在哪、谁记的；能看原话和前后变化，〈主人〉能改、忘、找回——都不真删）
const BY = {owner:["〈主人〉说的", "var(--brand)"], her:["〈我〉自己记的", "var(--good)"], import:["从旧记忆搬来的", "var(--faint)"]};
const PST = {replaced:"被取代了", forgot:"忘掉了"};
function mlPoint(p, o={}){
  const by = BY[p.by], told = (p.told_by || []).map(t => esc(t.name)).join("、");
  const btn = (act, label, cls="alt") => `<button class="btn sm ${cls}" data-act="${act}" data-id="${p.id}"${act === "mledit" ? ` data-t="${esc(p.text)}"` : ""}>${label}</button>`;
  const btns = [btn("mlpt", "原话和前后"), p.status === "active" && btn("mledit", "改"), p.status === "active" && btn("mlforget", "忘掉", "danger"), p.status === "forgot" && btn("mlrestore", "找回来")];
  return {m:p.status === "active" ? (by ? by[1] : "var(--tip)") : "var(--faint)", cls:p.status === "active" ? "" : "fade",
    h:`<b>#${p.id}</b>${p.kind ? ` <span class="tag">${esc(p.kind)}</span>` : ""}${by ? ` ${tagM(by[0], by[1])}` : ""}${PST[p.status] ? ` ${tagM(PST[p.status], "var(--faint)")}` : ""}${p.private ? ` <span class="lock">${ic("i-lock")}私聊</span>` : ""}`,
    t:fmtT(p.at), p:(told ? `<span class="small muted">${told} 说的、不是本人说的：</span>` : "") + esc(p.text),
    s:[p.where, !o.bare && (p.who || []).length ? "和 " + p.who.slice(0, 5).map(w => esc(w.name)).join("、") : "", p.replaced_by ? `后来是 #${p.replaced_by}` : ""].filter(Boolean).join(" · "),
    x:`<div class="ml-btns">${btns.filter(Boolean).join("")}</div><div class="ml-more" id="mlp${p.id}" hidden></div>`};
}
function mlDetail(d){
  const STATE = {active:"现在", replaced:"被取代", forgot:"忘掉了"};
  const hist = (d.history || []).length > 1 ? `<h4>前后变化（旧→新）</h4><ol class="ml-hist">${d.history.map(c => `<li class="${c.id === d.id ? "me" : ""}"><b>#${c.id}</b> <small>${fmtT(c.at)} · ${STATE[c.status] || c.status}${BY[c.by] ? " · " + BY[c.by][0] : ""}</small><p>${esc(c.text)}</p></li>`).join("")}</ol>` : "";
  const lines = (d.lines || []).length ? `<h4>当时的原话</h4><ol class="ml-src">${d.lines.map(l => `<li class="${l.mine ? "mine" : ""}"><small>${fmtT(l.ts)}${l.where ? " · " + esc(l.where) : ""}</small><b>${esc(l.who)}</b>${esc(l.text)}</li>`).join("")}</ol>`
    : `<p class="small muted">${d.imported ? "从旧记忆（LivingMemory、回味）搬来的，没有逐句的原话" : "没留原话（〈我〉或〈主人〉直接记的）"}</p>`;
  const edges = (d.edges || []).length ? `<h4>连上的线</h4><p class="small">${d.edges.map(e => `${esc(e.src)} <i>${esc(e.rel)}</i> ${esc(e.dst)}${e.until ? "（到期了）" : ""}`).join("；")}</p>` : "";
  return hist + lines + edges;
}
// 中间那张网的说明＋每种点的名单（窄屏看不到网，就靠这张）
function mlCard(g, sel){
  const s = g.stats, by = k => g.nodes.filter(n => n.kind === k), mx = Math.max(1, ...g.nodes.map(n => n.n));
  const rows = ns => blist(ns.map(n => ({lb:esc(n.name), v:n.n, w:n.n / mx, c:n.owner ? "#e0a630" : undefined, attr:` data-act="mlgo" data-id="${esc(n.id)}"`,
    img:n.kind === "person" ? av(n.id.slice(3), 40) : "", sub:`最近 ${ago(n.last)} 想起`})));
  const inj = {dm:"私聊里每轮带几条；群里、看 QQ 时还没带", all:"私聊、群里每轮都带几条", off:"现在不带，只记"}[g.inject] || g.inject;
  return card("记忆线", `<div class="stats">${stat("记忆点", N(s.points), `被取代 ${s.replaced} · 忘掉 ${s.forgot}`)}${stat("人", N(s.people), `群 ${s.groups} 个`)}${stat("事和梗", N(s.things), `线 ${s.edges} 条`)}</div>`
    + tabs([["人", rows(by("person")), by("person").length], ["群", rows(by("group")), by("group").length], ["事和梗", rows(by("thing")), by("thing").length]])
    + `<p class="small muted ml-foot">时间线 ${s.timeline} 条，还有 ${s.pending} 条没抽成记忆；${s.imported} 条是从旧记忆搬来的，〈主人〉说的 ${s.by_owner} 条、〈我〉自己记的 ${s.by_her} 条${s.no_vec ? `；${s.no_vec} 条还没算向量（想起来时只按字找）` : ""}。${esc(inj)}</p>`,
    {ic:"i-spark", raw:true, meta:`<b>${s.points}</b> 条`, note:"〈我〉自己的记忆里有哪些人、群、事和梗，后面的数是记得几条。点一个看〈我〉记得什么",
     foot:sel ? `<button class="btn alt sm" data-act="mlgo" data-id="">回到全貌</button>` : ""});
}
function mlNodeCard(d){
  const c = d.count || {}, kind = ML_KIND[d.kind] || "", qq = d.id.startsWith("qq:") ? d.id.slice(3) : "";
  const edges = (d.edges || []).length ? `<ul class="ml-edges">${d.edges.map(e => `<li><button class="lnk" data-act="mlgo" data-id="${esc(e.other)}">${esc(e.other_name || e.other)}</button><span>${e.out ? `${esc(d.name)} <i>${esc(e.rel)}</i> TA` : `TA <i>${esc(e.rel)}</i> ${esc(d.name)}`}</span><small>${fmtT(e.since)}</small></li>`).join("")}</ul>` : "";
  const pts = d.points.length ? tl(d.points.map(p => mlPoint(p))) : empty("sleep", "还没记得 TA 什么～");
  return card(`${esc(d.name)}${kind ? ` <small class="muted">${kind}</small>` : ""}`, tabs([["记得的", pts, c.active || ""], ["线", edges, (d.edges || []).length || ""], ["以前的", (d.old || []).length ? tl(d.old.map(p => mlPoint(p))) : "", (c.replaced || 0) + (c.forgot || 0) || ""]]) || `<div class="card-b">${pts}</div>`,
    {ic:d.kind === "person" ? "i-users" : "i-spark", raw:true, meta:`<b>${c.active || 0}</b> 条`,
     note:[(d.aliases || []).length ? "也叫：" + d.aliases.filter(a => a !== d.name).slice(0, 6).map(esc).join("、") : "", d.first ? `第一次记下 ${fmtT(d.first)}，最近 ${ago(d.last)}` : ""].filter(Boolean).join(" · ") + "。〈主人〉改了是记一条新的取代旧的，忘了能找回，都留着",
     foot:(qq ? `<button class="btn alt sm" data-act="mlperson" data-qq="${esc(qq)}">看 TA 的〈卡〉</button>` : "") + `<button class="btn alt sm" data-act="mlgo" data-id="">收起</button>`});
}
// 待认：旧资料里只知道名字、对不上 QQ 号的（同名的几个人，或者没在群里见过）；〈主人〉认给一个人，或者认成一件事、一个梗
function mlUnknownCard(us){
  const items = us.map((u, k) => ({m:"#e9724f", h:`<b>？${esc(u.name)}</b> <span class="small muted">${u.n} 条记忆</span>`,
    p:u.points.slice(0, 2).map(p => `<span class="clamp2"${tip(esc(p.text))}>#${p.id} ${esc(p.text)}</span>`).join(""),
    x:`<div class="ml-btns">${u.cands.map(c => `<button class="btn sm alt" data-act="mlclaim" data-node="${esc(u.id)}" data-to="${esc(c.id.slice(3))}"${tip(`QQ ${esc(c.id.slice(3))}${c.aliases.length ? "<br>也叫：" + c.aliases.map(esc).join("、") : ""}<br>记了 ${c.n} 回`)}>是「${esc(short(c.name, 8))}」</button>`).join("")}
      <button class="btn sm alt" data-act="mlclaim" data-node="${esc(u.id)}" data-to="thing">是个梗</button></div>
      <div class="ml-btns ml-qq"><input id="mlq${k}" inputmode="numeric" placeholder="或者写 TA 的 QQ 号" aria-label="${esc(u.name)} 的 QQ 号"><button class="btn sm" data-act="mlclaim" data-node="${esc(u.id)}" data-k="${k}">认这个号</button></div>`}));
  return card("待认的名字", tl(items), {ic:"i-users", cls:"alarm-soft", meta:`<b>${us.length}</b> 个`,
    note:"旧资料里只有名字、对不上 QQ 号的。认了以后这些记忆挂到那个人身上，以后这个名字也认得出来"});
}
// 时间线（简易版）：〈我〉看到、说的、做的、想的，一句一行，新的在上面；按地方筛、翻页；抽成了记忆的标出是哪条，点了在右边看
const TL = {place:"", page:0, data:null}, TL_PAGE = 30;
const TL_WHO = {said:"〈我〉", tool:"〈我〉做", did:"〈我〉做", thought:"〈我〉想", backstage:"后台的事"};
function tlBody(){
  const d = TL.data; if(!d) return fail("时间线");
  const name = Object.fromEntries(d.places.map(p => [p.place, p.name])), made = {};
  for(const p of d.points) for(const i of p.src) (made[i] ||= []).push(p.id);
  const rows = d.lines.filter(l => !TL.place || l.place === TL.place).reverse(), pages = Math.max(1, Math.ceil(rows.length / TL_PAGE));
  TL.page = Math.min(TL.page, pages - 1);
  const part = rows.slice(TL.page * TL_PAGE, (TL.page + 1) * TL_PAGE);
  const chips = `<div class="mchips">${[["", "全部", d.lines.length], ...d.places.slice(0, 10).map(p => [p.place, short(p.name, 12), p.n])]
    .map(([k, n, c]) => `<button class="mchip" data-act="tlplace" data-p="${esc(k)}" aria-pressed="${k === TL.place}">${esc(n)}<em>${c}</em></button>`).join("")}</div>`;
  const items = part.map(l => { const ids = made[l.id] || [];
    return `<li class="tlr k-${esc(l.kind)}${l.done ? "" : " todo"}"><time>${fmtT(l.ts)}</time><p>${TL.place ? "" : `<small>${esc(name[l.place] || l.place)}</small>`}<b>${esc(l.kind === "heard" ? l.who : TL_WHO[l.kind] ?? l.kind)}</b>${esc(l.text)}`
      + ids.slice(0, 3).map(i => ` <button class="lnk" data-act="mlgo" data-id="pt:${i}">→ #${i}</button>`).join("") + `</p></li>`; }).join("");
  const nav = pages > 1 ? `<div class="ml-btns tl-nav"><button class="btn alt sm" data-act="tlpage" data-d="-1"${TL.page ? "" : " disabled"}>新一点</button><small class="muted">${TL.page + 1} / ${pages}</small><button class="btn alt sm" data-act="tlpage" data-d="1"${TL.page < pages - 1 ? "" : " disabled"}>更早</button></div>` : "";
  return chips + (part.length ? `<ol class="tlrows">${items}</ol>` : empty("sleep", "这里还没有动静～")) + nav;
}
function tlCard(d){
  TL.data = d;
  const todo = d ? d.lines.filter(l => !l.done).length : 0;
  return card("时间线", `<div id="tlBox">${tlBody()}</div>`, {ic:"i-list", meta:d ? `<b>${d.lines.length}</b> 句` : "",
    note:`〈我〉最近三天看到、说的、做的、想的，一句一行，新的在上面；背景隔一会儿从这里抽成记忆，抽成了的后面标着是哪条${todo ? `（还有 ${todo} 句没抽，标了浅色）` : ""}`});
}
const tlRedraw = () => { const el = $("#tlBox"); if(el){ el.innerHTML = tlBody(); FX.decorate?.(el); More.check(); } };
async function renderMemory(sub){
  const [hr, ev, g, tm] = await Promise.all([soft(get("/api/heart")), soft(get("/api/evolve")), soft(get("/api/memline")), soft(get("/api/memline/time?hours=72"))]), h = new Date().getHours();
  const left = [], right = [], th = [];
  let kpi = [];
  // 三页：〈我〉记得的（""）、〈我〉的感受（feel）、〈主人〉定的（owner），每页 [左, 右]；待认的名字在「待你裁决」，忘掉的在「记录」
  const V = {"":[[], []], feel:[[], []], owner:[[], []]};
  if(g){
    const s = g.stats, top = g.nodes.find(n => n.kind === "person" && !n.owner);
    th.push({t:`〈我〉记得 ${s.points} 件事，跟 ${s.people} 个人有关～`});
    if(top) th.push({t:`除了〈主人〉，记得最多的是${top.name}，有 ${top.n} 条～`});
    if(g.unknowns.length) th.push({t:`还有 ${g.unknowns.length} 个名字〈我〉对不上是谁，〈主人〉在「待你裁决」帮〈我〉认一下～`});
    // 点开一条记忆（时间线、刚记下的里点的）：右边先放这一条的原话和前后，再放时间线
    if(sub?.startsWith("pt:")){
      const d = await soft(get("/api/memline/point?id=" + sub.slice(3), 20000));
      if(d) return {left:[mlCard(g, sub)], title:`记忆 #${d.id}`, sub:d.where || "记忆线", clip:"think",
        right:[card(`记忆 #${d.id}`, tl([mlPoint(d)]) + `<div class="ml-more">${mlDetail(d)}</div>`, {ic:"i-spark", foot:`<button class="btn alt sm" data-act="mlgo" data-id="">收起</button>`}), tlCard(tm)],
        thoughts:[{t:`〈我〉记得……${d.text}`}]};
    }
    if(sub && !V[sub]){
      const d = await soft(get("/api/memline/node?id=" + encodeURIComponent(sub), 20000));
      if(d) return {left:[mlCard(g, sub)], right:[mlNodeCard(d)], title:d.name,
        kpi:[["记得的", d.count?.active || 0, "条"], ["以前的", (d.count?.replaced || 0) + (d.count?.forgot || 0), "条"], ["线", (d.edges || []).length, "条"]],
        thoughts:[{t:d.points[0] ? `说到${d.name}……〈我〉记得${d.points[0].text}` : `${d.name}……〈我〉想不起什么～`}], sub:`${ML_KIND[d.kind] || ""} · 记忆线`, clip:"think"};
    }
    V[""][0].push(mlCard(g));
    V[""][1].push(tlCard(tm));
    V[""][1].push(card("刚记下的", (g.recent || []).length ? tl(g.recent.map(p => mlPoint(p))) : empty("sleep", "还没从聊天里记下什么～"),
      {ic:"i-book", note:"背景从〈我〉看到、说的话里抽出来的，最新的在上面"}));
  } else V[""][0].push(card("记忆线", fail("记忆"), {ic:"i-spark"}));
  if(hr?.ready){
    const pct = hr.memories ? Math.min(100, Math.round(hr.digested / hr.memories * 100)) : 0;
    V.feel[0].push(card("〈我〉在回味", `<div class="stats">${stat("回忆", `<span class="n">${hr.moments}</span>`, "拆成和每个人的片段")}${stat("和这些人", `<span class="n">${hr.people}</span>`, "有过一起的事")}</div>
      <div class="prog"><i style="width:${pct}%"></i></div>
      <p class="small muted" style="margin:0">${hr.init_done ? "以前的记忆都回味完了，以后每晚 4 点到 9 点回味" : `旧记忆回味了 ${hr.digested}/${hr.memories} 条，每半小时一批`}；上次 ${fmtT(hr.last_digest)}</p>`, {ic:"i-spark", meta:`<b>${pct}%</b>`}));
    const fw = Object.entries(hr.feelings_week || {}), mx = Math.max(1, ...fw.map(([, n]) => n));
    V.feel[0].push(card("这几天的感受", fw.length ? cbar(fw.slice(0, 8).map(([k, n]) => [k, n, mc(k), `<b>${esc(k)}</b> ${n} 段回忆`]), false)
        + `<div style="margin-top:4px">${blist(fw.slice(0, 8).map(([k, n]) => ({lb:tagM(k, mc(k)), v:n, w:n / mx, c:mc(k)})))}</div>` : empty("sleep", "这几天还没回味出感受～"),
      {ic:"i-heart", cls:"pink", note:"回忆里记下的当时的感受"}));
    th.push({t:`〈我〉记得和 ${hr.people} 个人的 ${hr.moments} 段事～`});
    if(!hr.init_done) th.push({t:`还有 ${hr.memories - hr.digested} 条旧记忆没回味完，慢慢来～`});
    if(fw[0]) th.push({t:`这几天最多的感受是${fw[0][0]}，有 ${fw[0][1]} 次……`});
    kpi = [["回忆", hr.moments, "段"], ["和这些人", hr.people, "个"], ["回味进度", pct, "%", pct < 100 ? "warn" : ""], ["上次回味", fmtT(hr.last_digest)]];
    if(g) kpi = [["记忆点", g.stats.points, "条"], ["人", g.stats.people, "个"], ["事和梗", g.stats.things, "个"], g.unknowns.length && ["待认", g.unknowns.length, "个", "warn", "对不上 QQ 号的名字，在左边认"], ["回忆", hr.moments, "段"]];
  } else V.feel[0].push(card("〈我〉在回味", fail("回忆"), {ic:"i-spark"}));
  if(g && !kpi.length) kpi = [["记忆点", g.stats.points, "条"], ["人", g.stats.people, "个"], ["事和梗", g.stats.things, "个"], g.unknowns.length && ["待认", g.unknowns.length, "个", "warn"]];
  if(ev) V.owner[1].push(notesCard(ev));
  const LAY = [["raw", "零碎记忆", "聊完马上记下，还没压", "#8fcaf2"], ["day", "日记忆", "每天 03:30 把零碎的压成一天一条", "#5f9ee8"], ["week", "周记忆", "七天压成一条", "#4a7ad6"],
    ["month", "月记忆", "四周压成一条", "#3a5bb8"], ["quarter", "季记忆", "最深的地方", "#26398a"]], tc = hr?.tiers;
  V[""][1].push(card("记忆一层层往下沉", `<div class="layers">${LAY.map(([k, n, s, c], i) => `<div class="layer" style="--lc:${c};margin-left:${i*10}px"><b>${n}</b><small>${s}</small>${tc ? `<em>${tc[k] || 0}<i>条</i></em>` : ""}</div>`).join("")}</div>`
      + (hr?.merged ? `<p class="small muted" style="margin:10px 0 0">另有 ${hr.merged} 条已经压进下一层了，原文留着、不再单独翻出来</p>` : ""),
    {ic:"i-list", meta:tc ? `<b>${Object.values(tc).reduce((a, v) => a + v, 0)}</b> 条` : "", note:"新的在上面，越久的压得越深越短；回味时把每段拆成和每个人的回忆"}));
  if(hr?.ready) V.feel[1].push(selfNotesCard(hr.self_notes || []));
  if(hr?.ready) V.owner[0].push(asksCard(hr.asks || []));
  if(hr?.ready) V.feel[1].push(card("刚回味到的", (hr.recent || []).length ? tl(hr.recent.slice(0, 4).map(momentItem)) : empty("sleep", "还没回味到什么～"), {ic:"i-book", meta:hr.last_digest ? `上次回味 ${fmtT(hr.last_digest)}` : "", note:"每晚 4～9 点回味白天的记忆时记下的，带着当时的感受"}));
  const view = V[sub] ? sub || "" : "";
  left.push(card("记忆", `<div class="mchips">${[["", "〈我〉记得的"], ["feel", "〈我〉的感受"], ["owner", "〈主人〉定的"]].map(([k, n]) => `<button class="mchip" data-go="memory${k ? "/" + k : ""}" aria-pressed="${k === view}">${n}</button>`).join("")}</div>`,
    {ic:"i-book", note:"待认的名字在「待你裁决」，忘掉的记忆在「记录」"}), ...V[view][0]);
  right.push(...V[view][1]);
  return {left, right, thoughts:th, kpi, sub:"聊过的事一层层沉下去，每晚回味成和每个人的回忆", clip:h >= 4 && h < 9 || h < 6 ? "sleep" : "file"};
}

// ---------- 群里 ----------
async function renderGroups(){
  const stP = soft(get("/api/settings", 10000));
  const ov = await soft(get("/api/overview"));
  if(!ov) return {left:[card("群里", fail("群聊"), {ic:"i-bubbles"})], right:[], clip:"look"};
  const {g, t, gmsg, replies} = todayOf(ov), ev = t["群里的事"] || [];
  const users = ov.hourly.users.map((v, i) => v + ov.hourly.bot[i]), mx = Math.max(1, ...users), peak = users.indexOf(Math.max(...users));
  const gs = Object.entries(g).sort((a, b) => b[1]["群消息"] - a[1]["群消息"]), gmax = Math.max(1, ...gs.map(([, v]) => v["群消息"]));
  const left = [card("今天的群", gs.length ? blist(gs.map(([n, v]) => { const rate = v["群消息"] ? Math.round(v["〈我〉回复"] / v["群消息"] * 100) : 0;
      return {lb:esc(n), sub:`回了 ${v["〈我〉回复"]} 句 · ${rate}%`, v:v["群消息"], w:v["群消息"] / gmax}; })) : empty("sleep", "今天群里还没人说话～"), {ic:"i-bubbles", note:"条长是今天的消息数，小字是〈我〉回了几句、插嘴率"}),
    card("一天里什么时候热闹", `<div class="heat">${users.map((u, i) => `<i class="${i === peak && u ? "pk" : ""}" style="height:${Math.max(3, Math.sqrt(u / mx) * 100)}%"${tip(`<b>${i} 点</b> ${u} 条`)}></i>`).join("")}</div>
      <div class="heat-ax">${[0, 6, 12, 18, 23].map(h => `<span style="grid-column:${h + 1}">${h}</span>`).join("")}</div>`, {ic:"i-chart", meta:users[peak] ? `最热闹 <b>${peak}</b> 点` : ""})];
  // 每个群现在的开关：这里只看，改在「设定」的按群那张表
  const st = await stP, sgs = st?.comic?.groups?.length ? st.comic.groups : st?.brain?.groups || [];
  if(sgs.length){
    const rows = sgs.map(g => { const c = st.comic?.groups?.find(x => x.gid === g.gid), b = st.brain?.groups?.find(x => x.gid === g.gid), chips = [];
      if(c) chips.push(`<span class="chip${c.on && st.comic.enabled ? " on" : ""}">群漫画${c.on && st.comic.enabled ? "开" : "关"}</span>`);
      if(b) chips.push(`<span class="chip${b.full ? " on" : ""}">${b.full ? "满血版" : "降智版"}</span>`);
      return `<div class="gst"><b>${esc(g.name || g.gid)}</b><span>${chips.join("")}</span></div>`; }).join("");
    left.push(card("每个群的开关", rows, {ic:"i-switch", note:"这里只看；要改去「设定」的按群那张表", foot:`<button class="btn alt sm" data-go="set/groups">${ic("i-switch")}去设定改</button>`}));
  }
  const right = [card("群里在聊什么", ev.length ? tl(ev.slice(0, 6).map(e => ({h:`<b>${esc(e["群"])}</b>`, x:`<div style="margin-top:4px">${(e["话题"] || []).slice(0, 4).map(x => `<span class="tag blue">${esc(x)}</span>`).join("")}</div>`,
      p:`<span class="clamp"${tip(esc(e["摘要"]))}>${esc(e["摘要"])}</span>`}))) : empty("sleep", "今天群里还没发生什么事～"), {ic:"i-spark", note:"群分析插件整理的话题和摘要"})];
  const th = [];
  if(gs[0]) th.push({t:`今天 ${gs[0][0]} 最热闹，${gs[0][1]["群消息"]} 条消息～`});
  ev.slice(0, 3).forEach(e => th.push({t:`${e["群"]}在聊：${(e["话题"] || []).slice(0, 3).join("、")}`, s:e["摘要"]?.slice(0, 40)}));
  const kpi = [["群", gs.length, "个"], ["今天的消息", gmsg, "条"], ["〈我〉回了", replies, "句"], users[peak] && ["最热闹", peak, "点"]];
  return {left, right, thoughts:th, kpi, sub:gs[0] ? `今天 ${gs[0][0]} 最热闹` : "今天群里还很安静", clip:"look"};
}

// ---------- 信箱：来信、说说，处理过的都留着记录 ----------
const gav = (gid, s=40) => `<img src="https://p.qlogo.cn/gh/${esc(gid)}/${esc(gid)}/${s}" alt="" referrerpolicy="no-referrer" loading="lazy" onerror="this.style.visibility='hidden'">`;
// 来信记录：申请和后来的处理合成一行（旧的在前扫一遍，处理结果盖到那封申请上）
function letterLog(log){
  const rows = [], open = new Map();
  for(const e of [...log].reverse()){
    const friend = /^friend/.test(e.kind), id = String(e.qq || e.id || e.group || "");
    if(e.kind === "friend_request" || e.kind === "group_invite"){
      const r = {friend, id, name:e.name, ts:e.ts, inviter:e.inviter_name || e.inviter, result:e.result || "等主人决定", talks:e.talks, late:e.late};
      rows.push(r); if(/^等/.test(r.result)) open.set((friend ? "f" : "g") + id, r);
    } else if(e.kind === "friend_decided" || e.kind === "group_decided"){
      const r = open.get((friend ? "f" : "g") + id), res = e.done === false ? `${e.action}（没成功）` : e.action;
      if(r){ r.result = res; r.by = e.via === "panel" ? "在面板" : e.via === "chat" ? "〈我〉在聊天里" : "在 QQ 里"; r.dts = e.ts; open.delete((friend ? "f" : "g") + id); }
      else rows.push({friend, id, name:e.name || (friend ? "" : e.group_name), ts:e.ts, result:res});
    } else if(e.kind === "joined" || e.kind === "kicked"){
      rows.push({friend:false, id, name:e.group_name || `群 ${e.group}`, ts:e.ts, result:e.kind === "joined" ? "进群了" : "被踢出群", inviter:e.operator_name || e.operator, event:true});
    }
  }
  return rows.reverse();
}
const STAMP = {自动通过:"ok", 同意:"ok", 进群了:"ok", 拒绝:"no", 黑名单拒绝:"no", 拉黑:"no", 被踢出群:"no", 等主人决定:"wait", "等〈我〉决定":"wait"};
// 等主人拍板的事：来信、说说草稿、成长提案、待认的名字、没修的错误、饭钱快吃完（此刻那一行、待你裁决、底下的红点都数这一份）
// 〈我〉想做的事等主人点评的不算在里面：点不点评都行
async function pendingAll(){
  const [pd, lg, bill, g] = await Promise.all([soft(get("/api/pending", 10000)), soft(get("/api/logs")), soft(get("/api/billing")), soft(get("/api/memline"))]);
  const rq = (pd?.requests || []).filter(r => !r.her), qd = pd?.qzone_draft || null, pr = pd?.proposals || [], who = g?.unknowns || [];
  const errs = lg ? logGroups(lg.logs.filter(l => l.level !== "WARNING" && !l.fixed)) : [];
  const ac = bill?.accounts?.[0], low = ac?.runway_days != null && ac.runway_days < 5 ? ac : null;
  const sum = [errs.length && `${errs.length} 种错误没修`, low && "饭钱快吃完", rq.length && `${rq.length} 封来信`, qd && "一条说说", pr.length && `${pr.length} 个成长提案`, who.length && `${who.length} 个名字待认`].filter(Boolean).join(" · ");
  return {pd, lg, rq, qd, pr, who, errs, low, sum, n:errs.length + (low ? 1 : 0) + rq.length + (qd ? 1 : 0) + pr.length + who.length};
}
// 同一句话（数字不算）的日志合成一组：几次、最后一次；byDay 时每天分开（记录那条时间线用）
function logGroups(logs, byDay=false){
  const m = new Map();
  for(const l of logs){ const k = (byDay ? new Date(l.ts * 1000).toDateString() + "|" : "") + (l.fixed ? "fixed|" : "") + l.level + "|" + l.msg.replace(/\d+/g, "#");
    const g = m.get(k) || {level:l.level, msg:l.msg, fixed:l.fixed, n:0, last:0}; g.n++; if(l.ts >= g.last){ g.last = l.ts; g.msg = l.msg; } m.set(k, g); }
  return [...m.values()].sort((a, b) => b.last - a.last);
}
const logItem = g => { const ex = explainLog(g.msg), bad = g.level !== "WARNING";
  if(g.fixed) return {h:`<span class="tag">${bad ? "错误" : "警告"}${g.n > 1 ? ` ×${g.n}` : ""}</span><b>${esc(g.fixed)}</b><span class="stamp ok">已修复</span>`, t:fmtT(g.last), s:`<span${tip(esc(g.msg.slice(0, 400)))}>${esc(g.msg.slice(0, 140))}</span>`};
  return {cls:bad ? "bad" : "warn", h:`<span class="tag ${bad ? "bad" : "warn"}">${bad ? "错误" : "警告"}${g.n > 1 ? ` ×${g.n}` : ""}</span>${ex ? `<b>${esc(ex)}</b>` : ""}`, t:fmtT(g.last), s:`<span${ex ? tip(esc(g.msg.slice(0, 400))) : ""}>${esc(g.msg.slice(0, 140))}</span>`}; };
// 一封新来的信（可以同意、拒绝、拉黑）
const letter = r => { const friend = r.type === "friend";
  return `<article class="letter"><div class="who">${friend ? av(r.id, 40) : gav(r.id)}<span><b>${esc(r.name || r.id)}</b>
    <small>${friend ? "想加好友" : `${esc(r.inviter_name || r.inviter || "有人")}邀请〈我〉进群`} · ${fmtT(r.ts)}</small></span><em class="stamp wait">${r.her ? "等〈我〉" : "等主人"}</em></div>
    ${friend ? `<q class="${r.comment ? "" : "none"}">${esc(r.comment || "没写验证信息")}</q><small class="muted">${(r.groups || []).length ? "共同群：" + r.groups.map(g => `<span class="chip">${esc(g)}</span>`).join("") : "不在〈我〉的群里"}</small>` : `<small class="muted">群号 ${esc(r.id)}</small>`}
    ${r.her ? `<small class="muted">〈主人〉拉的，进不进〈我〉自己定；在聊天里跟〈我〉说一声就行</small>` : `<div class="acts"><button class="btn sm" data-act="req" data-key="${esc(r.key)}" data-a="同意">同意</button><button class="btn sm alt" data-act="req" data-key="${esc(r.key)}" data-a="拒绝">拒绝</button>${friend ? `<button class="btn sm danger" data-act="req" data-key="${esc(r.key)}" data-a="拉黑">拉黑</button>` : ""}</div>`}</article>`; };
// 来信记录的一行（在「记录」里）
const TONE = {ok:"good", no:"bad", wait:"warn"};
const letterItem = r => { const k = STAMP[String(r.result).replace(/（.*/, "")] || "";
  return {cls:TONE[k] || "", t:fmtT(r.ts), h:`<b>${esc(r.name || r.id)}</b><em class="stamp ${k}">${esc(r.result)}</em>`,
    s:`${r.friend ? "加好友" : r.event ? (r.inviter ? `操作人 ${esc(r.inviter)}` : "群") : `拉〈我〉进群${r.inviter ? `（${esc(r.inviter)} 邀请）` : ""}`}${r.late ? " · 当时没收到，后来补上的" : ""}${r.talks ? ` · 聊过 ${r.talks} 句` : ""}${r.by ? ` · ${r.by}${esc(r.result)}` : ""}`}; };
// 〈我〉每周五把大家希望〈我〉学的本领整理成提案，等主人说好不好；说好时可以顺手写怎么做，记在提案上
const PROP = {ok:["同意了", "ok"], no:["不要", "no"], done:["学会了", "ok"]};
const propHead = (p, stamp) => `<div class="who"><span><b>【${esc(p.n)}】${esc(p.title)}</b>
    <small>${p.who ? `${esc(p.who)}想要 · ` : ""}${fmtT(p.ts)}${p.effort ? ` · 工作量${esc(p.effort)}` : ""}</small></span>${stamp}</div>`;
const propNote = p => p.note ? `<p class="prop-k">${p.status === "no" ? "为什么不要" : "〈主人〉定的做法"}</p><q class="prop-note">${esc(p.note)}</q>` : "";
const propWait = p => `<article class="letter">${propHead(p, `<em class="stamp wait">等主人</em>`)}
    ${p.idea ? `<q>${esc(p.idea)}</q>` : ""}${p.risk ? `<small class="muted">要注意：${esc(p.risk)}</small>` : ""}
    <div class="inline"><input id="propNote${esc(p.n)}" maxlength="300" placeholder="怎么做（说好时）或为什么不要，可以不写" aria-label="提案 ${esc(p.n)} 的做法"></div>
    <div class="acts"><button class="btn sm" data-act="prop" data-n="${esc(p.n)}" data-ok="1">好</button><button class="btn sm alt" data-act="prop" data-n="${esc(p.n)}" data-ok="0">不要</button></div></article>`;
const propDone = p => { const [w, k] = PROP[p.status] || [p.status, ""];
  return `<article class="letter">${propHead(p, `<em class="stamp ${k}">${esc(w)}</em>`)}
    ${propNote(p) || (p.status === "ok" ? `<q class="none">还没写怎么做，照需求书来</q>` : "")}
    ${p.status === "ok" ? `<div class="inline"><input id="propNote${esc(p.n)}" maxlength="300" placeholder="${p.note ? "改成……" : "写上怎么做"}" aria-label="提案 ${esc(p.n)} 的做法"><button class="btn sm alt" data-act="propnote" data-n="${esc(p.n)}">${p.note ? "改做法" : "写上"}</button></div>` : ""}</article>`; };
// 说说的配图（点开看大图）；配不配图〈我〉自己决定
const qzPic = (img, prompt) => typeof img === "string"
  ? `<a class="qz-pic" href="/api/image?from=qzone&f=${encodeURIComponent(img)}" target="_blank" rel="noopener"${prompt ? tip(`〈我〉想的画面：${esc(prompt)}`) : ""}><img src="/api/image?from=qzone&w=480&f=${encodeURIComponent(img)}" alt="说说配图" loading="lazy" onerror="this.parentNode.outerHTML='<small class=muted>配了一张图（图找不到了）</small>'"></a>`
  : img ? `<small class="muted">配了一张图（那时候还没把图留在后台）</small>` : "";
// 说说记录（在「记录」里）：完整的一条，全文＋配图；删掉的那条从发的时候那条找回字和图。回 [时间, 时间线的一行]
function qzItems(ql){
  const edited = new Set(ql.filter(e => e.kind === "edited").map(e => e.after));
  const posted = new Map(ql.filter(e => e.kind === "posted").map(e => [e.tid, e]));
  const QK = {posted:["发了说说", "ok"], rejected:["说说没发", "no"], deleted:["删掉了说说", "no"]};
  return ql.filter(e => QK[e.kind]).map(e => { const [w, c] = QK[e.kind], was = posted.get(e.tid) || {}, text = e.text || was.text || "", img = e.image ?? was.image;
    return [e.ts, {cls:TONE[c], t:fmtT(e.ts), h:`<b>${w}</b><span class="muted small">${e.kind === "posted" && edited.has(text) ? "主人改过" : ""}${e.via === "panel" ? " · 在面板" : ""}${img ? " · 带图" : ""}</span>`,
      p:`<span class="qz-full">${esc(text)}</span>`, x:qzPic(img, e.image_prompt || was.image_prompt)}]; });
}

// ---------- 待你裁决：要主人拍板的事都在这里，处理完就消失，处理过的进「记录」 ----------
async function renderMail(){
  const [pa, md] = await Promise.all([pendingAll(), soft(get("/api/mind"))]);
  const d = pa.pd;
  if(!d) return {left:[card("待你裁决", fail("信箱"), {ic:"i-mail"})], right:[], clip:"sigh"};
  const {rq, qd, pr, who, errs, low, n} = pa, all = d.requests || [], pdone = d.proposals_done || [];
  const left = [], right = [];
  if(errs.length) left.push(card("还没修的错误", tl(errs.slice(0, 8).map(logItem)), {ic:"i-bell", cls:"alarm-soft", meta:`<b>${errs.length}</b> 种`,
    note:"修好后标了「已修复」就从这里消失；警告不算在这里", foot:`<button class="btn alt sm" data-go="body">${ic("i-list")}在记录里看全部</button>`}));
  if(low) left.push(card("饭钱快吃完了", `<p style="margin:0">还剩 <b>¥${(+low.balance).toFixed(2)}</b>，照一天 ¥${(+low.per_day).toFixed(2)} 大概还能吃 <b>${low.runway_days}</b> 天。</p>`,
    {ic:"i-yen", cls:"alarm-soft", note:"充了钱就自己消失", foot:`<button class="btn alt sm" data-go="bill">${ic("i-yen")}看饭钱</button>`}));
  left.push(card("新来的信", all.length ? all.map(letter).join("") : empty("full", "没有人申请加好友或拉〈我〉进群～"), {ic:"i-mail", meta:all.length ? `<b>${all.length}</b> 封` : "",
    note:all.length ? "按钮要点两下才算" : "处理过的在「记录」里"}));
  left.push(qd ? card("说说草稿", `<div class="who">${av(BOT, 40)}<span><b>${esc(ME.bot_name || "〈名字〉")}</b><small>写于 ${fmtT(qd.ts)}${qd.source ? " · " + esc(qd.source) : ""} · 可以直接在纸上改${qd.image ? " · 配了图，改字不换图" : ""}</small></span></div>
      <textarea id="qzText" rows="6" aria-label="说说内容">${esc(qd.text)}</textarea><small class="qz-n" id="qzN">${qd.text.length} 字</small>${qzPic(qd.image, qd.image_prompt)}`,
      {ic:"i-quill", cls:"pink", foot:`<button class="btn" data-act="qz" data-a="publish">发布</button><button class="btn alt" data-act="qz" data-a="edit">发改后的</button><button class="btn alt" data-act="qz" data-a="rewrite">重写</button><button class="btn danger" data-act="qz" data-a="discard">不发</button>`, note:"按钮要点两下才算"})
    : card("说说草稿", empty("rice", "没有草稿～") + `<div class="inline"><input id="qzTopic" maxlength="50" placeholder="想让〈我〉写什么？留空〈我〉自己想" aria-label="说说主题"><button class="btn" data-act="qz" data-a="write">${ic("i-quill")}写一条</button></div>`,
      {ic:"i-quill", cls:"pink", note:"发过的、没发的在「记录」里"}));
  if(pr.length || pdone.length) right.push(card("成长提案", tabs([["等主人回", pr.length ? pr.map(propWait).join("") : empty("great", "这周没有新提案～"), pr.length], ["定了的", pdone.map(propDone).join(""), pdone.length]]),
    {ic:"i-spark", raw:true, meta:pr.length ? `<b>${pr.length}</b> 个等主人回` : "", note:"〈我〉想学的新本领；说好了〈我〉会把需求书发给主人，拿去给 agent 做；按钮要点两下才算"}));
  if(who.length) right.push(mlUnknownCard(who));
  // 〈我〉这一天看 QQ 时想做的事：主人 ✓ ✗ 点评，点不点评都行
  if(md){
    (md.actions || []).forEach(a => MIND_LABELS[a.id] = a.label);
    const bs = (md.beats || []).filter(b => (b.actions || []).length && Date.now() / 1000 - b.ts < 86400).slice(0, 12);
    const open = bs.reduce((a, b) => a + b.actions.filter(x => x.rv?.ok == null).length, 0);
    right.push(card("〈我〉想做的事", bs.length ? tl(bs.map(beatItem)) : empty("sleep", "这一天看 QQ 时没想做什么～"), {ic:"i-phone", meta:open ? `<b>${open}</b> 件没点评` : "",
      note:"这一天看 QQ 时想做的。✓ ✗ 点评〈我〉想得对不对；点不点评都行，不算在等主人的件数里"}));
  }
  const th = [{t:n ? `有 ${n} 件事等主人拍板～` : "没有事等主人，〈我〉可以安心吃饭了～"}];
  if(who.length) th.push({t:`有 ${who.length} 个名字〈我〉对不上是谁，〈主人〉帮〈我〉认一下～`});
  if(errs.length) th.push({t:`有 ${errs.length} 种错误还没修好……`});
  const kpi = [["等主人拍板", n, "件", n ? "warn" : ""], ["没修的错误", errs.length, "种", errs.length ? "bad" : ""], ["新来的信", rq.length, "封"], ["待认的名字", who.length, "个"]];
  return {left, right, thoughts:th, kpi, sub:n ? "要主人拍板的都在这里，处理完就消失；按钮点两下才算" : "现在没有事等主人", clip:n ? "curtsy" : "rice",
    after(){ const t = $("#qzText"); if(t) t.oninput = () => $("#qzN").textContent = `${t.value.length} 字`;
      $("#qzTopic")?.addEventListener("keydown", e => { if(e.key === "Enter") $('[data-act="qz"][data-a="write"]')?.click(); }); }};
}

// ---------- 日志、面板上做过的事翻成人话 ----------
// 常见的几种警告翻成人话；认不出来的就显示原文
function explainLog(msg){
  let m;
  if((m = msg.match(/retrying \((\d+)\/(\d+)\): (.+)$/i))) return `调用模型时${/connection/i.test(m[3]) ? "网断了一下" : "出了点错"}，已自动重试（第 ${m[1]}/${m[2]} 次）`;
  if((m = msg.match(/Temp dir exceeded limit.*Removed (\d+) files, released (\d+) bytes/i))) return `临时文件太多，自动清掉了 ${m[1]} 个旧文件（${Math.round(m[2]/1048576)} MB）`;
  if(/host='gxh\.vip\.qq\.com'/.test(msg)) return "有人发了 QQ 商城表情，QQ 给的图片链接下载不到（404）；〈我〉只看得到表情的名字，消息照常收";
  if(/获取引用消息失败.*消息为空/.test(msg)) return "有人引用的那条 QQ 那边找不到了（撤回了或太久以前），消息照常收，只是看不到引用的内容";
  if((m = msg.match(/获取 @ 用户信息失败.*成员(\d+)不存在/))) return `有人 @ 了一个这个群里还查不到的号（${m[1]}），多半是刚进群、名单还没刷新（比如群管家欢迎新人），跳过这个 @，消息照常收`;
  if(/获取 @ 用户信息失败.*reading 'coreInfo'/.test(msg)) return `QQ 那边这一刻自己掉了一下状态，查不到被 @ 的人，跳过这个 @，消息照常收；马上又连着了`;
  if((m = msg.match(/获取 @ 用户信息失败.*用户ID (\d+) 不存在/))) return `有人 @ 了一个查不到的号（${m[1]}），跳过这个 @，消息照常收`;
  if((m = msg.match(/Event loop lag detected: ([\d.]+)s/i))) return `〈我〉卡住了 ${Math.round(+m[1])} 秒没反应（服务器当时太忙）`;
  if(/timed? ?out|timeout/i.test(msg)) return "等太久，超时了";
  if(/rate.?limit|429/i.test(msg)) return "请求太频繁，被限流了";
  if(/connection (error|refused|reset)/i.test(msg)) return "网络连接出错";
  return null;
}
const SET_NAMES = {"mind.enabled":"自主", "proactive.enabled":"主动找熟人聊天", "proactive.mode":"主动聊天的方式", "qzone.enabled":"定时写说说", "qzone.mode":"定时说说怎么发",
  "comic.enabled":"每天画群漫画", "comic.auto_post":"群漫画画完直接发群", "comic.draw_chat":"聊天里画图（GPT）",
  "comic.draw_min_score":"能叫〈我〉画图的好感度", "comic.draw_daily_max":"每天最多画几张", "voice.enabled":"语音",
  "bg.caption":"看图走降智版", "bg.mind":"心跳走降智版",
};
const VAL_NAMES = {auto:"直接发", preview:"先给主人看", review:"先给主人审"};
// 面板上做过的事翻成人话
function auditText(a){
  const b = a.body || {};
  if(a.path === "/api/settings"){
    if(b.plugin === "proactive" && (b.key === "block" || b.key === "unblock")) return `${b.key === "block" ? "不让" : "重新允许"}〈我〉主动找 QQ ${esc(b.value)} 聊天`;
    if(b.plugin === "comic" && String(b.key).startsWith("group:")) return `${b.value ? "打开" : "关掉"}了群 ${esc(String(b.key).slice(6))} 的群漫画`;
    if(b.plugin === "mind" && String(b.key).startsWith("mode:")) return `把自主动作「${esc(MIND_LABELS[String(b.key).slice(5)] || String(b.key).slice(5))}」改成「${esc(MIND_MODES[b.value] || b.value)}」`;
    const nm = SET_NAMES[`${b.plugin}.${b.key}`] || `${b.plugin}.${b.key}`;
    return b.value === true ? `打开了「${esc(nm)}」` : b.value === false ? `关掉了「${esc(nm)}」` : `把「${esc(nm)}」改成「${esc(VAL_NAMES[b.value] || b.value)}」`;
  }
  if(a.path === "/api/report") return "让〈我〉写了一份今日汇报";
  if(a.path === "/api/asks") return `删了一条〈主人〉交代的事（交代${esc(b.id)}）`;
  if(a.path === "/api/selfnotes") return `删了一条〈我〉自己的事（S${esc(b.id)}）`;
  if(a.path === "/api/memline") return ({fix:`把〈我〉记的 #${esc(b.id)} 改成「${esc(b.text)}」`, forget:`让〈我〉忘掉记忆 #${esc(b.id)}`, restore:`把〈我〉忘掉的 #${esc(b.id)} 找回来`,
    claim:`认出〈我〉记忆里的「${esc(String(b.node || "").slice(2))}」是${b.to === "thing" ? "一件事、一个梗" : ` QQ ${esc(b.to)}`}`})[b.action] || "动了〈我〉的记忆";
  if(a.path === "/api/memepref") return `去掉了 QQ ${esc(b.qq)} 对表情包「${esc(b.file)}」的偏好`;
  if(a.path === "/api/memes"){ const fs = (b.files || []).map(f => String(f).split("/").pop().replace(/\.\w+$/, "")), n = fs.length > 3 ? `${fs.slice(0, 3).join("、")} 等 ${fs.length} 张` : fs.join("、");
    return ({move:`把表情包 ${esc(n)} 换到了「${esc(b.to)}」`, out:`把表情包 ${esc(n)} 拿下来放进了隔离区`, back:`把表情包 ${esc(n)} 放回了库里${b.to ? `（${esc(b.to)}）` : ""}`})[b.action] || "动了表情包"; }
  if(a.path === "/api/feeds") return b.action === "add" ? `记了一笔投喂：QQ ${esc(b.qq)} ¥${esc(b.amount)}${b.note ? `（${esc(b.note)}）` : ""}` : "删了一笔记错的投喂";
  if(a.path === "/api/evolve"){
    if(b.action === "proposal") return `${b.ok ? "同意" : "没同意"}成长提案【${esc(b.n)}】${b.note ? `：${esc(b.note)}` : ""}`;
    if(b.action === "del_note") return "删了一条相处经验";
    if(b.action === "align" || b.action === "rewrite") return b.action === "align" ? "让〈我〉按最新的人设重整相处经验" : "让〈我〉拿昨天的聊天重写相处经验";
  }
  if(a.path === "/api/mind/beat") return "让〈我〉看了一眼手机";
  if(a.path === "/api/mind/review") return b.ok === null ? "撤掉了一条点评" : `点评〈我〉想做的一件事：${b.ok ? "对" : "不对"}${b.note ? `（${esc(b.note)}）` : ""}`;
  if(a.path === "/api/mind/try") return `让〈我〉实测了一次「${esc(MIND_LABELS[b.action] || b.action)}」`;
  if(a.path === "/api/comic") return `让〈我〉画${b.day === "yesterday" ? "昨天" : "今天"}的群漫画`;
  if(a.path === "/api/pending"){
    if(b.what === "request") return `${esc(b.action || "处理")}了一个好友申请或群邀请`;
    if(b.what === "qzone") return ({write:`让〈我〉写一条说说${b.topic ? `（${esc(b.topic)}）` : ""}`, publish:"原样发布了说说", edit:"改过以后发布了说说", rewrite:"让〈我〉重写说说", discard:"没让发说说"})[b.action] || "处理了说说草稿";
    if(b.what === "comic") return b.action === "post" ? "把群漫画发到了群里" : "丢掉了一张群漫画";
  }
  return `${esc(a.path)} ${esc(JSON.stringify(b))}`;
}
// 自主（lively_mind）：她自己看 QQ、自己决定做的事
const MIND_MODES = {off:"关", shadow:"只记录", on:"开"};
const MIND_LABELS = {};
const MIND_RES = {done:"做了", shadow:"只记录", blocked:"没做", fail:"失败", queued:"排队中", unclear:"不知道成没成"};
// 自主动作的开关（「设定」里那张）：总开关＋每个动作 开／只记录／关
function mindSwitches(mi){
  (mi.actions || []).forEach(a => MIND_LABELS[a.id] = a.label);
  return `<div class="group">${toggle("mind.enabled", mi.enabled, "自主", `〈我〉自己定隔多久看一次 QQ、做什么；今天看了 ${mi.beats_today} 次${mi.sleeping ? "，现在在睡觉" : ""}`)}</div>
    <div class="sec">每个动作</div><div class="group">${(mi.actions || []).filter(a => a.id !== "note" && a.id !== "quiet").map(a => choose("mind.mode:" + a.id, a.mode,
      a.ready ? MIND_MODES : {off:"关", shadow:"只记录"}, a.label, `今天 ${a.today}${a.day ? "/" + a.day : ""}${a.ready ? "" : " · 还没接上，只能只记录"}${(a.rv || [0, 0])[0] + (a.rv || [0, 0])[1] ? ` · 点评 ✓${a.rv[0]} ✗${a.rv[1]}` : ""}`)).join("")}</div>
    <p class="small muted" style="margin:8px 0 0">「只记录」是想做什么都记下来、不真的动手</p>`;
}
// 〈我〉自己记着的名单和记事本：嫌〈我〉烦的人、嫌〈我〉插话多的群、记事（主人只看）
function mindLists(md){
  const qt = Object.entries(md.quiet || {});
  return (qt.length ? `<div class="sec">嫌〈我〉烦的人</div>` + tl(qt.map(([qq, v]) => ({cls:"warn", h:`<b>${esc(v.name || qq)}</b><span class="muted small">${esc(qq)}</span>`, t:fmtT(v.ts), s:esc(v.why || "")})))
      + `<p class="small muted">只是〈我〉自己记着，不拦；之后少不少打扰 TA 〈我〉自己定。要划掉就私信〈我〉「自主 嫌烦 删 QQ」</p>` : "")
    + (Object.keys(md.quiet_groups || {}).length ? `<div class="sec">有人嫌〈我〉插话多的群</div>` + tl(Object.entries(md.quiet_groups).map(([g, v]) => ({cls:"warn", h:`<b>${esc(g)}</b>`, t:fmtT(v.ts), s:esc(v.why || "")})))
      + `<p class="small muted">也只是记着，在那个群插不插话〈我〉自己掂量</p>` : "")
    + ((md.notes || []).length ? `<div class="sec">〈我〉的记事本</div>` + tl(md.notes.map(n => ({p:esc(n.text), s:`${esc(n.when || "有空")} · 记于 ${fmtT(n.ts)}`}))) : "");
}
// 看一眼 QQ 的一轮：想了什么、想做的事（主人能 ✓ ✗ 点评）
function beatItem(b){
  const acts = (b.actions || []).map((a, i) => { const rv = a.rv || {}, said = (a.args || {}).text;
    return `<div class="mact" data-beat="${esc(b.beat)}" data-i="${i}"><span class="chip${a.result === "blocked" || a.result === "fail" ? " no" : ""}"${tip(esc(a.why || "") + (said ? "<br>想说：" + esc(said) : "") + (a.blocked_by ? "<br>没做：" + esc(a.blocked_by) : ""))}>${esc(MIND_LABELS[a.action] || a.action)}${a.target ? " · " + esc(a.target.slice(0, 18)) : ""}${(a.args || {}).emoji ? " " + esc(a.args.emoji) : ""} · ${MIND_RES[a.result] || esc(a.result)}</span>`
      + `<span class="rv"><button class="rvb" data-act="mrv" data-ok="1" aria-pressed="${rv.ok === true}" aria-label="想得对">✓</button><button class="rvb bad" data-act="mrv" data-ok="0" aria-pressed="${rv.ok === false}" aria-label="想得不对">✗</button></span>`
      + `<input class="rv-note" maxlength="60" placeholder="哪里不对？回车记下" value="${esc(rv.note || "")}"${rv.ok === false ? "" : " hidden"}></div>`; }).join("");
  return {m:(b.actions || []).length ? "var(--blush)" : "", t:fmtT(b.ts), h:`<b>${b.manual ? "主人让看的" : "看了一眼"}</b><span class="muted small">${(b.seen || {}).msgs || 0} 条消息${(b.seen || {}).feeds ? `、${b.seen.feeds} 条动态` : ""}</span>`,
    p:b.result === "ok" ? esc(b.thought || "（没说想什么）") : esc(b.result), x:acts || `<small>只是看看</small>`};
}
// 〈我〉真的做了的一件事（看 QQ 时、聊天里）
const actItem = a => ({t:fmtT(a.ts), h:`<b>${esc(MIND_LABELS[a.action] || a.action)}</b><span class="muted small">${esc(a.where || "")}${a.by === "heartbeat" ? " · 看 QQ 时" : a.by === "chat" ? " · 聊天里" : ""}</span>${a.result !== "done" ? `<em class="stamp ${a.result === "blocked" || a.result === "fail" ? "no" : "wait"}">${esc(MIND_RES[a.result] || a.result)}</em>` : ""}`,
  p:esc((a.args || {}).text || a.why || ""), s:[(a.args || {}).text && a.why ? "为什么：" + esc(a.why) : "", a.blocked_by ? "没做：" + esc(a.blocked_by) : ""].filter(Boolean).join(" · ")});
// 发完再看一眼：程式撤了的残渣、她自己再看时撤了的（10-29 前那些模型只记录、没撤）
function recheckItem(c){
  const ids = new Set([...(c.rules || []).map(r => r.id), ...((c.model || {}).bad || [])]);
  const said = (c.msgs || []).filter(x => !ids.size || ids.has(x.id)).map(x => esc(x.text || "[消息]")).join("<br>");
  const rules = (c.rules || []).map(r => `<span class="chip${r.result === "blocked" || r.result === "fail" ? " no" : ""}"${r.blocked_by ? tip("没撤：" + esc(r.blocked_by)) : ""}>${esc(r.why)} · ${r.result === "queued" || r.result === "done" ? "撤了" : esc(MIND_RES[r.result] || r.result)}</span>`).join("");
  const mv = c.model || {};
  const took = (mv.done || []).some(d => d.result === "queued" || d.result === "done");
  const model = mv.ok === false ? (mv.done
    ? `<span class="chip${took ? "" : " no"}"${mv.fix ? tip((mv.fix_result === "queued" || mv.fix_result === "done" ? "补了：" : "想补没补成：") + esc(mv.fix)) : ""}>她自己撤${took ? "了" : "没撤成"}${mv.fix ? " · 补了一句" : ""}</span><small> ${esc(mv.why || "")}</small>`
    : `<span class="chip"${mv.fix ? tip("想补一句：" + esc(mv.fix)) : ""}>${esc(mv.problem || "有问题")} · 只记录</span><small> ${esc(mv.why || "")}</small>`) : "";
  return {m:(c.rules || []).length ? "var(--blush)" : "", t:fmtT(c.ts), h:`<b>${esc(c.where || "")}</b><span class="muted small">${c.by === "chat" ? "聊天回的" : "自己说的"}</span>`,
    p:said, x:rules + model};
}
// 掉线的时段（11-02）：回来后带给她的是 ≥30 分钟、不是后台停了的那些
const OUT_WHY = {qq:"QQ 那边掉的", down:"后台停了（不带给她）", kicked:"被踢下线、熔断停的"};
const fmtMins = m => m >= 60 ? `${Math.floor(m / 60)} 小时 ${m % 60} 分钟` : `${m} 分钟`;
const outageItem = r => ({cls:r.why === "kicked" ? "warn" : "", t:fmtT(r.from),
  h:`<b>QQ 掉线 ${fmtMins(r.mins)}</b><span class="muted small">${esc(OUT_WHY[r.why] || r.why)}${r.precise ? " · 精确到秒" : ""}</span>`, p:`${fmtT(r.from)} ～ ${fmtT(r.to)}`});
// 〈我〉的电脑（10-29）：电脑那边的工作记录，按一轮一轮排；点开一步看叫了什么、回来什么、截图
const hm = at => (at || "").slice(11, 16);
function pcRound(r){
  const bad = r.steps.filter(s => !s.ok).length;
  const where = r.direct ? "不是聊天里叫的：〈我〉自己写的程序直接叫的，或者维护时的测试" : [r.beat ? "看 QQ 时" : "", r.group ? "群里" : "私聊"].filter(Boolean).join(" · ");
  const steps = r.steps.map(s => `<details class="pcstep"><summary><span class="chip${s.ok ? "" : " no"}">${esc(s.tool)}${s.action ? " · " + esc(s.action) : ""}${s.ok ? "" : " · 没成"}</span><small class="muted">${esc((s.at || "").slice(11, 19))}${s.ms != null ? ` · ${s.ms} ms` : ""}</small></summary>
    <div class="sec">叫的</div><pre>${esc(s.args)}</pre><div class="sec">回来的</div><pre>${esc(s.res)}</pre>${s.shot ? `<img src="/api/pcshot?f=${encodeURIComponent(s.shot)}" loading="lazy" alt="截图">` : ""}</details>`).join("");
  return {m:bad ? "var(--blush)" : "", t:hm(r.start) + (hm(r.end) && hm(r.end) !== hm(r.start) ? "–" + hm(r.end) : ""),
    h:`<b>${r.direct ? "没带是谁" : r.owner ? "〈主人〉" : esc(r.who || r.qq || "")}</b><span class="muted small">${esc(where)} · ${r.steps.length} 步${bad ? `，${bad} 步没成` : ""}</span>`,
    p:r.msg ? esc(r.msg.slice(0, 200)) : "", x:steps + (r.reply.length ? `<small>〈我〉回的：${esc(r.reply.join(" / ").slice(0, 300))}</small>` : "")};
}
function pcBody(d){
  if(!d) return fail("电脑那边的记录");
  const days = (d.days || []).slice(0, 7).map(x => `<button class="chip${x === d.day ? " on" : ""}" data-act="pcday" data-day="${esc(x)}">${esc(x.slice(5))}</button>`).join("");
  const rs = d.rounds || [];
  return (days ? `<div class="pcdays">${days}</div>` : "") + (rs.length ? tl(rs.slice(0, 40).map(pcRound)) + (rs.length > 40 ? `<p class="small muted">这天还有 ${rs.length - 40} 轮更早的，在 DSH 里和电脑上的工作记录里都看得到</p>` : "")
    : empty("sleep", d.day ? "这天〈我〉没用电脑～" : "〈我〉还没用过电脑～"));
}
function pcCard(d){
  return card("〈我〉的电脑", `<div id="pcLog">${pcBody(d)}</div><p class="small muted" style="margin:8px 0 0">每一步都记在电脑上的工作记录里（只能追加、改不了）；DSH 里也有一份</p>`,
    {ic:"i-list", meta:d?.day ? `${(d.rounds || []).length} 轮` : ""});
}
// ---------- 记录与值班：上面是〈我〉现在怎样、让〈我〉做点事，下面是所有发生过的事，一条时间线按来源筛 ----------
const ANN = {err:["错误", "var(--bad)"], warn:["警告", "var(--warn)"], act:["〈我〉做的事", "var(--blush)"], beat:["看 QQ 想的", "#8fb3e8"], recheck:["发完复查", "#9b7fc6"],
  out:["掉线", "#7a4a5a"], mail:["来信", "var(--hair)"], qz:["说说", "var(--good)"], grow:["成长", "#e0a630"], audit:["面板上做的", "#5f6f99"], forgot:["忘掉的记忆", "var(--faint)"]};
const ANN_OFF = new Set(["warn", "beat"]);  // 这两种太多，默认收起
const ANN_MAX = 400;
// 忘掉的记忆：〈主人〉私聊里让〈我〉忘掉的（她先说清楚忘了会怎样、自己想不想忘，〈主人〉确认后才删）；删前留了备份，这里只能看
function forgotItem(f){
  const st = {done:["忘掉了", "var(--faint)"], failed:["没忘成", "var(--bad)"], asked:["等〈主人〉确认", "var(--hair)"]}, [lb, c] = st[f.result] || [f.result, "var(--faint)"];
  return {m:c, t:fmtT(f.ts), h:`<b>#${esc(f.id)}</b> ${tagM(lb, c)}${f.where ? ` <span class="small muted">${esc(f.where)}${f.date ? " · " + esc(f.date.slice(5) || f.date) : ""}</span>` : ""}`,
    p:f.summary ? `<span class="clamp"${tip(esc(f.summary))}>${esc(f.summary)}</span>` : (f.result === "asked" ? "〈我〉记下了要忘，正等〈主人〉在私聊里确认（30 分钟没确认就作废）" : ""),
    s:[f.why ? `为什么：${esc(f.why)}` : "", f.moments ? `回味出的 ${f.moments} 段片段一起删了` : "", f.error ? `出错：${esc(f.error)}` : ""].filter(Boolean).join(" · ")};
}
async function renderBody(){
  const [lg, ov, md, pc, pd, ev, hr] = await Promise.all([soft(get("/api/logs")), soft(get("/api/overview")), soft(get("/api/mind")), soft(get("/api/pclog")),
    soft(get("/api/pending", 10000)), soft(get("/api/evolve")), soft(get("/api/heart"))]);
  const left = [], right = [], th = [];
  if(qqDown(ov)) left.push(offlineCard(ov.offline_since));
  const live = lg ? lg.logs.filter(l => !l.fixed) : [], errs = live.filter(l => l.level !== "WARNING").length, warns = live.length - errs, kd = lg?.keep_days || 7;
  const awake = lg ? ago(lg.since).replace(" 前", "").replace("前", "") : "—";
  // 〈我〉现在：醒着多久、错误、看 QQ，鱼缸还剩多少地方
  let h = `<div class="stats">${stat("醒着", awake, ov ? (ov.online === false ? "QQ 掉线了" : "QQ 在线") : "")}${stat("错误", errs, `这 ${kd} 天${warns ? `，另有警告 ${warns}` : ""}`, errs ? "bad" : "")}${md ? stat("看 QQ", `${md.beats_today} 次`, md.sleeping ? "今天；现在在睡觉" : md.next_beat ? `今天；下次大约 ${fmtT(md.next_beat)}` : "今天") : ""}</div>`;
  if(ov?.system){
    const s = ov.system, mem = s.mem || {}, disk = s.disk || {}, pct = (x, y) => y ? Math.round(x / y * 100) : 0;
    h += `<div class="sec" style="margin-top:14px">鱼缸还剩多少地方</div>` + [["内存", pct(mem.total - mem.available, mem.total)], ["磁盘", pct(disk.used, disk.total)], ["交换区", pct(mem.swap_used, mem.swap_total)]]
      .map(([k, v]) => meter(k, v / 100, v + "%", "", v > 65)).join("");
  }
  left.push(card("〈我〉现在", h, {ic:"i-pulse", note:"没修的错误在「待你裁决」也有一份；饭钱在「饭钱」"}));
  left.push(card("让〈我〉做点事", `<div id="report"><p class="small muted" style="margin:0">汇报约十几秒；群漫画不用叫，每天自己画</p></div>`,
    {ic:"i-brush", foot:`<button class="btn" data-act="report">${ic("i-quill")}写汇报</button><button class="btn alt" data-act="mindbeat">${ic("i-phone")}看一眼 QQ</button>`}));
  if(pc) left.push(pcCard(pc));
  // 发生过的事：错误和警告（同一天同一句合成一条）、面板上做的、〈我〉做的事、看 QQ 想的、发完复查、掉线、来信、说说、成长、忘掉的记忆
  const E = [];
  if(lg){
    for(const g of logGroups(lg.logs, true)) E.push([g.level === "WARNING" ? "warn" : "err", g.last, logItem(g)]);
    for(const a of lg.audit || []) E.push(["audit", a.ts, {t:fmtT(a.ts), p:auditText(a), s:a.who === "local" ? "本机" : esc(a.who)}]);
  }
  if(md){
    (md.actions || []).forEach(a => MIND_LABELS[a.id] = a.label);
    for(const a of md.acts || []) E.push(["act", a.ts, actItem(a)]);
    for(const b of md.beats || []) E.push(["beat", b.ts, beatItem(b)]);
    for(const c of md.rechecks || []) E.push(["recheck", c.ts, recheckItem(c)]);
    for(const r of md.outages || []) E.push(["out", r.from, outageItem(r)]);
  }
  if(pd){
    for(const r of letterLog(pd.request_log || [])) E.push(["mail", r.ts, letterItem(r)]);
    for(const [ts, it] of qzItems(pd.qzone_log || [])) E.push(["qz", ts, it]);
    for(const p of pd.proposals_done || []) { const [w, k] = PROP[p.status] || [p.status, ""];
      E.push(["grow", p.ts, {t:fmtT(p.ts), h:`<b>成长提案【${esc(p.n)}】${esc(p.title)}</b><em class="stamp ${k}">${esc(w)}</em>`, p:p.note ? esc(p.note) : ""}]); }
  }
  if(ev) for(const c of ev.changes || []) E.push(["grow", c.ts, {t:fmtT(c.ts), h:`<b>相处经验${c.kind === "notes_align" ? "按新人设重整" : "每晚复盘"}</b>`, p:esc(c.text || "")}]);
  if(hr?.ready) for(const f of hr.forgotten || []) E.push(["forgot", f.ts, forgotItem(f)]);
  E.sort((a, b) => b[1] - a[1]);
  const cnt = {}; E.forEach(([k]) => cnt[k] = (cnt[k] || 0) + 1);
  const chips = `<div class="mchips">${Object.keys(ANN).filter(k => cnt[k]).map(k => `<button class="mchip" data-act="annf" data-k="${k}" aria-pressed="${!ANN_OFF.has(k)}"><i class="adot" style="--m:${ANN[k][1]}"></i>${ANN[k][0]}<em>${cnt[k]}</em></button>`).join("")}</div>`;
  const rows = E.slice(0, ANN_MAX).map(([k, , it]) => ({...it, m:it.m || ANN[k][1], attr:` data-src="${k}"${ANN_OFF.has(k) ? " hidden" : ""}`, h:`<span class="tag ann">${ANN[k][0]}</span>${it.h || ""}`}));
  right.push(card("发生过的事", E.length ? chips + `<div id="annBox">${tl(rows)}</div>` + (E.length > ANN_MAX ? `<p class="small muted">只列最新的 ${ANN_MAX} 条</p>` : "") : empty("sleep", "这几天什么都没发生～"),
    {ic:"i-list", meta:`<b>${E.length}</b> 条`, note:`最近 ${kd} 天，新的在上面。点上面的来源打开、收起；警告和「看 QQ 想的」太多，先收着`}));
  th.push({t:errs ? `这 ${kd} 天出了 ${errs} 条错误，〈我〉有点慌～` : "一直没出错，〈我〉真棒～"});
  if(md?.thought?.text) th.push({t:md.thought.text, s:`${fmtT(md.thought.ts)} · 看 QQ 时想的`});
  const kpi = [lg && ["醒着", awake], lg && ["错误", errs, "条", errs ? "bad" : ""], md && ["今天看 QQ", md.beats_today, "次"], ["记录", E.length, "条"]];
  return {left, right, thoughts:th, kpi, title:"记录与值班", sub:"〈我〉现在怎样，和这几天发生过的所有事", clip:errs ? "sigh" : "busy"};
}

// ---------- 设定：所有开关都在这一页，每个开关只在这里出现一次（〈我〉对 TA 的规矩在人的页面上也能拨，是同一个开关） ----------
// 表格里的小开关
const swc = (set, on, label, extra="") => `<label class="sw swc"><input type="checkbox" role="switch" data-set="${set}" ${extra} aria-label="${esc(label)}" ${on ? "checked" : ""}><i aria-hidden="true"></i></label>`;
async function renderSet(sub){
  const [st, ppl, md] = await Promise.all([soft(get("/api/settings", 10000)), soft(get("/api/people")), soft(get("/api/mind"))]);
  if(!st) return {left:[card("设定", fail("开关"), {ic:"i-switch"})], right:[], clip:"sigh"};
  const left = [], right = [];
  // 〈我〉能做的事：按用途分组，拨一下马上生效
  const chat = [], make = [], draw = [], other = [];
  if(st.proactive) chat.push(toggle("proactive.enabled", st.proactive.enabled, "主动找熟人聊天", st.proactive.by_heartbeat ? "现在她看 QQ 时自己决定找谁，这个开关暂不起作用" : `好感够的好友，每天最多 2 次${st.proactive.blocked.length ? `；不找 ${st.proactive.blocked.length} 人` : ""}`),
    ...(st.proactive.by_heartbeat ? [] : [choose("proactive.mode", st.proactive.mode, {auto:"直接发", preview:"先给主人看"}, "发送方式")]));
  if(st.voice) chat.push(toggle("voice.enabled", st.voice.enabled, "语音", st.voice.enabled && st.voice.ready ? `她想发语音时自己用；${esc(st.voice.ready)}` : "她想发语音时自己用（BreezeBlue 云端），关了就发不了"));
  if(st.qzone) make.push(toggle("qzone.enabled", st.qzone.enabled, "定时写说说", "20:30–21:30 写一条；她自己想发时不受这个限制，都先给主人审"), choose("qzone.mode", st.qzone.mode, {review:"先给主人审", auto:"直接发"}, "定时说说怎么发"));
  if(st.comic) make.push(toggle("comic.enabled", st.comic.enabled, `群漫画`, `提前画好给她过目，${esc(st.comic.at || "22:00")} 发到群里；哪些群画在「按群」那张表`));
  if(st.draw){ const D = st.draw, mods = (D.models || []).filter(Boolean);
    const opt = (xs, cur) => Object.fromEntries([...new Set([...xs, +cur])].sort((a, b) => a - b).map(x => [String(x), String(x)]));
    draw.push(toggle("comic.draw_chat", D.chat, "聊天里画图", `${mods.length ? `用 ${esc(mods.join("，不行换 "))}；` : ""}主人和好感度 ${D.min} 以上的人能叫；今天 ${D.today}/${D.max} 张`),
      choose("comic.draw_min_score", String(D.min), opt([50, 60, 70, 80], D.min), "至少好感度", "主人不受限"),
      choose("comic.draw_daily_max", String(D.max), opt([10, 20, 30, 50, 100], D.max), "每天最多几张", "所有人合计，含说说配图、定做形象；群漫画另算。最高可以拨到 100"));
  }
  if(st.search) other.push(toggle("search.enabled", st.search.enabled, "查图出处", `她想查一张图从哪来时自己用；主人和好感度 ${st.search.min_score} 以上的人叫得动；今天 ${st.search.today}/${st.search.daily_max} 次`));
  if(st.report) other.push(toggle("report.enabled", st.report.enabled, "每晚日报", `${esc(st.report.at)} 私信主人今天的事；关了也能私信问「日报」`));
  if(st.social) other.push(`<div class="sw ro"><span>好友黑名单<small>${st.social.blacklist.map(esc).join("、") || "空的"}</small></span></div>`);
  // 例行：每条一行，右边两个开关——先看今天的聊天、开着没
  const routine = (st.routines || []).map(r => `<div class="sw rt"><span>#${r.id} ${esc(r.name || "")}<small>${esc(String(r.desc || "").replace(/^#\d+\s*[^：]*：/, "").replace("【停了】", "").replace("，先看今天的聊天", ""))}${r.runs ? ` · 做过 ${r.runs} 次` : ""}</small></span><em class="rt-t">先看今天${swc(`evolve.today:${r.id}`, r.today, `#${r.id} 先看今天的聊天`)}</em>${swc(`evolve.routine:${r.id}`, r.enabled, `#${r.id} 开着`)}</div>`);
  const grp = (n, xs) => xs.length ? `<div class="sec">${n}</div><div class="group">${xs.join("")}</div>` : "";
  left.push(card("〈我〉能做的事", grp("聊天", chat) + grp("写和画", make) + grp("画图", draw) + grp("例行", routine) + grp("其他", other) || `<p class="muted">没有能开关的插件～</p>`, {ic:"i-switch", cls:"sec-can", note:"拨一下马上生效"}));
  if(st.mind) left.push(card("自主", mindSwitches(st.mind) + (md ? mindLists(md) : ""), {ic:"i-phone", cls:"pink sec-mind", note:"〈我〉看 QQ 时能做哪些事；想做的事在「待你裁决」点评，做过的在「记录」"}));
  // 模型和省钱：看图、心跳、群聊默认走不走降智版；降智版接口平常折起来
  const model = [];
  if(st.bg){ const B = st.bg;
    model.push(toggle("bg.caption", B.caption, "看图走降智版", `群聊背景、截图、表情包的看图用降智版（${esc(B.caption_pid)}）；失败自动换 ${esc(String(B.caption_pid).startsWith("workbuddy") ? "DeepSeek" : "原模型")} 重看${B.caption_loaded ? "" : "；还没加载"}`),
      toggle("bg.mind", B.mind, "心跳走降智版", `每次看 QQ 用降智版（${esc(B.mind_pid)}）；失败自动换回原模型${B.mind_loaded ? "" : "；还没加载"}`)); }
  if(st.brain) model.push(toggle("brain.default", st.brain.default_full, "群聊默认用满血版", `关着（默认）走降智版 ${esc(st.brain.model || "")}，额度便宜、回答简单；打开就用满血版${st.brain.full_id ? `（${esc(st.brain.full_id)}）` : ""}。单独的群在「按群」那张表`));
  if(model.length || st.brain){ const B = st.brain;
    left.push(card("模型和省钱", (model.length ? `<div class="group">${model.join("")}</div>` : "") + (B ? `<details class="adv"><summary>降智版接口（${B.loaded ? "已就绪" : "还没加载，重启一次才生效"} · 密钥 ${esc(B.key_hint)}）</summary><div class="group wbapi">
      <label class="sw"><span>降智版地址<small>OpenAI 兼容接口，默认 http://172.18.0.1:7863/v1</small></span><input type="text" id="wbBase" value="${esc(B.base)}" placeholder="http://172.18.0.1:7863/v1"></label>
      <label class="sw"><span>降智版 API Key<small>只显示掩码；留空就不改</small></span><input type="password" id="wbKey" placeholder="留空不改"></label>
      <label class="sw"><span>模型<small>降智版用的模型 ID</small></span><input type="text" id="wbModel" value="${esc(B.model)}" placeholder="global:deepseek-v4.1-flash"></label>
      <div style="display:flex;gap:8px;margin-top:8px"><button class="btn sm" data-act="wbsave">保存</button><button class="btn sm alt" data-act="wbprobe">测试</button></div></div></details>` : ""),
      {ic:"i-yen", cls:"sec-model", note:"降智版便宜、回答简单；接口平常不用动"}));
  }
  // 按群：一行一个群，一栏一种开关；总开关关着时那一栏变灰（格子照样记着）
  const gs = st.comic?.groups?.length ? st.comic.groups : st.brain?.groups || [], gcol = [];
  if(st.comic) gcol.push(["群漫画", st.comic.enabled ? "" : "总开关关着", g => { const x = st.comic.groups.find(y => y.gid === g.gid); return x ? swc("comic.group:" + g.gid, x.on, `${g.name} 群漫画`) : "—"; }]);
  if(st.brain) gcol.push(["用满血版", st.brain.default_full ? "默认都用" : "默认降智版", g => { const x = (st.brain.groups || []).find(y => y.gid === g.gid); return x ? swc("brain.group:" + g.gid, x.full, `${g.name} 用满血版`) : "—"; }]);
  if(gs.length && gcol.length) right.push(card("按群", `<table class="mx"><thead><tr><th>群</th>${gcol.map(([n, s]) => `<th>${n}${s ? `<small>${s}</small>` : ""}</th>`).join("")}</tr></thead>
    <tbody>${gs.map(g => `<tr><td><span class="who">${gav(g.gid, 40)}<span>${esc(g.name || g.gid)}</span></span></td>${gcol.map(([, s, f]) => `<td class="${/关着/.test(s) ? "off" : ""}">${f(g)}</td>`).join("")}</tr>`).join("")}</tbody></table>`,
    {ic:"i-bubbles", cls:"sec-groups", note:"〈我〉在哪些群说话是门禁定的，〈主人〉说了〈我〉用工具改，不在这里"}));
  // 按人：只列有特别规矩的人和好感 90 以上的；人的页面「〈我〉对 TA 的规矩」是同一个开关
  const blocked = new Set(st.proactive?.blocked || []), special = new Set(blocked);
  const cand = (ppl || []).filter(p => p.qq !== BOT && (p.favor >= 90 || special.has(p.qq))).slice(0, 15);
  const det = await Promise.all(cand.map(p => soft(get("/api/person/" + p.qq, 20000))));
  const pcol = [];
  pcol.push(["不要主动找", (p, d) => p.qq === OWNER ? "—" : swc("proactive.block", d ? d.proactive_blocked : blocked.has(p.qq), `不要主动找 ${p.name}`, `data-qq="${esc(p.qq)}"`)]);
  let below = "";
  right.push(card("按人", cand.length ? `<table class="mx"><thead><tr><th>人</th><th>好感</th>${pcol.map(([n]) => `<th>${n}</th>`).join("")}</tr></thead>
    <tbody>${cand.map((p, i) => `<tr><td><button class="who" data-go="people/${esc(p.qq)}">${av(p.qq, 40)}<span>${esc(p.name || p.qq)}</span></button></td><td>${Math.round(p.favor)}</td>${pcol.map(([, f]) => `<td>${f(p, det[i])}</td>`).join("")}</tr>`).join("")}</tbody></table>${below}`
    : empty("great", "还没有人有特别的规矩～"), {ic:"i-users", cls:"sec-person", note:"只列有特别规矩的人和好感 90 以上的；别的人在 TA 的页面里「〈我〉对 TA 的规矩」拨，和这里是同一个开关"}));
  const kpi = [["群", gs.length, "个"], ["有特别规矩的人", cand.length, "个"], st.mind && ["自主动作", (st.mind.actions || []).filter(a => a.mode === "on").length, "个开着"]];
  return {left, right, kpi, thoughts:[{t:"开关都在这里，拨一下马上生效～"}, {t:"〈我〉对谁有什么规矩，在右边那张表～"}], sub:"所有开关都在这一页；拨一下马上生效", clip:"busy",
    after(){ const el = sub && $(".card.sec-" + sub); if(el){ el.scrollIntoView({block:"start", behavior:REDUCED ? "auto" : "smooth"}); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1800); } }};
}

// ---------- 饭钱：谁吃了多少、什么时候来（按人的画像）----------
// 几位小数按数的大小定；比这位还小但不是 0 的写「<¥0.001」，不写成 ¥0.000
const yuanD = d => v => v > 0 && v < .5 / 10 ** d ? `<¥${(1 / 10 ** d).toFixed(d)}` : `¥${(+v || 0).toFixed(d)}`;
const yuan = v => yuanD(v >= 100 ? 0 : v >= 1 ? 2 : 3)(v);
// 同一列的钱用同样几位小数（按这一列最大的那个定），右对齐时小数点能对上
const yuanCol = vs => yuanD(Math.max(0, ...vs) >= 100 ? 0 : Math.max(0, ...vs) >= 1 ? 2 : 3);
const ktok = n => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n);
const WD = ["一", "二", "三", "四", "五", "六", "日"];
// 竖着的柱子：cols = [{l 底下的字, parts:[[值, 颜色, 名字]], t 悬停, attr 柱子上的属性}]
function columns(cols, unit=yuan){
  const mx = Math.max(1e-9, ...cols.map(c => c.parts.reduce((a, p) => a + p[0], 0)));
  return `<div class="vbars">${cols.map(c => { const tot = c.parts.reduce((a, p) => a + p[0], 0);
    return `<div class="vb"${c.attr || ""}${tip(`<b>${esc(c.t || c.l)}</b> ${unit(tot)}${c.parts.length > 1 ? "<br>" + c.parts.filter(p => p[0] > 0).map(p => `${esc(p[2])} ${unit(p[0])}`).join("<br>") : ""}`)}>
      <span class="vb-t"><span class="vb-s" style="height:${(tot / mx * 100).toFixed(1)}%">${tot ? c.parts.map(([v, col]) => `<i style="height:${(v / tot * 100).toFixed(1)}%;background:${col}"></i>`).join("") : ""}</span></span><small>${esc(c.l)}</small></div>`; }).join("")}</div>`;
}
// 星期 × 小时的热力格
const heatmap = h => { const mx = Math.max(1, ...h.flat());
  return `<div class="hm">${h.map((row, d) => `<span class="hm-l">周${WD[d]}</span>${row.map((v, i) => `<i style="--a:${v ? (.15 + .85 * v / mx).toFixed(2) : 0}"${tip(`<b>周${WD[d]} ${i} 点</b> ${v} 次`)}></i>`).join("")}`).join("")}
    <span></span>${Array.from({length:24}, (_, i) => `<small>${i % 6 ? "" : i}</small>`).join("")}</div>`; };
// 投喂档位的圆章：累计多少、第几档（档位和〈卡〉上的一样）
const fedStamp = f => f ? `<em class="fstamp"${tip(`投喂累计 <b>¥${+f.total}</b>（${f.n} 笔）${f.tier ? `<br>档位 ${ROMAN[f.tier] || f.tier} ${esc(f.tier_name || "")}` : ""}`)}><b>¥${+f.total}</b><small>${f.tier ? `${ROMAN[f.tier] || f.tier} ${esc(f.tier_name || "")}` : `${f.n} 笔`}</small></em>` : "";
const UBAND = {深夜:"#6f86d6", 早上:"#f2a65a", 下午:"#3fb0c9", 晚上:"#b58cd6"};
// 钱花在哪：按做的事分的几类各一种颜色（后端 billing 的 SPEND_CATS）；「没记到的」是余额实际掉得比算出来多的
const SPEND_C = {group:"#2f5fd0", private:"#e7799b", look:"#3fb0c9", squeeze:"#8ec9f2", digest:"#b58cd6", remember:"#6cc69a",
  phone:"#f2a65a", write:"#e0a630", test:"#9aa6c2", other:"#c9d3ea", unrecorded:"#a3a9c0"};
// 一张小票：每一类一行（名字、在做什么、花了多少、占几成），底下合计
function receipt(sp){
  const rows = (sp.cats || []).filter(c => c.cost >= .005 || (c.id === "group" && sp.free?.chat)).map(c => ({...c, c:SPEND_C[c.id] || "#c9d3ea"}));
  rows.sort((a, b) => b.cost - a.cost);
  // 「没记到的」不是哪件事，放在最后当找补
  if(sp.unrecorded >= .01) rows.push({id:"unrecorded", name:"没记到的", cost:sp.unrecorded, c:SPEND_C.unrecorded,
    desc:"余额实际掉的比上面加起来多：在 AstrBot 外面直接用这个 DeepSeek 账户的（比如助理在服务器上跑的测试），记不到是谁"});
  const sum = rows.reduce((a, r) => a + r.cost, 0), all = sum || 1, mx = Math.max(...rows.map(r => r.cost), 1e-9);
  const yc = yuanCol(rows.map(r => r.cost));
  const sub = r => r.id === "group" && sp.free?.chat ? `${r.desc}；降智版回的 ${sp.free.chat} 次不扣 DeepSeek 的钱` : r.desc + (r.n ? ` · ${r.n} 次` : "");
  return cbar(rows.filter(r => r.cost > 0).map(r => [r.name, +r.cost.toFixed(2), r.c, `<b>${esc(r.name)}</b> ${yuan(r.cost)}（${Math.round(r.cost / all * 100)}%）`]), false)
    + `<ol class="rcpt">${rows.map(r => `<li style="--m:${r.c}"${r.cost ? "" : ` class="free"`}><span class="rc-n"><b>${esc(r.name)}</b><small>${esc(sub(r))}</small></span>`
      + `<em>${yc(r.cost)}<small>${Math.round(r.cost / all * 100)}%</small></em><i class="rc-bar" style="width:${(r.cost / mx * 100).toFixed(1)}%"></i></li>`).join("")}</ol>
    <div class="rc-tot"><span>合计</span><b>${yc(sum)}</b></div>`;
}
// 投喂：群友给〈我〉的饭钱（钱在主人那里，这里只记账）
const today = () => { const d = new Date(); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`; };
const feedForm = (qq="") => `<div class="feedf" data-qq="${esc(qq)}">
    ${qq ? "" : `<input class="ff-qq" list="feedWho" inputmode="numeric" maxlength="12" placeholder="谁投喂的（QQ 号）" aria-label="QQ 号">`}
    <input class="ff-amt" type="number" min="0.01" step="0.01" placeholder="多少钱" aria-label="金额">
    <input class="ff-date" type="date" value="${today()}" max="${today()}" aria-label="哪天">
    <input class="ff-note" maxlength="60" placeholder="备注，可以不写" aria-label="备注">
    <button class="btn sm" data-act="feed">${ic("i-yen")}记一笔</button></div>`;
// TA 喜不喜欢〈我〉的哪几张表情包（〈我〉用 lively_meme_feedback 记的）；记错了主人可以去掉
const memePrefs = (ps, qq) => tl(ps.map(m => ({m:m.pref === "dislike" ? "#d8506f" : "#2f9e6e",
  h:`<img class="mp-img" src="/api/meme?f=${encodeURIComponent(m.file)}&w=96" alt="" loading="lazy" onerror="this.remove()"><b>${m.pref === "dislike" ? "不喜欢" : "喜欢"}</b><span class="muted small">${esc(m.file.split("/")[0])}</span>`,
  t:fmtT(m.ts).replace(/ \d+:\d+$/, ""), p:m.why ? esc(m.why) : "", s:m.pref === "like" && m.n > 1 ? `说过 ${m.n} 次喜欢` : "",
  x:`<button class="fd-del" data-act="memepref" data-qq="${esc(qq)}" data-file="${esc(m.file)}">记错了，去掉</button>`})));
const feedItems = (fs, who=true) => tl(fs.map(f => ({m:"#e0a630", h:`${who ? `<b>${esc(f.name || f.qq)}</b>` : ""}<em class="stamp ok">¥${+f.amount}</em>`,
  t:fmtT(f.ts).replace(/ \d+:\d+$/, ""), p:f.note ? esc(f.note) : "", s:f.from ? esc(f.from) : f.via === "qq" ? "在 QQ 里记的" : "",
  x:`<button class="fd-del" data-act="feeddel" data-id="${esc(f.id)}">记错了，删掉</button>`})));
// ---------- 按天的账（饭钱插件的 ledger）----------
const DAY_RE = /^d(\d{4}-\d\d-\d\d)$/;
const mdOf = k => `${+k.slice(5, 7)}月${+k.slice(8)}日`;
const BUCKETS = [["group", "群里聊天"], ["private", "私聊"], ["bg", "后台"], ["unrec", "没记到的"]];
const BUCKET_C = {group:SPEND_C.group, private:SPEND_C.private, bg:"#b58cd6", unrec:SPEND_C.unrecorded};
// 一天按四块分：群里聊天、私聊、后台（看图、回味、记忆、看 QQ……）、没记到的
const dayParts = x => { const c = x.cats || {}, v = k => (c[k] || [0])[0];
  const bg = Object.keys(c).filter(k => k !== "group" && k !== "private").reduce((a, k) => a + v(k), 0);
  return [v("group"), v("private"), bg, x.unrec || 0]; };
// 这一天一共花了多少：查过余额的按余额实际掉的，没查的按记到的
const dayTotal = x => x.actual != null && !(x.partial && !x.today) ? Math.max(x.actual, x.recorded) : x.recorded + (x.unrec || 0);
// 几天合起来的「钱花在哪」：和 receipt() 要的格式一样
function spendOf(L, list){
  const cats = (L.cats || []).map(c => ({...c, cost:0, n:0}));
  let unrec = 0, free = 0;
  for(const x of list){ for(const [k, [v, n]] of Object.entries(x.cats || {})){ const c = cats.find(c => c.id === k); if(c){ c.cost += v; c.n += n; } }
    unrec += x.unrec || 0; free += (x.free || [0])[0]; }
  return {cats:cats.filter(c => c.n), unrecorded:unrec, free:{chat:free}};
}
const sumOf = (list, f) => list.reduce((a, x) => a + (f(x) || 0), 0);
// 每天一行：哪天、四块的条、记到多少、没记到多少、充值投喂画图、一共
function ledgerList(list, mx){
  const yc = yuanCol(list.map(dayTotal));
  return `<ol class="ldg">${list.slice().reverse().map(x => { const ps = dayParts(x), tot = dayTotal(x), tags = [];
    if(x.topup) tags.push(`<span class="tag good">充了 ¥${+x.topup}</span>`);
    const fed = sumOf(x.feeds || [], f => f.amount); if(fed) tags.push(`<span class="tag fed">投喂 ¥${+fed.toFixed(2)}</span>`);
    if(x.img) tags.push(`<span class="tag">画了 ${x.img} 张</span>`);
    if(x.voice && x.voice[1]) tags.push(`<span class="tag">语音 ${x.voice[0]} 条</span>`);
    if(x.free && x.free[1] >= .01) tags.push(`<span class="tag good">降智版省 ¥${(+x.free[1]).toFixed(2)}</span>`);
    const sub = x.actual == null ? `没查余额，记到的 ${yuan(x.recorded)}` : `记到 ${yuan(x.recorded)}${x.unrec >= .01 ? ` · 没记到 ${yuan(x.unrec)}` : ""}`;
    return `<li><button class="ldg-r${x.today ? " now" : ""}" data-day="${x.day}"${tip(`<b>${mdOf(x.day)} 周${WD[x.wd]}</b>${BUCKETS.map(([k, n], i) => ps[i] >= .005 ? `<br>${n} ${yuan(ps[i])}` : "").join("")}`)}>
      <span class="ldg-d"><b>${+x.day.slice(8)}</b><small>${x.today ? "今天" : "周" + WD[x.wd]}</small></span>
      <span class="ldg-m"><span class="ldg-bar" style="width:${Math.max(1.5, tot / mx * 100).toFixed(1)}%">${ps.map((v, i) => v > 0 ? `<i style="flex:${v.toFixed(4)};background:${BUCKET_C[BUCKETS[i][0]]}"></i>` : "").join("")}</span>
        <small>${sub}${x.today ? ` · 到 ${fmtT(L_NOW).slice(-5)}` : x.partial && x.actual != null ? " · 余额没查全" : ""}</small>${tags.length ? `<span class="ldg-t">${tags.join("")}</span>` : ""}</span>
      <em>${tot ? yc(tot) : "—"}</em></button></li>`; }).join("")}</ol>`;
}
let L_NOW = 0;
const BAL_W = 320, BAL_H = 130;
// 余额的线：最近 14 天怎么掉的、哪天充了钱、照现在的速度大概哪天吃完
function balanceChart(L){
  const now = L.now, pts = (L.balance || []).filter(p => p[0] >= now - 14 * 864e2);
  if(pts.length < 2) return "";
  const t0 = pts[0][0];
  const per = L.per_day || 0, ahead = per && L.bal != null ? Math.min(10, L.bal / per) : 0, t1 = now + Math.max(1, ahead) * 864e2;
  const mx = Math.max(...pts.map(p => p[1]), L.alert_at || 0) * 1.12, X = t => 8 + (t - t0) / (t1 - t0) * (BAL_W - 16), Y = v => BAL_H - 18 - v / mx * (BAL_H - 30);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)} ${Y(p[1]).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1], days = [];
  for(let d = new Date(t0 * 1000); d.getTime() / 1000 <= t1; d.setDate(d.getDate() + 1)){ d.setHours(0, 0, 0, 0); if(d.getTime() / 1000 >= t0) days.push(d.getTime() / 1000); }
  const end = ahead ? new Date((now + L.bal / per * 864e2) * 1000) : null;
  return `<svg class="balc" viewBox="0 0 ${BAL_W} ${BAL_H}" role="img" aria-label="余额最近 14 天的变化">
    ${days.map((t, i) => `<line class="bc-g" x1="${X(t).toFixed(1)}" x2="${X(t).toFixed(1)}" y1="8" y2="${BAL_H - 18}"/>${i % 2 ? "" : `<text class="bc-x" x="${X(t).toFixed(1)}" y="${BAL_H - 5}">${new Date(t * 1000).getDate()}</text>`}`).join("")}
    ${L.alert_at ? `<line class="bc-alert" x1="8" x2="${BAL_W - 8}" y1="${Y(L.alert_at).toFixed(1)}" y2="${Y(L.alert_at).toFixed(1)}"/><text class="bc-al" x="10" y="${(Y(L.alert_at) - 4).toFixed(1)}">¥${L.alert_at} 提醒</text>` : ""}
    <path class="bc-area" d="${path} L${X(last[0]).toFixed(1)} ${BAL_H - 18} L${X(pts[0][0]).toFixed(1)} ${BAL_H - 18}Z"/>
    <path class="bc-line" d="${path}"/>
    ${ahead ? `<line class="bc-proj" x1="${X(last[0]).toFixed(1)}" y1="${Y(last[1]).toFixed(1)}" x2="${X(now + ahead * 864e2).toFixed(1)}" y2="${Y(Math.max(0, last[1] - per * ahead)).toFixed(1)}"/>` : ""}
    ${(L.topups || []).filter(t => t.ts >= t0).map(t => { const p = pts.find(p => p[0] >= t.ts) || last;
      return `<g class="bc-top"${tip(`<b>${fmtT(t.ts)}</b> 充了 ¥${t.amount}`)}><circle cx="${X(t.ts).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="4"/><text x="${X(t.ts).toFixed(1)}" y="${(Y(p[1]) - 8).toFixed(1)}">+¥${Math.round(t.amount)}</text></g>`; }).join("")}
    <circle class="bc-now" cx="${X(last[0]).toFixed(1)}" cy="${Y(last[1]).toFixed(1)}" r="3.5"/>
  </svg><p class="small muted bc-cap">实线是余额，虚线是照最近三天的速度往后推${end ? `：大约 <b>${end.getMonth() + 1}月${end.getDate()}日</b>吃完` : ""}</p>`;
}
// 语音走 BreezeBlue，按点数扣，不扣 DeepSeek 余额；点数是 BreezeBlue 记的，钱是估的
const VOICE_NOTE = L => `语音走 BreezeBlue，按点数扣（中文一个字 0.2 点），不扣 DeepSeek 的余额；点数是 BreezeBlue 那边记的，钱按 ¥${L.voice?.price_10k ?? "?"}／1 万点估，实际以 BreezeBlue 的 Subscription 页和生成前的确认为准`;
// 省钱看点：没记到的集中在哪几个钟点、缓存省了多少、白天高峰多花多少、降智版、画图、语音
function insights(L, list, label){
  const out = [], act = sumOf(list, x => x.actual), unrec = sumOf(list, x => x.unrec);
  if(unrec >= .05){
    const gaps = [];
    for(const x of list) (x.hours || []).forEach((h, i) => { if(h[3] == null) return; const g = h[3] - h[0] - h[1] - h[2]; if(g >= .1) gaps.push([g, x.day, i]); });
    gaps.sort((a, b) => b[0] - a[0]);
    out.push({m:SPEND_C.unrecorded, h:`<b>没记到的 ${yuan(unrec)}</b>${act ? `<span class="muted small">占实际扣的 ${Math.round(unrec / act * 100)}%</span>` : ""}`,
      p:"余额掉了，但 AstrBot 里没有这笔：多半是在服务器上直接用这个 DeepSeek 账户跑的测试、重放（不经过〈我〉），请求超时被掐断、钱照扣的也会算在这里",
      s:gaps.length ? "掉得最多的钟点：" + gaps.slice(0, 4).map(([g, d, i]) => `${list.length > 1 ? `${+d.slice(5, 7)}-${+d.slice(8)} ` : ""}${i} 点 ${yuan(g)}`).join("、") : ""});
  }
  const [m, h] = [sumOf(list, x => x.tok[0]), sumOf(list, x => x.tok[1])], saved = sumOf(list, x => x.cache_saved);
  if(m + h) out.push({m:"#6cc69a", h:`<b>缓存命中 ${Math.round(h / (m + h) * 100)}%</b><span class="muted small">省了 ${yuan(saved)}</span>`,
    p:`输入里 ${ktok(h)} token 是缓存里有的（便宜 50 倍），${ktok(m)} 没命中。聊天开头（人设、工具说明）每次一样才命中得多`});
  const peak = sumOf(list, x => x.peak_extra);
  if(peak >= .01) out.push({m:"#f2a65a", h:`<b>白天高峰多花了 ${yuan(peak)}</b>`, p:"DeepSeek 工作日 9～12 点、14～18 点价格翻倍；这段时间里做的都按两倍算"});
  const fn = sumOf(list, x => x.free[0]), fw = sumOf(list, x => x.free[1]);
  if(fn) out.push({m:SPEND_C.group, h:`<b>降智版省了 ${yuan(fw)}</b><span class="muted small">${fn} 次调用没扣 DeepSeek 的钱${list.length > 1 ? `，平均每天 ${yuan(fw / list.length)}` : ""}</span>`,
    p:`照 DeepSeek 的价算的。${list.length > 1 ? "每天：" + list.map(x => `${mdOf(x.day)} ${yuan(x.free[1] || 0)}`).join("、") : "这天走的都是降智版，一分钱没扣"}`});
  const img = sumOf(list, x => x.img);
  if(img) out.push({m:"#e0a630", h:`<b>画了 ${img} 张图</b><span class="muted small">约 ${yuan(img * (L.image_price || 0))}</span>`, p:`画图走中转站，不扣这里的余额；按一张 ¥${L.image_price} 估`});
  const vn = sumOf(list, x => (x.voice || [])[0]), vc = sumOf(list, x => (x.voice || [])[1]), vy = sumOf(list, x => (x.voice || [])[2]);
  if(vc) out.push({m:"#e7799b", h:`<b>发了 ${vn} 条语音</b><span class="muted small">扣了 ${+vc.toFixed(1)} 点，约 ${yuan(vy)}</span>`, p:VOICE_NOTE(L)});
  return out.length ? tl(out) : empty("sleep", `${label}没什么可说的～`);
}
async function renderBill(sub){
  const dm = DAY_RE.exec(sub || "");
  const [d, L] = await Promise.all([soft(get("/api/usage?days=30")), soft(get("/api/ledger?days=30"))]);
  if(L) L_NOW = L.now;
  if(dm) return renderBillDay(dm[1], L, d);
  if(!d && !L) return {left:[card("饭钱", fail("饭钱") + `<p class="small muted">要饭钱插件开着</p>`, {ic:"i-yen"})], right:[], clip:"sigh", kpi:[]};
  const us = d?.users || [], fs = d?.feeds || [];
  if(sub) return renderBillPerson(sub, d || {}, us.find(u => u.qq === sub), fs.filter(f => f.qq === sub), null);
  // 开始记账之前的那几天什么都没有，不列
  const all = L?.list || [], list = all.slice(Math.max(0, all.findIndex(x => x.recorded > 0 || x.actual != null))), l14 = list.slice(-14), l7 = list.slice(-7);
  const fedSum = fs.reduce((a, f) => a + f.amount, 0), per = L?.per_day || 0, fd = d?.feeders || [];
  // 左：每天的账（点一天看细账）、钱花在哪
  const left = [];
  if(L){
    const pane = ls => { const mx = Math.max(1e-9, ...ls.map(dayTotal));
      return columns(ls.map(x => ({l:String(+x.day.slice(8)), t:`${mdOf(x.day)} 周${WD[x.wd]}`, attr:` data-day="${x.day}"`,
          parts:dayParts(x).map((v, i) => [v, BUCKET_C[BUCKETS[i][0]], BUCKETS[i][1]])})))
        + `<div class="legend" style="margin:8px 0 12px">${BUCKETS.map(([k, n]) => `<span style="--m:${BUCKET_C[k]}">${n}</span>`).join("")}</div>` + ledgerList(ls, mx); };
    left.push(card("每天的账", tabs([["最近 14 天", pane(l14)], ["30 天", pane(list)]]),
      {ic:"i-chart", raw:true, meta:per ? `一天约 <b>${yuan(per)}</b>` : "", note:"每一天余额实际扣了多少、花在哪。点一天看那天的细账：每个钟点、谁、最贵的几次"}));
    const recv = ls => { const sp = spendOf(L, ls); return receipt(sp); };
    const imgs = sumOf(list, x => x.img), vn = sumOf(list, x => (x.voice || [])[0]), vc = sumOf(list, x => (x.voice || [])[1]), vy = sumOf(list, x => (x.voice || [])[2]);
    left.push(card("钱花在哪", tabs([["7 天", recv(l7)], ["30 天", recv(list)]])
        + `<p class="small muted rc-note" style="padding:0 18px 14px;margin:0">按每次用的 token 和 DeepSeek 的官方价算（白天高峰翻倍）；「没记到的」是余额实际掉得比记到的多的部分${imgs ? `。画图另算：这 30 天 ${imgs} 张，约 ${yuan(imgs * L.image_price)}` : ""}${vc ? `。语音另算：这 30 天 ${vn} 条，BreezeBlue 扣了 ${+vc.toFixed(1)} 点，约 ${yuan(vy)}` : ""}</p>`,
      {ic:"i-yen", raw:true, note:"〈我〉的 DeepSeek 饭钱都吃在哪了"}));
  } else left.push(card("每天的账", empty("rice", "饭钱插件太旧，还不会按天记账～"), {ic:"i-chart"}));
  // 右：余额、省钱看点、谁吃得最多、投喂
  const right = [];
  if(L?.bal != null){
    const low = L.runway != null && L.runway < 5;
    right.push(card("余额", `<div class="stats">${stat("还剩", yuan(L.bal), L.updated ? `${ago(L.updated)}查的` : "", low ? "bad" : "")}${stat("还够吃", L.runway != null ? `${L.runway} 天` : "—", per ? `一天约 ${yuan(per)}` : "", low ? "warn" : "")}</div>` + balanceChart(L),
      {ic:"i-yen", note:`余额大约每小时查一次；低于 ¥${L.alert_at} 会提醒主人充钱`}));
  }
  if(L?.voice?.bal != null){
    const vt = (list[list.length - 1]?.voice || [0, 0, 0]), v30 = sumOf(list, x => (x.voice || [])[1]);
    right.push(card("语音的点数", `<div class="stats">${stat("还剩", `${+(+L.voice.bal).toFixed(1)} 点`, L.voice.updated ? `${ago(L.voice.updated)}查的` : "")}${stat("今天", `${vt[0]} 条`, `扣了 ${+(+vt[1]).toFixed(1)} 点`)}${stat("30 天", `${+v30.toFixed(1)} 点`, `约 ${yuan(sumOf(list, x => (x.voice || [])[2]))}`)}</div>`
        + `<p class="small muted" style="margin:10px 0 0">${esc(VOICE_NOTE(L))}</p>`,
      {ic:"i-yen", note:"BreezeBlue 的点数大约每小时查一次，和 DeepSeek 的余额分开"}));
  }
  if(L) right.push(card("省钱看点", insights(L, l7, "这 7 天"), {ic:"i-spark", note:"最近 7 天：钱漏在哪、省在哪"}));
  const row = (u, v, w, c, sub) => ({qq:u.qq, img:av(u.qq, 40), lb:esc(u.name || u.qq) + (u.owner ? ` <span class="tag warn">主人</span>` : "") + (u.fed ? ` <span class="tag fed">投喂 ¥${+u.fed}</span>` : ""), v, w, c, sub});
  const mxc = Math.max(1e-9, ...us.map(u => u.cost));
  const where = u => u.private_share >= .5 ? "多在私聊" : u.private ? "群里和私聊" : "只在群里";
  const ycu = yuanCol(us.slice(0, 20).map(u => u.cost));
  const byCost = us.slice(0, 20).map(u => row(u, ycu(u.cost), u.cost / mxc, "#f2a65a", `${u.turns} 次 · ${where(u)}`));
  const mxf = Math.max(1e-9, ...fd.map(f => f.total));
  const byFed = fd.slice(0, 20).map(f => row(f, "¥" + +f.total, f.total / mxf, "#e0a630",
    `${f.tier ? `${ROMAN[f.tier] || f.tier} ${f.tier_name || ""} · ` : ""}${f.n} 笔 · 最近 ${ago(f.last)}`));
  const ranks = [["花得最多", us.length ? blist(byCost, true) : "", us.length],
    ["投喂", fd.length ? blist(byFed, true) : empty("rice", "还没有人投喂过〈我〉～"), fd.length]];
  if(d?.heat) ranks.push(["什么时候来", heatmap(d.heat) + `<p class="small muted" style="margin:8px 0 0">每一格是那个钟点被找了几次（按人记以后）</p>`]);
  right.push(card("谁吃得最多", tabs(ranks) || empty("sleep", "还没有按人记到的用量，过几个小时再来看～"),
    {ic:"i-users", raw:us.length > 0, note:"聊天回复算到叫〈我〉的人头上：群里是说话的人，私聊是对方。投喂按累计排，档位和〈卡〉上的一样。点一个人看 TA 的画像"}));
  right.push(card("投喂", (fs.length ? `<p class="fed-sum">大家一共投喂了 <b>¥${+fedSum.toFixed(2)}</b>（${fs.length} 笔）${per ? `，够〈我〉吃 ${(fedSum / per).toFixed(1)} 天` : ""}～</p>` + feedItems(fs.slice(0, 12)) : empty("rice", "还没有人投喂过〈我〉～"))
      + `<div class="sec" style="margin-top:14px">记一笔</div>` + feedForm() + `<datalist id="feedWho">${us.filter(u => !u.owner).map(u => `<option value="${esc(u.qq)}">${esc(u.name)}</option>`).join("")}</datalist>`,
    {ic:"i-heart", cls:"pink", meta:fs.length ? `<b>¥${+fedSum.toFixed(2)}</b>` : "", note:"群友给〈我〉的饭钱。钱在主人那里，这里只记账；〈我〉聊天时听说了会自己记上，写着是谁说的"}));
  const th = [], yd = list[list.length - 2], all30 = sumOf(list, dayTotal);
  if(yd && dayTotal(yd)) th.push({t:`昨天吃了 ${yuan(dayTotal(yd))}${yd.unrec >= .5 ? `，其中 ${yuan(yd.unrec)} 不是〈我〉吃的，多半是测试` : ""}～`});
  const sp7 = L ? spendOf(L, l7) : null, big = sp7?.cats.slice().sort((a, b) => b.cost - a.cost)[0];
  if(big && big.cost) th.push({t:`这 7 天${big.name}吃得最多，${yuan(big.cost)}～`});
  const top = us.find(u => !u.owner);
  if(top) th.push({t:`群友里 ${top.name} 让〈我〉吃得最多，${yuan(top.cost)}～`});
  if(fs.length) th.push({t:`${fs[0].name} 上次投喂了 ¥${+fs[0].amount}，〈我〉记着呢～`});
  if(fd.length > 1) th.push({t:`投喂得最多的是 ${fd[0].name}，一共 ¥${+fd[0].total}～`});
  if(L?.runway != null) th.push({t:`饭钱还剩 ${yuan(L.bal)}，照一天 ${yuan(per)} 还能吃 ${L.runway} 天～`});
  const low = L?.runway != null && L.runway < 5;
  const kpi = [yd && ["昨天", yuan(dayTotal(yd)), "", "", yd.unrec ? `记到的 ${yuan(yd.recorded)}＋没记到的 ${yuan(yd.unrec)}` : ""],
    L && [`${list.length} 天`, yuan(all30), "", "", "查过余额的日子按余额实际扣的，没查的按记到的"],
    L?.bal != null && ["还剩", yuan(L.bal), "", low ? "bad" : ""],
    L?.runway != null && ["还够吃", L.runway, "天", low ? "bad" : "", per ? `照一天 ${yuan(per)}（最近三天余额实际掉的平均）` : ""],
    ["大家投喂了", "¥" + +fedSum.toFixed(2), fs.length ? `${fs.length} 笔` : ""]];
  return {left, right, thoughts:th, kpi, sub:"每天吃了多少、吃在哪、谁让〈我〉吃得多、谁投喂过〈我〉", clip:"rice", after:bindBill};
}
function bindBill(){
  $$(".blist button[data-qq]").forEach(b => b.onclick = () => { FX.pickFrom(b.querySelector("img")); go("bill", b.dataset.qq); });
  $$("[data-day]").forEach(b => b.onclick = () => go("bill", "d" + b.dataset.day));
}
// 某一天的细账：这一天、钱花在哪、每个钟点；谁、最贵的几次、按模型设定、省钱看点
function renderBillDay(day, L, d){
  const list = L?.list || [], i = list.findIndex(x => x.day === day), x = list[i];
  const back = `<button class="btn alt sm" data-go="bill">${ic("i-list")}回到饭钱</button>`;
  if(!x) return {left:[card(mdOf(day), empty("sleep", L ? "这一天不在最近 30 天的账里～" : "读不到按天的账，饭钱插件可能太旧了～"), {ic:"i-yen", foot:back})], right:[], kpi:[], clip:"sigh", title:mdOf(day)};
  const prev = list[i - 1], next = list[i + 1], nav = (y, t) => y ? `<button class="btn alt sm" data-go="bill/d${y.day}">${t}</button>` : "";
  const foot = nav(prev, `← ${mdOf(prev?.day || "0000-00-00")}`) + nav(next, `${mdOf(next?.day || "0000-00-00")} →`) + back;
  const ps = dayParts(x), tot = dayTotal(x), fed = sumOf(x.feeds || [], f => f.amount), calls = sumOf(Object.values(x.cats || {}), c => c[1]);
  const notes = [];
  if(x.today) notes.push(`今天还没过完，这是到 ${fmtT(L.now).slice(-5)} 的`);
  else if(x.actual == null) notes.push("这天还没开始查余额，只有记到的");
  else if(x.partial) notes.push("这天余额没从一早查起，实际扣的少算了一点");
  if(x.topup) notes.push(`这天充了 ¥${+x.topup}`);
  if(fed) notes.push(`这天 ${x.feeds.map(f => `${esc(f.name)} 投喂了 ¥${+f.amount}`).join("、")}`);
  const hours = x.hours.map((h, k) => { const gap = h[3] != null ? Math.max(0, h[3] - h[0] - h[1] - h[2]) : 0;
    return {l:k % 3 ? "" : String(k), t:`${k}:00～${k + 1}:00${h[3] != null ? `，余额掉了 ${yuan(h[3])}` : ""}`, parts:[[h[0], BUCKET_C.group, "群里聊天"], [h[1], BUCKET_C.private, "私聊"], [h[2], BUCKET_C.bg, "后台"], [gap, BUCKET_C.unrec, "没记到的"]]}; });
  const left = [
    card("这一天", `<div class="stats">${stat("实际扣了", x.actual != null ? yuan(x.actual) : "—", x.bal ? `余额 ¥${(+x.bal[0]).toFixed(2)} → ¥${(+x.bal[1]).toFixed(2)}` : "没查余额")}${stat("记到的", yuan(x.recorded), `${calls} 次调用模型`)}`
        + `${stat("没记到的", x.unrec != null ? yuan(x.unrec) : "—", "在 AstrBot 外面用掉的", x.unrec > x.recorded ? "warn" : "")}${stat("降智版省了", x.free && x.free[1] != null ? yuan(x.free[1]) : "—", `${x.free ? x.free[0] : 0} 次，照 DeepSeek 价要花的钱`, "good")}</div>`
        + (notes.length ? `<div class="callout" style="margin-top:10px">${ic("i-info")}<span>${notes.join("；")}</span></div>` : ""),
      {ic:"i-yen", meta:`<b>${yuan(tot)}</b>`, foot}),
    card("钱花在哪", receipt(spendOf(L, [x])) + (x.img ? `<p class="small muted rc-note">画图另算：这天 ${x.img} 张，约 ${yuan(x.img_cost)}</p>` : "")
      + (x.voice && x.voice[1] ? `<p class="small muted rc-note">语音另算：这天 ${x.voice[0]} 条，BreezeBlue 扣了 ${+(+x.voice[1]).toFixed(1)} 点，约 ${yuan(x.voice[2])}</p>` : ""), {ic:"i-list"}),
    card("每个钟点", columns(hours) + `<div class="legend" style="margin-top:8px">${BUCKETS.map(([k, n]) => `<span style="--m:${BUCKET_C[k]}">${n}</span>`).join("")}</div>`,
      {ic:"i-clock", note:"灰色是那个钟点余额掉了、但 AstrBot 里没记到的"})];
  const pmx = Math.max(1e-9, ...(x.people || []).map(p => p.cost));
  const right = [
    card("这天谁吃得多", (x.people || []).length ? blist(x.people.map((p, _, a) => ({qq:p.qq, img:av(p.qq, 40), lb:esc(p.name), sub:`${p.n} 次`, v:yuanCol(a.map(q => q.cost))(p.cost), w:p.cost / pmx, c:"#f2a65a"})), true)
        + (x.people_n > x.people.length ? `<p class="small muted" style="margin:8px 0 0">还有 ${x.people_n - x.people.length} 个人</p>` : "") : empty("sleep", "这天没记到谁～"),
      {ic:"i-users", note:"只算聊天回复，后台的不算到人头上"}),
    card("最贵的几次", (x.top || []).length ? tl(x.top.map(t => ({m:SPEND_C[t.cat] || "#c9d3ea", h:`<b>${esc((L.cats.find(c => c.id === t.cat) || {}).name || t.cat)}</b><span class="muted small">${esc(t.what)}</span>${t.peak ? `<span class="tag warn">高峰</span>` : ""}`,
        t:fmtT(t.ts).slice(-5), s:`读了 ${ktok(t.in)}（缓存里有 ${ktok(t.hit)}），写了 ${ktok(t.out)} · <b>${yuan(t.cost)}</b> · ${esc(t.pid)}`}))) : empty("sleep", "这天没有花钱的调用～"),
      {ic:"i-spark", note:"一次调用花了多少：读得多（聊天记录长、带了一堆记忆）就贵"}),
    (x.keys || []).length ? card("按模型设定", blist(x.keys.map((k, _, a) => ({lb:esc(k.label), sub:k.label !== k.id ? esc(k.id) : "", v:yuanCol(a.map(q => q.cost))(k.cost), w:k.cost / Math.max(1e-9, x.keys[0].cost), c:"#8ec9f2"}))),
      {ic:"i-list", note:"钱记在哪个模型设定上（AstrBot 里配的），降智版不算"}) : "",
    card("省钱看点", insights(L, [x], "这天"), {ic:"i-spark"})].filter(Boolean);
  const th = [{t:`${mdOf(day)}〈我〉${x.today ? "到现在" : ""}吃了 ${yuan(tot)}～`}];
  const bigCat = spendOf(L, [x]).cats.sort((a, b) => b.cost - a.cost)[0];
  if(bigCat?.cost) th.push({t:`${bigCat.name}吃得最多，${yuan(bigCat.cost)}～`});
  if(x.unrec >= .3) th.push({t:`有 ${yuan(x.unrec)} 不是〈我〉吃的，余额自己掉的，多半是测试～`});
  if(x.people?.[0]) th.push({t:`这天 ${x.people[0].name} 找〈我〉最多，${x.people[0].n} 次～`});
  const kpi = [["一共", yuan(tot), "", "", x.actual != null ? "余额实际扣的" : "没查余额，按记到的"], ["记到的", yuan(x.recorded), "", "", `${calls} 次调用`],
    x.unrec != null && ["没记到的", yuan(x.unrec), "", x.unrec > x.recorded ? "warn" : ""], x.bal && ["余额", "¥" + (+x.bal[1]).toFixed(2), "", "", `这天从 ¥${(+x.bal[0]).toFixed(2)} 到 ¥${(+x.bal[1]).toFixed(2)}`],
    x.img && ["画图", x.img, "张"], x.voice && x.voice[1] && ["语音", x.voice[0], "条", "", `BreezeBlue 扣了 ${+(+x.voice[1]).toFixed(1)} 点，约 ${yuan(x.voice[2])}（估的）`]];
  return {left, right, thoughts:th, kpi, title:`${mdOf(day)} 周${WD[x.wd]}`, sub:"这一天的细账 · ← → 换一天 · Esc 回到饭钱", clip:"rice", after:bindBill};
}
function renderBillPerson(qq, d, u, fs, bill){
  const fed = fs.reduce((a, f) => a + f.amount, 0);
  const feedCard = card("TA 的投喂", (fs.length ? `<p class="fed-sum">一共投喂了 <b>¥${+fed.toFixed(2)}</b>（${fs.length} 笔）</p>` + feedItems(fs, false) : `<p class="small muted" style="margin:0 0 8px">TA 还没投喂过〈我〉</p>`) + feedForm(qq),
    {ic:"i-heart", cls:"pink", note:"钱在主人那里，这里只记账"});
  if(!u) return {left:[card("这个人", empty("sleep", "这 30 天 TA 没找过〈我〉～"), {ic:"i-users"}), feedCard], right:[], clip:"sigh", kpi:[], title:fs[0]?.name || qq};
  const gn = d.group_names || {}, tok = u.miss + u.hit + u.out;
  const facts = [["常来", u.band ? `${u.band}${u.peak_hour != null ? `，最常 ${u.peak_hour} 点` : ""}` : "—"], ["在哪聊", u.private_share >= .5 ? `私聊为主（${Math.round(u.private_share * 100)}%）` : u.private ? `群里为主，私聊 ${Math.round(u.private_share * 100)}%` : "只在群里"],
    ["主动", `${Math.round(u.called_share * 100)}% 是 TA 自己叫〈我〉`], ["周末", `${Math.round(u.weekend * 100)}% 在周末`], ["一次", `${yuan(u.per_turn)}，约 ${ktok(Math.round(tok / Math.max(1, u.turns)))} token`],
    ["认识", `第一次 ${fmtT(u.first)}，最近 ${ago(u.last)}`], u.favor != null && ["好感度", String(u.favor)]].filter(Boolean);
  const badge = fedStamp((d.feeders || []).find(f => f.qq === qq));
  const left = [card("画像", `<div class="who">${av(qq, 64)}<span><b>${esc(u.name)}</b><small>QQ ${esc(qq)}${u.owner ? " · 主人" : ""}</small></span>${badge}</div>
      <div style="margin:12px 0 4px">${u.tags.length ? u.tags.map(t => `<span class="tag blue">${esc(t)}</span>`).join("") : `<span class="muted small">聊得还太少，看不出习惯</span>`}</div>
      <dl class="dl">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`, {ic:"i-users", cls:"pink",
      foot:`<button class="btn alt sm" data-go="people/${esc(qq)}">${ic("i-heartcard")}看 TA 的〈卡〉</button><button class="btn alt sm" data-go="bill">${ic("i-list")}回到排行</button>`}),
    feedCard,
    card("token 用在哪", `<div class="stats">${stat("没命中缓存", ktok(u.miss), "最贵的输入")}${stat("命中缓存", ktok(u.hit), "便宜的输入")}${stat("〈我〉写的", ktok(u.out), "输出")}${stat("一共", yuan(u.cost), `${u.turns} 次对话`)}</div>`, {ic:"i-yen"})];
  const last14 = Array.from({length:14}, (_, i) => { const dt = new Date(Date.now() - (13 - i) * 864e5), k = `${dt.getFullYear()}-${p2(dt.getMonth() + 1)}-${p2(dt.getDate())}`;
    return {l:String(dt.getDate()), t:k, parts:[[(u.days || {})[k] || 0, "#2f5fd0", "花费"]]}; });
  const mh = Math.max(1, ...u.hours);
  const where = [...Object.entries(u.groups || {}).map(([g, n]) => [gn[g] || ("群 " + g), n]), ...(u.private ? [["私聊", u.private]] : [])].sort((a, b) => b[1] - a[1]);
  const right = [card("什么时候来", `<div class="sec">一天里</div><div class="heat">${u.hours.map((v, i) => { const band = HOUR_BAND(i);
        return `<i class="${i === u.peak_hour && v ? "pk" : ""}" style="height:${Math.max(3, v / mh * 100)}%;${i === u.peak_hour && v ? "" : `background:${UBAND[band]}`}"${tip(`<b>${i} 点</b> ${v} 次`)}></i>`; }).join("")}</div>
      <div class="heat-ax"><span>0 点</span><span>6</span><span>12</span><span>18</span><span>23</span></div>
      <div class="sec" style="margin-top:14px">一周里</div>${columns(u.wdays.map((v, i) => ({l:"周" + WD[i], parts:[[v, i >= 5 ? "#e7799b" : "#8ec9f2", "次数"]]})), v => v + " 次")}`, {ic:"i-clock", meta:u.band ? `多在 <b>${u.band}</b>` : ""}),
    card("每天花了多少", columns(last14) + `<p class="small muted" style="margin:8px 0 0">这 30 天来了 ${u.active_days} 天</p>`, {ic:"i-chart"}),
    card("在哪聊", where.length ? blist(where.map(([k, n]) => ({lb:esc(k), v:n + " 次", w:n / Math.max(1, u.turns), c:k === "私聊" ? "#e7799b" : "#2f5fd0"}))) : empty("sleep", "还没记到～"), {ic:"i-bubbles"})];
  const th = [{t:`${u.name} 这 30 天让〈我〉吃了 ${yuan(u.cost)}，聊了 ${u.turns} 次～`}];
  if(fed) th.push({t:`TA 投喂过〈我〉 ¥${+fed.toFixed(2)}，${fed >= u.cost ? "比 TA 让〈我〉吃掉的还多，嘿嘿" : "〈我〉记着呢"}～`});
  if(u.band) th.push({t:`TA 多半${u.band}来找〈我〉${u.peak_hour != null ? `，${u.peak_hour} 点最多` : ""}～`});
  const kpi = [["30 天花了", yuan(u.cost)], fed && ["投喂过", "¥" + +fed.toFixed(2), `${fs.length} 笔`], ["对话", u.turns, "次"], ["来了", u.active_days, "天"]];
  return {left, right, thoughts:th, kpi, title:u.name, sub:`${u.tags.slice(0, 3).join(" · ") || "聊得还太少"} · Esc 回到排行`, clip:fed ? "hop" : "think"};
}
const HOUR_BAND = h => h < 6 ? "深夜" : h < 12 ? "早上" : h < 18 ? "下午" : "晚上";
// 卡片底下「去别的脑区」的按钮
document.addEventListener("click", e => { const b = e.target.closest("[data-go]"); if(!b) return; const [r, s] = b.dataset.go.split("/"); go(r, s); });
addEventListener("keydown", e => { if(region !== "bill" || e.target.closest?.("input,textarea,select")) return;
  if(e.key === "Escape" && location.hash.includes("/")) go("bill");
  // 某一天的细账里左右键换一天
  const m = /#bill\/d(\d{4}-\d\d-\d\d)/.exec(location.hash);
  if(m && (e.key === "ArrowLeft" || e.key === "ArrowRight")){
    const t = $$(`.card-f [data-go^="bill/d"]`).map(b => b.dataset.go.slice(6)).find(k => e.key === "ArrowLeft" ? k < m[1] : k > m[1]);
    if(t) go("bill", "d" + t); } });

// ---------- 表情包（10-28）：库里每张看一眼、换分类、拿下来（放进隔离区，不删）、从隔离区放回 ----------
// 选中、筛选这些只在页面里，点一下就地重画，不用整页重新飘一遍
const QDIR = {quarantine_panel:"面板上拿下来的", quarantine_1024:"10-24 精简时", quarantine_1026_week_iter:"10-26 换一批时",
  quarantine_1026_weekly_overflow:"10-26 超出的", quarantine_screenshots_10202311:"10-20 截图"};
const qdirName = d => QDIR[d] || d.replace(/^quarantine_?/, "") || d;
const MG = {d:null, q:null, sel:[], from:"lib", filter:"all", sort:"cat", find:"", qdir:"", qfind:"", qn:60, multi:false, names:{}};
const mgUrl = (rel, w=128) => `/api/meme?f=${encodeURIComponent(rel)}&w=${w}`;
const kb = n => n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
const dislikes = it => (it.prefs || []).filter(p => p.pref === "dislike").length;
const MG_FILTERS = [["all", "全部", () => true], ["mine", "〈我〉收的", it => it.added], ["unused", "没发过", it => !it.uses[0]],
  ["disliked", "有人不喜欢", it => dislikes(it)], ["liked", "有人喜欢", it => (it.prefs || []).some(p => p.pref === "like")]];
const MG_SORTS = {cat:"按分类", new:"新放进来的在前", most:"发得多的在前", least:"发得少的在前"};
const mgHit = (it, word) => !word || `${it.code} ${it.desc} ${it.cat} ${it.added?.why || ""}`.toLowerCase().includes(word.toLowerCase());
function mgList(){
  if(MG.from === "q") return mgQList().slice(0, MG.qn).map(x => x.rel);
  const f = MG.filter.startsWith("c:") ? (it => it.cat === MG.filter.slice(2)) : (MG_FILTERS.find(x => x[0] === MG.filter) || MG_FILTERS[0])[2];
  const rows = (MG.d?.items || []).filter(it => f(it) && mgHit(it, MG.find));
  const by = {cat:(a, b) => a.cat.localeCompare(b.cat) || a.code.localeCompare(b.code), new:(a, b) => b.mtime - a.mtime,
    most:(a, b) => b.uses[0] - a.uses[0] || b.uses[1] - a.uses[1], least:(a, b) => a.uses[0] - b.uses[0] || a.uses[1] - b.uses[1]}[MG.sort];
  return rows.sort(by).map(it => it.rel);
}
const mgQList = () => (MG.q || []).filter(x => (!MG.qdir || x.dir === MG.qdir) && mgHit(x, MG.qfind));
const mgItem = rel => (MG.d?.items || []).find(it => it.rel === rel) || (MG.q || []).find(x => x.rel === rel);
const mgSince = () => MG.d?.since ? fmtT(MG.d.since).replace(/ \d+:\d+$/, "") : "现在";
function mgTile(rel){
  const it = mgItem(rel); if(!it) return "";
  const on = MG.sel.includes(rel), q = rel.startsWith("quarantine"), bad = !q && dislikes(it);
  const t = `<b>${esc(it.code)}</b> · ${esc(it.cat)}${it.desc ? `<br>${esc(it.desc)}` : ""}${q ? `<br>${esc(qdirName(it.dir))}` : it.uses[0] ? `<br>发过 ${it.uses[0]} 次` : ""}`;
  return `<button class="mt${on ? " on" : ""}" data-mg="${esc(rel)}" aria-pressed="${on}"${tip(t)}><img src="${mgUrl(rel)}" alt="${esc(it.desc || it.code)}" loading="lazy" onerror="this.style.opacity=.15">`
    + `${!q && it.added ? `<i class="mb mine">收</i>` : ""}${bad ? `<i class="mb bad">✗${bad > 1 ? bad : ""}</i>` : ""}${!q && it.uses[0] ? `<i class="mb n">${it.uses[0]}</i>` : ""}</button>`;
}
function mgBar(){
  const items = MG.d?.items || [], cnt = f => items.filter(f).length;
  const chip = (k, name, n, t="") => `<button class="mchip" data-mgf="${esc(k)}" aria-pressed="${MG.filter === k}"${t ? tip(t) : ""}>${esc(name)}<em>${n}</em></button>`;
  return `<div class="mchips">${MG_FILTERS.map(([k, n, f]) => cnt(f) || k === "all" ? chip(k, n, cnt(f), k === "unused" ? `${mgSince()} 起一次都没发过的` : "") : "").join("")}</div>`
    + `<div class="mchips cats">${(MG.d?.cats || []).filter(c => c.n).map(c => chip("c:" + c.name, c.name, c.n, esc(c.desc))).join("")}</div>`
    + `<div class="mtool"><input type="search" id="mgFind" placeholder="按描述、编号找" value="${esc(MG.find)}" aria-label="按描述找">`
    + `<select id="mgSort" aria-label="排序">${Object.entries(MG_SORTS).map(([k, v]) => `<option value="${k}"${k === MG.sort ? " selected" : ""}>${v}</option>`).join("")}</select>`
    + `<button class="mchip" id="mgMulti" aria-pressed="${MG.multi}"${tip("开着时点一张是加进选中、再点一下去掉（手机上用）；电脑上按住 ⌘ 或 Shift 点也行")}>多选</button></div>`;
}
const mgGrid = () => { const l = mgList(); return l.length ? `<div class="mgrid">${l.map(mgTile).join("")}</div>` : empty("meh", "这样筛没有图～"); };
function mgQPane(){
  if(!MG.q) return `<p class="loading">〈我〉在翻隔离区～</p>`;
  const dirs = {}; MG.q.forEach(x => dirs[x.dir] = (dirs[x.dir] || 0) + 1);
  const l = mgQList(), shown = l.slice(0, MG.qn);
  return `<div class="mchips"><button class="mchip" data-mgq="" aria-pressed="${!MG.qdir}">全部<em>${MG.q.length}</em></button>${Object.entries(dirs).map(([d, n]) => `<button class="mchip" data-mgq="${esc(d)}" aria-pressed="${MG.qdir === d}">${esc(qdirName(d))}<em>${n}</em></button>`).join("")}</div>`
    + `<div class="mtool"><input type="search" id="mgQFind" placeholder="按描述、编号、分类找" value="${esc(MG.qfind)}" aria-label="在隔离区里找"></div>`
    + (shown.length ? `<div class="mgrid">${shown.map(x => mgTile(x.rel)).join("")}</div>` : empty("meh", "这样筛没有图～"))
    + (l.length > shown.length ? `<button class="btn alt sm mg-more" id="mgQMore">再看 ${Math.min(60, l.length - shown.length)} 张</button>` : "");
}
function mgPrefs(it){
  return (it.prefs || []).map(p => `<span class="tag dot" style="--m:${p.pref === "dislike" ? "#d8506f" : "#2f9e6e"}"${p.why ? tip(esc(p.why)) : ""}>${esc(MG.names[p.qq] || p.qq)} ${p.pref === "dislike" ? "不喜欢" : "喜欢"}</span>`).join("");
}
const mgCatSel = (cur, pick) => `<select id="mgTo" aria-label="哪一类">${pick ? `<option value="">${pick}</option>` : ""}${(MG.d?.cats || []).map(c => `<option value="${esc(c.name)}"${c.name === cur ? " selected" : ""}${c.desc ? ` title="${esc(c.desc)}"` : ""}>${esc(c.name)}（${c.n}）</option>`).join("")}</select>`;
function mgDetail(){
  const sel = MG.sel.map(mgItem).filter(Boolean);
  if(!sel.length) return empty("cute", MG.from === "q" ? "点一张看看，能放回库里～" : "点一张看看；按住 ⌘ 或 Shift 点能多选，← → 换一张～");
  const q = MG.from === "q", cats = new Set((MG.d?.cats || []).map(c => c.name));
  const acts = q ? `<div class="mg-acts">${mgCatSel(sel.every(x => x.cat === sel[0].cat) && cats.has(sel[0].cat) ? sel[0].cat : "", "放回哪一类…")}<button class="btn sm" data-act="mgback">放回库里</button></div>`
    : `<div class="mg-acts">${mgCatSel("", "换到哪一类…")}<button class="btn alt sm" data-act="mgmove">换过去</button><button class="btn danger sm" data-act="mgout">拿下来</button></div>`;
  if(sel.length > 1) return `<p class="mg-n">选了 <b>${sel.length}</b> 张${sel.length > 60 ? "（一次最多动 60 张）" : ""}</p><div class="mgrid mini">${sel.slice(0, 40).map(x => `<img src="${mgUrl(x.rel, 96)}" alt="" loading="lazy">`).join("")}</div>${acts}`;
  const it = sel[0], cat = (MG.d?.cats || []).find(c => c.name === it.cat), ext = it.rel.split(".").pop();
  const rows = q ? [["在哪", `${esc(qdirName(it.dir))}<small class="muted">（${esc(it.dir)}/${esc(it.cat)}）</small>`], ["原来", `${esc(it.cat)}${cats.has(it.cat) ? "" : "<small class=\"muted\">（这一类现在没有了）</small>"}`], ["格式", `${esc(ext)} · ${kb(it.size)}`]]
    : [["分类", `${esc(it.cat)}${cat?.desc ? `<small class="muted">　${esc(cat.desc)}</small>` : ""}`], ["格式", `${esc(it.kind || ext)} · ${kb(it.size)}`],
      ["放进来", it.added ? `${fmtT(it.added.ts)} 〈我〉在${esc(it.added.where)}收的${it.added.why ? `：${esc(it.added.why)}` : ""}` : `${fmtT(it.mtime)}`],
      ["发过", `${it.uses[0] ? `${it.uses[0]} 次，最近 ${fmtT(it.uses[1])}` : "还没发过"}<small class="muted">（${mgSince()} 起数的）</small>`],
      (it.prefs || []).length && ["谁的感受", mgPrefs(it)]].filter(Boolean);
  // 动图给原图（才看得出在动），静图给大缩图（原图有的两三 MB，从外面连进来要等好几秒）
  const moving = /^动图/.test(it.kind || "") || ext.toLowerCase() === "gif";
  return `<div class="mg-one"><a class="mg-big" href="/api/meme?f=${encodeURIComponent(it.rel)}&raw=1" target="_blank" rel="noopener"${tip("点开看原图")}><img src="${moving ? `/api/meme?f=${encodeURIComponent(it.rel)}&raw=1` : mgUrl(it.rel, 320)}" alt=""></a>`
    + `<div class="mg-info"><h3>${esc(it.code)}</h3><p>${it.desc ? esc(it.desc) : `<span class="muted">${q ? "没有描述" : "还没描述（〈我〉过一会儿会补上）"}</span>`}</p></div></div>`
    + `<dl class="dl">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>${acts}`;
}
function mgCats(){
  const cs = MG.d?.cats || [], mx = Math.max(1, ...cs.map(c => c.n));
  return blist(cs.map(c => ({lb:esc(c.name) + (c.n ? "" : ` <span class="tag bad">空了</span>`), sub:esc(c.desc.slice(0, 16)) + (c.desc.length > 16 ? "…" : ""), v:c.n, w:c.n / mx,
    c:"#8ec9f2", attr:` data-mgf="c:${esc(c.name)}"`, tip:c.desc ? `<b>${esc(c.name)}</b><br>${esc(c.desc)}` : ""})));
}
const MV_NAME = {move:"换了分类", out:"拿下来", back:"放回"};
function mgLog(){
  const mv = MG.d?.moves || [];
  if(!mv.length) return empty("sleep", "还没在面板上动过表情包～");
  return tl(mv.slice(0, 15).map(e => { const cat = e.src.split("/").slice(-2)[0], code = e.src.split("/").pop().replace(/\.\w+$/, "");
    const undo = e.here ? (e.action === "out" ? ["back", cat] : e.action === "move" ? ["move", cat] : ["out", ""]) : null;
    return {m:e.action === "out" ? "#d8506f" : e.action === "back" ? "#2f9e6e" : "#2f5fd0", t:fmtT(e.ts),
      h:`<img class="mp-img" src="${mgUrl(e.here ? e.dst : e.src, 96)}" alt="" loading="lazy" onerror="this.remove()"><b>${MV_NAME[e.action] || e.action}</b><span class="muted small">${esc(cat)} 的 ${esc(code)}${e.action === "move" ? ` → ${esc(e.dst.split("/")[0])}` : ""}</span>`,
      p:e.desc ? esc(e.desc) : "", x:undo ? `<button class="fd-del" data-act="mgundo" data-a="${undo[0]}" data-f="${esc(e.dst)}" data-to="${esc(undo[1])}">撤回</button>` : `<small>已经又动过了</small>`}; }));
}
function mgKpi(){
  const d = MG.d; if(!d) return [];
  const [lo, hi] = d.target || [140, 150], n = d.total, uses = d.items.reduce((a, it) => a + it.uses[0], 0), qn = Object.values(d.quarantine || {}).reduce((a, x) => a + x, 0);
  return [["在库", n, "张", n > hi || n < lo ? "warn" : "", `说好维持约 ${lo}～${hi} 张`], ["分类", d.cats.filter(c => c.n).length, "类"],
    ["〈我〉收的", d.items.filter(it => it.added).length, "张"], ["发过", uses, "次", "", `${mgSince()} 起数的（表情包插件的发送记录只留三小时，〈我〉每十分钟数一次）`], ["隔离区", qn, "张", "", "拿下来的都在这里，没删"]];
}
function mgThoughts(){
  const d = MG.d; if(!d) return [];
  const [lo, hi] = d.target || [140, 150], th = [];
  th.push({t:d.total > hi ? `库里 ${d.total} 张，比说好的多了 ${d.total - hi} 张～` : d.total < lo ? `库里只剩 ${d.total} 张了，比说好的少 ${lo - d.total} 张～` : `库里 ${d.total} 张，刚刚好～`});
  const days = d.since ? (Date.now() / 1000 - d.since) / 86400 : 0, unused = d.items.filter(it => !it.uses[0]).length;
  th.push({t:days < 2 ? `发了几次是 ${mgSince()} 才开始数的，过两天再看哪些没人用～` : `${mgSince()} 起有 ${unused} 张一次都没发过～`});
  const top = d.items.slice().sort((a, b) => b.uses[0] - a.uses[0])[0];
  if(top?.uses[0] >= 3) th.push({t:`发得最多的是 ${top.cat} 的 ${top.code}${top.desc ? `「${top.desc.slice(0, 14).replace(/[，,。、；：]+$/, "")}」` : ""}，${top.uses[0]} 次～`});
  const bad = d.items.filter(dislikes).length;
  if(bad) th.push({t:`有 ${bad} 张有人说过不喜欢，〈我〉不会再给 TA 配～`});
  return th;
}
async function renderMeme(){
  const [d, ppl] = await Promise.all([soft(get("/api/memes")), soft(get("/api/people"))]);
  if(!d) return {left:[card("表情包", fail("表情包库") + `<p class="small muted">要自主插件开着</p>`, {ic:"i-smile"})], right:[], clip:"sigh", kpi:[]};
  MG.d = d; MG.names = Object.fromEntries((ppl || []).map(p => [String(p.qq), p.name || p.qq]));
  if(MG.from === "q"){ MG.from = "lib"; MG.sel = []; }  // 进来时左边是「库里」那页
  mgKeep();
  const lib = `<div id="mgBar">${mgBar()}</div><div id="mgGrid">${mgGrid()}</div>`;
  const qn = Object.values(d.quarantine || {}).reduce((a, x) => a + x, 0);
  const left = [card("表情包", tabs([["库里", lib, d.total], ["隔离区", `<div id="mgQ">${mgQPane()}</div>`, qn]]),
    {ic:"i-smile", raw:true, meta:`<b>${d.total}</b> / 约 ${(d.target || [0, 150])[1]}`, note:"点一张看详细，按住 ⌘ 或 Shift 点能多选。拿下来的放进隔离区，不删，随时放得回来"})];
  const right = [card("选中的", `<div id="mgSel">${mgDetail()}</div>`, {ic:"i-search", note:"换分类、拿下来都要点两下才算；动完自动选下一张"}),
    card("分类", `<div id="mgCats">${mgCats()}</div>`, {ic:"i-list", note:"点一类只看那一类；说明是表情包插件给〈我〉看的"}),
    card("最近动过的", `<div id="mgLog">${mgLog()}</div>`, {ic:"i-clock", note:"面板上换分类、拿下来、放回的；「撤回」照原样搬回去"})];
  return {left, right, kpi:mgKpi(), thoughts:mgThoughts(), sub:"库里每张表情包：看一眼、换分类、拿下来；拿下来的放隔离区，不删", clip:"look", after:mgBind};
}
// 选中的那几张还在不在（动过、换过页之后）
function mgKeep(){ const have = new Set(MG.from === "q" ? (MG.q || []).map(x => x.rel) : (MG.d?.items || []).map(it => it.rel)); MG.sel = MG.sel.filter(r => have.has(r)); }
function mgDraw(){
  const put = (id, h) => { const el = $("#" + id); if(el){ el.innerHTML = h; FX.decorate?.(el); } };
  mgKeep();
  put("mgBar", mgBar()); put("mgGrid", mgGrid()); put("mgSel", mgDetail()); put("mgCats", mgCats()); put("mgLog", mgLog());
  if(MG.q) put("mgQ", mgQPane());
  const card0 = $("#mgGrid")?.closest(".card"), [t1, t2] = card0 ? card0.querySelectorAll(".seg [role=tab] em") : [];
  if(t1) t1.textContent = MG.d.total; if(t2) t2.textContent = Object.values(MG.d.quarantine || {}).reduce((a, x) => a + x, 0);
  const m = card0?.querySelector(".card-m b"); if(m) m.textContent = MG.d.total;
  setKpi("表情包", "库里每张表情包：看一眼、换分类、拿下来；拿下来的放隔离区，不删", mgKpi());
  More.check();
}
async function mgReload(){
  const [d, q] = await Promise.all([soft(get("/api/memes")), MG.q ? soft(get("/api/memes?q=1")) : null]);
  if(d) MG.d = d; if(q) MG.q = q;
  mgDraw();
}
async function mgLoadQ(){
  if(MG.q) return;
  MG.q = await soft(get("/api/memes?q=1")) || [];
  const el = $("#mgQ"); if(el) el.innerHTML = mgQPane();
}
// 动一下：这几张换走后自动选上原来列表里的下一张（连着看、连着处理）
const mgDo = (b, body) => doing(b, async () => {
  const files = MG.sel.slice(0, 60), list = mgList(), i = Math.max(...files.map(f => list.indexOf(f)));
  const nxt = list.slice(i + 1).find(x => !files.includes(x)) || list.slice(0, i).reverse().find(x => !files.includes(x));
  const r = await post("/api/memes", {...body, files});
  MG.sel = nxt ? [nxt] : [];
  await mgReload();
  return r;
});
function mgPick(rel, e){
  const from = rel.startsWith("quarantine") ? "q" : "lib";
  if(from !== MG.from){ MG.from = from; MG.sel = []; }
  const list = mgList();
  if(e?.shiftKey && MG.sel.length){
    const a = list.indexOf(MG.sel[MG.sel.length - 1]), z = list.indexOf(rel);
    if(a >= 0 && z >= 0) for(const x of list.slice(Math.min(a, z), Math.max(a, z) + 1)) if(!MG.sel.includes(x)) MG.sel.push(x);
  } else if(e?.metaKey || e?.ctrlKey || MG.multi) MG.sel = MG.sel.includes(rel) ? MG.sel.filter(x => x !== rel) : [...MG.sel, rel];
  else MG.sel = MG.sel.length === 1 && MG.sel[0] === rel ? [] : [rel];
  $$(".mgrid .mt").forEach(t => { const on = MG.sel.includes(t.dataset.mg); t.classList.toggle("on", on); t.setAttribute("aria-pressed", on); });
  $("#mgSel").innerHTML = mgDetail(); FX.decorate?.($("#mgSel"));
  if(MG.sel.length === 1){ Pet.react("look", 1600); }
}
function mgBind(){
  const card0 = $("#mgGrid")?.closest(".card"); if(!card0) return;
  const [tLib, tQ] = card0.querySelectorAll(".seg [role=tab]");
  tQ?.addEventListener("click", () => { mgLoadQ(); });
  tLib?.addEventListener("click", () => { if(MG.from === "q"){ MG.from = "lib"; MG.sel = []; mgDraw(); } });
}
// 页面上的点击都在两侧的纸上：选图、筛选、换页
for(const side of ["#left", "#right"]){
  $(side).addEventListener("click", e => {
    if(region !== "meme") return;
    const t = e.target.closest(".mt[data-mg]"); if(t){ e.preventDefault(); mgPick(t.dataset.mg, e); return; }
    const f = e.target.closest("[data-mgf]"); if(f){ MG.filter = MG.filter === f.dataset.mgf ? "all" : f.dataset.mgf; if(MG.from !== "lib"){ MG.from = "lib"; MG.sel = []; }
      const tab = $("#mgGrid")?.closest(".card")?.querySelector(".seg [role=tab]"); if(tab?.getAttribute("aria-selected") !== "true") tab.click();
      mgDraw(); return; }
    const qd = e.target.closest("[data-mgq]"); if(qd){ MG.qdir = qd.dataset.mgq; MG.qn = 60; mgDraw(); return; }
    if(e.target.closest("#mgQMore")){ MG.qn += 60; $("#mgQ").innerHTML = mgQPane(); More.check(); return; }
    if(e.target.closest("#mgMulti")){ MG.multi = !MG.multi; e.target.closest("#mgMulti").setAttribute("aria-pressed", MG.multi); }
  });
  $(side).addEventListener("input", e => {
    if(e.target.id === "mgFind"){ MG.find = e.target.value.trim(); $("#mgGrid").innerHTML = mgGrid(); }
    if(e.target.id === "mgQFind"){ MG.qfind = e.target.value.trim(); MG.qn = 60; const el = $("#mgQ"), pos = e.target.selectionStart; el.innerHTML = mgQPane(); const inp = $("#mgQFind"); inp.focus(); inp.setSelectionRange(pos, pos); }
  });
  $(side).addEventListener("change", e => { if(e.target.id === "mgSort"){ MG.sort = e.target.value; $("#mgGrid").innerHTML = mgGrid(); } });
}
// ← → 换一张，Esc 不选了
addEventListener("keydown", e => { if(region !== "meme" || e.metaKey || e.ctrlKey || e.altKey || e.target.closest?.("input,textarea,select")) return;
  if(e.key === "Escape" && MG.sel.length){ MG.sel = []; mgDraw(); return; }
  if((e.key === "ArrowLeft" || e.key === "ArrowRight") && MG.sel.length === 1){
    const l = mgList(), i = l.indexOf(MG.sel[0]), j = i + (e.key === "ArrowLeft" ? -1 : 1);
    if(i >= 0 && j >= 0 && j < l.length){ e.preventDefault(); mgPick(l[j]); $(`.mt[data-mg="${CSS.escape(l[j])}"]`)?.scrollIntoView({block:"nearest", behavior:REDUCED ? "auto" : "smooth"}); } } });

// ---------- 其他 ----------
// 刚重启那半分钟 NapCat 还没连回来，不算掉线
const qqDown = ov => !!ov && ov.online === false && (!!ov.offline_since || (ov.uptime || 0) > 120);
function setOnline(on, since, starting){ const el = $("#online"); if(on == null) return; el.classList.toggle("off", !on && !starting);
  el.lastElementChild.textContent = on ? "QQ 在线" : starting ? "QQ 连接中" : `QQ 掉线了${since ? ` · ${fmtT(since)} 起` : ""}`; }
// QQ 掉线时放在此刻、值班最上面：一眼看出她收不到也发不出消息
const offlineCard = since => card("QQ 掉线了", `<p class="off-p">${since ? `从 <b>${fmtT(since)}</b>（${ago(since)}）起，` : ""}〈我〉收不到也发不出消息：群里、私聊、心跳、说说、主动找人都停着。</p>
  <p class="small muted" style="margin:6px 0 0">要在 NapCat 那边重新登录（扫码）。登上以后一分钟内这里会自己变回「QQ 在线」，值班记录里那条也会标成已恢复。</p>`,
  {ic:"i-bell", cls:"alarm", meta:`<em class="stamp no">离线</em>`});
function clock(){
  const d = new Date(), h = d.getHours();
  $("#clock").innerHTML = `<b>${p2(h)}:${p2(d.getMinutes())}</b>${h < 6 ? "〈我〉睡着了" : h < 9 ? "〈我〉刚醒" : "〈我〉醒着"}`;
  Water.night(h >= 22 || h < 5 ? .6 : h >= 19 || h < 7 ? .3 : 0);
}
clock(); setInterval(clock, 30000);
// 戳她一下
const POKE = [["giggle", "好痒好痒，别挠尾巴～"], ["shy", "呀！突然戳〈我〉干嘛～"], ["hop", "嘿嘿，〈我〉在呢～"], ["wave", "主人好呀～"], ["pout", "哼，再戳就不让你偷看了～"]];
// Live2D 时戳到哪儿反应不一样；偶尔戴上钢盆
const POKE_AT = {
  head:[["pat", "被摸头了，嘿嘿～"], ["pat", "再摸一下嘛～"], ["smug", "哼哼，〈我〉的头发好摸吧～"]],
  face:[["cheek", "不许戳脸！会变成包子的～"], ["tease", "略略略～戳不到～"], ["shy", "干、干嘛凑这么近～"]],
  ear:[["ear", "耳朵好痒，别碰别碰～"], ["giggle", "鳍耳朵是敏感的地方啦～"]],
  body:[["shy", "呀！往哪戳呢～"], ["pout", "哼，再戳就不让你偷看了～"], ["wave", "主人好呀～"], ["hop", "嘿嘿，〈我〉在呢～"]],
};
const pick = xs => xs[Math.floor(Math.random() * xs.length)];
$("#pet").onclick = e => {
  const z = Pet.zone(e.clientX, e.clientY);
  const [c, t] = z ? (Math.random() < .06 ? ["basin", "哎哟！先戴好钢盆再说～"] : pick(POKE_AT[z])) : pick(POKE);
  Pet.react(c); Thought.say(t); const [x, y] = z ? [e.clientX, e.clientY] : stageCenter(); Water.burst(x, y - (z ? 0 : 40), 12);
};
// 先在脑区泡泡上停一下，就把那边的数据先拉好
$$("#dock .orb").forEach(b => b.addEventListener("pointerenter", () => { ({people:["/api/people","/api/heart"], memory:["/api/heart","/api/evolve","/api/memline","/api/memline/time?hours=72"], groups:["/api/overview"], mail:["/api/pending","/api/logs","/api/billing","/api/memline","/api/mind"], body:["/api/logs","/api/overview","/api/mind","/api/pending","/api/pclog","/api/evolve","/api/heart"], set:["/api/settings","/api/people","/api/evolve"], bill:["/api/usage?days=30","/api/ledger?days=30"], meme:["/api/memes"]})[b.dataset.r]?.forEach(u => soft(get(u))); }));

// 底部脑区上的小红点：待你裁决的总件数、记录里没修的错误
async function badges(){
  const [pa, ov] = await Promise.all([pendingAll(), soft(get("/api/overview"))]);
  setOnline(ov?.online, ov?.offline_since, ov && !qqDown(ov));
  const put = (r, n, cls="") => { const o = $(`#dock .orb[data-r="${r}"]`); o.querySelector("small")?.remove();
    if(n) o.insertAdjacentHTML("beforeend", `<small class="${cls}">${n > 99 ? "99+" : n}</small>`); };
  put("mail", pa.n);
  if(pa.lg) put("body", pa.errs.length, "bad");
}
setInterval(badges, 120000);

// 数字键 1～9 换脑区（在输入框里打字时不算）
addEventListener("keydown", e => {
  if(e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || !$("#album").hidden) return;
  const i = +e.key; if(i >= 1 && i <= REGIONS.length) go(REGIONS[i - 1].id);
});
addEventListener("lively:privacy", () => Thought.again());

// ---------- 只看她：右上角按钮或按 H，左右两栏、要点、脑区那排、人泡泡都收起来，只留她和对话框；Esc 退出 ----------
// 这时她能放大缩小：滚轮、触控板双指捏、右下角的 − ＋（点百分比还原）、键盘 + − 0。做法是改取景（上下各取到身上哪里），
// 放大往脸上靠，缩小多露一点身子；退出就回到原来的取景。极客模式拼字用的取景也跟着变（geek.js 问 Solo.frameFor）
const Solo = (() => {
  const store = {get(k){ try{ return localStorage.getItem(k); }catch{ return null; } }, set(k, v){ try{ localStorage.setItem(k, v); }catch{} }};
  const btn = Object.assign(document.createElement("button"), {id:"soloBtn", type:"button", className:"pill solo-btn", title:"只看她：把两边的信息收起来（按 H，Esc 退出）",
    innerHTML:`<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path class="so-side" d="M8 5v14M16 5v14"/></svg><span>只看她</span>`});
  const hud = $(".hud"), after = hud.querySelector("#pvBtn") || hud.querySelector("#geekPal");
  if(after) after.after(btn); else hud.prepend(btn);
  let on = false;
  // 缩放：z 在 -1（最远，多露身子）到 1（最近，只看脸）之间，0 是原来的取景
  const ZMIN = -1, ZMAX = 1, FACE = .17;  // 脸在模型上大约哪个高度（形象设定的 zones：头顶 .115、脸 .2）
  let z = Math.max(ZMIN, Math.min(ZMAX, +store.get("lively.solo.z") || 0)), F0 = null;
  const lerp = (a, b, k) => a + (b - a) * k;
  function frameFor(base){
    if(!on || !base || !z) return base;
    const span = base.bot - base.top;
    // 最近是原来的两倍大，脸放在画面上面四成的地方（下面有对话框）；最远多露七成身子
    const sn = span / 2, end = z < 0 ? {top:Math.max(0, base.top - .03), bot:base.top + span * 1.7} : {top:FACE - sn * .4, bot:FACE + sn * .6};
    const k = Math.abs(z);
    return {top:lerp(base.top, end.top, k), bot:lerp(base.bot, end.bot, k)};
  }
  const pct = () => { const b = F0 || {top:0, bot:1}, f = frameFor(b); return Math.round((b.bot - b.top) / (f.bot - f.top) * 100); };
  const zc = document.createElement("div"); zc.id = "zoomCtl"; zc.setAttribute("role", "group"); zc.setAttribute("aria-label", "放大缩小");
  zc.innerHTML = `<button type="button" data-z="-1" aria-label="缩小">−</button><button type="button" data-z="0" class="zp" title="还原（按 0）"></button><button type="button" data-z="1" aria-label="放大">＋</button>`;
  document.body.appendChild(zc);
  function zapply(){
    if(window.L2D?.ok){ F0 ||= {...L2D.avatar.frame}; L2D.avatar.frame = on ? frameFor(F0) : {...F0}; }
    zc.querySelector(".zp").textContent = pct() + "%";
    zc.querySelector('[data-z="-1"]').disabled = zgo <= ZMIN; zc.querySelector('[data-z="1"]').disabled = zgo >= ZMAX;
  }
  let zt = null, zgo = z;  // zgo：正在去的那一档；连点时从它往上加，不从动画半路的值加
  function zoomTo(v, now){
    v = zgo = Math.max(ZMIN, Math.min(ZMAX, v)); store.set("lively.solo.z", String(v));
    zt?.kill();
    if(now || REDUCED){ z = v; zapply(); return; }
    const o = {z}; zt = gsap.to(o, {z:v, duration:.45, ease:"power3.out", onUpdate(){ z = o.z; zapply(); }});
  }
  zc.addEventListener("click", e => { const b = e.target.closest("button"); if(!b) return; const d = +b.dataset.z; zoomTo(d ? zgo + d * .25 : 0); });
  // 滚轮一格挪一点；触控板双指捏会带 ctrlKey（浏览器自己的整页缩放要拦下来）
  addEventListener("wheel", e => {
    if(!on || e.target.closest?.(".hud, #zoomCtl, #thought, #album")) return;
    e.preventDefault(); zt?.kill();
    z = zgo = Math.max(ZMIN, Math.min(ZMAX, z - e.deltaY * (e.ctrlKey ? .01 : .0015))); store.set("lively.solo.z", String(z)); zapply();
  }, {passive:false});
  window.L2D?.ready?.then(ok => ok && zapply());
  function set(v){
    on = !!v; document.documentElement.classList.toggle("solo", on);
    btn.setAttribute("aria-pressed", String(on)); store.set("lively.solo", on ? "1" : "");
    if(region === "people") Field.freeze(on);  // 人泡泡收起来时别空转
    zapply();
    dispatchEvent(new CustomEvent("lively:solo", {detail:on}));
  }
  btn.addEventListener("click", () => set(!on));
  addEventListener("keydown", e => {
    if(e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable || !$("#album").hidden) return;
    if(e.key === "h" || e.key === "H") set(!on);
    else if(e.key === "Escape" && on) set(false);
    else if(on && (e.key === "+" || e.key === "=")) zoomTo(zgo + .25);
    else if(on && (e.key === "-" || e.key === "_")) zoomTo(zgo - .25);
    else if(on && e.key === "0") zoomTo(0);
  });
  set(store.get("lively.solo") === "1");
  return {set, get on(){ return on; }, frameFor};
})();
window.Solo = Solo;  // geek.js 要问取景
FX.intro();
const r0 = (location.hash || "").slice(1).split("/")[0], sub0 = hashSub();  // 记忆深处的：人、群、事和梗、一条记忆（pt:编号）
go(REGIONS.some(r => r.id === r0) ? r0 : "now", /^\d{5,12}$/.test(sub0 || "") || r0 === "bill" && DAY_RE.test(sub0 || "") || r0 === "memory" && /^(qq|g|t|n|pt):|^(me|feel|owner)$/.test(sub0 || "") || r0 === "set" && /^[a-z]+$/.test(sub0 || "") || r0 === "people" && PEOPLE_PAGES.includes(sub0) ? sub0 : undefined).then(badges);
