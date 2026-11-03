// 隐私模式（演示用）：右上角「隐私」按钮或按 P。数据照真的跑，只把屏幕上看得见的隐私遮起来：
//  · 名字、群名 → 「用户 A」「群 1」，号码 → ●●●●（同一个人在哪都是同一个代号）
//  · 聊天内容、记忆、印象、她的心思等自由文字 → 打码模糊
//  · 头像、说说配图 → 模糊
// 做法：不碰各脑区的渲染。先包住 fetch，把 /api 返回里的名字、号码、文字记进词表；再盯着页面，
// 文字一出现就对照词表遮掉。关掉时原样还原。只遮屏幕上的画面，网页源码、网络请求里还是真的。
// 网址带 ?privacy=1 / ?privacy=0 直接开、关。
(() => {
  const store = {get(k){ try{ return localStorage.getItem(k); }catch{ return null; } }, set(k, v){ try{ localStorage.setItem(k, v); }catch{} }};
  const q = /[?&]privacy=([01])/.exec(location.search);
  if(q) store.set("lively.privacy", q[1]);
  const ME = window.LIVELY_ME || {};
  const root = document.documentElement;

  const f0 = window.fetch.bind(window);

  // ---------- 词表 ----------
  const people = new Map(), groups = new Map();   // 原名 → 代号
  const ids = new Set(), secrets = new Set();
  const texts = [];                               // 自由文字（整条）
  const seen = new Set(), heads = new Set(), shorts = new Set();   // shorts：两到五个字的短句（「赌！」），只在整段一模一样时才认
  let corpus = "", rePeople = null, reShort = null, reIds = null, reSecret = null, dirty = false;
  const KEEP = new Set(["本鱼", "TA", "你", "我", "他", "她", "它", "主人", "爹爹", "群友", "匿名", "未知", "无", "私聊", "群聊", "QQ", "me"]);
  const botName = String(ME.bot_name || "").trim();
  const NAME_KEYS = new Set(["name", "nick", "nickname", "card", "who", "inviter_name", "operator_name", "told_name", "who_name", "user_name"]);
  const GROUP_KEYS = new Set(["group_name", "gname", "群"]);
  const SECRET_KEYS = new Set(["key_hint", "token", "password", "secret", "api_key", "apikey"]);
  const ID_KEYS = new Set(["qq", "gid", "group", "place", "operator", "inviter", "asked_by", "told_by", "uin", "owner", "bot_qq", "a", "b", "umo", "id", "from_qq", "to_qq"]);
  // 这些字段是状态、编号、固定说法，不是她和人聊出来的内容，不打码
  const SAFE_KEYS = new Set(["kind", "mode", "status", "action", "day", "at", "ts", "now", "start", "end", "date", "日期", "pid", "label", "mood", "mood_desc", "mood_word",
    "favor_desc", "tier", "tier_name", "next_name", "stage", "band", "via", "src", "source", "by", "level", "plugin", "path", "model", "base", "effort", "tool", "to", "from_kind",
    "feeling", "desc", "cat", "code", "rel", "tid", "beat", "key", "result", "when", "default_id", "full_id", "caption_pid", "mind_pid", "draw_model", "type", "where", "what",
    "seen_day", "talk_day", "gain_day", "deep", "inject", "which", "title", "image", "value", "unit", "line", "tz", "id"]);
  const CJK = /[㐀-鿿぀-ヿ가-힯]/;

  const esc$ = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  function label(n){ let s = ""; n++; while(n > 0){ const r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = Math.floor((n - 1) / 26); } return s; }
  function addName(map, s, pre){
    s = String(s).trim();
    if(!s || s.length > 40 || KEEP.has(s) || /^[\d.\-:\s]+$/.test(s) && !/^\d{5,12}$/.test(s)) return;
    if(botName && (s === botName || botName.includes(s) && s.length > 1 || s.includes(botName))) return;
    if(/^\d{5,12}$/.test(s)){ addId(s); return; }
    if(people.has(s) || groups.has(s)) return;
    if(map === people) people.set(s, "用户 " + label(people.size));
    else groups.set(s, "群 " + (groups.size + 1));
    dirty = true;
  }
  function addId(s){ const m = String(s).match(/\d{5,12}/g); if(!m) return; for(const x of m) if(!ids.has(x)){ ids.add(x); dirty = true; } }
  function addText(s){
    s = String(s).trim();
    if(s.length < 6 || seen.has(s)) return;
    // 英文、数字、符号拼成的短串（模型名、编号、路径）不是聊天内容
    if(!CJK.test(s) && s.length <= 32 && /^[\w.:\-\/ ]+$/.test(s)) return;
    if(/^\d{4}-\d\d-\d\d([ T][\d:.]+)?$/.test(s)) return;
    seen.add(s); texts.push(s); corpus += s + "\u0001";
    if(s.length >= 8) heads.add(s.slice(0, 8));
  }
  function ingest(o, key, parent){
    if(o == null) return;
    if(typeof o === "string"){
      const m = /^(?:qq:|g:)?(\d{5,12})$/.exec(o);   // 单独一个号码（含 qq:、g: 前缀）
      if(m) addId(m[1]);
      if(SECRET_KEYS.has(key)){ if(o.length > 3 && !secrets.has(o)){ secrets.add(o); dirty = true; } return; }
      if(/^\d{5,12}$/.test(key || "")){ addName(groups, o); return; }   // {群号: 群名}
      if(GROUP_KEYS.has(key)) return addName(groups, o);
      if(NAME_KEYS.has(key)){
        // 只认「有号码的那条记录」里的 name；账目分类、表情包分类也叫 name（群里聊天、angry），那些是界面用词
        const gp = parent && !("qq" in parent) && (parent.kind === "group" || /^g:\d/.test(parent.place) || "gid" in parent);
        const e = parent && ("qq" in parent || "gid" in parent || "uin" in parent || /^(qq|g):\d/.test(parent.id) || /^g:\d/.test(parent.place) || parent.kind === "person" || parent.kind === "group");
        if(!e && !/_name$|^nick/.test(key)) return;
        return addName(gp ? groups : people, o);
      }
      if(ID_KEYS.has(key)){ addId(o); return; }
      if(SAFE_KEYS.has(key)){ addId(o); return; }       // 不打码，但里面夹着的号码照遮
      addId(/^\d{5,12}$/.test(o) ? o : "");
      const s = o.trim();
      if(s.length >= 6) addText(o);
      else if(s.length >= 2 && CJK.test(s)) shorts.add(s);
      return;
    }
    if(typeof o === "number"){ if(ID_KEYS.has(key) && o >= 10000) addId(String(o)); return; }
    if(Array.isArray(o)){ for(const x of o) ingest(x, key, parent); return; }
    if(typeof o === "object"){
      for(const [k, v] of Object.entries(o)){
        if(/^\d{5,12}$/.test(k)) addId(k);
        ingest(v, k, o);
      }
    }
  }
  // 界面自己的用词（页面、mind.js 里的字）：名字和它撞了，就只在整段正好是名字时才换
  let ui = document.documentElement.innerHTML;
  f0("/static/mind.js").then(r => r.text()).then(s => { ui += s; dirty = true; }).catch(() => {});
  const LETTER = "\u3400-\u9fff\u3040-\u30ff\uac00-\ud7afA-Za-z0-9_";
  function rebuild(){
    dirty = false;
    const rx = (arr, pre = "", post = "") => arr.length ? new RegExp(pre + "(?:" + arr.sort((a, b) => b.length - a.length).map(esc$).join("|") + ")" + post, "g") : null;
    const long = [], short = [];
    for(const n of [...people.keys(), ...groups.keys()]){
      if(n.length >= 3 && ui.includes(n)) continue;                 // 撞了界面用词：只整段匹配
      if(n.length >= 4 || n.length === 3 && !/^[\u3400-\u9fff]+$/.test(n)) long.push(n);
      else short.push(n);                                           // 一两个字的名字：前后不挨着字才换
    }
    rePeople = rx(long);
    reShort = rx(short, `(?<![${LETTER}])`, `(?![${LETTER}])`);
    reIds = rx([...ids]);
    reSecret = rx([...secrets]);
  }
  const pseudo = n => people.get(n) || groups.get(n) || "●●●";
  // 只换名字、号码、密钥；返回新字符串
  function names(s){
    if(dirty) rebuild();
    if(reSecret) s = s.replace(reSecret, "••••••");
    if(reIds) s = s.replace(reIds, m => "●".repeat(Math.min(m.length, 8)));
    if(rePeople) s = s.replace(rePeople, pseudo);
    if(reShort) s = s.replace(reShort, pseudo);
    // 整段就是一个名字（含撞了界面用词的）
    const t = s.trim();
    if(t && t.length <= 40){
      const bare = t.replace(/^[@＠]/, "");
      const p = people.get(bare) || groups.get(bare);
      if(p) return s.replace(bare, p);
    }
    return s;
  }
  function sensitive(t){
    t = t.trim().replace(/[…\.]{1,3}$/, "");
    if(shorts.has(t)) return true;
    if(t.length < 5) return false;
    if(corpus.includes(t)) return true;
    if(t.length >= 10) for(let i = 0; i + 8 <= t.length; i++) if(heads.has(t.slice(i, i + 8))) return true;
    return false;
  }

  // ---------- 把 /api 的返回记进词表（不管开没开，这样中途打开也遮得到之前读过的） ----------
  window.fetch = async (input, init) => {
    const r = await f0(input, init);
    try{
      const url = typeof input === "string" ? input : input?.url || "";
      if(!/\/api\//.test(url) || /\/api\/(image|avatar|madeav|meme)/.test(url) || (init?.method || input?.method || "GET") !== "GET") return r;
      const text = await r.clone().text();
      let j; try{ j = JSON.parse(text); }catch{ return r; }
      ingest(j?.data ?? j, "", null);
    }catch{}
    return r;
  };
  ingest(ME, "", null);
  if(ME.owner) addId(ME.owner);
  if(ME.bot_qq) addId(ME.bot_qq);

  // ---------- 遮页面 ----------
  const MASKED = new Map();      // 文字节点 → 原文
  const WRAPPED = new Set();     // 包着模糊的 span（里面是原来的文字节点）
  const BLURRED = new Set();     // SVG 里没法包 span，直接给上层元素加类
  const ATTR = new Map();        // 元素 → {属性: 原值}
  const SKIP = "script,style,textarea,input,select,noscript,.pv-b,[data-pv-skip]";
  let on = false;

  function scrubText(t){
    const par = t.parentNode;
    if(!par || par.nodeType !== 1 || par.closest?.(SKIP) || t._pv === t.data) return;
    const v = t.data;
    if(!v.trim()) return;
    const sens = sensitive(v);
    const s = names(v);
    if(s !== v){ MASKED.set(t, v); t.data = s; t._pv = s; }
    if(sens){
      if(par instanceof SVGElement){ par.classList.add("pv-bb"); BLURRED.add(par); }
      else{
        const sp = document.createElement("span"); sp.className = "pv-b";
        par.replaceChild(sp, t); sp.appendChild(t); WRAPPED.add(sp);
      }
    }
  }
  const ATTRS = ["title", "aria-label", "alt", "placeholder"];
  function scrubAttrs(el){
    for(const a of ATTRS){
      const v = el.getAttribute?.(a); if(!v) continue;
      const s = sensitive(v) ? "· · ·" : names(v);
      if(s === v) continue;
      let m = ATTR.get(el); if(!m) ATTR.set(el, m = {});
      if(!(a in m)) m[a] = v;
      el.setAttribute(a, s);
    }
  }
  function scrub(node){
    if(!node) return;
    if(node.nodeType === 3){ scrubText(node); return; }
    if(node.nodeType !== 1 || node.closest?.(SKIP)) return;
    const w = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    const list = []; for(let n = w.nextNode(); n; n = w.nextNode()) list.push(n);
    for(const t of list) scrubText(t);
    scrubAttrs(node); node.querySelectorAll?.("[title],[aria-label],[alt],[placeholder]").forEach(scrubAttrs);
  }
  function restore(){
    mo.disconnect();
    for(const [t, v] of MASKED){ t.data = v; delete t._pv; }
    MASKED.clear();
    for(const sp of WRAPPED){ if(sp.parentNode){ sp.replaceWith(...sp.childNodes); } }
    WRAPPED.clear();
    for(const el of BLURRED) el.classList.remove("pv-bb");
    BLURRED.clear();
    for(const [el, m] of ATTR) for(const a in m) el.setAttribute(a, m[a]);
    ATTR.clear();
  }

  // 观察器的回调在浏览器画下一帧之前就跑，所以真名字最多存在于一瞬间的内存里、不会被画出来
  const flush = q => {
    mo.disconnect();
    try{
      for(const n of q) if(n.isConnected){ try{ scrub(n); }catch(e){ console.warn("privacy", e); } }
      mo.takeRecords();
      // 页面换过的节点不再留着
      for(const t of MASKED.keys()) if(!t.isConnected) MASKED.delete(t);
      for(const s of WRAPPED) if(!s.isConnected) WRAPPED.delete(s);
    }finally{ if(on) connect(); }
  };
  const queue = new Set();
  const mo = new MutationObserver(recs => {
    for(const r of recs){
      if(r.type === "childList") r.addedNodes.forEach(n => { if(n.nodeType === 1 && n.classList?.contains("pv-b") || n.nodeType === 3 && n.parentNode?.classList?.contains("pv-b")) return; queue.add(n); });
      else if(r.type === "characterData"){ if(r.target._pv !== r.target.data) queue.add(r.target); }
      else if(r.type === "attributes") queue.add(r.target);
    }
    if(queue.size) flush([...queue]);
    queue.clear();
  });
  const connect = () => mo.observe(document.body, {childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:ATTRS});

  // 地址栏的 #people/QQ 号也别露出来
  function hideHash(){ try{ const h = location.hash; if(h.includes("/")) history.replaceState(null, "", h.split("/")[0]); }catch{} }

  function set(v){
    v = !!v; if(v === on) return;
    on = v; store.set("lively.privacy", on ? "1" : "0");
    root.classList.toggle("pv", on);
    btn?.setAttribute("aria-pressed", String(on));
    if(on){ if(dirty) rebuild(); hideHash(); mo.disconnect(); try{ scrub(document.body); }catch(e){ console.warn("privacy", e); } mo.takeRecords(); connect(); }
    else restore();
    dispatchEvent(new CustomEvent("lively:privacy", {detail:on}));
  }

  // ---------- 右上角的按钮 ----------
  const hud = document.querySelector(".hud");
  const btn = hud && Object.assign(document.createElement("button"), {
    id:"pvBtn", type:"button", className:"pill pv-btn", title:"隐私模式：把名字、号码、聊天内容遮起来，演示用（按 P）",
    innerHTML:`<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path class="pv-eye" d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle class="pv-eye" cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path class="pv-slash" d="M4 20L20 4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><span>隐私</span>`,
  });
  if(btn){
    btn.setAttribute("aria-pressed", "false");
    const after = hud.querySelector("#geekPal") || hud.querySelector("#geekBtn");
    if(after) after.after(btn); else hud.prepend(btn);
    btn.addEventListener("click", () => set(!on));
  }
  addEventListener("keydown", e => {
    if(e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable) return;
    if(e.key === "p" || e.key === "P") set(!on);
  });

  window.Privacy = {
    get on(){ return on; }, set, names,
    // 思考泡泡用：返回 {t, h}，h 是已经遮好的 HTML
    line(l){
      const e = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
      const t = names(l.t), sens = sensitive(l.t);
      return {...l, t, h:sens ? `<span class="pv-b">${e(t)}</span>` : e(t)};
    },
  };
  if(store.get("lively.privacy") === "1"){
    // 页面还空着，先打开；之后每次渲染都由观察器遮
    on = true; root.classList.add("pv"); btn?.setAttribute("aria-pressed", "true");
    hideHash(); connect();
    dispatchEvent(new CustomEvent("lively:privacy", {detail:true}));
  }
})();
