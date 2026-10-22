// 机器人控制面板：页面逻辑。接口见 main.py，POST 必须带 X-Lively: 1
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const p2 = x => String(x).padStart(2,"0");
const fmtT = ts => { if(!ts) return "—"; const d = new Date(ts*1000), n = new Date(), hm = p2(d.getHours())+":"+p2(d.getMinutes());
  return d.toDateString()===n.toDateString() ? hm : (d.getMonth()+1)+"-"+d.getDate()+" "+hm; };
const ago = ts => { if(!ts) return "—"; const s = Date.now()/1000-ts; if(s<3600) return Math.max(1,Math.round(s/60))+" 分钟前";
  if(s<86400) return Math.round(s/3600)+" 小时前"; return Math.round(s/86400)+" 天前"; };
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const memeImg = (k, attrs="") => (window.LIVELY_ME || {}).meme === false ? "" : `<img src="/static/meme/${k}.webp" alt="" loading="lazy" ${attrs} onerror="this.remove()">`;
const meme = (k, text) => `<div class="empty">${memeImg(k, 'width="120" height="120"')}<p>${text}</p></div>`;

// ---------- 桌宠 ----------
const pet = window.Pet && (window.LIVELY_ME || {}).pet !== false ? Pet.mount({base:"/static/pet/", lines: clip => petLine(clip)}) : null;
const P = { replies:0, fail:0, model:0, fresh:null, people:0, pending:0 };  // fresh 在读到总览前是 null，桌宠就不提
function petLine(clip){
  return ({ rice:"白饭真好吃，再来一碗～", token: P.model ? `今天吃了 ${P.model} 口 token～` : null, hum:"今天群里好热闹～", cube:"魔方比群聊简单多了～",
    bubble:"咕噜咕噜～", mutter: P.fresh == null ? null : P.fresh ? `今天认识了 ${P.fresh} 个新朋友～` : "今天没认识新朋友～", tail:"尾巴拍拍，〈我〉在干活～",
    look:"主人在看什么呢～", dance:"〈我〉跳得好不好看～", stretch:"伸个懒腰～", float:"〈我〉在发呆～", crab:"横着走也是走～",
    breakfast:"〈我〉在吃早饭～", lunch:"午饭时间到～", dinner:"晚饭吃什么呢～" })[clip] || null;
}
// 桌宠开关按钮：睡觉的 zzz / 招手的鲸尾
function petBtn(b, off){ b.innerHTML = `<svg class="ic" aria-hidden="true"><use href="#${off ? "i-wave" : "i-zzz"}"/></svg><span>${off ? "叫〈我〉回来" : "让〈我〉休息"}</span>`; }
$("#petToggle")?.addEventListener("click", e => {
  const on = pet?.hidden; pet?.toggle(on); e.currentTarget.setAttribute("aria-pressed", on ? "false" : "true");
  petBtn(e.currentTarget, !on);
  try{ localStorage.setItem("lively-pet-off", on ? "" : "1"); }catch{}
});
try{ if(localStorage.getItem("lively-pet-off") && pet){ pet.toggle(false); const b = $("#petToggle"); if(b){ petBtn(b, true); b.setAttribute("aria-pressed","true"); } } }catch{}

// ---------- 请求 ----------
let loading = 0, thinkTimer;
function toast(m, bad){ const t = $("#toast"); t.textContent = m; t.classList.toggle("bad", !!bad); t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(()=>t.classList.remove("on"), 2800); }
async function api(path, body, {quiet=false}={}){
  const post = body !== undefined;
  const opt = post ? {method:"POST", headers:{"Content-Type":"application/json","X-Lively":"1"}, body:JSON.stringify(body)} : {};
  if(!quiet && !post && ++loading === 1) thinkTimer = setTimeout(() => pet?.mood("think", "〈我〉在翻小本本～"), 350);
  if(post) pet?.mood("busy", "〈我〉在办～");
  try{
    const r = await fetch(path, {credentials:"same-origin", ...opt});
    let j; try{ j = await r.json(); }catch{ throw new Error(r.status === 403 ? "没有权限，要先登录" : "服务器回了 HTTP "+r.status); }
    if(!j.ok) throw new Error(j.error || ("HTTP "+r.status));
    if(post) pet?.mood("done", j.msg ? j.msg+"～" : "办好啦～");
    return j;
  }catch(e){
    if(!quiet) pet?.mood("error", (post ? "没办成：" : "读不到数据：") + e.message + "～");
    throw e;
  }finally{
    if(!quiet && !post && --loading === 0){ clearTimeout(thinkTimer); pet?.calm(); }
  }
}
const fail = e => toast("读取失败："+e.message, true);

// ---------- 导航 ----------
const TABS = {overview:loadOverview, graph:loadGraph, people:loadPeople, settings:loadSettings, pending:loadPending, logs:loadLogs};
$$("#nav [data-t]").forEach(b => b.onclick = () => show(b.dataset.t));
function show(t){
  $$("#nav [data-t]").forEach(b => { const on = b.dataset.t===t; b.classList.toggle("on", on); b.setAttribute("aria-current", on ? "page" : "false"); });
  $$("main > section").forEach(s => s.classList.toggle("on", s.id==="sec-"+t));
  history.replaceState(null,"","#"+t);
  TABS[t]();
  setTimeout(()=>charts.forEach(c=>c.resize()), 50);
}
const charts = [];
addEventListener("resize", ()=>charts.forEach(c=>c.resize()));
function chart(el){ const c = echarts.init(el, null, {renderer:"canvas"}); charts.push(c); return c; }
const axis = () => ({axisLine:{lineStyle:{color:css("--c-axis")}}, axisTick:{show:false}, axisLabel:{color:css("--c-label")}, splitLine:{lineStyle:{color:css("--c-grid")}}});
const tip = () => ({backgroundColor:css("--c-tip-bg"), borderColor:css("--c-tip-edge"), textStyle:{color:css("--c-tip-ink")}});

// ---------- 总览 ----------
let hourlyChart;
const N = v => `<span class="n">${esc(v)}</span>`;
async function loadOverview(auto){
  // auto = 每分钟自动刷新：不打扰桌宠
  let d; try{ d = (await api("/api/overview", undefined, {quiet:!!auto})).data; }catch(e){ return auto ? setOnline(false) : fail(e); }
  setOnline(d.online);
  const t = d.today || {}, m = t["模型回复"] || {}, g = t["各群"] || {}, rel = t["关系"] || {}, cnt = d.counts || {};
  const gmsg = Object.values(g).reduce((a,x)=>a+(x["群消息"]||0),0), replies = Object.values(g).reduce((a,x)=>a+(x["〈我〉回复"]||0),0);
  Object.assign(P, {replies, fail:m["失败"]||0, model:m["次数"]||0, fresh:(rel["新认识"]||[]).length, pending:cnt["待审申请"]||0});
  const now = new Date(), h = now.getHours();
  const hello = h<5 ? "这么晚还不睡呀" : h<11 ? "早上好呀" : h<14 ? "中午好呀" : h<18 ? "下午好呀" : "晚上好呀";
  $("#hello").innerHTML = d.online ? `主人${hello}～〈我〉今天回了 <span class="n">${replies}</span> 句话～` : `主人${hello}～〈我〉现在掉线了，听不到群里说话～`;
  const up = d.uptime, upS = up>86400 ? Math.floor(up/86400)+" 天" : up>3600 ? Math.floor(up/3600)+" 小时" : Math.floor(up/60)+" 分钟";
  $("#calM").textContent = `${now.getMonth()+1} 月`; $("#calD").textContent = now.getDate(); $("#calW").textContent = "星期" + "日一二三四五六"[now.getDay()];
  $("#cal").setAttribute("aria-label", `${now.getMonth()+1} 月 ${now.getDate()} 日 星期${"日一二三四五六"[now.getDay()]}`);
  $("#acct").innerHTML = d.account ? `<img src="/api/avatar/${esc(d.account.qq)}" alt=""><b>${esc(d.account.name)}</b>${esc(d.account.qq)}` : `<span style="padding-left:8px">napcat 没连上</span>`;
  $("#uptime").innerHTML = `<svg class="ic" aria-hidden="true"><use href="#i-clock"/></svg>这次醒着 <b>${upS}</b>`;

  if(ME.meme !== false) $("#sticker img").src = "/static/meme/" + (!d.online ? "dead" : P.fail ? "stress" : P.pending ? "keep" : "rice") + ".webp";
  else $("#sticker").hidden = true;

  // 机器人日记：把今天的数字写成机器人的话
  const users = d.hourly.users.map((v,i)=>v+d.hourly.bot[i]), peak = users.indexOf(Math.max(...users));
  const L = [];
  if(!d.online) L.push(["sad", `QQ 掉线了，napcat 没连上，〈我〉现在收不到消息～`]);
  L.push(["", `今天 ${Object.keys(g).length} 个群一共冒出 ${N(gmsg)} 条消息，〈我〉插嘴了 ${N(replies)} 句～`]);
  if(users[peak] > 0) L.push(["", `最热闹的是 ${N(peak+"点")}，一个小时 ${N(users[peak])} 条，〈我〉差点回不过来～`]);
  const sp = m["中位耗时秒"]!=null ? `，一般 ${N(m["中位耗时秒"])} 秒就能回一句` : "";
  L.push([P.fail?"sad":"", `模型帮〈我〉回了 ${N(P.model)} 次${sp}，${P.fail ? `失败了 ${N(P.fail)} 次，呜～` : "一次都没失败～"}`]);
  if((cnt["今天画图"]||0) + (cnt["今天语音"]||0)) L.push(["", `还画了 ${N(cnt["今天画图"]||0)} 张图，发了 ${N(cnt["今天语音"]||0)} 条语音～`]);
  const fr = rel["新认识"] || [];
  if(fr.length) L.push(["", `新认识了 ${N(fr.length)} 个人：${fr.slice(0,5).map(x=>`<span class="dname">${esc(x)}</span>`).join("、")}${fr.length>5?" 他们":""}～`]);
  const upL = rel["好感涨得最多"] || [], dnL = rel["好感掉了"] || [];
  if(upL.length) L.push(["", `${upL.slice(0,3).map(x=>`<span class="dname">${esc(x.replace(/\s*\+[\d.]+$/,""))}</span>`).join("、")}今天让〈我〉更喜欢了～`]);
  if(dnL.length) L.push(["sad", `${dnL.slice(0,3).map(x=>`<span class="dname">${esc(x.replace(/\s*-[\d.]+$/,""))}</span>`).join("、")}今天惹〈我〉不高兴了，哼～`]);
  L.push([P.pending?"sad":"", P.pending ? `有 ${N(P.pending)} 个好友申请等主人拍板～` : "没有要主人处理的申请，〈我〉可以安心吃饭了～"]);
  $("#dlines").innerHTML = L.map(([c,x]) => `<li class="${c}">${x}</li>`).join("");

  // 今天的账
  const row = (k,v,u,extra="",cls="") => `<tr class="${cls}"><td>${k}${extra}</td><td><b>${esc(v)}</b><small>${u}</small></td></tr>`;
  $("#ledger").innerHTML = row("群里的消息",gmsg,"条") + row("〈我〉回复",replies,"句") + row("模型回复",P.model,"次",P.fail?` <small class="muted">失败 ${P.fail}</small>`:"",P.fail?"hot":"")
    + row("回一句要",m["中位耗时秒"] ?? "—","秒") + row("画图",cnt["今天画图"] ?? 0,"张") + row("发语音",cnt["今天语音"] ?? 0,"条")
    + row("主动找人聊",cnt["今天主动聊天"] ?? 0,"次") + row("等主人审",P.pending,"件","",P.pending?"hot":"");
  const st = $("#stamp"); st.className = "stamp" + (P.fail ? "" : " ok"); st.innerHTML = P.fail ? `失败<br>${P.fail} 次` : "今天<br>零失败";
  $("#groups").innerHTML = Object.keys(g).length
    ? Object.entries(g).map(([n,v]) => row(esc(n), v["群消息"], "条", `<br><small class="muted">〈我〉回了 ${v["〈我〉回复"]} 句</small>`)).join("")
    : `<tr><td class="muted">今天群里还没人说话～</td></tr>`;

  // 鱼缸：水位 = 用掉的比例
  const s = d.system || {}, mem = s.mem || {}, disk = s.disk || {}, pct = (a,b) => b ? Math.round(a/b*100) : 0;
  const tank = (k,used,total,free,u) => { const p = pct(used,total);
    return `<div class="tank"><div class="tank-glass" role="img" aria-label="${k}用了 ${p}%"><div class="tank-water${p>85?" bad":p>65?" warn":""}" style="height:${p}%"><i style="left:22%;bottom:10%"></i><i style="left:62%;bottom:4%;animation-delay:-2s"></i></div><b>${p}%</b></div>
      <p>${k}<small>还空着 ${free}${u}</small></p></div>`; };
  $("#tanks").innerHTML = tank("内存", mem.total-mem.available, mem.total, mem.available, " MB") + tank("磁盘", disk.used, disk.total, disk.free, " GB")
    + tank("交换区", mem.swap_used, mem.swap_total, mem.swap_total-mem.swap_used, " MB");
  const ld = s.load?.[0] ?? 0, lr = ld/(s.cpus||1);
  $("#loadline").textContent = `负载 ${ld}（${s.cpus||"?"} 核）—— ${lr>.9 ? "服务器喘不过气了，〈我〉跑不动～" : lr>.5 ? "有点忙，〈我〉跑得慢一点～" : "很轻松，〈我〉跑得飞快～"}`;

  // 群里的事、最近动态
  const ev = t["群里的事"] || [];
  $("#events").innerHTML = ev.length ? ev.slice(0,6).map(e => `<li><div class="ev-h"><b>${esc(e["群"])}</b>${(e["话题"]||[]).slice(0,3).map(x=>`<span class="chip">${esc(x)}</span>`).join("")}</div><p>${esc(e["摘要"])}</p></li>`).join("")
    : `<li>${meme("sleep","群里今天还没发生什么事～")}</li>`;
  // 动态：只留「做了什么、在哪、几点」，模型名和英文提示词这些放进悬停提示
  const feedLine = f => { const kv = {}; String(f.detail||"").split(" · ").forEach(x => { const m = x.match(/^(.+?)：(.*)$/); if(m) kv[m[1]] = m[2]; });
    const extra = Object.entries(kv).filter(([k]) => !["在","群","模型","内容","画自己"].includes(k)).map(([k,v]) => `${k}：${v}`).join("，");
    return `<li title="${esc(f.detail)}"><span class="chip">${esc(f.src)}</span><b>${esc(f.kind)}</b>${(kv["在"]||kv["群"])?`<span class="muted small">　在 ${esc(kv["在"]||kv["群"])}</span>`:""}<time>${fmtT(f.ts)}</time>${extra?`<div class="small muted">${esc(extra)}</div>`:""}</li>`; };
  $("#feed").innerHTML = (d.feed||[]).slice(0,12).map(feedLine).join("") || `<li>${meme("sleep","还没有动态～")}</li>`;

  // 机器人的一天：24 小时钟，0 点在正上方顺时针走。最忙的一小时常常是别的几倍，按平方根画才看得出一天的起伏，提示框里还是原数
  if(!hourlyChart) hourlyChart = chart($("#hourly"));
  const hours = [...Array(24).keys()].map(x=>x+"点");
  // 整根柱子按总数开平方，再按真实比例分给群友和机器人，粉蓝比例不失真
  const part = k => users.map((tot,i) => tot ? Math.sqrt(tot) * (d.hourly[k][i]||0) / tot : 0);
  const night = hours.map((_,i) => i < 6 ? 1 : null);
  hourlyChart.setOption({tooltip:{trigger:"axis",axisPointer:{type:"shadow"},...tip(),
      formatter:x => `${x[0].axisValue}<br>群友和私聊 ${d.hourly.users[x[0].dataIndex]} 条<br>〈我〉 ${d.hourly.bot[x[0].dataIndex]} 句`},
    polar:{radius:["24%","88%"]},
    angleAxis:{type:"category",data:hours,startAngle:90,clockwise:true,
      axisLabel:{color:css("--c-label"),interval:2,fontSize:11},axisLine:{lineStyle:{color:css("--c-axis")}},axisTick:{show:false},
      splitLine:{show:true,interval:2,lineStyle:{color:css("--c-grid")}}},
    radiusAxis:{show:false,max:Math.max(3, ...users.map(v=>Math.sqrt(v)))},
    graphic:[{type:"text",left:"center",top:"middle",style:{text: users[peak] ? `${peak} 点\n最热闹` : "今天\n还很安静",
      textAlign:"center",fill:css("--ink"),font:`18px "Ruantang", sans-serif`,lineHeight:22}}],
    series:[
      {name:"夜里",type:"bar",coordinateSystem:"polar",data:night.map(v=>v?Math.max(3, ...users.map(u=>Math.sqrt(u))):null),barGap:"-100%",barCategoryGap:"0%",
        itemStyle:{color:css("--c-grid"),opacity:.6},silent:true,z:0,tooltip:{show:false}},
      {name:"群友和私聊",type:"bar",coordinateSystem:"polar",stack:"a",data:part("users"),barCategoryGap:"18%",
        itemStyle:{color:css("--c-users"),borderRadius:3}},
      {name:"〈我〉",type:"bar",coordinateSystem:"polar",stack:"a",data:part("bot"),itemStyle:{color:css("--c-bot"),borderRadius:3}}]}, true);

  // 机器人对大家的心情（要另外读一次人物表）
  loadMoodSummary(!!auto);
  loadBilling(!!auto);
  await refreshPendCount(true);
  // 桌宠：有待处理就行礼，深夜打哈欠，否则报一下今天的数
  if(!auto) setTimeout(() => {
    if(!d.online) pet?.mood("error", "QQ 掉线了，〈我〉听不到群里说话～");
    else if(P.pending) pet?.mood("pending", `有 ${P.pending} 件事等主人拍板～`);
    else if(h >= 23 || h < 5) pet?.mood("night", "好困…主人也早点睡～");
    else pet?.say(`今天回了 ${replies} 句，失败 ${P.fail} 次～`);
  }, 400);
}
// 机器人的饭钱：每把密钥分开记（按 token 算），账户余额每小时查一次，前后相减是真实扣了多少；画图按张数估
let billChart;
const KEY_COLORS = ["--c-accent","--c-owner","--c-peer","--c-users","--c-hit"];
async function loadBilling(quiet){
  let b; try{ b = (await api("/api/billing", undefined, {quiet:true})).data; }catch(e){ $("#bill").innerHTML = `<tr><td class="muted">饭钱插件还没装好～</td></tr>`; return; }
  const yuan = v => v==null ? "—" : (+v).toFixed(2);
  const row = (k,v,u,extra="",cls="") => `<tr class="${cls}"><td>${k}${extra}</td><td><b>${esc(v)}</b><small>${u}</small></td></tr>`;
  const t = b.days[b.days.length-1] || {}, y = b.days[b.days.length-2] || {};
  const accts = b.accounts || [], keys = b.keys || [];
  const low = accts.some(a => a.low);
  let h = accts.map(a => row(accts.length > 1 ? `DeepSeek 余额 · ${esc(keys.filter(k=>a.keys.includes(k.id)).map(k=>k.label).join("、"))}` : "DeepSeek 余额",
      yuan(a.balance), "元", a.keys.length > 1 ? `<br><small class="muted">${a.keys.length} 把密钥共用这个账户，余额只有一个总数</small>` : "", a.low?"hot":"")).join("");
  h += row("今天实际扣了", t.actual!=null ? yuan(t.actual) : "—", "元", t.actual==null ? `<br><small class="muted">余额记录满一小时后才有</small>` : "");
  h += keys.map(k => { const v = (t.keys||{})[k.id] || {};
      const by = Object.entries(v.by||{}).filter(([,c]) => c >= 0.005).map(([w,c]) => `${esc(w)} ${yuan(c)}`).join("，");
      return row(`　${esc(k.label)}`, yuan(v.total), "元", `<br><small class="muted">${esc(k.id)}：聊天 ${yuan(v.chat)}${by?`，${by}`:""}</small>`); }).join("");
  if(t.unattributed) h += row("　没记到的", yuan(t.unattributed), "元", `<br><small class="muted">实际扣的减去各密钥算出来的，比如别的程序也在用这个账户</small>`);
  h += row("昨天", y.actual!=null && !y.partial ? yuan(y.actual) : "≈"+yuan(y.estimated), "元")
    + row("画图（估）", t.images ?? 0, "张", `<br><small class="muted">约 ${yuan(t.image_cost)} 元，一张按 ${yuan(b.image_price)} 元算</small>`)
    + accts.map(a => row(accts.length > 1 ? "还能撑（这个账户）" : "还能撑", a.runway_days ?? "—", "天", `<br><small class="muted">按一天 ${yuan(a.per_day)} 元算</small>`, a.runway_days!=null && a.runway_days < 3 ? "hot" : "")).join("");
  $("#bill").innerHTML = h;
  const st = $("#billStamp"); st.className = "stamp" + (low ? "" : " ok"); st.innerHTML = low ? "该充<br>饭钱了" : "饭钱<br>够吃";
  $("#billNote").textContent = b.updated ? `余额 ${fmtT(b.updated)} 查的，每小时查一次；低于 ${b.alert_at} 元〈我〉会私信提醒主人。每把密钥的花费按 token 和官方单价算` : "还没查到余额～";
  if(!billChart) billChart = chart($("#billChart"));
  const days = b.days.map(d => d.day.slice(5).replace("-", "/"));
  const series = keys.map((k,i) => ({name:k.label,type:"bar",stack:"a",barWidth:"46%",data:b.days.map(d => (d.keys||{})[k.id]?.total ?? 0),
    itemStyle:{color:css(KEY_COLORS[i % KEY_COLORS.length])}}));
  series.push({name:"没记到的",type:"bar",stack:"a",data:b.days.map(d => d.unattributed ?? null),itemStyle:{color:css("--c-grid")}});
  series.push({name:"画图",type:"bar",stack:"a",data:b.days.map(d=>d.image_cost),itemStyle:{color:css("--c-bot"),borderRadius:[3,3,0,0]}});
  billChart.setOption({tooltip:{trigger:"axis",axisPointer:{type:"shadow"},...tip(),
      formatter:x => { const d = b.days[x[0].dataIndex];
        return `${d.day}${d.partial?"（不满一天）":""}<br>${d.actual!=null?`实际扣了 ${yuan(d.actual)} 元<br>`:""}`
          + keys.map(k => { const v = (d.keys||{})[k.id] || {}; return `${esc(k.label)} ${yuan(v.total)} 元（聊天 ${yuan(v.chat)}，后台 ${yuan(v.background)}）`; }).join("<br>")
          + `${d.unattributed?`<br>没记到的 ${yuan(d.unattributed)} 元`:""}<br>画图 ${d.images} 张，约 ${yuan(d.image_cost)} 元`; }},
    legend:{show:false},
    grid:{left:36,right:8,top:12,bottom:28},
    xAxis:{type:"category",data:days,axisLine:{lineStyle:{color:css("--c-axis")}},axisTick:{show:false},axisLabel:{color:css("--c-label")}},
    yAxis:{type:"value",splitLine:{lineStyle:{color:css("--c-grid")}},axisLabel:{color:css("--c-label"),formatter:v=>"¥"+v}},
    series}, true);
  $("#billLegend") && ($("#billLegend").innerHTML = keys.map((k,i) => `<span><i style="background:${css(KEY_COLORS[i % KEY_COLORS.length])}"></i>${esc(k.label)}</span>`).join("")
    + `<span><i style="background:${css("--c-grid")}"></i>没记到的</span><span><i style="background:${css("--c-bot")}"></i>画图（估）</span>`);
}

async function loadMoodSummary(quiet){
  let rows; try{ rows = (await api("/api/people", undefined, {quiet:true})).data; }catch{ if(!quiet) $("#moodsum").innerHTML = `<p class="muted">读不到～</p>`; return; }
  rows = rows.filter(hasImpr);
  const by = {}; rows.forEach(r => (by[r.mood||"平常"] ||= []).push(r));
  const kinds = Object.keys(by).sort((a,b) => (a==="平常") - (b==="平常") || by[b].length - by[a].length);
  const total = rows.length || 1;
  let h = `<div class="mbar" role="img" aria-label="心情分布">${kinds.map(k=>`<span data-mood="${esc(k)}" style="flex:${by[k].length}" title="${esc(k)} ${by[k].length} 人"></span>`).join("")}</div>
    <div class="mlegend">${kinds.map(k=>`<span data-mood="${esc(k)}">${esc(k)} <b>${by[k].length}</b> 人</span>`).join("")}</div>`;
  const special = kinds.filter(k => k !== "平常");
  h += special.length ? `<ul class="mwho">${special.map(k => `<li><span class="mood-pill" data-mood="${esc(k)}">${esc(k)}</span><span class="ppl">${by[k]
      .sort((a,b)=>(b.mood_at||0)-(a.mood_at||0)).slice(0,8).map(r=>`<button data-qq="${esc(r.qq)}"><img src="/api/avatar/${esc(r.qq)}" alt="" width="22" height="22" loading="lazy" onerror="this.style.visibility='hidden'">${esc(r.name||r.qq)}</button>`).join("")}</span></li>`).join("")}</ul>`
    : `<p class="muted">〈我〉今天对谁都心平气和～</p>`;
  $("#moodsum").innerHTML = h;
  $$("#moodsum .mwho button").forEach(b => b.onclick = () => openPerson(b.dataset.qq));
}
function setOnline(on){ $(".status").classList.toggle("on", !!on); $(".status").classList.toggle("off", !on); const d = $("#onlineDot"); d.className = "dot " + (on ? "on" : "off"); d.title = on ? "QQ 在线" : "QQ 离线"; $("#onlineText").textContent = on ? "QQ 在线" : "QQ 离线"; }

// ---------- 关系图 ----------
let graphChart, graphData, gGroup = "all";
const favorColor = f => f>=60?css("--f5"):f>=25?css("--f4"):f>=8?css("--f3"):f>-8?css("--f2"):f>-25?css("--f1"):css("--f0");
const avCache = new Map();
// 把头像裁成圆形、外面套一圈好感色，做成 ECharts 能用的 image:// 图标
function avatarSymbol(src, ring, px=96){
  const key = src+"|"+ring;
  if(avCache.has(key)) return avCache.get(key);
  const p = new Promise(res => {
    const img = new Image(); img.decoding = "async";
    const to = setTimeout(() => res(null), 6000);
    img.onload = () => { clearTimeout(to);
      const c = document.createElement("canvas"); c.width = c.height = px; const x = c.getContext("2d"), r = px/2, b = Math.round(px*.07);
      x.fillStyle = ring; x.beginPath(); x.arc(r,r,r,0,7); x.fill();
      x.save(); x.beginPath(); x.arc(r,r,r-b,0,7); x.clip(); x.fillStyle = "#fff"; x.fill(); x.drawImage(img, b, b, px-2*b, px-2*b); x.restore();
      try{ res("image://"+c.toDataURL("image/png")); }catch{ res(null); } };
    img.onerror = () => { clearTimeout(to); res(null); };
    img.src = src;
  });
  avCache.set(key, p); return p;
}
async function loadGraph(){
  const days = $("#gdays").value;
  try{ graphData = (await api(`/api/graph?days=${days}&group=${encodeURIComponent(gGroup)}`)).data; }catch(e){ return fail(e); }
  const keep = new Set(graphData.nodes.filter(hasImpr).map(n => n.id));
  graphData.nodes = graphData.nodes.filter(n => keep.has(n.id));
  graphData.links = graphData.links.filter(l => keep.has(l.source) && keep.has(l.target));
  P.people = graphData.nodes.length - 1;
  renderGroupTabs();
  if(!graphChart){ graphChart = chart($("#graphCanvas")); graphChart.on("click", p => { if(p.dataType==="node" && !p.data.bot) openPerson(p.data.id); }); }
  await drawGraph(true);
  const gname = gGroup === "all" ? "" : (graphData.groups.find(g => g.id === gGroup)?.name || "");
  pet?.say(gname ? `「${gname}」里〈我〉认识 ${P.people} 个人～` : `〈我〉认识 ${P.people} 个人啦，点头像看详情～`);
}
// 分页：全部 / 各群 / 私聊。人少于 2 个的小群不单独开页，在「全部」里看
function renderGroupTabs(){
  const gs = (graphData.groups || []).filter(g => g.people >= 2 || g.id === gGroup);
  $("#gtabs").innerHTML = [`<button role="tab" data-g="all" aria-selected="${gGroup==="all"}">全部</button>`,
    ...gs.map(g => `<button role="tab" data-g="${esc(g.id)}" aria-selected="${gGroup===g.id}">${esc(g.name)}</button>`)].join("");
  $$("#gtabs button").forEach(b => b.onclick = () => {
    if(b.dataset.g === gGroup) return;
    gGroup = b.dataset.g;
    // 全部里群友之间的线最乱，默认不画；单看一个群时默认画明显的
    $("#gpeople").value = gGroup === "all" ? "0" : "2";
    loadGraph();
  });
}
const gName = id => id === "dm" ? "私聊" : (graphData.group_names?.[id] || "群"+id);
async function drawGraph(withAvatars){
  const q = $("#gsearch").value.trim(), minW = +$("#gpeople").value;
  const box = $("#graphCanvas"), W = box.clientWidth, H = box.clientHeight, k = W < 640 ? .7 : 1;  // 手机上缩小，整张图放得下
  const nodes = await Promise.all(graphData.nodes.map(async n => {
    const size = Math.round(k * (n.bot ? 72 : Math.min(52, 20 + Math.sqrt(Math.max(0,n.familiarity))*2.6 + Math.min(8, Math.sqrt(n.talks||0)))));
    const hit = q && (n.name.includes(q) || n.id.includes(q));
    const ring = hit ? css("--c-hit") : n.bot ? css("--c-fish") : n.owner ? css("--c-owner") : favorColor(n.favor||0);
    const sym = withAvatars || avCache.size ? await avatarSymbol(n.bot ? "/static/fish.webp" : "/api/avatar/"+n.id, ring) : null;
    return {id:n.id, name:n.name, bot:n.bot, symbolSize: hit ? size+10 : size, value:n.favor,
      ...(n.bot?{fixed:true,x:W/2,y:H/2}:{}), ...(sym?{symbol:sym}:{itemStyle:{color:ring,borderColor:"#fff",borderWidth:2}}),
      label:{show: n.bot || n.owner || hit || size>34, fontSize: n.bot?14:12},
      tip: n.bot ? "〈名字〉（〈我〉）" : `<b>${esc(n.name)}</b>　${n.id}<br>好感 ${n.favor}，熟悉 ${n.familiarity}，聊过 ${n.talks} 次<br>心情：${esc(n.mood||"—")}<br>印象：${esc(n.impression||"—")}${(n.groups||[]).length?`<br>在：${n.groups.slice(0,3).map(g=>esc(gName(g))).join("、")}`:""}`};
  }));
  const links = graphData.links.filter(l => l.kind==="bond" || (minW>0 && l.weight>=minW)).map(l => l.kind==="bond"
    ? {source:l.source,target:l.target,lineStyle:{width:1+Math.max(0,l.favor)/22,color:favorColor(l.favor),opacity:.8},tip:`好感 ${l.favor}，熟悉 ${l.familiarity}`}
    : {source:l.source,target:l.target,lineStyle:{width:Math.min(5,.6+Math.sqrt(l.weight)*.6),type:"dashed",color:css("--c-peer"),opacity:.55},
       tip:`互相 @ ${l.at} 次，一起出现在 ${l.memory} 段记忆里`});
  graphChart.setOption({tooltip:{formatter:p=>p.data.tip||"",...tip()},
    series:[{type:"graph",layout:"force",roam:true,draggable:true,data:nodes,links,
      force: k < 1 ? {repulsion:120,edgeLength:[36,100],gravity:.14,friction:.15} : {repulsion:420,edgeLength:[90,230],gravity:.06,friction:.15},
      label:{position:"bottom",distance:4,color:css("--c-text"),textBorderColor:css("--c-text-halo"),textBorderWidth:3},
      emphasis:{focus:"adjacency",lineStyle:{width:3}},lineStyle:{curveness:.08}}]}, true);
}
$("#gdays").onchange = loadGraph;
$("#gsearch").oninput = () => graphData && drawGraph();
$("#gpeople").onchange = () => graphData && drawGraph();

// ---------- 人物详情：印象卡 ----------
let personChart, lastFocus;
const ME = window.LIVELY_ME || {};  // 主人、机器人是谁：面板后端从插件配置填进页面
const OWNER = ME.owner || "";
// 机器人还没有印象的人不在面板上出现（主人除外）
const hasImpr = x => x.bot || x.owner || (x.qq || x.id) === OWNER || String(x.impression || "").trim() !== "";
const tierOf = p => p.qq === OWNER || /主人/.test(p.stage||"") ? ["t-owner","主人"]
  : (p.favor||0) >= 25 ? ["t-love","喜欢"] : (p.favor||0) >= 8 ? ["t-close","亲近"] : (p.favor||0) > -8 ? ["t-mid","普通"] : ["t-hate","讨厌"];
// 小本本（人物卡）是「标签：内容；标签：内容；……；相处建议」，拆成一格一格
function parseCard(text){
  const out = {rows:[], tip:""};
  for(const seg of String(text||"").split(/[；;]\s*/).map(s=>s.trim()).filter(Boolean)){
    const m = seg.match(/^([^：:]{1,8})[：:](.+)$/);
    if(m) out.rows.push([m[1].trim(), m[2].trim()]); else out.tip += (out.tip?"；":"") + seg;
  }
  return out;
}
const chips = (v, cls="") => v.split(/[、，,]\s*/).filter(Boolean).map(x=>`<span class="chip ${cls}">${esc(x)}</span>`).join("");
async function openPerson(qq){
  const dr = $("#drawer"); if(!dr.classList.contains("on")) lastFocus = document.activeElement;
  dr.classList.add("on"); dr.setAttribute("aria-hidden","false"); $("#scrim").classList.add("on"); document.body.style.overflow = "hidden"; document.body.classList.add("card-open");
  dr.innerHTML = `<button class="pv-close" id="drClose" aria-label="关闭"><svg class="ic" aria-hidden="true"><use href="#i-close"/></svg></button><div class="empty" style="color:#fff"><p>〈我〉在翻小本本找这个人～</p></div>`;
  $("#drClose").onclick = closeDrawer;
  let d; try{ d = (await api("/api/person/"+qq)).data; }catch(e){ dr.innerHTML = `<button class="pv-close" id="drClose" aria-label="关闭"><svg class="ic" aria-hidden="true"><use href="#i-close"/></svg></button>`+meme("dead", "读不到："+esc(e.message)+"～"); $("#drClose").onclick = closeDrawer; return; }
  const p = {...d.profile, qq}, ev = d.events;
  const impr = ev.filter(e=>e.kind==="impression"), moods = ev.filter(e=>e.kind==="mood"), fav = ev.filter(e=>e.kind==="favor");
  const src = s => ({group:"群聊",dm:"私聊",private:"私聊",admin:"主人改的"})[s] || s || "";
  const [tcls, tname] = tierOf(p);
  const f = Math.max(-100, Math.min(100, p.favor||0));
  const node = graphData?.nodes?.find(n => n.id === qq);
  const where = (node?.groups||[]).slice(0,2).map(g => gName(g)).join("、");
  const card = parseCard(p.card);
  const memRow = m => { const long = (m.text||"").length > 140, t = String(m.where||"").match(/^(.+?记忆（.+?）)・(.*)$/);
    return `<div class="mem${long?" long":""}"><p>${esc(m.text)}</p><small>${fmtT(m.ts)}，${t?`<span class="tier">${esc(t[1])}</span>・${esc(t[2])}`:esc(m.where)}</small>${long?`<button class="more">展开</button>`:""}</div>`; };
  const tabs = [
    ["note","小本本",""], ["impr","印象",impr.length], ["mem","记得的事",d.memories.length], ["msg","说过的话",Math.min(d.messages.length,25)], ["link","联系",d.links.length]];
  dr.innerHTML = `<button class="pv-close" id="drClose" aria-label="关闭"><svg class="ic" aria-hidden="true"><use href="#i-close"/></svg></button>
  <div class="pv">
    <div class="fcard-wrap"><article class="fcard ${tcls}" id="fcard" aria-label="${esc(p.name||qq)} 的〈卡〉">
      <div class="fcard-in">
        <div class="fc-top"><span>QQ ${esc(qq)}</span><span class="fc-tier">${esc(p.favor_desc || tname)}</span></div>
        <div class="fc-art"><img src="https://q1.qlogo.cn/g?b=qq&nk=${esc(qq)}&s=640" alt="" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='/api/avatar/${esc(qq)}'">
          <span class="holo"></span>${p.mood?`<span class="fc-mood mood-pill" data-mood="${esc(p.mood)}">${esc(p.mood)}</span>`:""}<span class="fc-fav">${p.favor ?? 0}</span></div>
        <div class="fc-body">
          <h2 class="fc-name">${esc(p.name||qq)}</h2>
          ${p.stage?`<span class="fc-stage">${esc(p.stage)}</span>`:""}
          <div class="fc-meter" title="好感 ${p.favor ?? 0}（-100 到 100）"><i style="left:${(f+100)/2}%"></i></div>
          <div class="fc-meter-l"><span>讨厌</span><span>喜欢</span></div>
          <div class="fc-stats"><div><b>${p.familiarity ?? 0}</b><small>熟悉</small></div><div><b>${p.talks ?? 0}</b><small>聊过</small></div><div><b>${impr.length}</b><small>印象</small></div></div>
          <div class="fc-quote"><small>〈我〉觉得</small><p>${esc(p.impression || "还没有印象～")}</p></div>
          <div class="fc-foot"><img src="/static/fish.webp" alt=""><span>认识于 ${fmtT(p.first_met)}</span><span>${where ? esc(where) : "最近聊天 "+ago(p.last_talk)}</span></div>
        </div>
      </div><span class="holo frame"></span></article></div>
    <section class="dossier">
      <h2>${esc(p.name||qq)} 的档案</h2>
      <div class="dtabs" role="tablist">${tabs.map(([k,t,n],i)=>`<button role="tab" data-p="${k}" aria-selected="${i===0}">${t}${n!==""?`<small>${n}</small>`:""}</button>`).join("")}</div>
      <div class="dpane" data-p="note">
        ${card.rows.length ? `<dl class="facts">${card.rows.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${/喜欢|梗/.test(k)?chips(v):/别碰|雷|不要/.test(k)?chips(v,"no"):esc(v)}</dd>`).join("")}</dl>` : `<p class="muted">〈我〉还没给 TA 记小本本～</p>`}
        ${card.tip?`<div class="tip-box"><small>〈我〉跟 TA 相处的办法</small>${esc(card.tip)}</div>`:""}
        <p class="muted small" style="margin:14px 0 0">最近见到 ${ago(p.last_seen)}，最近聊天 ${ago(p.last_talk)}</p>
        <h3 class="sub-h">好感变化</h3>${fav.length?`<div id="pchart" class="pchart"></div>`:`<p class="muted">还没有好感变化～</p>`}
        <h3 class="sub-h">心情变化</h3>${moodBlock(p, moods, ev)}
      </div>
      <div class="dpane" data-p="impr" hidden>${impr.length?`<ol class="tl">${impr.slice().reverse().map(e=>`<li><p>${esc(e.note)}</p><small>${fmtT(e.ts)}，${esc(src(e.source))}</small></li>`).join("")}</ol>`:`<p class="muted">还没有～</p>`}</div>
      <div class="dpane" data-p="mem" hidden>${d.memories.map(memRow).join("")||`<p class="muted">还没有～</p>`}</div>
      <div class="dpane" data-p="msg" hidden>${d.messages.slice(0,25).map(memRow).join("")||`<p class="muted">没有记录～</p>`}</div>
      <div class="dpane" data-p="link" hidden>${d.links.length?`<div class="links">${d.links.map(l=>`<button data-qq="${esc(l.qq)}"><img src="/api/avatar/${esc(l.qq)}" alt="" width="34" height="34" loading="lazy" onerror="this.style.visibility='hidden'"><span><b>${esc(l.name||l.qq)}</b><small>互相 @ ${l.at}，记忆 ${l.memory}</small></span></button>`).join("")}</div>`:`<p class="muted">没有明显的联系～</p>`}</div>
      <div class="sw"><div>不要主动找 TA 聊天<small>打开后〈我〉不会主动私聊这个人</small></div><label class="toggle"><input type="checkbox" id="pBlock" ${d.proactive_blocked?"checked":""} aria-label="不要主动找 TA 聊天"><span></span></label></div>
    </section>
  </div>`;
  $("#drClose").onclick = closeDrawer; $("#drClose").focus();
  dr.onclick = e => { if(e.target === dr || e.target.classList.contains("pv")) closeDrawer(); };
  $("#pBlock").onchange = e => setS("proactive", e.target.checked?"block":"unblock", qq);
  dr.querySelectorAll(".links button").forEach(b => b.onclick = () => { dr.scrollTop = 0; openPerson(b.dataset.qq); });
  dr.querySelector(".mood-all")?.addEventListener("click", e => { dr.querySelectorAll(".mood-log li.old").forEach(li => li.hidden = false); e.currentTarget.remove(); });
  dr.querySelectorAll(".mem .more").forEach(b => b.onclick = () => { const m = b.parentElement; m.classList.toggle("open"); b.textContent = m.classList.contains("open") ? "收起" : "展开"; });
  dr.querySelectorAll(".dtabs button").forEach(b => b.onclick = () => {
    dr.querySelectorAll(".dtabs button").forEach(x => x.setAttribute("aria-selected", x === b));
    dr.querySelectorAll(".dpane").forEach(x => x.hidden = x.dataset.p !== b.dataset.p);
    if(b.dataset.p === "note") personChart?.resize();
  });
  tiltCard($("#fcard"));
  // 桌宠看到这张卡的反应
  if(tcls === "t-owner") pet?.mood("shy", "是主人！〈我〉最喜欢的人～");
  else if(tcls === "t-hate") pet?.mood("pout", `哼，是${p.name||"TA"}，〈我〉还在记仇～`);
  else if(tcls === "t-love") pet?.mood("hop", `${p.name||"TA"}！〈我〉喜欢 TA～`);
  else pet?.say(`这是${p.name||"TA"}，〈我〉觉得 TA ${p.impression||"还不太熟"}～`);
  if(personChart){ personChart.dispose(); charts.splice(charts.indexOf(personChart),1); personChart = null; }
  if(!fav.length) return;
  personChart = chart($("#pchart"));
  personChart.setOption({grid:{left:36,right:12,top:14,bottom:28},tooltip:{trigger:"axis",...tip(),formatter:x=>{const e=fav[x[0].dataIndex];return `${fmtT(e.ts)}<br>好感 ${e.after}（${e.delta>0?"+":""}${e.delta}）${e.note?"<br>"+esc(e.note):""}`}},
    xAxis:{type:"category",data:fav.map(e=>fmtT(e.ts)),...axis(),axisLabel:{fontSize:10,color:css("--c-label")}},yAxis:{type:"value",...axis()},
    series:[{type:"line",data:fav.map(e=>e.after),smooth:true,symbolSize:6,areaStyle:{color:css("--c-users-fill")},itemStyle:{color:css("--c-accent")},lineStyle:{color:css("--c-accent")}}]});
}
// 心情变化：一条按时间上色的心情带 + 每次变化的明细（对上前后半小时内的好感和印象，当作「当时发生了什么」）
function moodBlock(p, moods, ev){
  const now = Date.now()/1000;
  let h = `<div class="mood-now" data-mood="${esc(p.mood||"")}"><span class="mood-pill" data-mood="${esc(p.mood||"")}">${esc(p.mood||"平常")}</span><b>现在的心情</b><small>${esc(p.mood_desc||"")}${p.mood_at?`，从 ${fmtT(p.mood_at)} 开始`:""}</small></div>`;
  // 心情回到平常这类变化不写进事件表，用 mood_at 补上最后一段
  const last = moods[moods.length-1];
  if(p.mood && p.mood_at && (!last || (p.mood_at > last.ts + 60 && p.mood !== last.note))) moods = [...moods, {ts:p.mood_at, note:p.mood, source:"", synth:true}];
  if(!moods.length) return h + `<p class="muted small" style="margin-top:8px">〈我〉对 TA 的心情一直没变过～</p>`;
  const t0 = moods[0].ts, span = Math.max(1, now - t0);
  h += `<div class="mood-band" role="img" aria-label="心情随时间的变化">${moods.map((m,i) => { const end = moods[i+1]?.ts ?? now;
    return `<span data-mood="${esc(m.note)}" style="flex:${Math.max(.6,(end-m.ts)/span*100).toFixed(2)}" title="${esc(m.note)}：${fmtT(m.ts)} 到 ${moods[i+1]?fmtT(end):"现在"}"></span>`; }).join("")}</div>
    <div class="mood-axis"><span>${fmtT(t0)}</span><span>现在</span></div>`;
  const kinds = [...new Set(moods.map(m=>m.note))];
  h += `<div class="mood-keys">${kinds.map(k=>{ const n = moods.filter(m=>m.note===k).length; return `<span data-mood="${esc(k)}">${esc(k)} ${n} 次</span>`; }).join("")}</div>`;
  const src = s => ({group:"群聊",dm:"私聊",private:"私聊",admin:"主人改的"})[s] || s || "";
  h += `<ol class="mood-log">${moods.map((m,i) => {
    const prev = moods[i-1]?.note;
    const near = ev.filter(e => (e.kind==="favor"||e.kind==="impression") && Math.abs(e.ts-m.ts) <= 1800).sort((a,b)=>Math.abs(a.ts-m.ts)-Math.abs(b.ts-m.ts)).slice(0,2);
    const ctx = near.map(e => e.kind==="favor" ? `好感 ${e.delta>0?"+":""}${e.delta}${e.note&&!/^模型给/.test(e.note)?`（${esc(e.note)}）`:""}` : `新印象「${esc(e.note)}」`).join("；");
    return `<li${i < moods.length-8 ? ' class="old" hidden' : ""}><time>${fmtT(m.ts)}</time><span class="chg">${!prev?"<i>变成</i>":prev===m.note?"<i>仍然</i>":`<span class="mood-pill" data-mood="${esc(prev)}">${esc(prev)}</span><i>→</i>`}<span class="mood-pill" data-mood="${esc(m.note)}">${esc(m.note)}</span><i>${esc(src(m.source))}</i></span>${m.synth?`<span class="ctx">这次变化没有单独记录，时间取自现在这个心情开始的时候</span>`:ctx?`<span class="ctx">当时：${ctx}</span>`:""}</li>`;
  }).reverse().join("")}</ol>${moods.length > 8 ? `<button class="btn ghost mood-all" style="margin-top:10px">看全部 ${moods.length} 次</button>` : ""}`;
  return h;
}
// 镭射：光点跟着鼠标，彩虹纹反方向滑，看起来像真的箔
function holoAt(el, e){
  const r = el.getBoundingClientRect(), x = (e.clientX-r.left)/r.width, y = (e.clientY-r.top)/r.height;
  el.style.setProperty("--mx", (x*100).toFixed(1)+"%"); el.style.setProperty("--my", (y*100).toFixed(1)+"%");
  el.style.setProperty("--hx", (100-x*100).toFixed(1)+"%"); el.style.setProperty("--hy", (100-y*100).toFixed(1)+"%");
  el.style.setProperty("--ha", (100+x*50).toFixed(0)+"deg");
  return [x, y];
}
// 鼠标在卡上移动时轻轻倾斜、带出一道光（触屏和「减少动态效果」时不做）
function tiltCard(el){
  if(!el || !matchMedia("(hover:hover) and (pointer:fine)").matches || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  el.addEventListener("pointermove", e => { const [x, y] = holoAt(el, e);
    el.style.setProperty("--ry", ((x-.5)*12).toFixed(2)+"deg"); el.style.setProperty("--rx", ((.5-y)*10).toFixed(2)+"deg"); el.style.setProperty("--shine", 1); });
  el.addEventListener("pointerleave", () => { ["--rx","--ry"].forEach(k => el.style.setProperty(k,"0deg")); el.style.setProperty("--shine", 0); });
}
function closeDrawer(){ const dr = $("#drawer"); dr.classList.remove("on"); dr.setAttribute("aria-hidden","true"); dr.innerHTML = ""; $("#scrim").classList.remove("on"); document.body.style.overflow = ""; document.body.classList.remove("card-open"); if(personChart){ personChart.dispose(); charts.splice(charts.indexOf(personChart),1); personChart = null; } lastFocus?.focus?.(); }
$("#scrim").onclick = closeDrawer;
addEventListener("keydown", e => { if(e.key==="Escape" && $("#drawer").classList.contains("on")) closeDrawer(); });

// ---------- 好感度：印象卡册 ----------
let peopleRows = [];
async function loadPeople(){
  try{ peopleRows = (await api("/api/people")).data; }catch(e){ return fail(e); }
  renderPeople();
  const top = peopleRows.filter(r => r.qq !== OWNER && hasImpr(r)).sort((a,b)=>(b.favor||0)-(a.favor||0))[0];
  pet?.say(top ? `除了主人，〈我〉最喜欢 ${top.name}～` : "还没有认识的人～");
}
function renderPeople(){
  const q = $("#psearch").value.trim(), sk = $("#psort").value, key = sk.replace("-",""), dir = sk.startsWith("-") ? 1 : -1;
  const known = peopleRows.filter(hasImpr), hidden = peopleRows.length - known.length;
  const rows = known.filter(r => !q || [r.name,r.qq,r.impression].some(x => String(x||"").includes(q)))
    .sort((a,b) => ((a[key]||0)-(b[key]||0)) * dir);
  $("#pcount").textContent = `${rows.length} 张` + (hidden ? `（另有 ${hidden} 人〈我〉还没印象，先不放进来）` : "");
  $("#pgrid").innerHTML = rows.map(r => { const [tc] = tierOf(r);
    return `<button class="mcard ${tc}" data-qq="${esc(r.qq)}" aria-label="${esc(r.name||r.qq)}，好感 ${r.favor??0}">
      <span class="mc-in"><span class="mc-art"><img src="https://q1.qlogo.cn/g?b=qq&nk=${esc(r.qq)}&s=160" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='/api/avatar/${esc(r.qq)}'">
        <span class="holo"></span>${r.mood?`<span class="mood-pill" data-mood="${esc(r.mood)}">${esc(r.mood)}</span>`:""}<span class="mc-fav">${r.favor ?? 0}</span></span>
      <span class="mc-body"><span class="mc-name">${esc(r.name||r.qq)}</span>${r.stage?`<span class="mc-stage">${esc(r.stage)}</span>`:""}
        <span class="mc-impr">${esc(r.impression || "还没有印象～")}</span>
        <span class="mc-foot"><span>熟悉 ${r.familiarity??0}　聊过 ${r.talks??0}</span><span>${ago(r.last_talk)}</span></span></span></span>
      <span class="holo frame"></span></button>`; }).join("") || meme("meh","没找到这个人～");
  $$("#pgrid .mcard").forEach(b => b.onclick = () => openPerson(b.dataset.qq));
}
$("#psearch").oninput = renderPeople;
$("#psort").onchange = renderPeople;
// 卡册里鼠标经过哪张，哪张的镭射跟着动
$("#pgrid").addEventListener("pointermove", e => { const c = e.target.closest(".mcard"); if(c) holoAt(c, e); });

// ---------- 开关 ----------
async function loadSettings(){
  let s; try{ s = (await api("/api/settings")).data; }catch(e){ return fail(e); }
  const tg = (plugin,key,val,title,desc) => `<div class="sw"><div>${title}<small>${desc}</small></div><label class="toggle"><input type="checkbox" data-p="${plugin}" data-k="${key}" ${val?"checked":""} aria-label="${esc(title)}"><span></span></label></div>`;
  const sel = (plugin,key,val,opts,title,desc) => `<div class="sw"><div>${title}<small>${desc}</small></div><select data-p="${plugin}" data-k="${key}" aria-label="${esc(title)}">${Object.entries(opts).map(([k,v])=>`<option value="${esc(k)}" ${k===val?"selected":""}>${esc(v)}</option>`).join("")}</select></div>`;
  let h = "";
  if(s.proactive){ h += tg("proactive","enabled",s.proactive.enabled,"主动找熟人聊天","只找聊过、好感够的 QQ 好友，每天最多 2 次");
    h += sel("proactive","mode",s.proactive.mode,{auto:"直接发",preview:"先给主人看"},"主动聊天的方式",`屏蔽了 ${s.proactive.blocked.length} 人（在人物详情里改）`); }
  if(s.qzone){ h += tg("qzone","enabled",s.qzone.enabled,"每天写说说","20:30–21:30 之间写一条");
    h += sel("qzone","mode",s.qzone.mode,{review:"先给主人审",auto:"直接发"},"说说发布方式",""); }
  if(s.comic){ h += tg("comic","enabled",s.comic.enabled,`每天 ${esc(s.comic.at||"22:00")} 画群漫画`,"总开关；下面每个群可以单独关");
    (s.comic.groups||[]).forEach(g => h += tg("comic","group:"+g.gid,g.on,`群漫画 · ${esc(g.name)}`,esc(g.gid)));
    h += tg("comic","auto_post",s.comic.auto_post,"群漫画画完直接发群","关掉就先私信主人预览"); }
  if(s.voice){ h += tg("voice","enabled",s.voice.enabled,"偶尔发语音",s.voice.configured?`模型 ${esc(s.voice.model||"")}`:"还没配置密钥");
    const vs = {...s.voice.voices}; if(s.voice.voice_id && !vs[s.voice.voice_id]) vs[s.voice.voice_id] = s.voice.voice_id;
    h += sel("voice","voice_id",s.voice.voice_id,vs,"语音音色","马上生效"); }
  if(s.bond) h += `<div class="sw"><div>好感度模式<small>record 只记录，active 会影响说话态度</small></div><b>${esc(s.bond.mode)}</b></div>`;
  if(s.social) h += `<div class="sw"><div>好友黑名单<small>${s.social.blacklist.map(esc).join("、")||"空的"}</small></div></div>`;
  $("#setBox").innerHTML = h;
  $$("#setBox [data-p]").forEach(el => el.onchange = () => setS(el.dataset.p, el.dataset.k, el.type==="checkbox" ? el.checked : el.value));
  pet?.say("想开关什么，拨一下就马上生效～");
}
async function setS(plugin,key,value){
  try{ await api("/api/settings",{plugin,key,value}); toast("已保存"); }catch(e){ toast("保存失败："+e.message, true); loadSettings(); }
}
async function drawComic(day){
  if(!confirm(`现在画${day==="yesterday"?"昨天":"今天"}的群漫画？大约几分钟，会花一次画图的钱`)) return;
  try{ toast((await api("/api/comic",{day})).msg); }catch(e){ toast(e.message, true); }
}
async function qzWrite(){
  const topic = prompt("说说主题（可以留空，让〈我〉自己想）","");
  if(topic===null) return;
  try{ const r = await api("/api/pending",{what:"qzone",action:"write",topic}); toast(r.msg||"写好了，在「待处理」里"); refreshPendCount(true); }catch(e){ toast(e.message, true); }
}
$("#doToday").onclick = () => drawComic("today");
$("#doYesterday").onclick = () => drawComic("yesterday");
$("#doQz").onclick = qzWrite;

// ---------- 待处理：机器人的信箱 ----------
const BOT = ME.bot_qq || "";
const ICON = i => `<svg class="ic" aria-hidden="true"><use href="#${i}"/></svg>`;
const smallEmpty = (k, text) => `<div class="small-empty">${memeImg(k)}${text}</div>`;
async function refreshPendCount(quiet){
  try{ const d = (await api("/api/pending", undefined, {quiet})).data; const n = (d.requests||[]).length + (d.qzone_draft?1:0) + (d.comic||[]).length;
    const b = $("#pendCount"); b.textContent = n || ""; b.hidden = !n; P.pending = n; return d; }catch{ return null; }
}
async function loadPending(){
  const d = await refreshPendCount(false); if(!d){ toast("读取失败", true); return; }
  const rq = d.requests||[], cm = d.comic||[], qd = d.qzone_draft, n = rq.length + (qd?1:0) + cm.length;
  const parts = [rq.length && `${rq.length} 封来信`, qd && "1 条说说草稿", cm.length && `${cm.length} 张群漫画`].filter(Boolean);
  $("#mailSub").textContent = n ? `有 ${parts.join("、")}等主人拍板～` : "信箱空空的，没有要主人拍板的事，〈我〉去吃饭了～";
  const st = (ic, num, label) => `<div class="pstamp${num?" hot":""}"><span>${ICON(ic)}<b>${num}</b>${label}</span></div>`;
  $("#stamps").innerHTML = st("i-bell", rq.length, "来信") + st("i-quill", qd?1:0, "说说") + st("i-brush", cm.length, "漫画");

  // 来信
  const letter = r => { const friend = r.type === "friend";
    const meta = friend
      ? (r.groups && r.groups.length ? `共同群：${r.groups.map(g=>`<span class="chip">${esc(g)}</span>`).join("")}` : `<span>不在〈我〉的群里</span>`)
      : `<span>邀请人：${esc(r.inviter_name||"")}（${esc(r.inviter||"")}）</span>`;
    return `<article class="letter">
      <div class="letter-top"><img src="/api/avatar/${esc(r.id)}" alt="" width="46" height="46" onerror="this.style.visibility='hidden'">
        <div class="who-l"><b>${esc(r.name||r.id)}</b><small>${friend?"QQ":"群号"} ${esc(r.id)}，${fmtT(r.ts)}</small></div>
        <div class="lstamp${friend?"":" grp"}"><span>${friend?"加好友":"拉进群"}</span></div></div>
      ${friend ? `<p class="letter-q${r.comment?"":" none"}">${esc(r.comment || "没写验证信息")}</p>` : ""}
      <div class="letter-meta">${meta}</div>
      <div class="acts"><button class="btn" data-req="${esc(r.key)}" data-a="同意">同意</button><button class="btn ghost" data-req="${esc(r.key)}" data-a="拒绝">拒绝</button>${friend?`<button class="btn danger" data-req="${esc(r.key)}" data-a="拉黑">拉黑</button>`:""}</div>
    </article>`; };
  let h = `<section class="page tape"><h2>来信</h2>${rq.length ? `<div class="letters">${rq.map(letter).join("")}</div>` : smallEmpty("full","没有人申请加好友或拉〈我〉进群～")}</section>`;

  // 说说草稿
  h += `<section class="page"><h2>说说草稿</h2>`;
  if(qd){ h += `<div class="qzpost"><div class="qz-who"><img src="/api/avatar/${BOT}" alt="" width="40" height="40"><div><b>${esc(ME.bot_name||"")}</b><small>草稿，写于 ${fmtT(qd.ts)}</small></div></div>
      <textarea id="qzText" aria-label="说说内容">${esc(qd.text)}</textarea><div class="qz-count" id="qzCount"></div></div>
      <div class="acts"><button class="btn" data-qz="publish">原样发布</button><button class="btn ghost" data-qz="edit">按改过的发布</button><button class="btn ghost" data-qz="rewrite">让〈我〉重写</button><button class="btn danger" data-qz="discard">不发</button></div>`; }
  else h += smallEmpty("rice", "没有草稿～想发说说就去「开关」里点「写」");
  if((d.qzone_posted||[]).length) h += `<h3>最近发过的</h3><ol class="posted-list">${d.qzone_posted.slice().reverse().slice(0,6).map(p=>`<li>${esc(p.text)}<small>${fmtT(p.ts)}</small></li>`).join("")}</ol>`;
  h += `</section>`;

  // 群漫画
  h += `<section class="page wide"><h2>群漫画预览</h2>${cm.length ? cm.map(c=>`<figure class="frame"><img src="${esc(c.image)}" alt="群漫画预览" loading="lazy">
      <figcaption>${esc(c.label||"")}「${esc(c.group)}」，${fmtT(c.ts)}</figcaption>
      <div class="acts"><button class="btn" data-cm="post" data-gid="${esc(c.gid)}">${ICON("i-brush")}发到群里</button><button class="btn danger" data-cm="discard" data-gid="${esc(c.gid)}">不发</button></div></figure>`).join("")
    : smallEmpty("great","没有等主人看的漫画～")}</section>`;
  $("#pendBox").innerHTML = h;
  const qt = $("#qzText"); if(qt){ const c = () => $("#qzCount").textContent = `${qt.value.length} 字`; qt.oninput = c; c(); }
  $$("#pendBox [data-req]").forEach(b => b.onclick = () => actReq(b.dataset.req, b.dataset.a));
  $$("#pendBox [data-qz]").forEach(b => b.onclick = () => qz(b.dataset.qz));
  $$("#pendBox [data-cm]").forEach(b => b.onclick = () => comicAct(b.dataset.cm, b.dataset.gid));
  if(n) pet?.mood("pending", `有 ${n} 件事等主人拍板～`); else pet?.say("没有要处理的，〈我〉去吃饭了～");
}
async function actReq(key, action){
  if(!confirm(`确定「${action}」？`)) return;
  try{ await api("/api/pending",{what:"request",key,action}); toast(`已${action}`); }catch(e){ toast(e.message, true); } loadPending();
}
async function qz(action){
  const labels = {publish:"原样发布到 QQ 空间",edit:"按改过的内容发布",rewrite:"丢掉这条，让〈我〉重写",discard:"丢掉这条"};
  if(!confirm(labels[action]+"？")) return;
  try{ const r = await api("/api/pending",{what:"qzone",action,text:$("#qzText")?.value}); toast(r.msg||"好了"); }catch(e){ toast(e.message, true); } loadPending();
}
async function comicAct(action,gid){
  if(!confirm(action==="post"?"把这张漫画发到群里？":"丢掉这张漫画？")) return;
  try{ const r = await api("/api/pending",{what:"comic",action,gid}); toast(r.msg||"好了"); }catch(e){ toast(e.message, true); } loadPending();
}

// ---------- 日志：机器人的值班日志 ----------
// 常见的几种警告翻成人话；认不出来的就只显示原文
function explainLog(msg){
  let m;
  if((m = msg.match(/retrying \((\d+)\/(\d+)\): (.+)$/i))) return `调用模型时${/connection/i.test(m[3]) ? "网断了一下" : "出了点错"}，已自动重试（第 ${m[1]}/${m[2]} 次）`;
  if((m = msg.match(/Temp dir exceeded limit.*Removed (\d+) files, released (\d+) bytes/i))) return `临时文件太多，自动清掉了 ${m[1]} 个旧文件（${Math.round(m[2]/1048576)} MB）`;
  if((m = msg.match(/Event loop lag detected: ([\d.]+)s/i))) return `〈我〉卡住了 ${Math.round(+m[1])} 秒没反应（服务器当时太忙）`;
  if(/timed? ?out|timeout/i.test(msg)) return "等太久，超时了";
  if(/rate.?limit|429/i.test(msg)) return "请求太频繁，被限流了";
  if(/connection (error|refused|reset)/i.test(msg)) return "网络连接出错";
  return null;
}
const SET_NAMES = {"proactive.enabled":"主动找熟人聊天","proactive.mode":"主动聊天的方式","qzone.enabled":"每天写说说","qzone.mode":"说说发布方式",
  "comic.enabled":"每天 22:00 画群漫画","comic.auto_post":"群漫画画完直接发群","voice.enabled":"偶尔发语音","voice.voice_id":"语音音色"};
const VAL_NAMES = {auto:"直接发",preview:"先给主人看",review:"先给主人审"};
// 面板操作记录翻成人话：[图标, 一句话]
function auditText(a){
  const b = a.body || {};
  if(a.path === "/api/settings"){
    if(b.plugin === "proactive" && (b.key === "block" || b.key === "unblock")) return ["i-switch", `${b.key==="block"?"不让":"重新允许"}〈我〉主动找 QQ ${esc(b.value)} 聊天`];
    const name = SET_NAMES[`${b.plugin}.${b.key}`] || `${b.plugin}.${b.key}`;
    return ["i-switch", b.value === true ? `打开了「${esc(name)}」` : b.value === false ? `关掉了「${esc(name)}」` : `把「${esc(name)}」改成「${esc(VAL_NAMES[b.value] || b.value)}」`];
  }
  if(a.path === "/api/report") return ["i-quill", "让〈我〉写了一份今日汇报"];
  if(a.path === "/api/comic") return ["i-brush", `让〈我〉画${b.day==="yesterday"?"昨天":"今天"}的群漫画`];
  if(a.path === "/api/pending"){
    if(b.what === "request") return ["i-bell", `${esc(b.action||"处理")}了一个好友申请或群邀请`];
    if(b.what === "qzone") return ["i-quill", ({write:`让〈我〉写一条说说草稿${b.topic?`（主题：${esc(b.topic)}）`:""}`, publish:"原样发布了说说", edit:"改过以后发布了说说", rewrite:"让〈我〉重写说说", discard:"丢掉了说说草稿"})[b.action] || "处理了说说草稿"];
    if(b.what === "comic") return ["i-brush", b.action === "post" ? "把群漫画发到了群里" : "丢掉了一张群漫画"];
  }
  return ["i-book", `${esc(a.path)} ${esc(JSON.stringify(b))}`];
}
async function loadLogs(){
  let d; try{ d = (await api("/api/logs")).data; }catch(e){ return fail(e); }
  const up = Date.now()/1000 - d.since, upS = up>86400 ? Math.floor(up/86400)+" 天" : up>3600 ? Math.floor(up/3600)+" 小时" : Math.max(1,Math.floor(up/60))+" 分钟";
  const errs = d.logs.filter(l => l.level !== "WARNING").length, warns = d.logs.length - errs;
  $("#logSince").textContent = `从 ${fmtT(d.since)} 这次醒来开始记，已经值班 ${upS}，${errs ? `出了 ${errs} 条错误` : "没出过错"}${warns ? `，有 ${warns} 条警告` : ""}～`;
  const hl = $("#health"); hl.className = "health" + (errs ? " bad" : warns ? " warn" : "");
  hl.innerHTML = errs ? `<b>有 ${errs} 条<br>错误</b><small>〈我〉有点慌</small>` : warns ? `${ICON("i-tail")}<b>小毛病</b><small>${warns} 条警告</small>` : `${ICON("i-tail")}<b>一切正常</b><small>〈我〉很健康</small>`;
  // 一样的消息合成一条，按最近一次排
  const groups = new Map();
  for(const l of d.logs){ const k = l.level + "|" + l.msg.replace(/\d+/g, "#");
    const g = groups.get(k) || {level:l.level, msg:l.msg, n:0, first:l.ts, last:l.ts}; g.n++; g.first = Math.min(g.first, l.ts); if(l.ts >= g.last){ g.last = l.ts; g.msg = l.msg; } groups.set(k, g); }
  const rows = [...groups.values()].sort((a,b) => b.last - a.last);
  $("#logBox").innerHTML = rows.length ? rows.map(g => { const bad = g.level !== "WARNING", ex = explainLog(g.msg);
    return `<div class="logrow${bad?" bad":""}"><span class="lv" aria-label="${bad?"错误":"警告"}">${bad?"×":"!"}</span>
      <p>${esc(ex || (bad ? "出了一个错误" : "有一条警告"))}</p>
      <div class="meta"><span>${bad?"错误":"警告"}</span>${g.n>1?`<span class="times">×${g.n} 次</span>`:""}<span>${g.n>1?`${fmtT(g.first)} 到 ${fmtT(g.last)}`:fmtT(g.last)}</span></div>
      <details${ex?"":" open"}><summary>原文</summary><code>${esc(g.msg)}</code></details></div>`; }).join("")
    : smallEmpty("great","启动以来没有警告和错误～");
  $("#audit").innerHTML = d.audit.map(a => { const [ic, t] = auditText(a);
    return `<li>${ICON(ic)}<p>${t}</p><small>${fmtT(a.ts)}，${a.who === "local" ? "本机" : esc(a.who)}</small></li>`; }).join("") || `<li><p class="muted">还没有人在面板上操作过～</p></li>`;
  if(errs) pet?.mood("error", `启动以来有 ${errs} 条错误，〈我〉有点慌～`);
  else if(d.logs.length) pet?.say(`有 ${d.logs.length} 条警告，不算大事～`);
  else pet?.mood("done", "没出错，〈我〉真棒～");
}
async function makeReport(){
  const b = $("#repBtn"); b.disabled = true; $("#report").textContent = "〈我〉在写，十几秒～"; pet?.mood("busy", "〈我〉在写汇报～");
  try{ $("#report").innerHTML = `<div class="report-text">${esc((await api("/api/report",{})).text)}</div>`; }
  catch(e){ $("#report").textContent = "没写成："+e.message; }
  b.disabled = false;
}
$("#repBtn").onclick = makeReport;

// ---------- 启动 ----------
async function ping(){ try{ const d = (await api("/api/overview", undefined, {quiet:true})).data; setOnline(d.online); }catch{ setOnline(false); } }
// #people/QQ 这样的链接直接翻开那个人的印象卡
const [first, firstQQ] = (location.hash||"").slice(1).split("/");
show(first in TABS ? first : "overview");
if(first in TABS && first !== "overview") ping();
if(/^\d{5,12}$/.test(firstQQ||"")) openPerson(firstQQ);
addEventListener("hashchange", () => { const t = location.hash.slice(1); if(t in TABS && !$("#sec-"+t).classList.contains("on")) show(t); });
setInterval(() => { if($("#sec-overview").classList.contains("on")) loadOverview(true); else ping(); }, 60000);
