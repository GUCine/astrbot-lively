// 动效层：日记纸从她头上冒成泡泡、飘过去“啵”地展开；思考泡泡一个个字冒出来；悬停的小纸条；手绘圈画；数字跳动、条形长出来；脑区泡泡放大
// 库都放在 vendor/（不走 CDN，国内打开也稳）：GSAP 3.15（MotionPath、SplitText、CustomEase）、Floating UI 1.8、Rough Notation 0.5
gsap.registerPlugin(MotionPathPlugin, SplitText, CustomEase);
gsap.config({nullTargetWarn:false});  // 卡片里没有某种小部件时不用每次都在控制台警告
const FX = (() => {
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
  CustomEase.create("unfold", "M0,0 C0.12,0.6 0.3,1.02 0.55,1.02 0.75,1.02 0.86,1 1,1");

  // ---------- 飞来飞去的小泡泡 ----------
  let live = null;            // 正在进行的出场或退场，换脑区时先掐掉
  const ghosts = new Set();
  function ghost(x, y, s){
    const g = document.createElement("i"); g.className = "ghost"; document.body.appendChild(g); ghosts.add(g);
    gsap.set(g, {x, y, xPercent:-50, yPercent:-50, width:s, height:s});
    return g;
  }
  const drop = g => { g.remove(); ghosts.delete(g); };
  function stop(){ live?.kill(); live = null; ghosts.forEach(drop); }
  // 高的卡片对准上半截，泡泡别飞到屏幕外
  const spot = r => [r.left + r.width/2, r.top + Math.min(r.height, 180)/2];
  const visible = r => r.bottom > 70 && r.top < innerHeight - 90;
  // 两点之间往上拱一下的弧线
  const arc = (a, b, up=90) => [{x:a[0], y:a[1]}, {x:(a[0] + b[0])/2, y:Math.min(a[1], b[1]) - up - Math.random()*50}, {x:b[0], y:b[1]}];
  // 从卡片里某一点展开，要盖住最远的角
  const reach = (r, x, y) => Math.max(...[[0,0],[r.width,0],[0,r.height],[r.width,r.height]].map(([a, b]) => Math.hypot(a - x, b - y))) + 6;

  // 左右两列的卡片交替排好
  const interleave = cols => { const out = [], n = Math.max(...cols.map(c => c.length)); for(let i = 0; i < n; i++) cols.forEach(c => c[i] && out.push(c[i])); return out; };

  let flyFrom = null;  // 点了哪颗泡泡（或排行里的头像），头像从那里飞进卡片
  function cardsIn(cols, from){
    stop();
    const cards = interleave(cols), tl = gsap.timeline(); live = tl;
    cards.forEach((c, i) => {
      const r = c.getBoundingClientRect(), tape = c.querySelector(":scope > .tp"), kids = [...c.children].filter(k => k !== tape);
      c.querySelectorAll("img[data-fly]").forEach(img => flyFrom && gsap.set(img, {autoAlpha:0}));
      if(REDUCED){ tl.from(c, {autoAlpha:0, duration:.25}, i * .04).call(decorate, [c]); return; }
      let t = .08 + i * .14;
      if(c.classList.contains("bare")){ tl.call(decorate, [c], t); tl.from(c.querySelectorAll(".deck-h,.album-btn"), {y:12, autoAlpha:0, duration:.5, stagger:.4, ease:"power2.out"}, t); return; }
      gsap.set(c, {autoAlpha:0});
      const to = spot(r), ox = to[0] - r.left, oy = to[1] - r.top;
      if(visible(r)){
        // 一颗泡泡从她头上沿弧线飘到卡片的位置，越飘越大，到了就破掉
        const g = ghost(from[0], from[1], 22);
        tl.to(g, {motionPath:{path:arc(from, to), curviness:1.3}, width:58, height:58, duration:.6, ease:"power2.inOut"}, t)
          .to(g, {scale:1.8, autoAlpha:0, duration:.24, ease:"power1.out", onStart:() => Water.burst(to[0], to[1], 9), onComplete:() => drop(g)}, t + .58);
        t += .55;
      }
      // 纸从泡泡破掉的地方圆圆地展开
      tl.fromTo(c, {autoAlpha:1, clipPath:`circle(26px at ${ox}px ${oy}px)`, scale:.94, rotation:i % 2 ? 2.5 : -2.5},
          {clipPath:`circle(${reach(r, ox, oy)}px at ${ox}px ${oy}px)`, scale:1, rotation:0, duration:.62, ease:"unfold", clearProps:"clipPath,scale,rotation", immediateRender:false}, t);
      if(tape) tl.from(tape, {scaleX:0, transformOrigin:c.classList.contains("b") ? "100% 50%" : "0 50%", duration:.34, ease:"power3.out"}, t + .42);
      tl.from(kids, {y:10, autoAlpha:0, duration:.42, stagger:.05, ease:"power2.out"}, t + .16);
      tl.call(decorate, [c], t + .5);
    });
    return tl;
  }
  function cardsOut(cols, to){
    stop(); clearMarks();
    const cards = interleave(cols);
    if(!cards.length) return Promise.resolve();
    const tl = gsap.timeline(); live = tl;
    cards.forEach((c, i) => {
      const r = c.getBoundingClientRect(), at = i * .035, p = spot(r), ox = p[0] - r.left, oy = p[1] - r.top;
      gsap.killTweensOf(c);
      if(REDUCED){ tl.to(c, {autoAlpha:0, duration:.15}, 0); return; }
      // 纸缩回一颗泡泡，再被她吸回脑子里
      tl.fromTo(c, {clipPath:`circle(${reach(r, ox, oy)}px at ${ox}px ${oy}px)`}, {clipPath:`circle(20px at ${ox}px ${oy}px)`, scale:.92, duration:.3, ease:"power2.in"}, at)
        .set(c, {autoAlpha:0}, at + .3);
      if(visible(r)){
        const g = ghost(p[0], p[1], 44); gsap.set(g, {autoAlpha:0});
        tl.set(g, {autoAlpha:1}, at + .28)
          .to(g, {motionPath:{path:arc(p, to, 40), curviness:1.2}, width:14, height:14, duration:.4, ease:"power2.in", onComplete:() => drop(g)}, at + .28);
      }
    });
    // 万一被打断，最多等一秒半
    return Promise.race([tl.then(() => {}), new Promise(r => setTimeout(r, 1500))]);
  }

  // ---------- 纸展开以后：数字跳、水管灌满、圈画重点 ----------
  const marks = new Set();
  function clearMarks(){ marks.forEach(a => a.remove()); marks.clear(); }
  // 数字从 0 跳到这个数；只动开头那段文字（后面跟着单位之类的小标签不动）
  function countUp(el){
    const node = el.firstChild?.nodeType === 3 ? el.firstChild : el.children.length ? null : el;
    if(REDUCED || !node) return;
    const m = node.textContent.match(/^(\D*?)(\d+(?:\.\d+)?)(.*)$/s); if(!m) return;
    const v = +m[2], dec = (m[2].split(".")[1] || "").length, o = {v:0};
    gsap.to(o, {v, duration:Math.min(1.5, .7 + v/300), ease:"power2.out", onUpdate:() => { node.textContent = m[1] + o.v.toFixed(dec) + m[3]; }});
  }
  // 分页里还没打开的那几页先不动，切过去时再动（藏着的东西量不出大小，圈画会画歪）
  const hiddenIn = el => !!el.closest(".pane[hidden]");
  const fresh = (c, sel) => [...c.querySelectorAll(sel)].filter(el => !hiddenIn(el) && !el.dataset.dec && (el.dataset.dec = 1));
  function decorate(c){
    if(!c.isConnected) return;
    const d = REDUCED ? 0 : 1, from = (sel, vars) => { const els = fresh(c, sel); if(els.length) gsap.from(els, vars); };
    fresh(c, ".n,.big,.meter em,.blist em,.stat b,.scale-cap b").forEach(countUp);
    from(".meter .bar i,.prog i", {scaleX:0, transformOrigin:"0 50%", duration:1.2 * d, ease:"expo.out", stagger:.08});
    from(".blist .bf", {scaleX:0, transformOrigin:"0 50%", duration:1 * d, ease:"expo.out", stagger:.05});
    from(".cbar i", {scaleX:0, transformOrigin:"0 50%", duration:.8 * d, ease:"power3.out", stagger:.06});
    from(".vb-s", {scaleY:0, transformOrigin:"50% 100%", duration:.7 * d, ease:"back.out(1.4)", stagger:.03});
    from(".hm i", {scale:0, duration:.4 * d, ease:"back.out(2)", stagger:{each:.002, from:"start"}});
    from(".heat i", {scaleY:0, transformOrigin:"50% 100%", duration:.7 * d, ease:"back.out(1.6)", stagger:.018});
    from(".layer", {x:-26, autoAlpha:0, duration:.5 * d, ease:"power3.out", stagger:.08});
    from(".tl > li", {y:10, autoAlpha:0, duration:.45 * d, ease:"power2.out", stagger:.05});
    fresh(c, "svg.radar").forEach(radar);
    fresh(c, "svg.scale").forEach(scale);
    fresh(c, "img[data-fly]").forEach(fly);
    fresh(c, ".fcard").forEach(fishCard);
    fresh(c, ".hand").forEach(hand);
    // 手绘的圈、下划线、荧光笔；等数字跳完再画
    fresh(c, "[data-mark]").forEach((el, i) => {
      const type = el.dataset.mark;
      const a = RoughNotation.annotate(el, {type, color:el.dataset.mc || "#e7799b", multiline:true, animate:!REDUCED, animationDuration:650,
        strokeWidth:type === "highlight" ? 1 : 1.7, padding:type === "circle" ? [4, 8] : type === "box" ? 3 : 2, iterations:type === "highlight" ? 1 : 2});
      marks.add(a);
      setTimeout(() => el.isConnected && a.show(), REDUCED ? 0 : 1100 + i * 260);
    });
  }
  // 脑区抬头的几个数：一个个冒出来，数字跳到位
  function kpi(el){
    const ks = [...el.querySelectorAll(".kpi")];
    ks.forEach(k => countUp(k.querySelector("b")));
    gsap.fromTo([el.querySelector(".kpi-name"), ...ks], {y:-10, autoAlpha:0}, {y:0, autoAlpha:1, duration:REDUCED ? 0 : .5, ease:"power3.out", stagger:.06});
  }

  // 八种感情的雷达：从中心长出来，弹两下
  function radar(svg){
    const vals = JSON.parse(svg.dataset.radar), n = vals.length, C = +svg.dataset.cx, Y = +svg.dataset.cy, R = +svg.dataset.r;
    const shape = svg.querySelector(".rd-shape"), dots = svg.querySelectorAll(".rd-dot"), o = {k:REDUCED ? 1 : 0};
    const pt = (i, v) => { const a = -Math.PI/2 + i * 2*Math.PI/n; return [C + Math.cos(a) * R * v, Y + Math.sin(a) * R * v]; };
    const draw = () => { const ps = vals.map((v, i) => pt(i, Math.max(.04, v/100) * o.k));
      shape.setAttribute("points", ps.map(p => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" "));
      dots.forEach((dt, i) => { dt.setAttribute("cx", ps[i][0].toFixed(1)); dt.setAttribute("cy", ps[i][1].toFixed(1)); }); };
    draw();
    gsap.to(o, {k:1, duration:1.6, delay:.15, ease:"elastic.out(1,.45)", onUpdate:draw});
  }
  // 天平：回忆一颗颗掉进秤盘，横梁晃两下停在倾斜的位置
  function scale(svg){
    const target = +svg.dataset.ang, beam = svg.querySelector(".beam"), L = svg.querySelector(".pan.L"), R = svg.querySelector(".pan.R"), o = {a:0};
    const set = () => { const r = o.a * Math.PI / 180, c = Math.cos(r) * 110, s = Math.sin(r) * 110;
      beam.setAttribute("transform", `rotate(${o.a.toFixed(2)} 150 40)`);
      L.setAttribute("transform", `translate(${(150 - c).toFixed(1)},${(40 - s).toFixed(1)})`); R.setAttribute("transform", `translate(${(150 + c).toFixed(1)},${(40 + s).toFixed(1)})`); };
    if(REDUCED){ o.a = target; return set(); }
    set();
    gsap.from(svg.querySelectorAll(".pan circle"), {y:-90, autoAlpha:0, duration:.8, ease:"bounce.out", stagger:.07, delay:.1});
    gsap.to(o, {a:target, duration:2.2, delay:.75, ease:"elastic.out(1.1,.28)", onUpdate:set});
  }
  // 头像从点的地方沿弧线飞进卡片
  function fly(img){
    const from = flyFrom; flyFrom = null;
    const to = img.getBoundingClientRect();
    if(!from || REDUCED || !visible(to)){ gsap.set(img, {autoAlpha:1}); return; }
    const c = img.cloneNode(); c.removeAttribute("data-fly"); c.className = "flyer"; document.body.appendChild(c);
    gsap.set(c, {width:from.width, height:from.height, x:from.left, y:from.top});
    gsap.to(c, {motionPath:{path:arc([from.left, from.top], [to.left, to.top], 60), curviness:1.2}, width:to.width, height:to.height, duration:.75, ease:"power3.inOut",
      onComplete:() => { c.remove(); gsap.fromTo(img, {autoAlpha:1, scale:1.3}, {scale:1, duration:.55, ease:"back.out(3)"}); }});
  }

  // ---------- 〈卡〉：镭射箔跟着鼠标流、卡片倾斜、点一下翻面 ----------
  function holoAt(el, e){
    const r = el.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    el.style.setProperty("--mx", (x*100).toFixed(1) + "%"); el.style.setProperty("--my", (y*100).toFixed(1) + "%");
    el.style.setProperty("--hx", (100 - x*100).toFixed(1) + "%"); el.style.setProperty("--hy", (100 - y*100).toFixed(1) + "%");
    el.style.setProperty("--ha", (100 + x*50).toFixed(0) + "deg");
    return [x, y];
  }
  document.addEventListener("pointermove", e => { const m = e.target.closest?.(".mcard"); if(m) holoAt(m, e); });
  function fishCard(el){
    let side = 0;  // 0 正面，180 背面
    let ry, rx;
    const quick = () => { ry = gsap.quickTo(el, "rotationY", {duration:.6, ease:"power3"}); rx = gsap.quickTo(el, "rotationX", {duration:.6, ease:"power3"}); };
    quick();
    gsap.set(el, {transformPerspective:1100});
    // 刚发到手里：从下面翻上来一点
    if(!REDUCED) gsap.from(el, {rotationX:-28, duration:1.1, ease:"elastic.out(1,.6)"});
    if(!REDUCED) el.addEventListener("pointermove", e => {
      const [x, y] = holoAt(el, e);
      if(gsap.isTweening(el) && !el._q) return;
      el._q = true; ry(side + (x - .5) * (side ? -14 : 14)); rx((.5 - y) * 10);
      el.classList.add("lit");
    });
    el.addEventListener("pointerleave", () => { el.classList.remove("lit"); if(el._q){ ry(side); rx(0); } });
    const flip = () => {
      side = side ? 0 : 180; el._q = false; el.classList.toggle("flipped", !!side);
      ry.tween.kill(); rx.tween.kill();
      gsap.to(el, {rotationY:side, rotationX:0, duration:REDUCED ? 0 : .9, ease:"back.out(1.3)", onComplete:() => { quick(); el._q = true; }});
      gsap.fromTo(el, {scale:1}, {scale:.94, duration:.22, yoyo:true, repeat:1, ease:"power1.inOut"});
    };
    el.addEventListener("click", e => { if(!e.target.closest("a,button,[data-tip]")) flip(); });
    el.addEventListener("keydown", e => { if(e.key === "Enter" || e.key === " "){ e.preventDefault(); flip(); } });
  }
  // 一手扇形的卡：绕着下方很远的一点扇开（像真的捏在手里），正中间那张压在最上面；
  // 鼠标移到哪张，哪张抽出来、扶正一点，两边再让开一些
  function hand(el){
    const cs = [...el.querySelectorAll(".mcard")], n = cs.length, mid = (n - 1) / 2, step = mid ? Math.min(4.6, 10 / mid) : 0;  // 右列只有 300 宽，扇太开两边会被裁掉
    const pos = (i, hot) => { const d = i - mid, push = hot == null || i === hot ? 0 : (i < hot ? -1 : 1) * 3.5;
      return {rotation:i === hot ? d * step * .4 : d * step + push, y:i === hot ? -22 : Math.abs(d) * 4, scale:i === hot ? 1.08 : 1,
        zIndex:i === hot ? 20 : 10 - Math.round(Math.abs(d) * 2)}; };
    gsap.set(cs, {xPercent:-50, transformOrigin:"50% 300%"});
    if(REDUCED) cs.forEach((c, i) => gsap.set(c, pos(i)));
    else {
      // 先叠成一摞从下面递上来，再一张张扇开
      gsap.set(cs, {zIndex:i => pos(i).zIndex});
      gsap.fromTo(cs, {rotation:0, y:90, autoAlpha:0}, {rotation:i => pos(i).rotation, y:i => pos(i).y, autoAlpha:1, duration:1, ease:"back.out(1.4)",
        stagger:{each:.07, from:"center"}, delay:.05});
    }
    const fan = hot => cs.forEach((c, i) => gsap.to(c, {...pos(i, hot), duration:.45, ease:"power3.out", overwrite:"auto"}));
    cs.forEach((c, i) => { c.addEventListener("pointerenter", () => fan(i)); c.addEventListener("focus", () => fan(i)); });
    el.addEventListener("pointerleave", () => fan(null));
  }
  // 卡册：从她那里一张张发出来
  function deal(cards, from){
    gsap.killTweensOf(cards);
    if(REDUCED || !from){ gsap.fromTo(cards, {autoAlpha:0, y:10}, {autoAlpha:1, y:0, duration:.3, stagger:.012}); return; }
    cards.forEach((c, i) => {
      const r = c.getBoundingClientRect();
      if(r.top > innerHeight) return;
      gsap.from(c, {x:from[0] - r.left - r.width/2, y:from[1] - r.top - r.height/2, rotation:gsap.utils.random(-40, 40), scale:.3, autoAlpha:0,
        duration:.75, delay:.15 + i * .035, ease:"power3.out"});
    });
  }
  function albumIn(el){
    gsap.fromTo(el, {autoAlpha:0, backdropFilter:"blur(0px)"}, {autoAlpha:1, backdropFilter:"blur(14px)", duration:REDUCED ? 0 : .4, overwrite:true});
    gsap.from(el.querySelector(".al-head"), {y:-30, autoAlpha:0, duration:.5, ease:"power3.out", delay:.1});
  }
  function albumOut(el){
    Tip.hide();
    return gsap.to(el, {autoAlpha:0, duration:REDUCED ? 0 : .3, overwrite:true}).then(() => {});
  }

  // ---------- 头顶的思考泡泡：旧字往上飘走，新字进来，泡泡跟着变大变小 ----------
  // 纸面：像文字冒险游戏的对话框，字从左到右一个个打出来；极客：乱码从左到右一位位解出来（Amber）
  const GLYPHS = "01<>[]{}#%&*+=/\\$@ABCDEFXYZｱｲｳｴｵｶｷｸ鱼饭";
  function decode(root, dur){
    const nodes = [], walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while(walk.nextNode()) nodes.push([walk.currentNode, [...walk.currentNode.nodeValue]]);
    const total = nodes.reduce((a, [, c]) => a + c.length, 0) || 1, t0 = performance.now();
    cancelAnimationFrame(root._dec);
    const step = now => {
      const k = (now - t0) / dur; let at = 0;
      for(const [n, cs] of nodes){
        n.nodeValue = cs.map((c, i) => { const u = (at + i) / total; return c === " " || u < k - .15 ? c : u < k + .1 ? GLYPHS[Math.random() * GLYPHS.length | 0] : ""; }).join("");
        at += cs.length;
      }
      if(k < 1.2) root._dec = requestAnimationFrame(step); else for(const [n, cs] of nodes) n.nodeValue = cs.join("");
    };
    root._dec = requestAnimationFrame(step);
  }
  function thought(el, html){
    const old = el._split, geek = document.documentElement.classList.contains("geek");
    const swap = () => {
      const w0 = el.offsetWidth, h0 = el.offsetHeight;
      cancelAnimationFrame(el._dec); old?.revert(); el._split = null; el.innerHTML = html;
      const tt = el.querySelector(".tt");
      if(REDUCED || !tt) return;
      const w1 = el.offsetWidth, h1 = el.offsetHeight;
      gsap.fromTo(el, {width:w0, height:h0}, {width:w1, height:h1, duration:.5, ease:"back.out(1.6)", clearProps:"width,height"});
      if(geek){ decode(el, 18 * tt.textContent.length + 260); return; }
      const sp = el._split = SplitText.create(tt, {type:"chars", tag:"span"}), n = sp.chars.length;
      const each = Math.min(.04, 2.4 / n);
      gsap.from(sp.chars, {autoAlpha:0, y:3, duration:.16, ease:"power1.out", stagger:each, delay:.05});
      const s = el.querySelector("small"); if(s) gsap.from(s, {autoAlpha:0, y:5, duration:.4, delay:.2 + n * each});
    };
    if(old && !REDUCED && old.chars?.length) gsap.to(old.chars, {autoAlpha:0, y:-10, duration:.2, stagger:.004, ease:"power1.in", onComplete:swap});
    else swap();
  }

  // ---------- 悬停的小纸条（Floating UI 负责位置，贴着目标、碰边就翻面） ----------
  const Tip = (() => {
    const {computePosition, offset, flip, shift, arrow, autoUpdate} = window.FloatingUIDOM;
    const el = document.createElement("div"); el.id = "tip"; el.setAttribute("role", "tooltip");
    el.innerHTML = `<div class="tip-b"></div><i class="tip-a"></i>`; document.body.appendChild(el);
    const body = el.firstChild, ar = el.lastChild;
    let ref = null, off = null;
    async function place(){
      if(!ref) return;
      if(!ref.isConnected) return hide();
      const {x, y, placement, middlewareData:m} = await computePosition(ref, el, {strategy:"fixed", placement:ref.dataset.tipAt || "top",
        middleware:[offset(12), flip({padding:12}), shift({padding:12}), arrow({element:ar, padding:12})]});
      const side = placement.split("-")[0];
      Object.assign(el.style, {left:x + "px", top:y + "px"});
      Object.assign(ar.style, {left:m.arrow?.x != null ? m.arrow.x + "px" : "", top:m.arrow?.y != null ? m.arrow.y + "px" : "", right:"", bottom:"",
        [{top:"bottom", bottom:"top", left:"right", right:"left"}[side]]:"-6px"});
      el.style.transformOrigin = {top:"50% 100%", bottom:"50% 0", left:"100% 50%", right:"0 50%"}[side];
    }
    function show(t){
      ref = t; body.innerHTML = t.dataset.tip; off?.();
      off = autoUpdate(t, el, place, {animationFrame:!!t.closest(".ring-layer")});
      gsap.fromTo(el, {autoAlpha:0, scale:.82}, {autoAlpha:1, scale:1, duration:REDUCED ? 0 : .26, ease:"back.out(2.2)", overwrite:true});
    }
    function hide(){
      if(!ref) return; ref = null; off?.(); off = null;
      gsap.to(el, {autoAlpha:0, scale:.9, duration:.12, overwrite:true});
    }
    const pick = e => { const t = e.target.closest?.("[data-tip]"); if(t){ if(t !== ref) show(t); } else hide(); };
    document.addEventListener("pointerover", pick);
    document.addEventListener("focusin", pick);
    document.documentElement.addEventListener("pointerleave", hide);
    gsap.set(el, {autoAlpha:0});
    return {hide};
  })();

  // ---------- 底部脑区泡泡：鼠标靠近的放大（像 Dock），选中的背后有一团光滑过去 ----------
  function dock(nav, lifts){
    const orbs = [...nav.querySelectorAll(".orb")];
    const halo = document.createElement("span"); halo.className = "halo"; halo.setAttribute("aria-hidden", "true"); nav.prepend(halo);
    orbs.forEach((o, i) => gsap.set(o, {y:lifts[i], transformOrigin:"50% 100%"}));
    if(!REDUCED){
      const qs = orbs.map(o => gsap.quickTo(o, "scale", {duration:.35, ease:"power3.out"}));
      nav.addEventListener("pointermove", e => orbs.forEach((o, i) => { const r = o.getBoundingClientRect(); qs[i](1 + .3 * Math.max(0, 1 - Math.abs(e.clientX - r.left - r.width/2) / 150)); }));
      nav.addEventListener("pointerleave", () => qs.forEach(q => q(1)));
      // 磁吸：游标在哪颗上，那颗往游标那边吸一点；离开弹回去（GreenSock 的磁吸按钮）
      orbs.forEach(o => {
        o.addEventListener("pointermove", e => { const r = o.getBoundingClientRect();
          gsap.to(o, {x:(e.clientX - r.left - r.width / 2) * .32, y:(e.clientY - r.top - r.height / 2) * .38, duration:.4, ease:"power2.out", overwrite:"auto"}); });
        o.addEventListener("pointerleave", () => gsap.to(o, {x:0, y:0, duration:.8, ease:"elastic.out(1,.4)", overwrite:"auto"}));
      });
      gsap.from(orbs, {y:i => lifts[i] + 90, autoAlpha:0, duration:1, ease:"back.out(1.6)", stagger:.07, delay:.25});
    }
    let first = true;
    return function to(btn){
      const bubble = btn.querySelector("i"), nr = nav.getBoundingClientRect(), r = bubble.getBoundingClientRect();
      // 被吸偏的那一点不算，光圈落在它弹回去以后的位置
      const x = r.left + r.width/2 - nr.left - gsap.getProperty(btn, "x"), y = r.top + r.height/2 - nr.top - gsap.getProperty(btn, "y");
      if(first || REDUCED){ first = false; gsap.set(halo, {x, y, xPercent:-50, yPercent:-50}); }
      else gsap.to(halo, {x, y, duration:.8, ease:"elastic.out(1,.6)"});
      gsap.fromTo(bubble, {scale:.8}, {scale:1, duration:.7, ease:"elastic.out(1.2,.4)"});
    };
  }

  // ---------- 刚打开页面 ----------
  function intro(){
    if(REDUCED) return;
    gsap.from("body > header", {y:-40, autoAlpha:0, duration:.9, ease:"power3.out"});
    gsap.from("#pet", {scale:.5, autoAlpha:0, duration:1.4, ease:"elastic.out(1,.5)", delay:.1});
    gsap.from("#thought", {autoAlpha:0, duration:.6, delay:.7});  // 它靠 CSS 的 translate 定位，这里不动 transform
  }

  return {cardsIn, cardsOut, thought, dock, intro, deal, albumIn, albumOut, decorate, kpi, hideTip:Tip.hide, pickFrom(el){ flyFrom = el?.getBoundingClientRect() || null; }};
})();
