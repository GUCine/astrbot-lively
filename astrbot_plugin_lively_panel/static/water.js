// 内心海：WebGL 画水光（焦散 + 从水面斜照下来的体积光和光里的浮尘 + 她身后的一团光），另一层 canvas 画泡泡
// 用法：Water.tint("now")  切换脑区的颜色；Water.burst(x, y)  从某处冒一串泡泡；Water.night(0～1) 夜里暗下来
(function(){
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const hex = h => [1,3,5].map(i => parseInt(h.slice(i,i+2),16)/255);
// 每个脑区一种水色：[水面, 水底, 光]
const PALETTES = {
  now:    ["#9fdcf7", "#2a63c9", "#e8f7ff"],
  people: ["#f4bfd6", "#5b4fb8", "#ffe3f0"],
  memory: ["#6f8de0", "#0e1a52", "#c9d8ff"],
  groups: ["#9be6d4", "#1f6f9a", "#e6fff8"],
  mail:   ["#ffd8bc", "#c66a8f", "#fff1e4"],
  body:   ["#c9dcf2", "#34508f", "#f2f7ff"],
  bill:   ["#ffe2a8", "#a8612f", "#fff5dc"],
  set:    ["#d9d2f4", "#4a3f8f", "#f3efff"],
};
const cur = {top:hex(PALETTES.now[0]), bot:hex(PALETTES.now[1]), glow:hex(PALETTES.now[2])};
let target = {...cur}, nightK = 0, mouse = [0,0];

const cv = document.getElementById("water");
const gl = cv.getContext("webgl", {antialias:false, premultipliedAlpha:false});
const FRAG = `precision mediump float;
uniform vec2 R; uniform float T; uniform vec3 cTop, cBot, cGlow; uniform vec2 M; uniform float N;
float h21(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float n11(float x){ float i = floor(x), f = fract(x); f = f*f*(3.-2.*f); return mix(h21(vec2(i, 1.7)), h21(vec2(i + 1., 1.7)), f); }
float caustic(vec2 uv, float t){
  vec2 p = mod(uv*6.2832, 6.2832) - 250.0, i = p; float c = 1.0, inten = .005;
  for(int n = 0; n < 4; n++){
    float tt = t * (1.0 - (3.5 / float(n + 1)));
    i = p + vec2(cos(tt - i.x) + sin(tt + i.y), sin(tt - i.y) + cos(tt + i.x));
    c += 1.0 / length(vec2(p.x / (sin(i.x + tt) / inten), p.y / (cos(i.y + tt) / inten)));
  }
  c /= 4.0; c = 1.17 - pow(c, 1.4); return pow(abs(c), 8.0);
}
void main(){
  vec2 uv = gl_FragCoord.xy / R, p = (gl_FragCoord.xy - .5 * R) / R.y;
  vec3 col = mix(cBot, cTop, smoothstep(-.1, 1.05, uv.y));
  // 体积光（Volumetric Light）：光源在水面左上，往右下散开；按角度用噪声切成一束一束，越远越淡
  vec2 d = p - vec2(-.55, .75); float ang = atan(d.x, -d.y), dist = length(d);
  float shafts = pow(n11(ang * 9. + T * .05), 3.) * .9 + pow(n11(ang * 23. - T * .08 + 4.), 4.) * .6;
  float vol = shafts * smoothstep(.15, .55, ang) * smoothstep(1.35, .75, ang) * exp(-dist * .85) * (1. - N * .65);
  col += cGlow * vol * .4;
  // 浮尘：只在光里看得见，一闪一闪往上飘
  vec2 g = (p + vec2(0., T * .012)) * 70.; float r = h21(floor(g));
  col += vec3(1.) * step(.965, r) * smoothstep(.35, .0, length(fract(g) - .5)) * (.5 + .5 * sin(T * 1.5 + r * 40.)) * vol * 2.2;
  float c = caustic(uv * vec2(R.x / R.y, 1.0) * .85 + M * .015, T * .3);
  col += c * cGlow * .32 * (.25 + uv.y);
  vec2 q = p - vec2(0.0, -.03);
  col += cGlow * .22 * exp(-dot(q, q) * 4.5);
  col = mix(col, col * vec3(.32, .36, .55), N);
  col *= 1.0 - .38 * dot(p * vec2(.75, 1.0), p * vec2(.75, 1.0));
  gl_FragColor = vec4(col, 1.0);
}`;
let prog, U = {};
if(gl){
  const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); return o; };
  prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}"));
  gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
  gl.linkProgram(prog);
  if(!gl.getProgramParameter(prog, gl.LINK_STATUS)){ console.warn("水光着色器没编译成功", gl.getProgramInfoLog(prog)); prog = null; }
}
if(prog){
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  const a = gl.getAttribLocation(prog, "a"); gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
  for(const k of ["R","T","cTop","cBot","cGlow","M","N"]) U[k] = gl.getUniformLocation(prog, k);
} else {
  cv.style.background = "linear-gradient(#9fdcf7,#2a63c9)";
}

// 水光不用全分辨率，省电
const SCALE = .55;
function size(){
  cv.width = Math.round(innerWidth * SCALE); cv.height = Math.round(innerHeight * SCALE);
  fz.width = innerWidth * devicePixelRatio; fz.height = innerHeight * devicePixelRatio;
  if(prog) gl.viewport(0, 0, cv.width, cv.height);
}

// ---------- 泡泡 ----------
const fz = document.getElementById("fizz"), cx = fz.getContext("2d");
const bubbles = [];
function spawn(x, y, r, vy, life){ bubbles.push({x, y, r, vy, vx:(Math.random()-.5)*.25, ph:Math.random()*6.3, life, age:0}); }
function ambient(){ spawn(Math.random()*innerWidth, innerHeight + 10, 1.5 + Math.random()*4.5, .25 + Math.random()*.55, 1e9); }
for(let i = 0; i < 26; i++){ ambient(); bubbles[i].y = Math.random()*innerHeight; }

const lerp = (a, b, k) => a.map((v, i) => v + (b[i] - v) * k);
let t0 = performance.now(), last = t0, paused = false;
function frame(now){
  const dt = Math.min(50, now - last); last = now;
  if(paused){ requestAnimationFrame(frame); return; }
  const k = 1 - Math.pow(.0025, dt/1000);  // 大约一秒多换完颜色
  cur.top = lerp(cur.top, target.top, k); cur.bot = lerp(cur.bot, target.bot, k); cur.glow = lerp(cur.glow, target.glow, k);
  if(prog){
    gl.uniform2f(U.R, cv.width, cv.height); gl.uniform1f(U.T, REDUCED ? 8 : (now - t0)/1000);
    gl.uniform3fv(U.cTop, cur.top); gl.uniform3fv(U.cBot, cur.bot); gl.uniform3fv(U.cGlow, cur.glow);
    gl.uniform2f(U.M, mouse[0], mouse[1]); gl.uniform1f(U.N, nightK);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  const d = devicePixelRatio;
  cx.setTransform(d,0,0,d,0,0); cx.clearRect(0, 0, innerWidth, innerHeight);
  for(let i = bubbles.length - 1; i >= 0; i--){
    const b = bubbles[i]; b.age += dt;
    if(!REDUCED){ b.y -= b.vy * dt/16; b.ph += dt/700; b.x += Math.sin(b.ph) * .25 + b.vx; }
    const fade = b.life < 1e8 ? Math.max(0, 1 - b.age/b.life) : 1;
    if(b.y < -20 || fade <= 0){ bubbles.splice(i, 1); if(b.life > 1e8) ambient(); continue; }
    cx.globalAlpha = .55 * fade;
    cx.beginPath(); cx.arc(b.x, b.y, b.r, 0, 6.283); cx.strokeStyle = "#fff"; cx.lineWidth = 1.1; cx.stroke();
    cx.globalAlpha = .7 * fade;
    cx.beginPath(); cx.arc(b.x - b.r*.35, b.y - b.r*.35, Math.max(.6, b.r*.22), 0, 6.283); cx.fillStyle = "#fff"; cx.fill();
  }
  cx.globalAlpha = 1;
  requestAnimationFrame(frame);
}
addEventListener("resize", size);
addEventListener("pointermove", e => { mouse = [e.clientX/innerWidth - .5, e.clientY/innerHeight - .5]; });
size(); requestAnimationFrame(frame);

window.Water = {
  tint(name){ const p = PALETTES[name] || PALETTES.now; target = {top:hex(p[0]), bot:hex(p[1]), glow:hex(p[2])}; },
  pause(v){ paused = !!v; },  // 整页被盖住（卡册）时不画
  night(v){ nightK = Math.max(0, Math.min(.85, v)); },
  burst(x, y, n=26){ if(REDUCED) return; for(let i = 0; i < n; i++) spawn(x + (Math.random()-.5)*120, y + (Math.random()-.5)*40, 2 + Math.random()*7, .9 + Math.random()*1.8, 1600 + Math.random()*1400); },
};
})();
