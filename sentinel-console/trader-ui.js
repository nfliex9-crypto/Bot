"use strict";
/* Read-only dashboard for independent cloud and optional local MT5 DEMO engines. */
window.SentinelTrader=(()=>{
 let snapshot=null,loaded=false;
 const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
 function render(){
  const cloud=snapshot?.cloud||{status:"NOT_INSTALLED",mode:"SHADOW_ONLY",observations:[],orders_sent:0};
  const rows=(cloud.observations||[]).map(s=>`<tr><td>${esc(s.symbol)}</td><td>${esc(s.status)}</td><td>${esc(s.strategy||"—")}</td><td>${esc(s.side||"—")}</td><td>${esc(s.risk_at_stop??"—")}</td><td>${esc(s.trades_submitted||0)}</td></tr>`).join("");
  const cloudPanel=`<section class="trader-panel"><div class="trader-eyebrow">SENTINEL / TICKERALL / CLOUD DEMO</div>
    <h2>بوت Sentinel السحابي المستقل</h2>
    <p>يرتبط بحساب MT5 الموجود في موقعنا. وضع البحث لا يفتح أي صفقة، ولا يحتاج Windows.</p>
    <div class="trader-alert">${esc(cloud.status)} • ${esc(cloud.reason||"لم يبدأ الفحص السحابي بعد")}</div>
    <div class="trader-metadata">الوضع: ${esc(cloud.mode)} | حساب Demo •••• ${esc(cloud.account_last4||"—")} | أوامر مرسلة: ${esc(cloud.orders_sent||0)} | آخر فحص: ${esc(cloud.observed_at||"—")}</div>
    <table class="trader-table"><thead><tr><th>السوق</th><th>القرار</th><th>الاستراتيجية</th><th>الاتجاه</th><th>المخاطرة المقدّرة</th><th>الأوامر</th></tr></thead><tbody>${rows||'<tr><td colspan="6">لا يوجد تحليل سحابي مكتمل حالياً</td></tr>'}</tbody></table>
    <p class="trader-muted">هذه بيانات مراقبة وليست تأكيداً لصفقات مكتملة. الموقع لا يوفر أمر تداول عن بُعد.</p>
   </section>`;
  const top=`<section class="trader-panel"><div class="trader-eyebrow">SENTINEL / INDEPENDENT TRADER</div>
   <h2>نظام التداول الخاص بنا</h2>
   <p>مستقل عن Grok. المسار السحابي عبر TickerAll، ومسار Windows المحلي اختياري للتحليل وOrder Book.</p>
   <div class="trader-alert">${!loaded?"جارٍ قراءة الحالة":snapshot?.ok?"حالة محركات Sentinel من قاعدة البيانات":"الاتصال ببيانات الحالة غير متوفر"}</div></section>`;
  const natives=(!snapshot?.trader?.length)?`<section class="trader-panel"><strong>عميل Windows غير متصل.</strong><p>المسار المحلي اختياري، ولا يمنع البحث عبر TickerAll.</p></section>`:
    snapshot.trader.map(d=>{
      const symbols=(d.symbols||[]).map(s=>`<tr><td>${esc(s.symbol)}</td><td>${esc(s.status)}</td><td>${esc(s.brain_status||"—")}</td><td>${esc(s.orderbook_status||"—")}</td><td>${esc(s.order_submissions||0)}</td></tr>`).join("");
      return `<section class="trader-panel"><div class="trader-status-line"><strong>${d.status==="DEMO_TELEMETRY_FRESH"?"Windows Demo متصل":"Windows Demo غير متصل"}</strong><span>حساب •••• ${esc(d.account_last4)}</span></div>
      <table class="trader-table"><thead><tr><th>السوق</th><th>الحالة</th><th>العقل</th><th>Order Book</th><th>الأوامر</th></tr></thead><tbody>${symbols||'<tr><td colspan="5">لا يوجد رصد محلي</td></tr>'}</tbody></table></section>`;
    }).join("");
  return top+cloudPanel+natives;
 }
 async function refresh(){
  try{const r=await fetch("/api/trader",{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"});snapshot=r.ok?await r.json():null}catch(_){snapshot=null}
  loaded=true;
  if(document.querySelector('.nav-item.active[data-nav="sentinel_trader"]')){
   const el=document.getElementById("page");if(el)el.innerHTML=render();
  }
 }
 return {render,refresh};
})();
