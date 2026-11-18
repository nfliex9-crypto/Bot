/* Sentinel Free MT5 Demo Bridge — TickerAll, no Windows, no paid plans. */
"use strict";
window.FreeMT5UI=(()=>{
 let accounts=[],configured=false,loading=false,error="",lastSync=null,details={},pending=false;
 async function api(action,body){
   if(!state.key)throw Error("أدخل مفتاح لوحة Sentinel بالأعلى أولاً");
   const r=await fetch("/api/free-mt5?action="+encodeURIComponent(action),{
     method:body===undefined?"GET":"POST",
     headers:{"Content-Type":"application/json","x-console-key":state.key},
     body:body===undefined?undefined:JSON.stringify(body),
     cache:"no-store"
   });
   let json=null;
   try{json=await r.json()}catch(_){throw Error("تعذّر قراءة استجابة السيرفر")}
   if(!r.ok||!json?.ok)throw Error(json?.error||"BRIDGE_FAILED");
   return json;
 }
 const asMoney=(v,c)=>v==null?"—":money(v,c||"USD");
 function card(a){
   const d=details[a.id],isReady=a.isDemo&&a.hot&&d?.online===true;
   const badgeState=!a.isDemo?"REAL BLOCKED":isReady?"DEMO VERIFIED":a.hot?"CHECKING":"COLD / OFFLINE";
   return '<section class="panel" style="margin-bottom:13px">'+
    '<div class="panel-title"><div><h3>◉ MT5 · '+esc(a.accountNumber||"****")+'</h3><p class="mono">'+esc(a.server||"UNKNOWN")+'</p></div><span class="tag '+(isReady?"mint":a.isDemo?"amber":"red")+'">'+badgeState+'</span></div>'+
    '<div class="panel-pad"><div class="grid kpi-grid">'+
    kpi("الرصيد",isReady?asMoney(d.balance,d.currency):"—","MT5 ACCOUNT","#4ce3bd")+
    kpi("Equity",isReady?asMoney(d.equity,d.currency):"—","BROKER DATA","#799dff")+
    kpi("المراكز المفتوحة",isReady?num(d.positions?.length||0,0):"—","POSITIONS","#ab8cff")+
    kpi("Connection",a.hot?"HOT":"COLD","FREE TIER","#ffca80")+
    '</div><div class="action-strip"><span class="small subtle">'+
     (a.hot?"الجلسة السحابية نشطة":"الجلسة انتهت أو بردت؛ قد تحتاج إعادة اتصال")+
     '</span><div class="head-buttons">'+
     button("↻ فحص الحساب","free-inspect:"+a.id,"btn-sm",!a.isDemo)+
     button("إلغاء الربط","free-disconnect:"+a.id,"btn-danger btn-sm",!a.isDemo)+
     '</div></div>'+
     (a.hot===false?'<div class="notice" style="margin-top:12px;margin-bottom:0">الخطة المجانية ممكن تنهي الجلسة بعد الخمول. إذا ظهر COLD، استخدم زر إعادة الاتصال وأدخل كلمة مرور الديمو من جديد.</div>':"")+
     '</div></section>';
 }
 function render(){
   const connected=accounts.filter(a=>a.isDemo&&a.hot).length;
   let page=heading("ZERO-COST MT5 / DEMO ONLY","MT5 Bridge مجاني",
      "بدون MetaApi المدفوع، بدون Windows، وبدون VPS. ربط مباشر مع TickerAll Free لحسابات MT5 التجريبية.",
      button("↻ تحديث","free-status","btn-sm")+
      '<a class="btn btn-primary" href="https://tickerall.com/sign-up" target="_blank" rel="noopener noreferrer">إنشاء حساب مجاني ↗</a>');
   if(error)page+='<div class="notice"><strong>حالة الربط</strong><span class="notice-small">'+esc(error)+'</span>'+button("إعادة المحاولة","free-status","btn-sm")+'</div>';
   else page+='<div class="notice success"><strong>ZERO SUBSCRIPTION</strong><span class="notice-small">الخطة المجانية المعلنة تدعم 5 حسابات Demo بدون بطاقة، مع اتصال قد يبرد عند الخمول. لا يوجد أي اشتراك مدفوع مفعّل عبر Sentinel.</span></div>';
   page+='<div class="grid kpi-grid">'+
     kpi("التكلفة الأساسية","$0","TICKERALL FREE DEMO","#4ce3bd")+
     kpi("الحسابات",num(accounts.length,0),"MT5 ACCOUNT LINKS","#799dff")+
     kpi("جلسات نشطة",num(connected,0),"BROKER CONNECTIONS","#4ce3bd")+
     kpi("حساب TickerAll",configured?"CONNECTED":"NOT SET","API AUTH","#ffca80")+'</div>';
   page+='<div class="hero"><div class="hero-label">NO WINDOWS · NO METAAPI FEES</div><h2>ربط MT5 التجريبي من الجوال مباشرة</h2><p>أنشئ مفتاح API مجاني من TickerAll واحفظه هنا بشكل مشفّر. بعدها اربط حساب MT5 التجريبي باستخدام Login وServer وكلمة مرور التداول مرة واحدة. ما بنحتفظ بكلمة مرور الوسيط.</p><div class="hero-actions">'+
     '<a class="btn btn-primary" href="https://tickerall.com/sign-up" target="_blank" rel="noopener noreferrer">1. حساب TickerAll مجاني ↗</a>'+
     button(configured?"تغيير مفتاح API":"2. ربط مفتاح API","free-key","btn-sm")+
     (configured?button("3. ربط MT5 Demo","free-connect","btn-sm"):"")+
     '</div></div>';
   if(configured){
     page+=panel("حسابات MT5 المرتبطة","من TickerAll API فعلي وليس من بيانات تجريبية",
      accounts.length?'<div class="panel-pad"><span class="small subtle">'+accounts.length+' حساب</span></div>':empty("ما في حساب متصل بعد","اضغط «ربط MT5 Demo» وأدخل بيانات حسابك التجريبي."));
     page+=accounts.map(card).join("");
   }
   page+='<div class="content-grid">'+
    panel("كيف رح يشتغل بدون مصاريف؟","FREE DEMO SERVICE",'<div class="panel-pad">'+[
      ["1","TickerAll Free","5 حسابات MT5 Demo وطلبات تجريبية غير محدودة وفق العرض المنشور"],
      ["2","Sentinel","حفظ API Key مشفّر وقراءة حسابك بدون رسوم MetaApi"],
      ["3","أوقات الخمول","الربط ممكن يبرد؛ إعادة الاتصال اليدوية متاحة"],
      ["4","التداول الآلي المستمر","يتطلب Worker دائم لم يتم نشره؛ الموقع لوحده لا يشغّل استراتيجية 24/7"]
    ].map(x=>'<div class="feed-item"><div class="mono" style="color:var(--mint);font-size:17px">'+x[0]+'</div><div class="feed-body"><strong>'+x[1]+'</strong><p>'+x[2]+'</p></div></div>').join("")+
    '</div>')+
    panel("الأمان والاستمرارية","NEVER CLAIM INFINITE UPTIME",'<div class="panel-pad">'+[
      ["الحسابات المسموحة","DEMO ONLY"],
      ["الأوامر الحقيقية","غير مفعّلة"],
      ["حفظ كلمة مرور MT5","لا"],
      ["API Token","AES-256-GCM مشفّر"],
      ["Always-hot مدفوع","غير مفعّل"],
      ["ضمان تشغيل 24/7","غير متاح على الخطة المجانية"]
    ].map(x=>'<div class="key-value"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join("")+
    '<div style="margin-top:15px">'+button("حذف مفتاح TickerAll","free-forget","btn-sm btn-danger",!configured)+'</div></div>')+'</div>';
   return page;
 }
 async function status(silent=false){
  if(loading||!state.key)return;
  loading=true;
  try{
   const x=await api("status");
   accounts=x.accounts||[];configured=x.configured===true;
   lastSync=x.generatedAt;error="";
  }catch(e){error=e.message;if(!silent)toast("Free MT5: "+e.message,"error")}
  finally{loading=false;if(state.page==="mt5")renderPage()}
 }
 function keyModal(){
   showModal("مفتاح TickerAll المجاني",'<div class="info-block"><strong>API key وليس كلمة مرور MT5</strong>افتح TickerAll → API Keys، أنشئ مفتاحاً للخطة Free الخاصة بحسابات Demo، وبعدها الصقه هنا. لا ترسل المفتاح بالمحادثة.</div>'+
    '<div class="field" style="margin-top:16px"><label>TickerAll API Key</label><input id="freeApiKey" class="input mono" type="password" autocomplete="off" placeholder="cf_api_..."></div>'+
    '<div style="margin-top:15px"><a href="https://tickerall.com/docs" target="_blank" rel="noopener noreferrer">الشرح الرسمي للمفتاح ↗</a></div>',
    button("إلغاء","close-modal","btn-sm")+button("احفظ المفتاح","free-save-key","btn-sm btn-primary"));
 }
 function accountModal(){
  showModal("ربط حساب MT5 Demo",'<div class="info-block"><strong>DEMO ONLY · NO PAID ACCOUNT</strong>استخدم فقط رقم حساب MT5 التجريبي وبيانات الوسيط. كلمة مرور التداول تنتقل إلى TickerAll للتحقق، ولا تُحفظ عندنا.</div>'+
   '<div class="form-grid" style="margin-top:17px"><div class="field"><label>MT5 Demo Login</label><input id="freeLogin" inputmode="numeric" class="input mono" placeholder="12345678"></div>'+
   '<div class="field"><label>Broker Server</label><input id="freeServer" class="input mono" placeholder="Broker-Demo"></div>'+
   '<div class="field" style="grid-column:1/-1"><label>MT5 Trading Password</label><input id="freePassword" type="password" class="input mono" autocomplete="off" placeholder="Demo account password"></div></div>'+
   '<p class="small subtle" style="margin-top:12px">لا تستخدم حساب Real. ما بنطلب بيانات خاصة أو كلمات مرور بالمحادثة.</p>',
   button("إلغاء","close-modal","btn-sm")+button("ربط حساب Demo","free-submit-account","btn-primary btn-sm"),true);
 }
 async function action(op){
  if(op==="free-status"){await status();return}
  if(op==="free-key"){keyModal();return}
  if(op==="free-connect"){accountModal();return}
  try{
   if(op==="free-save-key"){
     const value=byId("freeApiKey")?.value.trim()||"";
     if(!value){toast("أدخل API Key","error");return}
     await api("saveKey",{apiKey:value});
     byId("freeApiKey").value="";
     closeModal();await status(true);toast("مفتاح TickerAll جاهز ومشفّر","success");
     return;
   }
   if(op==="free-submit-account"){
     if(pending)return;pending=true;
     try{
       const account=byId("freeLogin")?.value.trim()||"";
       const server=byId("freeServer")?.value.trim()||"";
       const password=byId("freePassword")?.value||"";
       if(!account||!server||!password){toast("أكمل حقول حساب الديمو","error");return}
       const res=await api("connect",{account,server,password});
       if(byId("freePassword"))byId("freePassword").value="";
       closeModal();
       await status(true);
       toast("تم ربط حساب MT5 Demo بنجاح","success");
       eventLog("free-mt5","Cloud MT5 demo session connected: "+res.accountId?.slice(0,8));
     }finally{pending=false}
     return;
   }
   if(op.startsWith("free-inspect:")){
     const id=op.slice("free-inspect:".length);
     const result=await api("inspect",{accountId:id});
     details[id]=result.account;
     renderPage();
     toast(result.account.online?"حساب Demo متصل وموثق":"الحساب بارد أو خارج الاتصال",result.account.online?"success":"info");
     return;
   }
   if(op.startsWith("free-disconnect:")){
     if(!confirm("إلغاء ربط الحساب من TickerAll فقط؟ لا يلغي صفقات الوسيط المفتوحة."))return;
     const id=op.slice("free-disconnect:".length);
     await api("disconnect",{accountId:id});
     delete details[id];await status(true);toast("تم فصل حساب Demo","success");return;
   }
   if(op==="free-forget"){
     if(!confirm("حذف API Key من Sentinel؟ لن يتمكن الموقع من قراءة الحسابات حتى تعيد ربطه."))return;
     await api("forgetKey",{});accounts=[];details={};await status(true);
     toast("تم حذف المفتاح المشفّر","success");return;
   }
  }catch(e){
   toast(e.message==="TICKERALL_KEY_REJECTED"?"المفتاح مرفوض أو غير مخوّل":e.message,"error");
  }
 }
 setInterval(()=>{if(state.page==="mt5")status(true)},30000);
 return {render,status,action};
})();