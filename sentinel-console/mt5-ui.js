/* MT5 connection page — real, agent-reported telemetry only. No broker credentials in browser. */
"use strict";
window.MT5UI=(()=>{
 let devices=[],error="",loading=false,lastCheck=null,pairing=null;
 const api=async(action,body=null)=>{
  if(!state.key)throw Error("أدخل مفتاح لوحة التحكم أولاً");
  const response=await fetch("/api/mt5?action="+encodeURIComponent(action),{
   method:body===null?"GET":"POST",
   headers:{"x-console-key":state.key,"Content-Type":"application/json"},
   body:body===null?undefined:JSON.stringify(body),cache:"no-store"
  });
  let data;
  try{data=await response.json()}catch(_){throw Error("Invalid server response")}
  if(!response.ok||!data.ok)throw Error(data.error||"MT5 connection API error");
  return data;
 };
 function statusLabel(d){
  if(d.stale)return {name:"OFFLINE",cls:"red",desc:"لم تصل إشارة Heartbeat خلال 90 ثانية"};
  if(d.connected)return {name:"DEMO CONNECTED",cls:"mint",desc:"الوكيل أبلغ عن اتصال حساب تجريبي"};
  if(d.connection_state==="revoked")return {name:"REVOKED",cls:"red",desc:"تم إلغاء ربط الجهاز"};
  return {name:"DISCONNECTED",cls:"amber",desc:"الوكيل يعمل لكن منصة MT5 غير متصلة بديمو"};
 }
 function deviceCard(d){
  const s=statusLabel(d),good=d.connected&&!d.stale;
  const age=d.age_seconds===null?"—":d.age_seconds+" sec";
  return '<section class="panel" style="margin-bottom:16px"><div class="panel-title"><div><h3>◉ '+esc(d.agent_name)+'</h3><p class="mono">DEVICE ID '+esc(String(d.agent_id).slice(0,8))+'... • '+esc(d.broker_server||"NO SERVER")+'</p></div><span class="tag '+s.cls+'">'+s.name+'</span></div>'+
  '<div class="panel-pad"><div class="grid kpi-grid" style="margin-bottom:16px">'+
  kpi("الرصيد",good?money(d.balance,d.account_currency||"USD"):"—","ACCOUNT BALANCE","#4ce3bd")+
  kpi("Equity",good?money(d.equity,d.account_currency||"USD"):"—","BROKER REPORTED","#799dff")+
  kpi("المراكز المفتوحة",good?num(d.open_positions,0):"—","OPEN POSITIONS","#ab8cff")+
  kpi("آخر نبضة",age,"HEARTBEAT AGE","#ffca80")+'</div>'+
  '<div class="form-grid">'+[
   ["حساب MT5","••••"+esc(d.account_last4||"—")],
   ["Broker Server",esc(d.broker_server||"—")],
   ["Account Mode",esc(String(d.trade_mode||"unknown").toUpperCase())],
   ["Bot Process",esc(String(d.bot_state||"unconfigured").toUpperCase())],
   ["MT5 Version",esc(d.terminal_version||"—")],
   ["Heartbeats",num(d.heartbeat_count,0)],
   ["آخر اتصال ناجح",esc(d.last_ok_at?dateFmt(d.last_ok_at)+" UTC":"—")],
   ["آخر اتصال الوكيل",esc(d.last_seen_at?dateFmt(d.last_seen_at)+" UTC":"—")]
  ].map(x=>'<div class="key-value"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join("")+'</div>'+
  (d.last_error?'<div class="notice" style="margin:15px 0 0"><strong>LAST ERROR</strong><span class="notice-small">'+esc(d.last_error)+'</span></div>':"")+
  '<div class="action-strip" style="margin-top:16px"><span class="small subtle">'+s.desc+'</span>'+button("إلغاء ربط الجهاز","mt5-revoke:"+d.agent_id,"btn-danger btn-sm")+'</div></div></section>';
 }
 function render(){
  let h=heading("MT5 CONNECTION / 02","ربط حساب MetaTrader 5","ربط آمن لحساب Demo من Windows، ومراقبة مستمرة مع إعادة الاتصال تلقائياً.",button("↻ فحص الآن","mt5-refresh","btn-sm")+button("＋ ربط حساب MT5","mt5-pair","btn-primary btn-sm"));
  if(!state.key)h+='<div class="notice"><strong>مفتاح لوحة التحكم مطلوب</strong><span class="notice-small">أدخل مفتاح Sentinel لعرض أجهزة MT5 وتوليد رمز ربط آمن.</span>'+button("إدخال المفتاح","mt5-key","btn-sm")+'</div>';
  else if(error)h+='<div class="notice"><strong>تعذّر جلب حالة الأجهزة</strong><span class="notice-small">'+esc(error)+'</span>'+button("إعادة المحاولة","mt5-refresh","btn-sm")+'</div>';
  else h+='<div class="notice info"><strong>MT5 Bridge / '+(devices.length?"ACTIVE REGISTRY":"READY FOR PAIRING")+'</strong><span class="notice-small">هذه بيانات يبلغ عنها وكيل Windows مباشرة، وليست بيانات العرض التجريبي في Dashboard.</span></div>';
  h+='<div class="grid kpi-grid">'+
  kpi("أجهزة مسجلة",num(devices.length,0),"PAIRED WINDOWS AGENTS","#799dff")+
  kpi("اتصالات Demo نشطة",num(devices.filter(d=>d.connected&&!d.stale).length,0),"HEARTBEAT < 90s","#4ce3bd")+
  kpi("أجهزة غير متصلة",num(devices.filter(d=>d.stale||!d.connected).length,0),"OFFLINE / DEGRADED","#ffca80")+
  kpi("تحديث الحالة",lastCheck?new Date(lastCheck).toLocaleTimeString("en-GB",{hour12:false}):"—","UTC / CLOUD CHECK","#ab8cff")+'</div>';
  if(devices.length)h+=devices.map(deviceCard).join("");
  else h+=panel("الأجهزة المتصلة","لا يوجد أي حساب MT5 مرتبط حتى الآن",empty("لم يتم ربط جهاز بعد","اربط Windows MT5 Agent باستخدام رمز مؤقت. لا ترسل كلمة مرور حساب التداول إلى الموقع."),button("＋ ابدأ الربط","mt5-pair","btn-sm btn-primary"));
  h+='<div class="content-grid">'+panel("الربط في 4 خطوات","ONE-TIME SECURE PAIRING",'<div class="panel-pad">'+[
   ["01","جهّز Windows MT5","افتح منصة MT5 على الكمبيوتر أو Windows VPS، وسجّل الدخول بحساب Demo فقط."],
   ["02","نزّل وكيل Sentinel","شغّل أداة التثبيت على نفس جهاز Windows الذي يعمل عليه MT5."],
   ["03","أنشئ رمز ربط","اضغط «ربط حساب MT5»، وانسخ الرمز المؤقت إلى برنامج الوكيل."],
   ["04","فعّل التشغيل التلقائي","ثبّت Scheduled Task وWatchdog، ثم راقب Heartbeat من هذه الصفحة."]
  ].map(x=>'<div class="feed-item"><div class="mono" style="color:var(--mint);font-size:17px">'+x[0]+'</div><div class="feed-body"><strong>'+x[1]+'</strong><p>'+x[2]+'</p></div></div>').join("")+
  '<div style="margin-top:16px">'+button("↓ ملف إعداد Windows","mt5-download","btn-sm")+'</div></div>')+
  panel("استمرارية التشغيل","RECOVERY & MONITORING",'<div class="panel-pad">'+[
   ["إعادة اتصال MT5","تلقائي بعد انقطاع المنصة أو الوسيط"],
   ["Heartbeat","كل 20 ثانية من Windows"],
   ["Offline Detection","إذا مرّ 90 ثانية بلا Heartbeat"],
   ["Windows Startup","Scheduled Task عند تسجيل الدخول"],
   ["Watchdog","يفحص عملية الوكيل كل 5 دقائق"],
   ["Bot Restart","اختياري فقط لبوت Demo مُعرّف محلياً"]
  ].map(x=>'<div class="key-value"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join("")+
  '<div class="notice" style="margin:16px 0 0"><strong>لا يمكن ضمان 100% Uptime</strong><span class="notice-small">إذا انطفأ الجهاز، انقطع الإنترنت، انتهت صلاحية الحساب، أو تعطلت خوادم الوسيط، قد يتوقف التداول. أفضل استضافة Windows VPS دائمة التشغيل مع مراقبة خارجية.</span></div></div>')+'</div>';
  h+='<div class="info-block"><strong>خصوصية الحساب</strong>لا نطلب رقم الحساب الكامل أو كلمة مرور الوسيط أو كلمة مرور Investor على الموقع. الوكيل يتصل بالمنصة المسجّل دخولها مسبقاً، ويُرسل فقط حالة الاتصال وآخر 4 أرقام ومعلومات الأداء. لا يمكن تنفيذ أوامر شراء أو بيع عبر Endpoint الربط.</div>';
  return h;
 }
 async function poll(silent=false){
  if(loading||!state.key)return;
  loading=true;
  try{const r=await api("status");devices=r.devices||[];lastCheck=new Date().toISOString();error=""}
  catch(e){error=e.message;if(!silent)toast("MT5: "+e.message,"error")}
  finally{loading=false;if(state.page==="mt5")renderPage()}
 }
 function showPairing(result){
  pairing=result;
  showModal("ربط Windows MT5 Agent",
   '<div class="info-block"><strong>رمز ربط لمرة واحدة • 15 دقيقة</strong>يُستخدم هذا الرمز لربط برنامج Windows بالموقع. لا تدخل بيانات الوسيط هنا.</div>'+
   '<div class="code-block" style="text-align:center;font-size:18px;letter-spacing:2px;margin:18px 0;user-select:all">'+esc(result.pairing_code)+'</div>'+
   '<p class="small subtle">1. حمّل ملفات Windows Agent. 2. افتح PowerShell في مجلدها. 3. شغّل الأمر التالي، مع استبدال الرمز:</p>'+
   '<div class="code-block" style="font-size:10px">py agent.py pair --url https://sentinel-mt5-console.vercel.app --code '+esc(result.pairing_code)+'</div>'+
   '<p class="small subtle" style="margin-top:12px">بعد نجاح الربط شغّل: <span class="mono">powershell -ExecutionPolicy Bypass -File .\\install_agent.ps1</span></p>',
   button("نسخ الرمز","mt5-copy-code","btn-sm")+button("إغلاق","close-modal","btn-sm btn-primary"),true);
 }
 async function action(op){
  if(op==="mt5-refresh"){await poll();return}
  if(op==="mt5-key"){
   showModal("مفتاح لوحة Sentinel",'<div class="field"><label>Console Access Key</label><input type="password" id="mt5ConsoleKey" class="input mono" placeholder="Private dashboard access key" value="'+esc(state.key)+'"></div><p class="small subtle">يُحفظ في sessionStorage فقط، وليس في حساب الوسيط.</p>',
    button("حفظ وفحص","mt5-save-key","btn-primary btn-sm"));return;
  }
  if(op==="mt5-save-key"){
   state.key=byId("mt5ConsoleKey")?.value.trim()||"";
   sessionStorage.setItem("sentinel_console_key",state.key);
   closeModal();await poll();return;
  }
  if(op==="mt5-pair"){
   if(!state.key){await action("mt5-key");return}
   try{const r=await api("setup",{});showPairing(r);eventLog("mt5-pairing","Created a temporary 15-minute MT5 pairing code")}
   catch(e){toast(e.message,"error")}
   return;
  }
  if(op==="mt5-copy-code"){if(pairing?.pairing_code){await navigator.clipboard.writeText(pairing.pairing_code);toast("تم نسخ الرمز","success")}return}
  if(op==="mt5-download"){window.open("https://github.com/nfliex9-crypto/Bot/tree/sentinel-console-isolated-v1/sentinel-console/mt5-agent","_blank","noopener,noreferrer");return}
  if(op.startsWith("mt5-revoke:")){
   const id=op.slice("mt5-revoke:".length);
   if(!confirm("هل تريد إلغاء ربط الجهاز؟ سيتوقف وصوله إلى لوحة التحكم، ولن يُغلق حساب MT5."))return;
   try{await api("revoke",{agent_id:id});eventLog("mt5-revoke","Device revoked: "+id.slice(0,8));toast("تم إلغاء ربط الجهاز","success");await poll(true)}
   catch(e){toast(e.message,"error")}return;
  }
 }
 setInterval(()=>{if(state.page==="mt5")poll(true)},20000);
 return {render,poll,action};
})();
