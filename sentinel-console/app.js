/* Sentinel Control Center - isolated front-end. No broker secrets in browser. */
"use strict";
const byId=id=>document.getElementById(id);
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money=(n,currency="USD")=>(n!==null&&n!==undefined&&n!=="")&&Number.isFinite(Number(n))?new Intl.NumberFormat("en-US",{style:"currency",currency,maximumFractionDigits:2}).format(Number(n)):"—";
const num=(n,d=2)=>(n!==null&&n!==undefined&&n!=="")&&Number.isFinite(Number(n))?Number(n).toLocaleString("en-US",{maximumFractionDigits:d}):"—";
const percent=n=>Number.isFinite(Number(n))?(Number(n)*100).toFixed(2)+"%":"—";
const dateFmt=v=>v?new Date(v).toLocaleString("en-GB",{timeZone:"UTC",month:"short",day:"2-digit",hour:"2-digit",minute:"2-digit"}):"—";
const idName=s=>String(s||"").replace(/_/g," ").toUpperCase();
const STORE="sentinel-console-v1";
const nav=[
 ["live","مركز القيادة المباشر","◉","LIVE COMMAND CENTER"],
 ["overview","ملخص الحساب","◈","ACCOUNT OVERVIEW"],
 ["mt5","MT5 مجاني","⌁","FREE MT5"],
 ["sentinel_trader","بوت Sentinel","◉","INDEPENDENT DEMO TRADER"],
 ["trades","الصفقات والمراكز","⇄","TRADES"],
 ["signals","الإشارات والقرارات","◉","SIGNALS"],
 ["strategies","مكتبة الاستراتيجيات","▦","STRATEGIES"],
 ["backtest","مختبر الاختبارات","▤","BACKTEST LAB"],
 ["ai","العقل المتعلّم","✧","ADAPTIVE INTELLIGENCE"],
 ["risk","المخاطرة والإعدادات","⬡","RISK & CONFIG"],
 ["logs","مركز الأحداث","≡","EVENT CENTER"],
 ["settings","الربط والنظام","⚙","SYSTEM"]
];
const strategyList=[
 {id:"TREND_PULLBACK",name:"Trend Pullback",ar:"تداول التصحيحات مع اتجاه السوق باستخدام EMA وATR.",group:"TREND",score:65,tf:"M5 / M15"},
 {id:"BREAKOUT",name:"Range Breakout",ar:"الاختراق المؤكد لنطاق 20 شمعة مع حجم جسم وزخم.",group:"BREAKOUT",score:65,tf:"M5 / M15"},
 {id:"VOLATILITY_EXPANSION",name:"Volatility Expansion",ar:"التقاط حركة السوق بعد ضغط وتقلص نطاق التقلب.",group:"BREAKOUT",score:65,tf:"M5 / M15"},
 {id:"MEAN_REVERSION",name:"Mean Reversion",ar:"ارتداد الانحرافات الكبيرة باتجاه VWAP أو المتوسط.",group:"RANGE",score:65,tf:"M5 / M15"},
 {id:"RANGE_TRADING",name:"Range Trading",ar:"الشراء عند قاع النطاق والبيع من أعلاه.",group:"RANGE",score:65,tf:"M15"},
 {id:"MOMENTUM",name:"Momentum",ar:"اقتناص استمرار التسارع السعري والاتجاه القوي.",group:"TREND",score:65,tf:"M5 / M15"},
 {id:"MARKET_STRUCTURE",name:"Market Structure",ar:"BOS وCHOCH وكسر مستويات السوينغ المؤكدة.",group:"STRUCTURE",score:70,tf:"M5 / M15"},
 {id:"LIQUIDITY_SWEEP",name:"Liquidity Sweep",ar:"سحب السيولة وعودة السعر مع تأكيد الرفض.",group:"STRUCTURE",score:70,tf:"M5 / M15"},
 {id:"VWAP_ENGINE",name:"VWAP Engine",ar:"VWAP trend وpullback وmean reversion.",group:"RANGE",score:65,tf:"M5 / M15"},
 {id:"OPENING_RANGE_BREAKOUT",name:"Opening Range",ar:"اختراق نطاق افتتاح الجلسة مع تأكيد الزخم.",group:"SESSION",score:65,tf:"M5"},
 {id:"TREND_CONTINUATION",name:"Trend Continuation",ar:"اتجاه قوي ثم راحة قصيرة واختراق للاستمرار.",group:"TREND",score:65,tf:"M5 / M15"},
 {id:"REVERSAL",name:"Reversal",ar:"انعكاس هيكلي بعد exhaustion وliquidity sweep.",group:"STRUCTURE",score:70,tf:"M15"},
 {id:"ORDER_FLOW",name:"Order Flow Filter",ar:"تأكيد إضافي من tick acceleration وDOM عند توافره.",group:"FILTER",score:60,tf:"M5"}
];
const getSave=()=>{try{return JSON.parse(localStorage.getItem(STORE)||"{}")}catch(_){return {}}};
const saved=getSave();
const state={
 page:"live",preview:false,connected:false,key:"",
 remote:{},errors:{},strategyDraft:saved.strategyDraft||Object.fromEntries(strategyList.map(s=>[s.id,{enabled:s.id!=="ORDER_FLOW",score:s.score}])),
 riskDraft:saved.riskDraft||{risk:.5,maxDaily:3,maxPortfolio:2,minConfidence:65,tradeLimit:3},
 search:"",strategySearch:"",strategyGroup:"ALL",tradeFilter:"ALL",symbolFilter:"ALL",
 events:[],localBacktest:null,backendBacktest:null,csvBars:null,lastSync:null,loading:false
};
function save(){localStorage.setItem(STORE,JSON.stringify({preview:state.preview,strategyDraft:state.strategyDraft,riskDraft:state.riskDraft}))}
function toast(msg,type="info"){const item=document.createElement("div");item.className="toast "+type;item.textContent=msg;byId("toastRoot").prepend(item);setTimeout(()=>item.remove(),4800)}
function eventLog(type,message){state.events.unshift({type,message,time:new Date().toISOString()});state.events=state.events.slice(0,150)}
function mockSeries(){return Array.from({length:62},(_,i)=>({date:i,value:4960+Math.sin(i/5)*110+i*8.5+Math.sin(i*1.7)*23}))}
const sampleTrades=[
 {id:501,ticket:"SMP-501",symbol:"XAUUSD",direction:"long",status:"closed",lot_size:.08,entry_price:2671.80,exit_price:2676.31,pnl:36.08,ai_confidence:.82,strategy:"TREND_PULLBACK",opened_at:"2026-11-16T09:15:00Z"},
 {id:502,ticket:"SMP-502",symbol:"EURUSD",direction:"short",status:"closed",lot_size:.12,entry_price:1.08128,exit_price:1.07988,pnl:16.8,ai_confidence:.76,strategy:"BREAKOUT",opened_at:"2026-11-16T12:10:00Z"},
 {id:503,ticket:"SMP-503",symbol:"NAS100",direction:"long",status:"closed",lot_size:.06,entry_price:21521.4,exit_price:21492.1,pnl:-17.58,ai_confidence:.73,strategy:"MOMENTUM",opened_at:"2026-11-16T15:15:00Z"},
 {id:504,ticket:"SMP-504",symbol:"BTCUSD",direction:"long",status:"open",lot_size:.01,entry_price:95320, current_price:95611,stop_loss:94950,take_profit_1:95880,pnl:2.91,ai_confidence:.84,strategy:"LIQUIDITY_SWEEP",opened_at:"2026-11-17T10:05:00Z"},
 {id:505,ticket:"SMP-505",symbol:"XAUUSD",direction:"short",status:"closed",lot_size:.05,entry_price:2692.20,exit_price:2685.40,pnl:34.00,ai_confidence:.88,strategy:"MARKET_STRUCTURE",opened_at:"2026-11-17T13:15:00Z"}
];
const sampleSignals=[
 {id:200,symbol:"XAUUSD",direction:"long",ai_confidence:.84,session:"London",status:"executed",h1_bias:"bullish",m15_trend:"bullish",created_at:"2026-11-17T10:20:00Z"},
 {id:201,symbol:"EURUSD",direction:"short",ai_confidence:.68,session:"London",status:"rejected",rejection_reason:"Low momentum",created_at:"2026-11-17T11:45:00Z"},
 {id:202,symbol:"BTCUSD",direction:"long",ai_confidence:.79,session:"NY",status:"pending",created_at:"2026-11-17T14:35:00Z"}
];
const live=()=>state.connected&&!state.preview;
const canTrade=()=>live()&&["demo","paper"].includes(String(state.remote.config?.trading_mode||"").toLowerCase());
const trades=()=>state.preview?sampleTrades:((state.remote.trades?.trades||state.remote.trades?.recent||state.remote.trades?.items||[]));
const signals=()=>state.preview?sampleSignals:((state.remote.signals?.signals||state.remote.overview?.recent_signals||[]));
const backendState=()=>state.preview?"sample":(state.remote.status?.state||state.remote.overview?.bot?.state||"unknown");
const backendMode=()=>state.preview?"SAMPLE":String(state.remote.config?.trading_mode||state.remote.status?.trading_mode||"unverified").toUpperCase();

async function call(op,body=null){
 if(!state.key)throw Error("أدخل مفتاح لوحة التحكم أولاً");
 const method=body!==null?"POST":"GET";
 const response=await fetch("/api/gateway?op="+encodeURIComponent(op),{
  method,headers:{"x-console-key":state.key,"Content-Type":"application/json"},
  body:body!==null?JSON.stringify(body):undefined,cache:"no-store"
 });
 let d;
 try{d=await response.json()}catch(_){throw Error("استجابة غير صالحة من البوابة")};
 if(!response.ok||!d.ok)throw Error(d.error||d.data?.detail||"Gateway error");
 return d.data;
}
async function connect(){
 if(!state.key){openConnect();return}
 state.loading=true;renderHeader();renderPage();
 try{
  const health=await call("connection");
  if(!health||health.status!=="healthy")throw Error("Backend health not verified");
  state.connected=true;state.preview=false;save();
  eventLog("connected","تم الاتصال بواجهة API الخاصة بالبوت");
  await refresh(true);toast("تم الاتصال بالبوت والتحقق من واجهته","success");
 }catch(e){state.connected=false;state.preview=true;save();toast("الاتصال غير مكتمل: "+e.message,"error");}
 state.loading=false;render();
}
async function refresh(silent=false){
 if(!state.connected||state.preview){render();return}
 const ops=["status","config","overview","trades","signals","equity","risk","guards","model","registry","metrics"];
 const results=await Promise.allSettled(ops.map(op=>call(op)));
 let errors=0;
 results.forEach((r,i)=>{if(r.status==="fulfilled"){state.remote[ops[i]]=r.value;delete state.errors[ops[i]]}else{errors++;state.errors[ops[i]]=r.reason.message}});
 if(results[0].status!=="fulfilled"){state.connected=false;state.preview=true;save();if(!silent)toast("انقطع الاتصال؛ تم التحويل إلى وضع المعاينة","error")}
 else {state.lastSync=new Date().toISOString();if(!silent)toast(errors?"تم التحديث مع "+errors+" أخطاء جزئية":"تم التحديث بنجاح",errors?"error":"success")}
 render();
}
function renderNav(){byId("nav").innerHTML=nav.map(n=>'<button class="nav-item '+(state.page===n[0]?"active":"")+'" data-nav="'+n[0]+'"><span class="nav-icon">'+n[2]+'</span><span>'+n[1]+'</span></button>').join("")}
function renderHeader(){
 const n=nav.find(n=>n[0]===state.page);byId("breadcrumb").textContent=n?.[1]||"";
 const mt=window.FreeMT5UI?.summary()||{},ok=Boolean(mt.verified);
 const source=window.SentinelLive?.getSnapshot(),cloud=source?.health,
   cloudFresh=cloud?.trader==="FRESH",hasCloud=Boolean(source?.account?.last4);
 byId("modeBadge").className="mode-indicator"+((cloudFresh||ok)?" connected":"");
 byId("modeBadge").innerHTML='<span class="mode-dot"></span>'+
   (hasCloud?(cloudFresh?"FUSION MT5 DEMO / "+esc(source.account.last4):
     "MT5 DEMO / DATA STALE"):ok?"MT5 DEMO / VERIFIED":mt.configured?"MT5 / NOT VERIFIED":"CONNECTING");
 byId("connectorMini").innerHTML='<span class="socket '+((cloudFresh||ok)?"live":"")+
   '"></span><div><strong>MT5 / Demo</strong><small>'+
   (hasCloud?("Fusion •••• "+esc(source.account.last4)):ok?"Broker connected":"ربط الحساب")+
   '</small></div><span class="mini-chevron">↗</span>';
 byId("footStatus").textContent=hasCloud?("FUSION DEMO / "+(cloudFresh?"RECENT DATA":"STALE DATA")):
   ok?"BROKER DEMO / VERIFIED":"SENTINEL / WAITING FOR SOURCE";
 byId("footTimestamp").textContent=source?.trader_at?
   "Last cloud scan "+dateFmt(source.trader_at)+" UTC":
   mt.lastSync?"Last check "+dateFmt(mt.lastSync)+" UTC":"Awaiting provider connection";
}
function render(){renderNav();renderHeader();renderPage()}
function heading(k,title,description,actions=""){return '<div class="page-heading"><div><div class="eyebrow">'+k+'</div><h1>'+title+'</h1><p>'+description+'</p></div><div class="head-buttons">'+actions+'</div></div>'}
function button(label,action,klass="",disabled=false){return '<button class="btn '+klass+'" data-action="'+action+'" '+(disabled?"disabled":"")+'>'+label+'</button>'}
function statusNotice(){
 const c=window.FreeMT5UI?.summary()||{};
 if(c.verified)return '<div class="notice success"><strong>MT5 Demo متصل</strong><span class="notice-small">الحساب مؤكد عبر مزود الاتصال.</span></div>';
 if(c.configured)return '<div class="notice info"><strong>TickerAll متصل</strong><span class="notice-small">اكمل ربط حساب MT5 Demo.</span>'+button("إدارة الحساب","nav-mt5","btn-sm")+'</div>';
 return '<div class="notice info"><strong>Sentinel جاهز</strong><span class="notice-small">اربط حساب MT5 Demo لمتابعة البيانات الحقيقية.</span>'+button("ربط MT5","nav-mt5","btn-sm btn-primary")+'</div>';
}
function kpi(label,value,sub,color="#7ca1f5",cls=""){return '<article class="kpi" style="--color:'+color+'"><div class="kpi-caption">'+label+'<span class="kpi-icon">◈</span></div><div class="kpi-value '+cls+'">'+value+'</div><div class="kpi-delta">'+sub+'</div></article>'}
function simpleChart(series,locked=false){
 if(!series.length)return '<div class="empty-state"><div class="empty-icon">⌁</div><strong>لا توجد بيانات Equity موثقة</strong><span>تظهر هنا حركة الحساب عند ربط API فعلي وتوافر سجلات صفقات.</span></div>';
 const vals=series.map(p=>Number(p.value??p.equity)).filter(Number.isFinite);
 if(vals.length<2)return '<div class="empty-state">No plotable points</div>';
 const lo=Math.min(...vals),hi=Math.max(...vals),span=Math.max(hi-lo,1);
 const pts=vals.map((v,i)=>[(i/(vals.length-1))*680,210-((v-lo)/span)*175]);
 const line=pts.map(p=>p.join(",")).join(" ");
 const area="0,215 "+line+" 680,215";
 return '<div class="chart-area"><svg viewBox="0 0 720 240" role="img" aria-label="Equity curve"><defs><linearGradient id="chartGrad" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#45e1bb" stop-opacity=".26"/><stop offset="100%" stop-color="#45e1bb" stop-opacity="0"/></linearGradient></defs><g transform="translate(15,7)">'+[35,95,155,215].map(y=>'<line x1="0" x2="690" y1="'+y+'" y2="'+y+'" stroke="#2b3a48" stroke-dasharray="3 7" stroke-width=".7"/>').join("")+'<polygon points="'+area+'" fill="url(#chartGrad)"/><polyline points="'+line+'" stroke="#5ce4bd" stroke-width="2.5" fill="none" stroke-linejoin="round" stroke-linecap="round"/><circle cx="'+pts[pts.length-1][0]+'" cy="'+pts[pts.length-1][1]+'" r="4.5" fill="#5ce4bd" stroke="#193f38" stroke-width="5"/></g></svg>'+(locked?'<div class="chart-note"><span>SAMPLE CHART — NOT LIVE MT5</span></div>':"")+'</div>';
}
function tradeTable(rows){
 if(!rows.length)return empty("لا توجد صفقات","ستظهر الصفقات بعد الربط وتسجيل عمليات التنفيذ.");
 return '<div class="table-wrap"><table class="table"><thead><tr><th>الرمز</th><th>النوع</th><th>الحالة</th><th>الحجم</th><th>Entry</th><th>الاستراتيجية</th><th>الربح والخسارة</th><th>الوقت UTC</th></tr></thead><tbody>'+rows.map(t=>'<tr><td class="mono">'+esc(t.symbol)+'</td><td><span class="direction '+(String(t.direction||"").toLowerCase().includes("long")?"long":"short")+'">'+esc(idName(t.direction))+'</span></td><td><span class="tag">'+esc(t.status)+'</span></td><td class="mono">'+num(t.lot_size,3)+'</td><td class="mono">'+num(t.entry_price,5)+'</td><td class="mono">'+esc(t.strategy||"—")+'</td><td class="mono '+(Number(t.pnl||0)>=0?"pos":"neg")+'">'+money(t.pnl)+'</td><td class="mono">'+dateFmt(t.opened_at)+'</td></tr>').join("")+'</tbody></table></div>';
}
function empty(title,desc){return '<div class="empty-state"><div class="empty-icon">⌁</div><strong>'+title+'</strong><span>'+desc+'</span></div>'}
function panel(title,sub,content,actions=""){return '<section class="panel"><div class="panel-title"><div><h3>'+title+'</h3>'+(sub?'<p>'+sub+'</p>':"")+'</div><div class="panel-head-actions">'+actions+'</div></div>'+content+'</section>'}
function mockSignalMarkup(items){return items.length?items.map(s=>'<div class="feed-item"><div class="feed-line"></div><div class="feed-body"><div class="action-strip"><strong><span class="mono">'+esc(s.symbol)+'</span> · '+esc(s.direction||"neutral")+'</strong><span class="tag '+(String(s.status)==="executed"?"mint":"")+'">'+esc(s.status||"pending")+'</span></div><p>'+esc(s.rejection_reason||("AI confidence "+percent(s.ai_confidence)+" • "+(s.session||"—")) )+'</p><time>'+dateFmt(s.created_at)+'</time></div></div>').join(""):empty("لا إشارات","ستظهر أحدث إشارات البوت مع أسباب الرفض والتنفيذ.")}
function parseEquity(){if(state.preview)return mockSeries();let v=state.remote.equity?.curve||state.remote.equity?.equity_curve||[];return Array.isArray(v)?v.map((p,i)=>({date:p.date||p.time||i,value:p.equity??p.balance??p.value})).filter(p=>Number.isFinite(Number(p.value))):[]}
function overview(){
 const mt=window.FreeMT5UI?.summary()||{},ok=Boolean(mt.verified);
 let html=heading("SENTINEL / OPERATIONS","مركز التحكم","حالة الحساب المباشرة وأدوات متابعة النظام.",
 button("↻ تحديث","free-status","btn-sm")+button("⌁ إدارة MT5","nav-mt5","btn-primary btn-sm"));
 html+=statusNotice();
 if(!mt.configured)html+='<div class="connect-hero"><div class="hero-kicker"><span class="live-spark"></span> CONNECTION READY</div><h2>جاهز لربط أول حساب تداول</h2><p>ربط سحابي مجاني لحساب MT5 Demo، بدون Windows أو MetaApi.</p><div class="connect-actions">'+button("ربط حساب MT5","nav-mt5","btn-primary")+'</div></div>';
 html+='<div class="grid kpi-grid">'+
  kpi("الرصيد",ok&&mt.financialsReady&&mt.balance!=null?money(mt.balance,mt.currency||"USD"):"—","BROKER BALANCE","#46e3bb")+
  kpi("Equity",ok&&mt.financialsReady&&mt.equity!=null?money(mt.equity,mt.currency||"USD"):"—","VERIFIED EQUITY","#799dff")+
  kpi("مراكز مفتوحة",ok&&mt.financialsReady?num(mt.positions.length,0):"—","MT5 POSITIONS","#ab8cff")+
  kpi("حالة الاتصال",ok?"CONNECTED":mt.configured?"PENDING":"OFFLINE","CLOUD BRIDGE",ok?"#46e3bb":"#ffca80")+'</div>';
 const positions=ok?mt.positions:[];
 const positionTable=positions.length?'<div class="table-wrap"><table class="table"><thead><tr><th>الرمز</th><th>الاتجاه</th><th>الحجم</th><th>P&L</th></tr></thead><tbody>'+
  positions.map(p=>'<tr><td class="mono">'+esc(p.symbol)+'</td><td>'+esc(p.side)+'</td><td class="mono">'+num(p.volume,3)+'</td><td class="mono">'+(p.profit==null?"—":money(p.profit,mt.currency||"USD"))+'</td></tr>').join("")+'</tbody></table></div>':
  empty(mt.financialsReady?"لا توجد مراكز مفتوحة":"بيانات المراكز قيد التحديث","المراكز الفعلية تظهر فور وصول بيانات الوسيط.");
 html+='<div class="content-grid">'+panel("مراكز MT5","BROKER POSITIONS / READ ONLY",positionTable,button("فتح MT5","nav-mt5","btn-sm btn-quiet"))+
 panel("حالة النظام","LIVE INFRASTRUCTURE",'<div class="panel-pad">'+[
  ["TickerAll API",mt.configured?"CONFIGURED":"NOT CONNECTED"],
  ["MT5 Demo",ok?"ONLINE":"NOT CONNECTED"],
  ["Trading engine",window.SentinelLive?.getSnapshot()?.health?.trade_status||"UNVERIFIED"],
  ["Auto execution",window.SentinelLive?.getSnapshot()?.authorization?.enabled===true?"DEMO TRIAL":"NOT ARMED"],
  ["Account type","DEMO ONLY"]
 ].map(x=>'<div class="key-value"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join("")+'</div>')+'</div>';
 html+=panel("منحنى رأس المال","بانتظار سجل حقيقي للقيم الزمنية",empty("لا يوجد سجل Equity تاريخي بعد","ما منعرض رسوم أو أرقام صناعية."));
 return html;
}
function tradesView(){
 const mt=window.FreeMT5UI?.summary()||{},positions=mt.verified?mt.positions||[]:[];
 const rows=positions.length?'<div class="table-wrap"><table class="table"><thead><tr><th>الرمز</th><th>الاتجاه</th><th>الحجم</th><th>P&L</th></tr></thead><tbody>'+
 positions.map(p=>'<tr><td class="mono">'+esc(p.symbol)+'</td><td><span class="direction '+(p.side==="BUY"?"long":"short")+'">'+esc(p.side||"—")+'</span></td><td class="mono">'+num(p.volume,3)+'</td><td class="mono '+(p.profit>=0?"pos":"neg")+'">'+(p.profit==null?"—":money(p.profit,mt.currency||"USD"))+'</td></tr>').join("")+'</tbody></table></div>':
 empty("لا توجد صفقات مفتوحة موثقة","يظهر سجل الحساب الفعلي بعد ربط MT5 Demo والتحقق من الاتصال.");
 return heading("TRADING DESK / 02","الصفقات والمراكز","عرض مباشر لحساب MT5 Demo دون بيانات تجريبية.",
 button("↻ تحديث","free-status","btn-sm")+button("إدارة الحساب","nav-mt5","btn-primary btn-sm"))+
 statusNotice()+panel("المراكز المفتوحة","FROM CONNECTED MT5 DEMO",rows)+
 '<div class="info-block" style="margin-top:15px">يمكن عرض سجل الصفقات المغلقة من صفحة MT5 بعد الربط. فتح وإغلاق الصفقات آلياً يتطلب تشغيل محرك الاستراتيجيات بشكل مستقل.</div>';
}
function signalsView(){
 return heading("INTELLIGENCE / 03","الإشارات والقرارات","تظهر الإشارات عندما يتم تشغيل محرك التداول وربطه بالواجهة.",
 button("إدارة MT5","nav-mt5","btn-sm"))+statusNotice()+
 panel("تغذية الإشارات","NO SYNTHETIC SIGNALS",empty("المحرك غير متصل","لن نعرض إشارات مصطنعة أو قرارات مزعومة قبل ربط مصدر فعلي."));
}
function strategiesView(){
 const all=strategyList.filter(s=>(state.strategyGroup==="ALL"||s.group===state.strategyGroup)&&(!state.strategySearch||s.id.toLowerCase().includes(state.strategySearch.toLowerCase())||s.ar.includes(state.strategySearch)));
 const active=strategyList.filter(s=>state.strategyDraft[s.id]?.enabled).length;
 return heading("STRATEGY WORKSPACE / 04","مكتبة الاستراتيجيات","تحرير مسودة مستقلة لـ13 محركاً — لا تؤثر على البوت حتى يدعم API إعدادات الاستراتيجيات.",button("↓ تصدير ملف الاستراتيجيات","export-strategies","btn-sm btn-primary"))+statusNotice()+
 '<div class="notice info"><strong>Draft Mode</strong><span class="notice-small">التفعيل والـScore هنا يحفظان محلياً كملف إعدادات، وليس تغييراً على استراتيجيات الإنتاج. البوت الحالي يستخدم SMC في كوده.</span></div>'+
 '<div class="filterbar"><input class="input short" id="strategySearch" placeholder="ابحث عن استراتيجية" value="'+esc(state.strategySearch)+'"><select class="input select short" id="strategyGroup">'+["ALL","TREND","RANGE","BREAKOUT","STRUCTURE","SESSION","FILTER"].map(g=>'<option '+(state.strategyGroup===g?"selected":"")+'>'+g+'</option>').join("")+'</select><span class="tag mint">'+active+' / '+strategyList.length+' ENABLED IN DRAFT</span></div>'+
 '<div class="grid strat-grid">'+all.map(s=>{let x=state.strategyDraft[s.id]||{enabled:false,score:s.score};return '<article class="strat '+(!x.enabled?"strat-off":"")+'"><div class="strat-top"><span class="strat-code">'+s.id+'</span><button class="switch '+(x.enabled?"on":"")+'" data-toggle-strategy="'+s.id+'" title="تبديل التفعيل في المسودة فقط" aria-label="تفعيل/إيقاف '+s.id+'"></button></div><h3>'+s.name+'</h3><p>'+s.ar+'</p><div class="strat-params"><span class="pill">'+s.tf+'</span><span class="pill">'+s.group+'</span><span class="pill">SCORE ≥ '+x.score+'</span></div><div class="strat-bottom"><span class="small subtle">MIN SCORE / '+x.score+'</span><button class="btn btn-sm" data-edit-strategy="'+s.id+'">تعديل ↗</button></div></article>'}).join("")+'</div>';
}
function backtestView(){
 const r=state.localBacktest;
 let content=heading("RESEARCH ENGINE / 05","مختبر الـBacktest","اختبر CSV محلياً أو نفّذ اختبار backend الصناعي مع تحذير واضح.",button("↓ تحميل نموذج CSV","sample-csv","btn-sm"))+statusNotice();
 content+='<div class="content-grid">'+panel("اختبار على بيانات CSV حقيقية","EMA 20/50 crossover + ATR 14 stop + 2R target; اختبار مبسط بحثي",'<div class="panel-pad"><div class="field"><label>ملف OHLCV بترويسة time,open,high,low,close</label><input class="input" type="file" accept=".csv,text/csv" id="csvInput"></div><div class="form-grid" style="margin-top:15px"><div class="field"><label>Spread كنسبة من السعر (%)</label><input class="input mono" type="number" id="csvSpread" value="0.02" min="0" max="5" step="0.01"></div><div class="field"><label>بداية الحساب ($)</label><input class="input mono" type="number" id="csvBalance" value="5000" min="100"></div></div><div class="action-strip" style="margin-top:17px"><span class="small subtle" id="csvMeta">'+(state.csvBars?state.csvBars.length+" bars loaded":"No CSV loaded")+'</span>'+button("▶ تشغيل الاختبار المحلي","run-csv","btn-sm btn-primary",!state.csvBars)+'</div></div>')+
 panel("الاختبار عبر API","المحرك الحالي يولّد أسعاراً صناعية؛ ليس اختبار سوق تاريخي",'<div class="panel-pad"><div class="notice" style="margin:0 0 15px"><span>⚠</span><div>نتائج هذا الاختبار <strong>SYNTHETIC ONLY</strong> ولا تصلح لتقييم الربحية الحقيقية.</div></div><div class="field"><label>Symbol</label><select id="remoteBacktestSymbol" class="input select"><option>XAUUSD</option><option>EURUSD</option><option>BTCUSDT</option><option>NAS100</option></select></div><div class="field" style="margin-top:12px"><label>M5 Bars</label><select id="remoteBars" class="input select"><option>1000</option><option selected>2000</option><option>5000</option></select></div><div style="margin-top:16px">'+button("▶ تشغيل اختبار صناعي","run-backend-backtest","btn-sm",!canTrade())+'</div></div>')+'</div>';
 if(r){content+='<div class="grid kpi-grid">'+kpi("عدد الصفقات",num(r.trades,0),"LOCAL CSV TEST","#799dff")+kpi("نتيجة الاختبار",money(r.pnl),"SIMULATED RETURNS",r.pnl>=0?"#4ce3bd":"#ff748f")+kpi("Win rate",percent(r.winRate),"CLOSED TRADES","#ab8cff")+kpi("Max drawdown",percent(r.maxDD),"INTRA-TEST DRAWDOWN","#ffca80")+'</div>'+panel("نتائج الاختبار المحلي","تجاهل تأثير السيولة والفجوات ورسوم الوسيط — بحث أولي فقط",simpleChart(r.curve)+ '<div class="chart-foot">CSV INPUT / '+r.bars+' CANDLES <span>EMA 20/50 • ATR STOP • 2R TARGET</span></div>')}
 if(state.backendBacktest){const b=state.backendBacktest;content+=panel("Synthetic Backtest Result","NOT HISTORICAL / RANDOM GENERATED PRICE DATA",'<div class="panel-pad"><pre class="code-block">'+esc(JSON.stringify(b.metrics||b,null,2).slice(0,5000))+'</pre></div>')}
 return content;
}
function aiView(){
 const m=state.remote.model||{},reg=state.remote.registry||{};
 return heading("AI SYSTEMS / 06","الذكاء الاصطناعي والتدريب","مراقبة النماذج وإطلاق التدريب على سجلات صفقات البوت فقط.",button("↻ تحديث","refresh","btn-sm"))+statusNotice()+
 '<div class="content-grid">'+panel("حالة نموذج الذكاء","MODEL REGISTRY / CONNECTED API",'<div class="panel-pad">'+[
 ["Active model",state.preview?"SAMPLE UI":reg.active_version||m.active_model_version||"NOT LOADED"],
 ["Loaded versions",state.preview?"—":m.loaded_versions],
 ["Last training",state.preview?"—":m.last_training?.status],
 ["Training completed",state.preview?"—":dateFmt(m.last_training?.completed_at)]
 ].map(x=>'<div class="key-value"><span>'+x[0]+'</span><strong>'+esc(x[1]??"—")+'</strong></div>').join("")+'</div>')+
 panel("تدريب نموذج جديد","Source: real recorded trades • synthetic_samples = 0",'<div class="panel-pad"><div class="field"><label>آخر عدد أيام من بيانات التداول</label><select class="input select" id="trainDays"><option>90</option><option selected>180</option><option>365</option></select></div><div class="field" style="margin-top:13px"><label>Random Forest trees</label><select class="input select" id="trainTrees"><option selected>200</option><option>300</option><option>500</option></select></div><div class="info-block" style="margin:15px 0">لا نستخدم التدريب الصناعي بشكل صامت. لن يُرسل الطلب إلا بوجود اتصال وتجهيز في الـAPI.</div>'+button("✧ تدريب على السجلات الحقيقية","train-model","btn-primary",!canTrade())+'</div>')+'</div>'+
 panel("المراقبة الذكية","نتيجة أحدث جلسة تدريب مسجلة",m.last_training?.report?'<div class="panel-pad"><pre class="code-block">'+esc(JSON.stringify(m.last_training.report,null,2).slice(0,4500))+'</pre></div>':empty("لا يوجد تقرير معتمد","النتائج تظهر بعد اكتمال التدريب الفعلي من قاعدة البيانات."))+
 '<div class="info-block" style="margin-top:15px"><strong>Champion / Challenger</strong>واجهة البرمجة الحالية توفر Train / Reload / Registry، لكنها لا توفر طبقة ترقية Champion مستقلة. لن نعرض زراً يرقّي نموذجاً مباشرة دون تحقق.</div>';
}
function riskView(){
 const r=state.riskDraft;
 return heading("RISK ENGINE / 07","إدارة المخاطر","لوحة إعدادات عملية — تعديلات محلية فقط حتى تتوفر واجهة API لتعديل إعدادات المحرك.",button("↓ تصدير إعدادات المخاطرة","export-risk","btn-primary btn-sm"))+statusNotice()+
 '<div class="content-grid">'+panel("Risk Parameters · Draft","لا تعدّل معاملات حساب تداول قائم",'<div class="panel-pad form-grid">'+[
 ["risk","Risk per trade (%)","0.1","2","0.05"],["maxDaily","Daily loss limit (%)","1","10","0.5"],
 ["maxPortfolio","Portfolio exposure (%)",".5","10",".5"],["minConfidence","Signal confidence threshold","50","95","1"],
 ["tradeLimit","Max concurrent trades","1","10","1"]
 ].map(x=>'<div class="field"><label>'+x[1]+'</label><input class="input mono" type="number" data-risk="'+x[0]+'" min="'+x[2]+'" max="'+x[3]+'" step="'+x[4]+'" value="'+esc(r[x[0]])+'"></div>').join("")+'</div><div class="panel-pad" style="padding-top:0"><div class="info-block"><strong>Draft only</strong>القيم تُحفظ في هذا المتصفح ويمكن تصديرها JSON. لا يتم استدعاء Endpoint تعديل إعدادات غير موجود.</div></div>')+
 panel("حالة المخاطرة عند البوت","LIVE CONFIG • READ ONLY",'<div class="panel-pad">'+[
 ["Trading mode",backendMode()],["Risk/trade",state.preview?"—":percent(state.remote.config?.risk_management?.risk_per_trade)],
 ["Max drawdown",state.preview?"—":percent(state.remote.config?.risk_management?.max_drawdown)],
 ["Trades per session",state.preview?"—":state.remote.config?.risk_management?.max_trades_per_session||"—"],
 ["Min confidence",state.preview?"—":percent(state.remote.config?.ai?.min_confidence)]
 ].map(x=>'<div class="key-value"><span>'+x[0]+'</span><strong>'+esc(x[1])+'</strong></div>').join("")+'</div>')+'</div>';
}
function logsView(){
 const ev=state.events;
 return heading("AUDIT TRAIL / 08","مركز الأحداث والسجلات","سجل عمليات لوحة التحكم المحلية ونتائج API. ليس بديلاً عن MT5 Journal.",button("↓ Export Logs","export-logs","btn-sm"))+statusNotice()+
 panel("System Event Stream","SESSION EVENTS / THIS BROWSER ONLY",ev.length?'<div class="list-feed">'+ev.map(e=>'<div class="feed-item"><div class="feed-line"></div><div class="feed-body"><strong>'+esc(e.type).toUpperCase()+'</strong><p>'+esc(e.message)+'</p><time>'+dateFmt(e.time)+'</time></div></div>').join("")+'</div>':empty("ليس هناك أحداث","ابدأ الاتصال أو استخدم أدوات البحث حتى يتم تسجيل الأحداث."))+
 '<div class="notice info" style="margin-top:17px"><strong>Logs Scope</strong><span>سجل MetaApi موجود في قسم MT5 Cloud Bridge؛ سجل تنفيذ محرك التداول يحتاج خدمة تشغيل مستقلة.</span></div>';
}
function settingsView(){
 const c=window.FreeMT5UI?.summary()||{};
 return heading("SYSTEM / 09","إعدادات النظام","حالة Sentinel ومصادر البيانات.",button("ربط MT5","nav-mt5","btn-primary btn-sm"))+
 '<div class="content-grid">'+
 panel("حالة الخدمات","ACTUAL STATUS",'<div class="panel-pad">'+[
  ["Dashboard access","VERCEL SSO"],
  ["TickerAll API",c.configured?"READY":"NOT CONNECTED"],
  ["MT5 Demo",c.verified?"VERIFIED":"NOT VERIFIED"],
  ["Strategy worker",window.SentinelLive?.getSnapshot()?.health?.research_status||"UNVERIFIED"],
  ["Auto execution",window.SentinelLive?.getSnapshot()?.authorization?.enabled===true?"DEMO TRIAL":"NOT ARMED"]
 ].map(x=>'<div class="key-value"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join("")+'</div>')+
 panel("الأدوات","LOCAL RESEARCH ONLY",'<div class="panel-pad">'+
 '<p class="subtle">إعدادات الاستراتيجيات والمخاطر ما زالت مسودات محلية، بدون تأثير على محرك التداول.</p>'+
 button("الاستراتيجيات","nav-strategies","btn-sm")+
 button("المخاطر","nav-risk","btn-sm")+
 button("Backtest","nav-backtest","btn-sm")+'</div>')+'</div>';
}
function mt5View(){return window.FreeMT5UI?.render()||heading("FREE MT5","الربط المجاني","جاري تحميل MT5 Bridge...")}
function renderPage(){
 let h="";
 try{switch(state.page){
 case"live":h=window.SentinelLive?.render()||heading("LIVE COMMAND","مركز القيادة المباشر","جارٍ تحميل بيانات Neon");break;
 case"overview":h=overview();break;case"mt5":h=mt5View();break;case"trades":h=tradesView();break;case"signals":h=signalsView();break;
 case"strategies":h=strategiesView();break;case"backtest":h=backtestView();break;case"ai":h=window.SentinelBrain?.render()||aiView();break;case"sentinel_trader":h=window.SentinelTrader?.render()||heading("SENTINEL TRADER","بوت Sentinel المستقل","لم يتم تحميل الوحدة");break;
 case"risk":h=riskView();break;case"logs":h=logsView();break;case"settings":h=settingsView();break;
 default:h=overview();}}catch(e){h=heading("DISPLAY ERROR","تعذّر عرض الصفحة",esc(e.message));eventLog("render-error",e.message)}
 byId("page").innerHTML=h;
}
function navigate(page){state.page=page;if(page==="live")void window.SentinelLive?.refresh();if(page==="mt5")window.FreeMT5UI?.sync(true);if(page==="sentinel_trader")void window.SentinelTrader?.refresh();if(page==="ai")void (async()=>{await window.SentinelBrain?.refresh(true);await window.SentinelBrain?.symbols(true);await window.SentinelBrain?.maybeAutoSync?.()})();state.search="";byId("sidebar").classList.remove("open");render();document.querySelector(".scroll-area").scrollTop=0}
function showModal(title,content,footer="",wide=false){byId("modalRoot").innerHTML='<div class="modal-overlay" data-close-modal><div class="modal '+(wide?"wide":"")+'" role="dialog" aria-modal="true"><div class="modal-head"><strong>'+title+'</strong><button class="modal-x" data-action="close-modal" aria-label="إغلاق">×</button></div><div class="modal-content">'+content+'</div>'+(footer?'<div class="modal-footer">'+footer+'</div>':"")+'</div></div>'}
function closeModal(){byId("modalRoot").innerHTML=""}
function openConnect(){navigate("mt5");}

function editStrategy(id){
 const s=strategyList.find(x=>x.id===id);if(!s)return;const d=state.strategyDraft[id]||{score:s.score,enabled:true};
 showModal("ضبط "+s.name,'<p class="subtle">'+s.ar+'</p><div class="field"><label>الحد الأدنى للـScore</label><input type="range" id="strategyScoreSlider" min="50" max="95" step="1" style="accent-color:#50e1bb;width:100%" value="'+d.score+'"><div class="mono" id="sliderValue" style="text-align:center;font-size:23px;color:var(--mint)">'+d.score+'</div></div><div class="info-block" style="margin-top:13px">هذا الإعداد للمسودة فقط؛ لا يؤثر على التنفيذ الفعلي.</div>',
 button("إلغاء","close-modal","btn-sm")+button("حفظ المسودة","save-strategy","btn-primary btn-sm"));byId("modalRoot").dataset.edit=id;
 byId("strategyScoreSlider").addEventListener("input",e=>byId("sliderValue").textContent=e.target.value);
}
async function runCommand(cmd){
 if(!canTrade()){toast("تحتاج اتصالاً موثقاً مع بوت DEMO/PAPER","error");return}
 const labels={start:"تشغيل",stop:"إيقاف",pause:"إيقاف مؤقت",resume:"استئناف"};
 if(!confirm("هل تؤكد "+labels[cmd]+" بوت "+backendMode()+"؟ قد يؤثر الأمر على الصفقات الموجودة."))return;
 try{const r=await call(cmd,{});eventLog("command",cmd+" "+JSON.stringify(r).slice(0,130));toast("تم قبول الأمر من API: "+labels[cmd],"success");setTimeout(()=>refresh(true),650)}
 catch(e){eventLog("command-error",cmd+" "+e.message);toast(e.message,"error")}
}
function fileDownload(name,content,type="application/json"){
 const blob=new Blob([content],{type:type+";charset=utf-8"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2500);
}
function exportConfig(part){let data=part==="strategies"?{version:"sentinel-draft-v1",mode:"DRAFT_NOT_APPLIED",strategies:state.strategyDraft}:{version:"sentinel-draft-v1",mode:"DRAFT_NOT_APPLIED",risk:state.riskDraft};fileDownload("sentinel-"+part+"-draft.json",JSON.stringify(data,null,2));toast("تم تصدير المسودة","success")}
function parseCSV(text){
 const lines=text.trim().split(/\r?\n/).filter(Boolean);if(lines.length<110)throw Error("يلزم 110 شموع أو أكثر");
 const sep=lines[0].includes(";")?";":",";
 const fields=lines[0].toLowerCase().replace(/[<>"']/g,"").split(sep).map(s=>s.trim());
 const idx=["open","high","low","close"].map(k=>fields.indexOf(k));
 if(idx.some(i=>i<0))throw Error("الملف يجب أن يحتوي open,high,low,close");
 const bars=[];for(let i=1;i<lines.length&&bars.length<100000;i++){let parts=lines[i].split(sep);let [o,h,l,c]=idx.map(j=>Number(parts[j]));if([o,h,l,c].every(Number.isFinite)&&l<=Math.min(o,c)&&h>=Math.max(o,c)&&l>0)bars.push({o,h,l,c,time:parts[0]})}
 if(bars.length<110)throw Error("بيانات صالحة غير كافية");return bars;
}
function localBacktest(bars,balance,spreadPct){
 // Research-only close-to-next-open EMA crossover, stop/TP checked on subsequent bars.
 let cash=balance,peak=balance,maxDD=0,position=null,trades=0,wins=0,curve=[{date:0,equity:cash}];
 let ema20=bars[0].c,ema50=bars[0].c,atr=bars[0].h-bars[0].l,prevE20=ema20,prevE50=ema50;
 let prevClose=bars[0].c;
 for(let i=1;i<bars.length;i++){
   const b=bars[i];
   prevE20=ema20;prevE50=ema50;
   ema20=b.c*(2/21)+ema20*(19/21);
   ema50=b.c*(2/51)+ema50*(49/51);
   const tr=Math.max(b.h-b.l,Math.abs(b.h-prevClose),Math.abs(b.l-prevClose));
   atr=(atr*13+tr)/14;prevClose=b.c;
   if(position){
     const hitStop=position.dir===1?b.l<=position.stop:b.h>=position.stop;
     const hitTarget=position.dir===1?b.h>=position.tp:b.l<=position.tp;
     if(hitStop||hitTarget){
       // Conservative: SL wins when both touched in same bar.
       const exit=hitStop?position.stop:position.tp;
       const pnl=position.units*(exit-position.entry)*position.dir - position.units*exit*spreadPct/100;
       cash+=pnl;trades++;if(pnl>0)wins++;position=null;
     }
   }
   // Signal at closed candle, execute next candle's open — no future close leakage.
   if(!position && i>=55 && i+1<bars.length && atr>0){
     const crossUp=prevE20<=prevE50&&ema20>ema50;
     const crossDown=prevE20>=prevE50&&ema20<ema50;
     if(crossUp||crossDown){
       const dir=crossUp?1:-1;
       const entry=bars[i+1].o*(1+dir*spreadPct/200);
       const stop=entry-dir*atr*1.5, tp=entry+dir*atr*3;
       const units=(cash*.005)/(atr*1.5);
       position={dir,entry,stop,tp,units};
     }
   }
   if(i%Math.max(1,Math.floor(bars.length/150))===0){
     let equity=cash+(position?position.units*(b.c-position.entry)*position.dir:0);
     peak=Math.max(peak,equity);maxDD=Math.max(maxDD,(peak-equity)/Math.max(peak,1));
     curve.push({date:i,equity});
   }
 }
 return {trades,wins,winRate:trades?wins/trades:0,pnl:cash-balance,maxDD,curve,bars:bars.length,openAtEnd:!!position};
}
async function act(action){
 if(action.startsWith("brain-")){await window.SentinelBrain?.action(action);return}
 if(action.startsWith("free-")){await window.FreeMT5UI?.action(action);return}
 if(action.startsWith("nav-")){navigate(action.slice(4));return}
 if(action==="refresh"){await window.FreeMT5UI?.sync();return}
 if(action==="open-connect"){openConnect();return}
 if(action==="close-modal"){closeModal();return}
 if(action==="connect"){navigate("mt5");return}
 if(action==="save-connect"){closeModal();navigate("mt5");return}
 if(action==="toggle-preview"){state.preview=!state.preview;save();render();return}
 if(action==="save-strategy"){let id=byId("modalRoot").dataset.edit;state.strategyDraft[id].score=Number(byId("strategyScoreSlider").value);save();closeModal();renderPage();toast("تم حفظ استراتيجية في المسودة","success");return}
 if(action==="export-strategies"){exportConfig("strategies");return}
 if(action==="export-risk"){exportConfig("risk");return}
 if(action==="export-logs"){fileDownload("sentinel-events.json",JSON.stringify(state.events,null,2));return}
 if(action==="sample-csv"){fileDownload("sentinel-ohlcv-sample.csv","time,open,high,low,close\n2026-01-01T00:00:00Z,100,101,99,100.5\n2026-01-01T00:05:00Z,100.5,101.2,100.1,101\n","text/csv");toast("هذا مجرد نموذج للترويسة؛ استخدم بيانات أطول للاختبار");return}
 if(action==="run-csv"){
   if(!state.csvBars){toast("اختر ملف CSV أولاً","error");return}
   try{state.localBacktest=localBacktest(state.csvBars,Number(byId("csvBalance")?.value||5000),Number(byId("csvSpread")?.value||.02));eventLog("backtest","Local CSV run: "+state.localBacktest.trades+" trades");renderPage();toast("اكتمل اختبار CSV المحلي","success")}
   catch(e){toast(e.message,"error")}
   return;
 }
 if(action==="run-backend-backtest"){
   if(!canTrade())return;
   if(!confirm("هذا الاختبار يستعمل أسعاراً صناعية مولّدة. هل تريد تشغيله؟"))return;
   try{state.backendBacktest=await call("backtest",{symbol:byId("remoteBacktestSymbol").value,n_candles_m5:Number(byId("remoteBars").value),acknowledge_synthetic:true});eventLog("synthetic-backtest","Request accepted");renderPage();toast("اكتمل الاختبار الصناعي","success")}
   catch(e){toast(e.message,"error")}return;
 }
 if(action==="train-model"){
   if(!canTrade())return;
   if(!confirm("سيتم تدريب النموذج على سجلات قاعدة بيانات البوت. لا تستخدم عينات صناعية. هل تؤكد؟"))return;
   try{const r=await call("train",{days_history:Number(byId("trainDays").value),n_estimators:Number(byId("trainTrees").value)});eventLog("train","Training requested: "+JSON.stringify(r).slice(0,80));toast("تم إرسال طلب التدريب إلى البوت","success")}
   catch(e){toast(e.message,"error")}return;
 }
}
document.addEventListener("click",async e=>{
 const navEl=e.target.closest("[data-nav]");if(navEl){navigate(navEl.dataset.nav);return}
 const cmd=e.target.closest("[data-command]");if(cmd){await runCommand(cmd.dataset.command);return}
 const toggle=e.target.closest("[data-toggle-strategy]");if(toggle){const id=toggle.dataset.toggleStrategy;state.strategyDraft[id].enabled=!state.strategyDraft[id].enabled;save();renderPage();return}
 const edit=e.target.closest("[data-edit-strategy]");if(edit){editStrategy(edit.dataset.editStrategy);return}
 const btn=e.target.closest("[data-action]");if(btn){btn.disabled=true;try{await act(btn.dataset.action)}finally{btn.disabled=false}return}
 if(e.target.classList.contains("modal-overlay"))closeModal();
});
document.addEventListener("change",async e=>{
 const t=e.target;
 if(t.id==="csvInput"){try{const file=t.files[0];if(!file)return;if(file.size>15000000)throw Error("الملف أكبر من 15MB");state.csvBars=parseCSV(await file.text());toast(state.csvBars.length+" شموع تم تحميلها","success");renderPage()}catch(err){toast(err.message,"error")}return}
 if(t.id==="tradeFilter"){state.tradeFilter=t.value;renderPage();return}
 if(t.id==="strategyGroup"){state.strategyGroup=t.value;renderPage();return}
 if(t.dataset.risk){const name=t.dataset.risk;const n=Number(t.value);if(!Number.isFinite(n)||n<Number(t.min)||n>Number(t.max)){toast("القيمة خارج المجال","error");renderPage();return}state.riskDraft[name]=n;save();toast("تم تعديل المسودة","success");return}
});
document.addEventListener("input",e=>{
 const t=e.target;
 if(t.id==="tradeSearch"){state.search=t.value;let pos=t.selectionStart;renderPage();let input=byId("tradeSearch");input.focus();input.setSelectionRange(pos,pos)}
 if(t.id==="strategySearch"){state.strategySearch=t.value;let pos=t.selectionStart;renderPage();let input=byId("strategySearch");input.focus();input.setSelectionRange(pos,pos)}
});
byId("refreshBtn").onclick=()=>state.page==="live"?window.SentinelLive?.refresh():window.FreeMT5UI?.sync();
byId("connectBtn").onclick=()=>navigate("mt5");
byId("connectorMini").onclick=()=>navigate("mt5");
byId("mobileMenu").onclick=()=>byId("sidebar").classList.toggle("open");
function clockTick(){byId("clock").textContent=new Date().toLocaleTimeString("en-GB",{timeZone:"UTC",hour12:false})+" UTC"}
clockTick();setInterval(clockTick,1000);
setInterval(()=>{if(state.connected&&!state.preview)refresh(true)},25000);
eventLog("system","Sentinel isolated dashboard initialized");
render();
sessionStorage.removeItem("sentinel_console_key");
