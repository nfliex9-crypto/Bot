/* Sentinel Brain v1 — broker-grounded research dashboard. No order execution. */
"use strict";
window.SentinelBrain=(()=>{
 let view={data:null,symbols:[],symbol:"",timeframe:"M15",hours:720,loading:false,stage:"",error:"",
  lastImport:null,lastTrades:null,lastEvaluation:null};
 const msg={
  DEMO_ACCOUNT_REQUIRED:"الربط لا يخص حساب MT5 Demo مؤكد.",
  BROKER_SESSION_COLD:"جلسة MT5 بردت؛ افتح MT5 وأعد تنشيطها قبل الاستيراد.",
  TICKERALL_NOT_CONNECTED:"اربط مفتاح TickerAll في صفحة MT5.",
  IMPORT_HISTORY_FIRST:"استورد شموع تاريخية كافية قبل تشغيل التحليل.",
  TICKERALL_UNREACHABLE:"تعذّر الاتصال بمصدر TickerAll.",
  INVALID_SYMBOL:"الرمز غير موجود ضمن الرموز المسموحة.",
  INVALID_HISTORY_WINDOW:"هذه الفترة الزمنية غير متاحة للفاصل المحدد.",
  INVALID_TIMEFRAME:"فاصل زمني غير مدعوم.",
  TICKERALL_RATE_LIMIT:"تم الوصول إلى حد الطلبات. جرّب بعد قليل.",
  RESEARCH_WORKER_UNAVAILABLE:"تعذّر إكمال الفحص البحثي. راجع سجل الوظائف."
 };
 const errorText=x=>msg[x]||String(x||"Error");
 const account=()=>window.FreeMT5UI?.summary()?.account||null;
 const isOnline=()=>Boolean(window.FreeMT5UI?.summary()?.verified);
 const curr=()=>window.FreeMT5UI?.summary()?.currency||"";
 const currentAccountMemory=()=>view.data?.accounts?.find(a=>a.account_id===account()?.id)||null;
 const activeRuns=()=>view.data?.runs?.filter(r=>r.account_id===account()?.id)||[];
 const maxWindow={M5:720,M15:2200,H1:8760,H4:17520,D1:43800};
 async function call(action,body){
  const r=await fetch("/api/brain?action="+encodeURIComponent(action),{
   method:body===undefined?"GET":"POST",credentials:"same-origin",
   headers:{"Content-Type":"application/json"},
   body:body===undefined?undefined:JSON.stringify(body),cache:"no-store",redirect:"error"
  });
  let j;
  try{j=await r.json()}catch(_){throw Error("تعذرت قراءة استجابة السيرفر")}
  if(!r.ok||!j?.ok)throw Error(errorText(j?.error));
  return j.data;
 }
 const fx=x=>x===null||x===undefined||x===""?"—":Number.isFinite(Number(x))?Number(x).toFixed(3):"—";
 const badgeFor=status=>{
  if(status==="PAPER_CANDIDATE"||status==="BOOST_PAPER_RESEARCH_2X")
   return '<span class="tag mint">'+esc(status)+'</span>';
  if(["PAUSE_RESEARCH","PAUSE_PAPER_RESEARCH","PAUSE_PAPER_RESEARCH_DRIFT","AVOID_PAPER","AVOID_PAPER_EXPERIMENTS","DATA_INCOMPLETE","COST_DATA_WEAK"].includes(status))return '<span class="tag red">'+esc(status)+'</span>';
  return '<span class="tag amber">'+esc(status)+'</span>';
 };
 const percentCount=(n,d)=>d>0?((n/d)*100).toFixed(1)+"%":"—";
 function strategyTable(run){
  if(!run?.strategies?.length)return empty("لا توجد نتائج OOS موثقة","استورد شموع السوق الحقيقية ثم نفّذ تحليل الاستراتيجيات.");
  return '<div class="table-wrap"><table class="table"><thead><tr><th>Strategy</th><th>القرار</th><th>OOS Trades</th><th>Expectancy (R)</th><th>Costs x2 (R)</th><th>Days</th><th>Adjusted LB (R)</th></tr></thead><tbody>'+
   run.strategies.map(s=>'<tr><td class="mono">'+esc(s.id)+'</td><td>'+badgeFor(s.status)+'</td><td class="mono">'+num(s.trades,0)+'</td>'+
    '<td class="mono '+(s.expectancy_r>0?"pos":"neg")+'">'+fx(s.expectancy_r)+'</td>'+
    '<td class="mono '+(s.stress_expectancy_r>0?"pos":"neg")+'">'+fx(s.stress_expectancy_r)+'</td>'+
    '<td class="mono">'+(s.integrity?num(s.integrity.sample_days,0):"—")+'</td>'+
    '<td class="mono '+(s.integrity?.lower_bound_r>0?"pos":"neg")+'">'+fx(s.integrity?.lower_bound_r)+'</td></tr>').join("")+
   '</tbody></table></div>';
 }
 function render(){
  const mt=window.FreeMT5UI?.summary()||{},mem=currentAccountMemory(),latest=activeRuns()[0],running=view.loading;
  const realTradeCount=mem?.completed_trades||0;
  const pnl=mem?.recorded_broker_profit;
  const total=(view.data?.candles||0);
  let html=heading("SENTINEL / INTELLIGENCE","العقل المتعلّم","تغذية من صفقات MT5 والشموع التاريخية. فحص خارج العيّنة وترتيب بحثي للاستراتيجيات.",
    button("↻ تحديث","brain-refresh","btn-sm",running)+button("↓ تصدير Evidence JSON","brain-export","btn-sm",running||!latest)+button("فتح MT5","nav-mt5","btn-sm",running));
  html+='<div class="notice info"><strong>RESEARCH MODE · NO ORDERS</strong><span class="notice-small">النتائج تُستخدم لاستبعاد الاستراتيجيات الضعيفة من التجارب وترشيح الأفضل للتداول الورقي، بدون مضاعفة اللوت أو تفعيل تداول تلقائي.</span></div>';
  if(!account())html+='<div class="notice"><strong>لا يوجد حساب Demo مرتبط</strong><span class="notice-small">اربط حساب MT5 عبر TickerAll قبل الاستيراد.</span>'+button("ربط MT5","nav-mt5","btn-sm btn-primary")+'</div>';
  else if(!isOnline())html+='<div class="notice"><strong>اتصال MT5 غير نشط</strong><span class="notice-small">فعّل جلسة TickerAll قبل تحميل سجل الصفقات والشموع.</span></div>';
  if(view.error)html+='<div class="notice"><strong>فحص البيانات</strong><span class="notice-small">'+esc(view.error)+'</span></div>';
  html+='<div class="grid kpi-grid">'+
    kpi("صفقات تاريخية",num(realTradeCount,0),"COMPLETE BROKER TRADES","#4ce3bd")+
    kpi("منسوبة لاستراتيجية",num(mem?.attributed_trades||0,0),"VERIFIED STRATEGY TAGS","#799dff")+
    kpi("شموع محفوظة",num(total,0),"PERSISTENT HISTORICAL BARS","#ad8cff")+
    kpi("نتائج البحث",num(activeRuns().length,0),"VISIBLE RECENT RUNS","#ffca80")+'</div>';
  const provenance=mem&&pnl!==null?'<span class="mono">'+num(pnl,2)+(curr()?" "+esc(curr()):"")+'</span>':'—';
  html+='<div class="content-grid">'+panel("Trade Memory","صفقات مكتملة من TickerAll، بدون نسخ مكررة",'<div class="panel-pad">'+[
    ["Closed trades",num(realTradeCount,0)],
    ["Broker-reported profit",provenance],
    ["Recorded win rate",percentCount(mem?.wins||0,realTradeCount)],
    ["Unknown strategy attribution",num(realTradeCount-(mem?.attributed_trades||0),0)],
    ["Trading execution","DISABLED"]
  ].map(x=>'<div class="key-value"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join("")+
   '<div class="info-block" style="margin-top:15px"><strong>Cost & attribution</strong>تاريخ TickerAll قد لا يحتوي عمولة الوسيط الفعلية أو الاستراتيجية التي أنشأت الصفقة. لا نستخدم هذه الصفقات لتفضيل استراتيجية محددة بدون وسم موثوق قبل التنفيذ.</div></div>')+
  panel("Historical Lab","أربع استراتيجيات فعلية بقواعد محددة، على شموع MT5",'<div class="panel-pad">'+
    '<div class="field"><label>رمز الوسيط</label><select class="input select" id="brainSymbol">'+
    (view.symbols.length?view.symbols.map(s=>'<option value="'+esc(s)+'" '+(view.symbol===s?"selected":"")+'>'+esc(s)+'</option>').join(""):
      '<option value="">اضغط تحديث الرموز</option>')+'</select></div>'+
    '<div class="form-grid" style="margin-top:13px"><div class="field"><label>Timeframe</label><select id="brainTimeframe" class="input select">'+
    ["M5","M15","H1","H4","D1"].map(tf=>'<option '+(view.timeframe===tf?"selected":"")+'>'+tf+'</option>').join("")+'</select></div>'+
    '<div class="field"><label>التاريخ المطلوب</label><select id="brainHours" class="input select">'+
    [168,720,2200,8760,17520,43800].filter(h=>h<=maxWindow[view.timeframe]).map(h=>
      '<option value="'+h+'" '+(view.hours===h?"selected":"")+'>'+({168:"7 أيام",720:"30 يوماً",2200:"~3 أشهر",8760:"سنة",17520:"سنتان",43800:"5 سنوات"}[h])+'</option>').join("")+
    '</select></div></div>'+
    '<div class="info-block" style="margin-top:14px"><strong>Out-of-sample</strong>اختبار 3 فترات متتابعة، دخول الشمعة التالية، تكلفة مضاعفة، وحد ثقة يومي مصحّح لأربع استراتيجيات. لا تنفيذ تلقائي.</div>'+
    '<div class="action-strip" style="margin-top:16px">'+
      '<span class="small subtle">'+(running?"جاري: "+esc(view.stage):"جاهز للتحليل")+'</span>'+
      button(running?"جاري فحص البيانات...":"▶ استيراد وتحليل الاستراتيجيات","brain-pipeline","btn-primary btn-sm",running||!isOnline()||!view.symbol)+
      '</div>'+
    '<div class="action-strip" style="margin-top:10px">'+
      button("↻ الرموز","brain-symbols","btn-sm",running||!isOnline())+
      button("سجل الصفقات فقط","brain-trades","btn-sm",running||!isOnline())+
      button("إعادة تقييم الموجود","brain-evaluate","btn-sm",running||!view.symbol)+
    '</div></div>')+'</div>';
  const tradeMemory=view.data?.trade_memory_by_account?.[account()?.id];
  if(tradeMemory?.overall?.trades>0){
   const rows=(tradeMemory.by_symbol||[]).slice(0,10);
   html+=panel("Broker Pattern Memory","الصفقات المكتملة المستوردة (حتى آخر 5000) ولو بلا وسم استراتيجية · تحليل لا يغيّر صفقات البوت",
    '<div class="table-wrap"><table class="table"><thead><tr><th>Symbol</th><th>Trades</th><th>Broker P/L</th><th>Recent mean</th><th>Research</th></tr></thead><tbody>'+
    rows.map(x=>'<tr><td class="mono">'+esc(x.name)+'</td><td class="mono">'+num(x.trades,0)+'</td>'+
     '<td class="mono">'+fx(x.broker_reported_profit)+'</td><td class="mono">'+fx(x.recent_mean_broker_profit)+'</td><td>'+badgeFor(x.status)+'</td></tr>').join("")+
    '</tbody></table></div>');
   const sessions=(tradeMemory.by_session||[]).filter(x=>x.trades>0);
   html+=panel("Session Memory","الأداء بحسب جلسة الدخول UTC، أو الإغلاق إذا كان وقت الدخول غير متوفر",
    '<div class="panel-pad">'+sessions.map(x=>
      '<div class="key-value"><span>'+esc(x.name)+' · '+num(x.trades,0)+' trades</span><strong>'+fx(x.broker_reported_profit)+' · '+esc(x.status)+'</strong></div>'
    ).join("")+'<div class="small subtle" style="margin-top:12px">الأرقام من P/L الوسيط؛ قد لا تشمل كل الرسوم. لا يمكن استنتاج استراتيجية الصفقة من نتيجتها.</div></div>');
  }
  const importRow=view.data?.imports?.find(x=>x.account_id===account()?.id&&x.symbol===view.symbol&&x.timeframe===view.timeframe);
  if(importRow)html+='<div class="notice '+(importRow.truncated?"":"success")+'"><strong>تغطية بيانات الشموع: '+esc(importRow.coverage)+'</strong><span class="notice-small">'+num(importRow.provider_count,0)+' شمعة · '+esc(importRow.timeframe)+' · '+(importRow.truncated?"تاريخ غير مكتمل — لا ترقية":"تم فحص سجل المصدر")+'</span></div>';
  html+=panel("Strategy Selector","نتائج خارج العينة بعد التكاليف · أفضل المرشحين فقط للتجربة الورقية",
    strategyTable(latest),
    latest?'<span class="tag">'+esc(latest.symbol)+' · '+esc(latest.timeframe)+' · '+dateFmt(latest.date)+'</span>':'<span class="tag">AWAITING RESEARCH</span>');
  if(latest)html+='<div class="info-block" style="margin-top:16px"><strong>حالات القرار</strong>PAPER_CANDIDATE: مرشح ورقي فقط بعد تصحيح الاختبارات · MULTIPLE_TESTS_UNCERTAIN: حد الثقة اليومي غير كافٍ · PAUSE_RESEARCH: مستبعد بحثياً · DATA_INCOMPLETE: بيانات ناقصة. لا توجد صفقات آلية من هذا المختبر.</div>';
  if(latest?.quality){
   const q=latest.quality;
   html+=panel("Data Quality","جودة المصدر التاريخي قبل أي ترقية للاستراتيجية",
    '<div class="panel-pad">'+[
     ["Coverage",String(q.source_coverage||"unknown")],
     ["Dataset SHA-256",latest.dataset?.id?latest.dataset.id.slice(0,20)+"…":"—"],
     ["Bars",num(latest.candles||0,0)],
     ["Missing spread",q.missing_spread_ratio==null?"—":(Number(q.missing_spread_ratio)*100).toFixed(1)+"%"],
     ["Rejected / duplicate bars",num(q.rejected_rows||0,0)+" / "+num(q.duplicate_rows||0,0)],
     ["Time gap events",q.time_gap_events==null?"—":num(q.time_gap_events,0)]
    ].map(x=>'<div class="key-value"><span>'+esc(x[0])+'</span><strong>'+esc(x[1])+'</strong></div>').join("")+
    '<div class="small subtle" style="margin-top:12px">فجوات نهاية الأسبوع ممكن تكون طبيعية؛ لا تعتبر وحدها دليلاً على خلل السوق.</div></div>');
  }
  if(latest?.strategies?.length){
   const regimeRows=latest.strategies.flatMap(s=>
     Object.entries(s.regimes||{}).filter(([,v])=>v.trades>=12)
      .map(([regime,v])=>({strategy:s.id,regime,...v})));
   html+=panel("Market Regime Lab","نتائج مستقلة حسب اتجاه السوق أو تذبذبه؛ لا ترقية بدون عينة كافية",
    regimeRows.length?'<div class="table-wrap"><table class="table"><thead><tr><th>Strategy</th><th>Regime</th><th>Trades</th><th>2× Cost R</th><th>Decision</th></tr></thead><tbody>'+
    regimeRows.map(x=>'<tr><td class="mono">'+esc(x.strategy)+'</td><td>'+esc(x.regime)+'</td><td class="mono">'+num(x.trades,0)+'</td><td class="mono">'+fx(x.double_cost_expectancy_r)+'</td><td>'+badgeFor(x.status)+'</td></tr>').join("")+'</tbody></table></div>':
    empty("عينات الأنظمة السوقية غير كافية","يلزم سجل شموع أوسع لاختبار الاتجاه والتذبذب بصورة مستقلة."));
  }
  const forward=view.data?.forward_by_account_symbol?.[account()?.id]?.[view.symbol];
  const forwardRows=(forward?.strategy_results||[]).filter(x=>x.metrics.count>0);
  html+=panel("Forward Learner · "+esc(view.symbol||"—"),"تعلّم منفصل لكل رمز، من صفقات موسومة عند فتحها، قبل معرفة نتائجها",
    forwardRows.length?'<div class="table-wrap"><table class="table"><thead><tr><th>Strategy</th><th>حالة التعلّم</th><th>Forward Trades</th><th>Days</th><th>Recent R</th><th>Research Weight</th></tr></thead><tbody>'+
      forwardRows.map(f=>'<tr><td class="mono">'+esc(f.strategy_id)+'</td><td>'+badgeFor(f.status)+'</td>'+
       '<td class="mono">'+num(f.metrics.count,0)+'</td><td class="mono">'+num(f.metrics.active_days,0)+'</td><td class="mono">'+fx(f.metrics.recent_mean_r)+'</td>'+
       '<td class="mono">'+f.relative_research_multiplier+'×</td></tr>').join("")+'</tbody></table></div>':
      empty("بانتظار صفقات موسومة مسبقاً","نحفظ كل صفقات MT5 لكن لا ننسب استراتيجية من الربح والخسارة. عند ربط محرك التنفيذ سيتم تسجيل هوية الاستراتيجية فور فتح الصفقة."));
  if(latest?.paper_schedule?.allocations?.length){
    html+=panel("Paper Research Allocation","توزيع أولوية التجارب، وليس أوامر تداول أو تغيير حجم مخاطرة",
      '<div class="panel-pad">'+latest.paper_schedule.allocations.map(a=>
        '<div class="key-value"><span>'+esc(a.strategy_id)+'</span><strong>'+Math.round(a.weight*100)+'% · '+esc(a.forward_status)+'</strong></div>'
      ).join("")+'</div>');
  }
  return html;
 }
 async function refresh(silent=false){
  try{view.data=await call("status");view.error="";if(!silent)toast("تم تحديث ذاكرة التداول","success")}
  catch(e){view.error=e.message;if(!silent)toast(e.message,"error")}
  if(state.page==="ai")renderPage();
 }
 async function symbols(silent=false){
  const a=account();
  if(!a)return;
  try{
   const r=await call("symbols",{accountId:a.id});
   view.symbols=(r.symbols||[]).filter(x=>typeof x==="string"&&/^[A-Za-z0-9._#-]{2,24}$/.test(x));
   const priorities=["XAUUSD","GOLD","BTCUSD","EURUSD","NAS100"];
   if(!view.symbols.includes(view.symbol))view.symbol=priorities.find(x=>view.symbols.includes(x))||view.symbols[0]||"";
   if(!silent)toast(view.symbols.length+" رموز من الوسيط","success");
  }catch(e){view.error=e.message;if(!silent)toast(e.message,"error")}
  if(state.page==="ai")renderPage();
 }
 // On-demand catch-up: refreshes broker history when the owner opens the Intelligence page.
 // Not a background worker or a guarantee of uninterrupted Free-tier sessions.
 let lastAutoAttempt=0;
 async function maybeAutoSync(){
  const a=account();
  if(!a||!isOnline()||view.loading||state.page!=="ai")return;
  const now=Date.now(),key="sentinel_brain_auto_v2_"+a.id+"_"+view.timeframe;
  let last=0;
  try{last=Number(localStorage.getItem(key)||0)}catch(_){}
  if(now-last<6*3600*1000||now-lastAutoAttempt<60000)return;
  lastAutoAttempt=now;view.loading=true;view.error="";
  try{
   if(!view.symbol)await symbols(true);
   view.stage="تحديث ذاكرة الصفقات";renderPage();
   view.lastTrades=await call("syncTrades",{accountId:a.id});
   if(view.symbol){
    const prior=view.data?.imports?.find(x=>x.account_id===a.id&&x.symbol===view.symbol&&x.timeframe===view.timeframe);
    if(!prior||!Number.isFinite(new Date(prior.imported_at).getTime())||now-new Date(prior.imported_at).getTime()>24*3600*1000){
     view.stage="تحديث التاريخ الحقيقي";renderPage();
     view.lastImport=await call("syncCandles",{accountId:a.id,symbol:view.symbol,timeframe:view.timeframe,hours:view.hours});
    }
    view.stage="تحديث ترتيب الاستراتيجيات";renderPage();
    view.lastEvaluation=await call("evaluate",{accountId:a.id,symbol:view.symbol,timeframe:view.timeframe});
   }
   try{localStorage.setItem(key,String(Date.now()))}catch(_){}
  }catch(e){view.error="Auto-sync: "+e.message}
  finally{const error=view.error;view.loading=false;view.stage="";await refresh(true);if(error)view.error=error;renderPage()}
 }
 async function pipeline(){
  const a=account();
  if(!a||!isOnline()||view.loading||!view.symbol)return;
  view.loading=true;view.error="";
  try{
   view.stage="الصفقات المكتملة";renderPage();
   view.lastTrades=await call("syncTrades",{accountId:a.id});
   view.stage="الشموع التاريخية";renderPage();
   view.lastImport=await call("syncCandles",{accountId:a.id,symbol:view.symbol,timeframe:view.timeframe,hours:view.hours});
   view.stage="تحليل الاستراتيجيات";renderPage();
   view.lastEvaluation=await call("evaluate",{accountId:a.id,symbol:view.symbol,timeframe:view.timeframe});
   toast("اكتمل التحليل الحقيقي — بدون أوامر تداول","success");
  }catch(e){view.error=e.message;toast(e.message,"error")}
  finally{const error=view.error;view.loading=false;view.stage="";await refresh(true);if(error)view.error=error;renderPage()}
 }
 async function action(cmd){
  if(cmd==="brain-export"){
   const current=activeRuns()[0];
   if(!current){toast("لا يوجد تحليل حقيقي لتصديره","error");return}
   const exportPayload={
    format:"sentinel-perspective-compatible-evidence-v1",
    exported_at:new Date().toISOString(),
    source:"Sentinel broker-verified research",
    symbol:current.symbol,timeframe:current.timeframe,
    dataset:current.dataset||null,quality:current.quality||null,
    research_mode:"READ_ONLY_NO_EXECUTION",
    strategies:(current.strategies||[]).map(x=>({
     strategy_id:x.id,status:x.status,oos_trades:x.trades,
     expectancy_r:x.expectancy_r,double_cost_expectancy_r:x.stress_expectancy_r,
     independent_days:x.integrity?.sample_days??null,
     adjusted_lower_bound_r:x.integrity?.lower_bound_r??null,
     adjusted_confidence:x.integrity?.effective_confidence??null,
     decision:x.status==="PAPER_CANDIDATE"?"RESEARCH_ONLY":"NO_PROMOTION"
    }))
   };
   const filename="sentinel-quant-evidence-"+String(current.symbol||"market").replace(/[^A-Za-z0-9._-]/g,"_")+"-"+String(current.timeframe||"TF")+".json";
   fileDownload(filename,JSON.stringify(exportPayload,null,2),"application/json");
   toast("تم تصدير بيانات البحث للتحليل والمقارنة","success");
   return;
  }
  if(cmd==="brain-refresh"){await refresh();return}
  if(cmd==="brain-symbols"){await symbols();return}
  if(cmd==="brain-pipeline"){await pipeline();return}
  if(cmd==="brain-trades"){
   const a=account();if(!a||view.loading)return;
   view.loading=true;view.stage="جلب سجل الصفقات";renderPage();
   try{view.lastTrades=await call("syncTrades",{accountId:a.id});toast("تمت مزامنة سجل MT5","success")}
   catch(e){view.error=e.message;toast(e.message,"error")}
   finally{const error=view.error;view.loading=false;view.stage="";await refresh(true);if(error)view.error=error;renderPage()}
   return;
  }
  if(cmd==="brain-evaluate"){
   const a=account();if(!a||!view.symbol||view.loading)return;
   view.loading=true;view.stage="تحليل بيانات سابقة";renderPage();
   try{view.lastEvaluation=await call("evaluate",{accountId:a.id,symbol:view.symbol,timeframe:view.timeframe});toast("تم إعادة التقييم","success")}
   catch(e){view.error=e.message;toast(e.message,"error")}
   finally{const error=view.error;view.loading=false;view.stage="";await refresh(true);if(error)view.error=error;renderPage()}
  }
 }
 document.addEventListener("change",e=>{
  if(e.target.id==="brainSymbol")view.symbol=e.target.value;
  if(e.target.id==="brainTimeframe"){
   view.timeframe=e.target.value;
   if(view.hours>maxWindow[view.timeframe])view.hours=maxWindow[view.timeframe];
   if(![168,720,2200,8760,17520,43800].filter(h=>h<=maxWindow[view.timeframe]).includes(view.hours))
    view.hours=720;renderPage();
  }
  if(e.target.id==="brainHours")view.hours=Number(e.target.value);
 });
 async function init(){await refresh(true);await maybeAutoSync()}
 return {render,refresh,symbols,action,init,maybeAutoSync};
})();
window.SentinelBrain.init();
