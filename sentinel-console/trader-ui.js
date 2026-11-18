"use strict";
/* Owner Dashboard view: read-only device status, never trading controls. */
window.SentinelTrader=(()=>{
 let snapshot=null,loaded=false;
 const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
 function render(){
  const top=`<section class="trader-panel"><div class="trader-eyebrow">SENTINEL / INDEPENDENT ENGINE</div>
   <h2>بوت Sentinel المستقل</h2>
   <p>هذا البوت منفصل عن Grok، ومراقبته قراءة فقط. فتح الصفقات يتم حصرياً داخل MT5 Demo على جهاز مستقل، بعد التفعيل المحلي.</p>
   <div class="trader-alert">${!loaded?"جارٍ فحص حالة المحرك":snapshot?.ok?"بيانات جهاز تجريبي — نتائج الإرسال ليست تأكيداً لتنفيذ الصفقة":"غير متصل أو لم تُنشر التحديثات بعد"}</div></section>`;
  if(!snapshot?.ok||!snapshot.trader?.length)return top+`<section class="trader-panel"><strong>لا يوجد بوت Sentinel مستقل متصل حالياً.</strong><p>لا توجد صفقات أو أرصدة افتراضية للعرض.</p></section>`;
  return top+snapshot.trader.map(device=>{
   const fresh=device.status==="DEMO_TELEMETRY_FRESH";
   const instruments=(device.symbols||[]).map(s=>`<tr><td>${esc(s.symbol)}</td><td>${esc(s.status)}</td><td>${esc(s.strategy||"—")}</td><td>${esc(s.side||"—")}</td><td>${esc(s.brain_status||"—")}</td><td>${esc(s.orderbook_status||"—")}${s.book_imbalance===undefined?"":` (${esc(s.book_imbalance)})`}</td><td>${esc(s.order_submissions||0)}</td></tr>`).join("");
   return `<section class="trader-panel"><div class="trader-status-line"><strong>${fresh?"متصل — Demo":"غير متصل / بيانات قديمة"}</strong><span>حساب Demo •••• ${esc(device.account_last4)}</span></div>
    <div class="trader-metadata">وضع المحرك: ${esc(device.mode)} | سياسة العقل: ${esc(device.strategy_policy||"—")} | عمق السوق: ${esc(device.orderbook_mode||"—")} | تفعيل محلي: ${device.execution_armed?"Demo enabled":"غير مفعل"}</div>
    <table class="trader-table"><thead><tr><th>الرمز</th><th>الحالة</th><th>الاستراتيجية</th><th>الاتجاه</th><th>قرار العقل</th><th>Order Book</th><th>طلبات أُرسلت</th></tr></thead><tbody>${instruments||'<tr><td colspan="7">ما في بيانات إشارات جديدة</td></tr>'}</tbody></table>
    <p class="trader-muted">لا يوجد تأكيد لصفقات مكتملة من هذه الشاشة. لا يمكن إصدار أوامر تداول من الموقع.</p></section>`;
  }).join("");
 }
 async function refresh(){
  try{const r=await fetch("/api/trader",{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"});
    snapshot=r.ok?await r.json():null;
  }catch(_){snapshot=null}
  loaded=true;
  if(document.querySelector('.nav-item.active[data-nav="sentinel_trader"]')){
   const page=document.getElementById("page");if(page)page.innerHTML=render();
  }
 }
 return {render,refresh};
})();
