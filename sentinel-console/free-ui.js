/* Sentinel / MT5 connection — protected by Vercel SSO, no secondary site password. */
"use strict";
window.FreeMT5UI=(()=>{
 let stateMT={configured:false,accounts:[],details:{},history:{},symbols:{},loading:false,error:"",lastSync:null,connecting:false};
 const errText={
  CONSOLE_PROTECTION_REQUIRED:"تعذّر تأكيد حماية لوحة التحكم. أعد فتح الموقع من رابط Sentinel الرسمي.",
  BRIDGE_NOT_CONFIGURED:"إعدادات الربط السحابي غير مكتملة على السيرفر.",
  TICKERALL_KEY_REJECTED:"مفتاح TickerAll غير صالح أو لا يملك صلاحية الدخول.",
  INVALID_TICKERALL_API_KEY:"صيغة المفتاح غير صحيحة. انسخه كما هو من TickerAll.",
  TICKERALL_RATE_LIMIT:"الخدمة استقبلت طلبات كثيرة. أعد المحاولة بعد قليل.",
  TICKERALL_UNREACHABLE:"تعذّر الوصول إلى TickerAll حالياً.",
  BROKER_AUTH_FAILED:"رفض الوسيط بيانات الحساب. تأكد من رقم الديمو وكلمة المرور والسيرفر.",
  FREE_TIER_LIVE_REJECTED:"الخطة المجانية لا تسمح بربط الحساب الحقيقي. اختر Demo.",
  DEMO_ONLY_CONNECTION_REQUIRED:"الحساب ليس Demo. لم يتم ربطه.",
  NOT_A_VERIFIED_DEMO_ACCOUNT:"لم يتم التحقق أن هذا حساب MT5 Demo.",
  BROKER_ACCOUNT_NOT_HOT:"جلسة الوسيط غير نشطة. أعد ربط حساب الديمو.",
  BROKER_SESSION_COLD:"انتهت الجلسة المجانية. أعد الاتصال.",
  INVALID_BROKER_CREDENTIAL_FIELDS:"يرجى التأكد من رقم الحساب وكلمة المرور واسم السيرفر.",
  PROVIDER_ERROR:"تعذّر إكمال العملية لدى TickerAll. تحقق من حسابك وأعد المحاولة.",
  PENDING_BROKER_SNAPSHOT:"جاري قراءة بيانات الحساب من TickerAll.",
  BROKER_SNAPSHOT_OFFLINE:"الجلسة نشطة لكن الوسيط لم يرجع بيانات الحساب بعد؛ سنحاول مجدداً.",
  BROKER_SNAPSHOT_UNVERIFIED:"بيانات الحساب غير مؤكدة؛ لم نتحقق من أنه حساب Demo.",
  BROKER_SNAPSHOT_FAILED:"تعذرت قراءة تفاصيل الحساب. حاول تحديث الحالة."
 };
 const friendly=x=>errText[x]||String(x||"تعذّر تنفيذ العملية");
 async function api(action,body){
  const res=await fetch("/api/free-mt5?action="+encodeURIComponent(action),{
   method:body===undefined?"GET":"POST",
   headers:{"Content-Type":"application/json"},
   credentials:"same-origin",
   body:body===undefined?undefined:JSON.stringify(body),
   cache:"no-store",redirect:"error"
  });
  let result;
  try{result=await res.json()}catch(_){throw Error("تعذّر قراءة استجابة الخدمة. سجّل الدخول إلى Vercel وأعد المحاولة.")}
  if(!res.ok||!result?.ok)throw Error(friendly(result?.error||"PROVIDER_ERROR"));
  return result;
 }
 const primary=()=>stateMT.accounts.find(a=>a.isDemo&&a.verified)||stateMT.accounts.find(a=>a.isDemo&&a.hot)||stateMT.accounts.find(a=>a.isDemo)||null;
 const connected=()=>{const a=primary();return Boolean(a?.isDemo&&a?.online)};
 const financialsReady=()=>{const a=primary(),d=a?stateMT.details[a.id]:null;return Boolean(a?.verified&&d?.online&&d?.isDemo)};
 function summary(){
  const a=primary(),d=a?stateMT.details[a.id]:null;
  return {
   configured:stateMT.configured,accounts:stateMT.accounts.length,
   hot:stateMT.accounts.filter(x=>x.isDemo&&x.hot).length,
   verified:connected(),financialsReady:financialsReady(),
   balance:financialsReady()?d.balance:null,
   equity:financialsReady()?d.equity:null,currency:financialsReady()?d.currency:null,
   positions:financialsReady()?(d.positions||[]):[],account:a,
   connection:a?(a.hot?"hot":"cold"):"unlinked",error:stateMT.error,lastSync:stateMT.lastSync
  };
 }
 async function sync(silent=false){
  if(stateMT.loading)return;
  stateMT.loading=true;
  try{
    const r=await api("status");
    stateMT.accounts=(r.accounts||[]).filter(x=>x.broker==="mt5"&&x.isDemo===true);
    stateMT.configured=r.configured===true;
    stateMT.error="";
    stateMT.lastSync=new Date().toISOString();
    // Same-request provider verification: no hidden POST failure.
    stateMT.details={};
    for(const account of stateMT.accounts){
      if(account.verified&&account.snapshot?.online&&account.snapshot?.isDemo){
        stateMT.details[account.id]=account.snapshot;
      }
    }
    if(!silent)toast("تم تحديث حالة الحساب","success");
  }catch(e){stateMT.error=e.message;if(!silent)toast(e.message,"error");}
  finally{stateMT.loading=false;renderHeader();if(state.page==="mt5"||state.page==="overview")renderPage();
    if(state.page==="ai"&&window.SentinelBrain?.maybeAutoSync)void window.SentinelBrain.maybeAutoSync();}
 }
 function section(label,num,content,done=false){
  return '<div class="step-card '+(done?"complete":"")+'"><div class="step-index">'+num+'</div><div class="step-text"><div class="step-label">'+label+'</div>'+content+'</div>'+(done?'<span class="step-check">✓</span>':"")+'</div>';
 }
 function connectHero(){
  const a=primary();
  const step=stateMT.configured?(a?3:2):1;
  return '<div class="connect-hero">'+
  '<div class="hero-kicker"><span class="live-spark"></span> SENTINEL / BROKER GATEWAY</div>'+
  '<h2>'+(a?"حساب MT5 تحت المراقبة":"ربط حساب MT5 بدون تعقيد")+'</h2>'+
  '<p>'+(a?"الاتصال السحابي آمن، وكل الأرقام من الوسيط مباشرة.":"خطوتان فقط، بدون Windows أو رسوم MetaApi.")+'</p>'+
  '<div class="onboarding-path">'+
  section("TickerAll API",1,'<span class="step-meta">'+(stateMT.configured?"تم حفظ المفتاح بأمان":"انسخ المفتاح من TickerAll")+'</span>',stateMT.configured)+
  section("MT5 Demo",2,'<span class="step-meta">'+(connected()?"حساب Demo ONLINE":a?"تم العثور على الحساب":"أضف حسابك التجريبي")+'</span>',connected())+
  '</div>'+
  '<div class="connect-actions">'+
   (!stateMT.configured?button("ربط TickerAll API","free-key","btn-primary"):!a?button("ربط حساب MT5 Demo","free-connect","btn-primary"):button("تحديث حالة الحساب","free-status","btn-primary"))+
   '<a class="btn btn-soft" target="_blank" rel="noopener noreferrer" href="https://tickerall.com/dashboard">فتح TickerAll <span aria-hidden="true">↗</span></a>'+
  '</div></div>';
 }
 function accountView(a){
  const d=stateMT.details[a.id];
  const ok=Boolean(a.online);
  const financial=Boolean(a.verified&&d?.online&&d?.isDemo);
  return '<div class="panel"><div class="panel-title"><div><h3>حساب MetaTrader 5</h3><p class="mono">'+esc(a.server||"UNKNOWN")+' · '+esc(a.accountNumber||"••••")+'</p></div><span class="tag '+(ok?"mint":"amber")+'">'+(ok?"DEMO ONLINE":"OFFLINE")+'</span></div>'+
  '<div class="grid kpi-grid" style="padding:16px;margin:0">'+
   kpi("الرصيد",financial&&d.balance!=null?money(d.balance,d.currency||"USD"):"—","BALANCE","#4ce3bd")+
   kpi("رأس المال",financial&&d.equity!=null?money(d.equity,d.currency||"USD"):"—","EQUITY","#799dff")+
   kpi("المراكز",financial?num(d.positions?.length||0,0):"—","OPEN POSITIONS","#ab8cff")+
   kpi("الحالة",ok?"ONLINE":a.hot?"ACTIVE":"IDLE","CLOUD SESSION",a.hot?"#4ce3bd":"#ffca80")+
  '</div><div class="panel-pad" style="padding-top:0"><div class="action-strip">'+
   '<span class="small subtle">'+(ok?"بيانات الحساب مؤكدة":ok?"الحساب متصل · قراءة الرصيد قيد التحديث":a.verificationError?friendly(a.verificationError):"بانتظار قراءة بيانات الوسيط")+'</span>'+
   '<div class="head-buttons">'+button("فحص الحساب","free-inspect:"+a.id,"btn-sm")+
   button("سجل الصفقات","free-history:"+a.id,"btn-sm")+
   button("الرموز","free-symbols:"+a.id,"btn-sm")+
   button("فصل الحساب","free-disconnect:"+a.id,"btn-sm btn-danger")+'</div></div>'+
   (financial&&(d.positions||[]).length?'<div class="table-wrap" style="margin-top:16px"><table class="table"><thead><tr><th>الرمز</th><th>الصفقة</th><th>الحجم</th><th>P&L</th></tr></thead><tbody>'+d.positions.map(p=>'<tr><td class="mono">'+esc(p.symbol)+'</td><td>'+esc(p.side)+'</td><td class="mono">'+esc(p.volume)+'</td><td class="mono">'+esc(p.profit)+'</td></tr>').join("")+'</tbody></table></div>':"")+
   (!ok?'<div class="compact-alert"><icon name="refresh-cw"></icon><span>الاتصال بارد. الخطة المجانية قد تحتاج إعادة ربط الحساب بعد الخمول.</span>'+button("إعادة الربط","free-connect","btn-sm")+'</div>':"")+
   '</div></div>';
 }
 function render(){
  const all=stateMT.accounts,primaryAccount=primary();
  let html=heading("ACCOUNTS / 01","ربط وإدارة MT5","الاتصال السحابي · Demo فقط",button("↻ تحديث","free-status","btn-sm"));
  if(stateMT.error)html+='<div class="notice"><strong>تعذّر تحديث الحالة</strong><span class="notice-small">'+esc(stateMT.error)+'</span>'+button("المحاولة مجدداً","free-status","btn-sm")+'</div>';
  html+=connectHero();
  if(all.length)html+=all.map(accountView).join("");
  if(stateMT.configured&&!all.length){
    html+=panel("جاهز للربط","TickerAll API متصل بالفعل",empty("ما في حساب MT5 مرتبط بعد","اضغط «ربط حساب MT5 Demo» لإكمال الاتصال."),button("ربط MT5","free-connect","btn-primary btn-sm"));
  }
  html+='<div class="microfoot"><span>DEMO ONLY</span><span>VERCEL SSO</span><span>ZERO LIVE ORDERS</span><a href="https://tickerall.com/docs" target="_blank" rel="noopener noreferrer">TickerAll Docs ↗</a></div>';
  return html;
 }
 function keyModal(){
  showModal("ربط TickerAll",'<div class="field"><label>API Key</label><input type="password" class="input mono" id="freeApiKey" placeholder="cf_api_..." autocomplete="off" spellcheck="false"></div><p class="small subtle" style="margin-top:10px">من قائمة API Keys في TickerAll. لا تستخدم كلمة مرور الوسيط هون.</p>',
  button("إلغاء","close-modal","btn-sm")+button("ربط المفتاح","free-save-key","btn-primary btn-sm"));
 }
 function accountModal(){
  showModal("إضافة حساب MT5 Demo",'<div class="form-grid">'+
   '<div class="field"><label>رقم الحساب</label><input id="freeLogin" type="text" inputmode="numeric" class="input mono" autocomplete="off" placeholder="12345678"></div>'+
   '<div class="field"><label>سيرفر الوسيط</label><input id="freeServer" class="input mono" autocomplete="off" placeholder="Broker-Demo"></div>'+
   '<div class="field" style="grid-column:1/-1"><label>كلمة مرور حساب Demo</label><input id="freePassword" type="password" class="input mono" autocomplete="new-password" placeholder="••••••••"></div>'+
   '</div><p class="small subtle" style="margin-top:12px">تُرسل بيانات الدخول إلى TickerAll عبر اتصال مشفر ولا تُخزن في Sentinel.</p>',
  button("إلغاء","close-modal","btn-sm")+button("ربط الحساب","free-submit-account","btn-primary btn-sm"),true);
 }
 async function action(a){
  if(a==="free-status"){await sync();return}
  if(a==="free-key"){keyModal();return}
  if(a==="free-connect"){accountModal();return}
  try{
   if(a==="free-save-key"){
     const key=byId("freeApiKey")?.value?.trim()||"";
     if(!key){toast("أدخل API Key","error");return}
     const field=byId("freeApiKey");
     await api("saveKey",{apiKey:key});
     if(field)field.value="";
     closeModal();await sync(true);toast("تم ربط TickerAll بنجاح","success");return;
   }
   if(a==="free-submit-account"){
     if(stateMT.connecting)return;
     const login=byId("freeLogin")?.value?.trim()||"",server=byId("freeServer")?.value?.trim()||"",pwd=byId("freePassword")?.value||"";
     if(!/^\d{4,16}$/.test(login)||!server||!pwd){toast("راجع بيانات حساب الديمو","error");return}
     stateMT.connecting=true;
     try{
       const result=await api("connect",{account:login,server,password:pwd});
       if(byId("freePassword"))byId("freePassword").value="";
       closeModal();await sync(true);
       toast(result.isDemo?"تم ربط الديمو. جاري التحقق من حالة الاتصال.":"لم يتأكد الاتصال","success");
       eventLog("mt5-connect","Demo account session linked, awaiting provider confirmation");
     }finally{stateMT.connecting=false}
     return;
   }
   if(a.startsWith("free-inspect:")){
     await sync(true);
     const item=stateMT.accounts.find(x=>x.id===a.slice(13));
     toast(item?.online?"MT5 Demo ONLINE"+(item.verified?" · الرصيد محدث":" · بيانات الرصيد لم تصل بعد"):friendly(item?.verificationError||"BROKER_SNAPSHOT_FAILED"),item?.online?"success":"info");
     return;
   }
   if(a.startsWith("free-history:")){
     const id=a.slice(13),r=await api("history",{accountId:id});
     const data=r.data;
     const rows=Array.isArray(data)?data:(data?.history||data?.trades||data?.items||[]);
     showModal("سجل الصفقات · MT5",'<div class="table-wrap"><table class="table"><thead><tr><th>الرمز</th><th>النوع</th><th>النتيجة</th></tr></thead><tbody>'+
       (rows.length?rows.slice(0,25).map(x=>'<tr><td class="mono">'+esc(x.symbol||"—")+'</td><td>'+esc(x.side||x.direction||"—")+'</td><td class="mono">'+esc(x.profit??x.pnl??"—")+'</td></tr>').join(""):'<tr><td colspan="3">لا يوجد سجل متاح لهذا الحساب</td></tr>')+'</tbody></table></div>',button("إغلاق","close-modal","btn-sm"),true);
     return;
   }
   if(a.startsWith("free-symbols:")){
     const id=a.slice(13),r=await api("symbols",{accountId:id}),data=r.data;
     const symbols=(Array.isArray(data)?data:data?.symbols||[]).slice(0,250);
     showModal("رموز التداول المتاحة",'<div class="symbols-grid">'+symbols.map(x=>'<span class="tag">'+esc(typeof x==="string"?x:x.symbol||x.name||"—")+'</span>').join("")+'</div>',button("إغلاق","close-modal","btn-sm"),true);
     return;
   }
   if(a.startsWith("free-disconnect:")){
     if(!confirm("فصل اتصال هذا الحساب من TickerAll؟ هذا ما بيسكّر صفقاته عند الوسيط."))return;
     await api("disconnect",{accountId:a.slice(16)});await sync(true);toast("تم فصل الحساب","success");return;
   }
  }catch(e){toast(friendly(e.message),"error");}
 }
 async function init(){await sync(true);if(!stateMT.configured&&state.page==="overview")navigate("mt5")}
 setInterval(()=>{if(document.visibilityState==="visible"&&["mt5","overview"].includes(state.page))sync(true)},45000);
 document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible"&&["mt5","overview"].includes(state.page))sync(true)});
 return {render,sync,init,action,summary};
})();
window.FreeMT5UI.init();
