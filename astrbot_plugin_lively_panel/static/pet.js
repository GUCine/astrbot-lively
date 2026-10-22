// 机器人桌宠：素材来自 PC2005-cloud/dsh-pet（素材允许开源使用，禁止商用）
// 用法：const pet = Pet.mount({base:"/static/pet/", floor: () => innerHeight});
//       pet.mood("think") / pet.say("…") / pet.react()
(function(){
const UA = navigator.userAgent;
// WebKit（Safari、iOS 上所有浏览器）不支持 VP9 透明通道，改用动图 webp
const WEBKIT = /AppleWebKit/.test(UA) && !/Chrome|Chromium|Edg|OPR/.test(UA);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const pick = a => a[Math.floor(Math.random()*a.length)];

const IDLE = ["hum","breathe","rice","bubble","tail","cube","dance","mutter","look","stretch","float","crab","token"];
const CLICK = [
  ["shy","呀！突然戳〈我〉干嘛～"],["hop","嘿嘿，〈我〉在呢～"],["giggle","好痒好痒，别挠尾巴～"],
  ["pout","哼，再戳就不给你看数据了～"],["wave","主人好呀～"],
];

class Pet {
  constructor(opt){
    this.base = opt.base || "/static/pet/";
    this.size = opt.size || (() => innerWidth < 640 ? 150 : 210);
    this.lines = opt.lines || (() => null);
    this.el = document.createElement("div");
    this.el.className = "pet";
    this.el.innerHTML = `<div class="pet-bubble" role="status" aria-live="polite"></div><div class="pet-stage"></div><button class="pet-hit" aria-label="戳一下〈名字〉"></button>`;
    this.parent = opt.parent || document.body;
    if(opt.parent) this.el.classList.add("in");
    this.parent.appendChild(this.el);
    this.stage = this.el.querySelector(".pet-stage");
    this.bubble = this.el.querySelector(".pet-bubble");
    this.hit = this.el.querySelector(".pet-hit");
    this.x = Math.max(20, this.W() - this.size() - 40); this.y = 0; this.vy = 0;
    this.face = 1; this.busyUntil = 0; this.moodName = null; this.hidden = false;
    this.layout(); this.bind();
    this.play("breathe", {loop:true});
    this.timer = setTimeout(() => this.tick(), 6000);
    addEventListener("resize", () => { this.x = Math.min(this.x, this.W() - this.size()*0.8); this.layout(); });
  }
  W(){ return this.parent === document.body ? innerWidth : this.parent.clientWidth;
  }
  layout(){
    const s = this.size();
    this.el.style.width = s + "px"; this.el.style.height = Math.round(s*255/336) + "px";
    this.el.style.transform = `translate(${Math.round(this.x)}px, ${Math.round(-this.y)}px)`;
    this.stage.style.transform = `scaleX(${this.face})`;
  }
  // 换动画：新素材准备好再替换，避免闪白
  play(slug, {loop=false, then=null}={}){
    this.cur = slug;
    let m;
    if(WEBKIT || REDUCED){
      m = new Image(); m.alt = ""; m.draggable = false;
      m.src = this.base + slug + (REDUCED ? ".p.webp" : ".webp");
      m.onload = () => { if(this.cur !== slug) return; this.stage.replaceChildren(m); };
      clearTimeout(this._end);
      if(!loop && then) this._end = setTimeout(() => this.cur === slug && then(), 10000);
    }else{
      m = document.createElement("video");
      m.muted = true; m.playsInline = true; m.autoplay = true; m.loop = loop; m.preload = "auto";
      m.poster = this.base + slug + ".p.webp";
      m.src = this.base + slug + ".webm";
      // 新动画开播后把台上其他的全撤掉（连续换动作时可能叠了好几个还没开播的）
      // 台上已经有动画时，新的先藏着，开播那一刻再换上，免得首帧和旧动画叠在一起
      if(this.stage.childElementCount) m.style.visibility = "hidden";
      m.addEventListener("playing", () => { if(this.cur !== slug){ m.remove(); return; } m.style.visibility = ""; [...this.stage.children].forEach(c => c !== m && c.remove()); }, {once:true});
      if(!loop && then) m.addEventListener("ended", () => this.cur === slug && then(), {once:true});
      m.addEventListener("error", () => { if(this.cur === slug){ this.stage.replaceChildren(Object.assign(new Image(), {src:this.base+slug+".p.webp"})); then && setTimeout(then, 4000); } }, {once:true});
      this.stage.appendChild(m);
      m.play?.().catch(()=>{});
    }
  }
  say(text, ms=4200){
    if(!text) return;
    const b = this.bubble; b.textContent = text; b.classList.add("on");
    clearTimeout(this._say); this._say = setTimeout(() => b.classList.remove("on"), ms);
  }
  // 面板状态 → 动画
  mood(name, text){
    this.moodName = name;
    const map = {think:"think", error:"sigh", pending:"curtsy", night:"yawn", sleep:"sleep", busy:"busy", done:"cheer", file:"file"};
    const loop = name === "think" || name === "busy" || name === "sleep";
    this.stopWalk();
    this.busyUntil = Date.now() + (loop ? 1e9 : 10000);
    this.play(map[name] || name, {loop, then: () => this.idle()});
    if(text) this.say(text, loop ? 60000 : 5200);
  }
  calm(text){
    // 结束循环类的状态（读取完了）
    if(this.moodName === "think" || this.moodName === "busy"){ this.moodName = null; this.busyUntil = 0; this.bubble.classList.remove("on"); this.idle(); }
    if(text) this.say(text);
  }
  idle(){
    this.moodName = null; this.busyUntil = 0;
    const h = new Date().getHours();
    if(h >= 1 && h < 6) return this.play("sleep", {loop:true});
    this.play(pick(["breathe","breathe","hum","look"]), {loop:true});
  }
  tick(){
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.tick(), 14000 + Math.random()*14000);
    if(document.hidden || this.dragging || Date.now() < this.busyUntil || this.y > 0) return;
    const h = new Date().getHours(), r = Math.random();
    if(h >= 1 && h < 6){ if(this.cur !== "sleep") this.play(r < .5 ? "yawn" : "sleep", {loop: r >= .5, then: () => this.play("sleep",{loop:true})}); return; }
    if(r < .38 && !REDUCED) return this.walk();
    let clip = pick(IDLE);
    if(h >= 7 && h < 9 && r < .6) clip = "breakfast";
    else if(h >= 11 && h < 13 && r < .6) clip = "lunch";
    else if(h >= 17 && h < 19 && r < .6) clip = "dinner";
    else if(h >= 23 || h < 1) clip = r < .6 ? "yawn" : clip;
    this.busyUntil = Date.now() + 10000;
    this.play(clip, {then: () => this.idle()});
    if(Math.random() < .55) this.say(this.lines(clip));
  }
  walk(){
    const s = this.size(), max = this.W() - s*0.85, min = -s*0.15;
    const to = Math.max(min, Math.min(max, this.x + (Math.random() < .5 ? -1 : 1) * (120 + Math.random()*Math.min(420, this.W()/2))));
    this.face = to > this.x ? -1 : 1;   // 素材是向左跑，向右时镜像
    this.layout(); this.play("run", {loop:true});
    const speed = 95; let last = performance.now();
    const step = t => {
      const dx = (t - last)/1000*speed; last = t;
      if(this.dragging) return;
      if(Math.abs(to - this.x) <= dx){ this.x = to; this.layout(); this.walking = 0; this.face = 1; this.layout(); this.idle(); return; }
      this.x += Math.sign(to - this.x) * dx; this.layout();
      this.walking = requestAnimationFrame(step);
    };
    this.walking = requestAnimationFrame(step);
  }
  stopWalk(){ if(this.walking){ cancelAnimationFrame(this.walking); this.walking = 0; this.face = 1; this.layout(); } }
  react(){
    if(this.cur === "sleep"){ this.busyUntil = Date.now()+10000; this.play("startle", {then: () => this.idle()}); this.say("唔…谁吵醒〈我〉了～"); return; }
    const [clip, line] = pick(CLICK);
    this.stopWalk(); this.busyUntil = Date.now() + 10000;
    this.play(clip, {then: () => this.idle()}); this.say(line);
  }
  bind(){
    const h = this.hit; let sx, sy, ox, oy, moved = false, lastY = 0, lastT = 0;
    h.addEventListener("pointerdown", e => {
      h.setPointerCapture(e.pointerId); sx = e.clientX; sy = e.clientY; ox = this.x; oy = this.y; moved = false;
      this.dragging = true; lastY = e.clientY; lastT = performance.now();
    });
    h.addEventListener("pointermove", e => {
      if(!this.dragging) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if(!moved && Math.hypot(dx,dy) > 6){ moved = true; this.stopWalk(); this.el.classList.add("held"); this.play("drag", {loop:true}); this.say("放〈我〉下来～", 2000); }
      if(moved){ this.x = ox + dx; this.y = Math.max(0, oy - dy); this.layout(); }
    });
    const up = () => {
      if(!this.dragging) return; this.dragging = false; this.el.classList.remove("held");
      if(!moved){ this.react(); return; }
      this.x = Math.max(-this.size()*0.2, Math.min(this.W() - this.size()*0.8, this.x));
      this.fall();
    };
    h.addEventListener("pointerup", up); h.addEventListener("pointercancel", up);
    h.addEventListener("keydown", e => { if(e.key === "Enter" || e.key === " "){ e.preventDefault(); this.react(); } });
  }
  fall(){
    let last = performance.now(); this.vy = 0;
    const step = t => {
      const dt = Math.min(.05, (t-last)/1000); last = t;
      this.vy += 2200*dt; this.y -= this.vy*dt;
      if(this.y <= 0){ this.y = 0; this.layout(); this.busyUntil = Date.now()+10000; this.play("tail", {then: () => this.idle()}); this.say("哎哟，尾巴先着地～"); return; }
      this.layout(); requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  toggle(on){ this.hidden = !on; this.el.hidden = !on; }
}
window.Pet = { mount: opt => new Pet(opt||{}), WEBKIT };
})();
