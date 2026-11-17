/* Sentinel Cloud MT5 Bridge. Standalone, no Windows, read-only demo validation. */
"use strict";
window.CloudMT5UI=(()=>{
 let info={accounts:[],token_configured:false},discover=[],error="",busy=false,lastStatus=null;
 const backend=async(action,body)=>{
   if(!state.key)throw Error("CONSOLE_KEY_REQUIRED");
   const result=await fetch("/api/cloud?action="+encodeURIComponent(action),{
     method:body===undefined?"GET":"POST",
     headers:{"Content-Type":"application/json","x-console-key":state.key},
     body:body===undefined?undefined:JSON.stringify(body),cache:"no-store"
   });
   let payload;
   try{payload=await result.json()}catch(_){throw Error("BAD_GATEWAY_RESPONSE")}
   if(!result.ok||!payload.ok)throw Error(payload.error||"CLOUD_ERROR");
   return payload;
 };
 function notice(status){
   return '<div class="notice '+(status==="ready"?"success":"info")+'"><strong>'+(
     status==="ready"?"MetaApi Cloud Bridge — جاهز للربط":"اتصال سحابي، بدون تطبيق أو جهاز Windows")+
    '</strong><div class="notice-small">منصة MetaApi تدير اتصال MT5 على خوادمها. Sentinel يعرض حالة حساب Demo ويتحقق منها عبر API. لا يتم إرسال أوامر تداول من صفحة الربط.</div></div>';
 }
 function accountCard(d){
   const isLive=d.cloud_connected;
   const invalid=d.trade_mode==="REJECTED_NON_DEMO";
   const label=invalid?"REAL/CONTEST BLOCKED":isLive?"VERIFIED DEMO":(d.error_code||d.account_state);
   const cls=invalid?"red":isLive?"mint":"amber";
   const source=d.last_verified_at?"Verified "+dateFmt(d.last_verified_at):"Not verified";
   return '<section class="panel" style="margin-bottom:15px">'+
    '<div class="panel-title"><div><h3>◉ '+esc(d.name)+'</h3><p class="mono">'+esc(d.server||"SERVER UNKNOWN")+' • ****'+esc(d.account_last4||"—")+'</p></div><span class="tag '+cls+'">'+esc(label)+'</span></div>'+
    '<div class="panel-pad"><div class="grid kpi-grid">'+
     kpi("الرصيد",isLive?money(d.balance,d.currency||"USD"):"—","BROKER API","#46e3bb")+
     kpi("Equity",isLive?money(d.equity,d.currency||"USD"):"—","BROKER API","#799dff")+
     kpi("Account Type",esc(d.trade_mode||"UNKNOWN"),"VERIFIED, NOT INFERRED",isLive?"#46e3bb":"#ffca80")+
     kpi("Connection",esc(d.connection_status),"METAAPI TERMINAL","#ad8cff")+'</div>'+
    '<div class="action-strip"><span class="small subtle">'+esc(source)+' • '+esc(d.last_checked_at?dateFmt(d.last_checked_at):"never checked")+'</span><div class="head-buttons">'+
     button("↻ تحديث حالة الحساب","cloud-refresh:"+d.id,"btn-sm")+
     button("إلغاء الربط","cloud-unlink:"+d.id,"btn-danger btn-sm")+'</div></div>'+
    (d.error_code?'<div class="notice" style="margin:12px 0 0"><span class="small">'+esc(d.error_code)+'</span></div>':"")+
    '</div></section>';
 }
 function available(){
   return '<section class="panel" style="margin-bottom:15px">'+
     '<div class="panel-title"><div><h3>حسابات MT5 المكتشفة لدى MetaApi</h3><p>اختر الحساب التجريبي الذي أضفته مسبقاً في MetaApi</p></div>'+button("↻ اكتشاف","cloud-discover","btn-sm")+'</div>'+
     (discover.length?'<div class="table-wrap"><table class="table"><thead><tr><th>الحساب</th><th>السيرفر</th><th>المنصة</th><th>Cloud State</th><th>التنفيذ</th></tr></thead><tbody>'+
     discover.map(x=>'<tr><td>'+esc(x.name)+' <span class="dim mono">****'+esc(x.last4)+'</span></td><td class="mono">'+esc(x.server)+'</td><td>'+esc(x.platform)+'</td><td><span class="tag">'+esc(x.connectionStatus)+' / '+esc(x.state)+'</span></td><td>'+button("ربط","cloud-link:"+x.id,"btn-sm btn-primary")+'</td></tr>').join("")+'</tbody></table></div>':
     empty("اضغط اكتشاف الحسابات","إذا ما ظهر حساب، افتح MetaApi وأضف حساب MT5 Demo من لوحة مزود الخدمة أولاً."))+
     '</section>';
 }
 function render(){
   let h=heading("CLOUD MT5 / NO WINDOWS","MT5 Cloud Bridge","ربط MT5 Demo عبر السحابة من الموقع مباشرة — بدون تنزيل ملفات أو إبقاء الكمبيوتر مفتوحاً.",
      button("↻ تحديث","cloud-status","btn-sm")+
      '<a class="btn btn-primary" href="https://app.metaapi.cloud/accounts" target="_blank" rel="noopener noreferrer">MetaApi Portal ↗</a>');
   if(!state.key)h+='<div class="notice"><strong>مفتاح Sentinel مطلوب</strong><span class="notice-small">ادخل مفتاح لوحة التحكم في زر الاتصال أعلى الصفحة.</span>'+button("تسجيل الدخول","open-connect","btn-sm")+'</div>';
   else if(error)h+='<div class="notice"><strong>حالة الاتصال</strong><span class="notice-small">'+esc(error)+'</span></div>';
   else h+=notice(info.token_configured?"ready":"new");
   h+='<div class="grid kpi-grid">'+kpi("طريقة الربط","CLOUD","NO WINDOWS REQUIRED","#4ce3bd")+
     kpi("الحسابات",String(info.accounts?.length||0),"LINKED MT5 ACCOUNTS","#799dff")+
     kpi("حسابات Demo المتصلة",String((info.accounts||[]).filter(x=>x.cloud_connected).length),"VERIFIED FROM BROKER API","#4ce3bd")+
     kpi("MetaApi Token",info.token_configured?"SAVED":"NOT SET","AES-256-GCM ENCRYPTED",info.token_configured?"#4ce3bd":"#ffca80")+'</div>';
   h+='<div class="hero"><div class="hero-label">CLOUD-FIRST WORKFLOW</div><h2>اربط حساب التداول من هاتفك، وخلي اتصال MT5 عند MetaApi.</h2><p>أضف حسابك في MetaApi نفسه، ثم اربط مفتاح API بواجهة Sentinel. ما رح نطلب منك كلمة مرور MT5 هون، ولا أي برنامج Windows.</p><div class="hero-actions">'+
    '<a class="btn btn-primary" href="https://app.metaapi.cloud/accounts" target="_blank" rel="noopener noreferrer">① افتح MetaApi ↗</a>'+
    button(info.token_configured?"تغيير MetaApi Token":"② ربط مفتاح MetaApi","cloud-token","btn-sm")+
    (info.token_configured?button("③ اكتشاف الحسابات","cloud-discover","btn-sm"): "")+
    '</div></div>';
   if(info.token_configured){
      h+=available();
      if(info.accounts?.length)h+=info.accounts.map(accountCard).join("");
   }
   h+='<div class="content-grid">'+panel("تشغيل مستقر 24/7","INFRASTRUCTURE / CLOUD",'<div class="panel-pad">'+[
      ["MT5 terminal hosting","MetaApi Cloud — لا يحتاج جهازك"],
      ["Broker connection","MetaApi cloud account DEPLOYED"],
      ["Read account balance","REST API, when verified Demo"],
      ["Verify account type","ACCOUNT_TRADE_MODE_DEMO only"],
      ["Trading strategy engine","غير مربوط بعد — يحتاج خدمة تشغيل مستقلة"],
      ["Unlimited uptime guarantee","غير ممكن تقنياً"]
   ].map(a=>'<div class="key-value"><span>'+a[0]+'</span><strong>'+a[1]+'</strong></div>').join("")+'</div>')+
   panel("حدود التكامل","SERVICE STATUS / IMPORTANT",'<div class="panel-pad"><div class="info-block"><strong>الحساب التجريبي فقط</strong>ما بنعتمد على اسم السيرفر لتحديد Demo. الربط بيتأكد من نوع الحساب الفعلي عبر MetaApi Account Information.</div><div class="info-block" style="margin-top:11px"><strong>المحرك المنفصل</strong>وجود اتصال سحابي ما بيشغّل استراتيجية البوت القديمة تلقائياً. تشغيلها المستمر يحتاج Worker مستقل على استضافة مناسبة.</div><div style="margin-top:16px">'+button("حذف مفتاح MetaApi","cloud-forget-token","btn-danger btn-sm",!info.token_configured)+'</div></div>')+'</div>';
   return h;
 }
 async function status(silent=false){
   if(busy||!state.key)return;
   busy=true;
   try{info=await backend("status");error="";lastStatus=new Date().toISOString()}
   catch(e){error=e.message;if(!silent)toast("Cloud MT5: "+e.message,"error")}
   finally{busy=false;if(state.page==="mt5")renderPage()}
 }
 function tokenModal(){
   showModal("ربط MetaApi Cloud",
    '<div class="info-block"><strong>لا تدخل بيانات الوسيط</strong>سجّل حساب MT5 عند MetaApi أولاً، ثم انسخ MetaApi API Token من حسابك عندهم. Sentinel يحفظ التوكن مشفراً داخل قاعدة البيانات ولا يعرضه مرة أخرى.</div>'+
    '<div class="field" style="margin-top:18px"><label>MetaApi API Token</label><input class="input mono" type="password" autocomplete="off" id="cloudToken" placeholder="MetaApi account/API token"></div>'+
    '<p class="small subtle">هذه الخطوة تستدعي MetaApi للتحقق من الرمز قبل حفظه. لا تضع التوكن في المحادثة أو ملفات GitHub.</p>',
    button("إلغاء","close-modal","btn-sm")+button("تحقق واحفظ","cloud-save-token","btn-primary btn-sm"));
 }
 async function action(op){
   try{
    if(op==="cloud-status"){await status();return}
    if(op==="cloud-token"){tokenModal();return}
    if(op==="cloud-save-token"){
      const value=byId("cloudToken")?.value.trim();
      if(!value){toast("أدخل MetaApi Token","error");return}
      await backend("token",{token:value});byId("cloudToken").value="";closeModal();
      discover=[];await status(true);eventLog("cloud-token","Encrypted MetaApi API token configured");
      toast("تم ربط وتشفير MetaApi Token","success");return;
    }
    if(op==="cloud-discover"){
      const d=await backend("discover");discover=d.accounts||[];renderPage();
      toast("تم اكتشاف "+discover.length+" حساب MT5","success");return;
    }
    if(op.startsWith("cloud-link:")){
      const id=op.slice("cloud-link:".length);
      const data=await backend("link",{provider_account_id:id});
      await status(true);
      const active=data.account?.cloud_connected;
      toast(active?"تم تأكيد اتصال حساب Demo":"تم حفظ الحساب، لم يتم تأكيد Demo متصل بعد",active?"success":"info");
      return;
    }
    if(op.startsWith("cloud-refresh:")){
      const id=op.slice("cloud-refresh:".length);
      const d=await backend("refresh",{id});await status(true);
      toast(d.account?.cloud_connected?"تم التحقق من اتصال Demo":"الحساب غير جاهز أو نوعه غير مؤكد",d.account?.cloud_connected?"success":"info");
      return;
    }
    if(op.startsWith("cloud-unlink:")){
      if(!confirm("إزالة ربط هذا الحساب من Sentinel فقط؟ سيبقى الحساب موجوداً لدى MetaApi."))return;
      await backend("unlink",{id:op.slice("cloud-unlink:".length)});await status(true);
      toast("تم حذف الربط المحلي","success");return;
    }
    if(op==="cloud-forget-token"){
      if(!confirm("حذف MetaApi API Token من Sentinel؟ ستتوقف عمليات التحقق إلى حين إعادة ربطه."))return;
      await backend("forget-token",{});discover=[];await status(true);
      toast("تم حذف MetaApi Token","success");return;
    }
   }catch(e){toast(e.message,"error")}
 }
 setInterval(()=>{if(state.page==="mt5")status(true)},30000);
 return {render,status,action};
})();