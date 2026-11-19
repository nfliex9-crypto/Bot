"use strict";
/**
 * Sentinel Command Center V3 — read-only, broker-grounded.
 * UI polling is 20s; trading scans are ~5m and research scans ~15m.
 * No mocked P&L, equity curves, broker positions, or order buttons.
 */
window.SentinelLive=(()=>{
  let snapshot=null,lastError="",fetching=false,lastFetched=0,activeTab="fills";
  const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  })[c]);
  const num=(v,maximum=2)=>{
    if(v===null||v===undefined||v==="")return "—";
    const n=Number(v);return Number.isFinite(n)?new Intl.NumberFormat("en-GB",{maximumFractionDigits:maximum}).format(n):"—";
  };
  const money=(v,currency)=>{
    if(v===null||v===undefined||!currency||!Number.isFinite(Number(v)))return "—";
    try{return new Intl.NumberFormat("en-GB",{style:"currency",currency,maximumFractionDigits:2}).format(Number(v))}
    catch(_){return num(v)+" "+esc(currency)}
  };
  const localTime=t=>{
    const d=new Date(t);return t&&!Number.isNaN(d.getTime())?
      new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Brussels",day:"2-digit",
        month:"short",hour:"2-digit",minute:"2-digit",hour12:false}).format(d):"—";
  };
  const shortAge=seconds=>{
    if(seconds===null||seconds===undefined||!Number.isFinite(Number(seconds)))return "غير معروف";
    if(seconds<60)return Math.round(seconds)+" ثانية";
    if(seconds<3600)return Math.floor(seconds/60)+" دقيقة";
    return Math.floor(seconds/3600)+" ساعة";
  };
  const safeStatus=s=>esc(String(s||"UNKNOWN").replace(/_/g," "));
  const fresh=seconds=>Number.isFinite(Number(seconds))&&seconds!==null&&seconds>=0&&seconds<=480;
  function statusPill(active,text){
    return '<span class="lc-status '+(active?"lc-positive":"lc-warning")+'"><span class="lc-dot"></span>'+esc(text)+'</span>';
  }
  function sparkline(points){
    const vals=(points||[]).map(x=>Number(x.mid)).filter(Number.isFinite);
    if(vals.length<3)return '<div class="lc-no-chart">بانتظار عينات أسعار كافية لرسم الحركة الفعلية</div>';
    const min=Math.min(...vals),max=Math.max(...vals),spread=Math.max(max-min,Math.max(Math.abs(max),1)*0.00001);
    const coords=vals.map((v,i)=>[(i/(vals.length-1))*280,75-(v-min)/spread*59-7]);
    const line=coords.map(p=>p.map(n=>n.toFixed(2)).join(",")).join(" ");
    const area="0,82 "+line+" 280,82";
    const direction=vals[vals.length-1]>=vals[0]?"up":"down";
    return '<svg class="lc-spark '+direction+'" viewBox="0 0 280 88" role="img" aria-label="حركة عينات الأسعار الحقيقية">'+
      '<path d="M0 44 H280" stroke="#33445a" stroke-width=".6" stroke-dasharray="3 6"/>'+
      '<polygon points="'+area+'" fill="currentColor" opacity=".08"/>'+
      '<polyline points="'+line+'" stroke="currentColor" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'+
      '</svg>';
  }
  function marketCard(m){
    const available=m.contract_status==="BROKER_CONTRACT_VERIFIED"&&m.quote_ready===true&&
      m.quote&&m.quote_age_seconds!==null&&m.quote_age_seconds<=600;
    const code=esc(m.symbol),q=m.quote||{};
    const title={XAUUSD:"الذهب",BTCUSD:"البيتكوين",EURUSD:"يورو / دولار",NAS100:"ناسداك"}[m.symbol]||m.symbol;
    return '<article class="lc-market '+(available?"lc-available":"lc-limited")+'">'+
      '<div class="lc-market-head"><div><span class="lc-market-symbol">'+code+'</span><h3>'+esc(title)+'</h3></div>'+
      statusPill(available,available?"أسعار موثقة":"بيانات محدودة")+'</div>'+
      '<div class="lc-market-price" dir="ltr">'+(available?num(q.mid,m.symbol==="EURUSD"?5:2):"—")+'</div>'+
      '<div class="lc-market-caption">منتصف آخر سعر Bid / Ask موثّق</div>'+
      sparkline(m.history)+
      '<div class="lc-market-foot"><span>Spread <strong dir="ltr">'+
        (m.spread_bps===null?"—":num(m.spread_bps,3)+" bps")+'</strong></span>'+
        '<span>عينة: '+esc(shortAge(m.quote_age_seconds))+'</span></div>'+
      '<div class="lc-market-state">'+safeStatus(m.status)+
        (m.contract_status==="BROKER_CONTRACT_VERIFIED"?' <span class="lc-tick">✓ Contract</span>':"")+
      '</div></article>';
  }
  function stat(label,value,description,kind){
    return '<article class="lc-stat lc-'+kind+'"><span class="lc-stat-label">'+esc(label)+
      '</span><div class="lc-stat-value" dir="ltr">'+value+'</div>'+
      '<div class="lc-stat-description">'+esc(description)+'</div></article>';
  }
  function renderTrades(d){
    const fills=d.trades?.recent||[],orders=d.trades?.orders||[];
    let rows="";
    if(activeTab==="fills"){
      rows=fills.map(f=>'<tr><td><strong>'+esc(f.symbol)+'</strong><small>'+esc(f.family)+'</small></td>'+
        '<td><span class="lc-side">'+esc(f.side)+'</span></td>'+
        '<td class="'+(f.net!==null&&f.net<0?"lc-loss":"lc-gain")+' lc-mono" dir="ltr">'+
        money(f.net,f.currency)+'</td><td>'+esc(localTime(f.closed_at))+'</td>'+
        '<td><span class="lc-status lc-positive">Broker history</span></td></tr>').join("");
    }else{
      rows=orders.map(o=>'<tr><td><strong>'+esc(o.symbol)+'</strong><small>'+esc(o.family)+'</small></td>'+
        '<td class="lc-mono">'+esc(o.side)+'</td><td colspan="2">'+
        safeStatus(o.status)+'</td><td>'+esc(localTime(o.updated_at))+'</td></tr>').join("");
    }
    return '<section class="lc-panel lc-trade-panel"><div class="lc-section-top"><div><span class="lc-kicker">EXECUTION LEDGER</span>'+
      '<h2>الصفقات والتحقق من التنفيذ</h2><p>السجل الحقيقي من Neon، وليس نتائج Backtest</p></div>'+
      '<div class="lc-toggle" role="group" aria-label="نوع السجل">'+
      '<button type="button" data-lc-tab="fills" class="'+(activeTab==="fills"?"selected":"")+'">المغلقة</button>'+
      '<button type="button" data-lc-tab="orders" class="'+(activeTab==="orders"?"selected":"")+'">الأوامر</button></div></div>'+
      '<div class="lc-table-wrap"><table class="lc-table"><thead><tr><th>الرمز / الاستراتيجية</th>'+
      '<th>الاتجاه</th><th>'+(activeTab==="fills"?"صافي النتيجة":"الحالة")+'</th><th>'+
      (activeTab==="fills"?"وقت الإغلاق":"")+'</th><th>المصدر / الوقت</th></tr></thead><tbody>'+
      (rows||'<tr><td colspan="5" class="lc-empty">لا توجد سجلات موثقة من هذا النوع حتى الآن</td></tr>')+
      '</tbody></table></div></section>';
  }
  function renderBrain(d){
    const brain=d.brain||{},health=d.health||{},last=brain.last_market||{};
    const quality=last.missing_spread_ratio===1||last.reason==="BROKER_DATA_QUALITY_GATE";
    return '<section class="lc-panel lc-brain-panel"><div class="lc-section-top">'+
      '<div><span class="lc-kicker">RESEARCH ENGINE</span><h2>نشاط عقل Sentinel</h2>'+
      '<p>مصادر السوق، اختبارات الاستراتيجيات، وجودة البيانات</p></div>'+
      statusPill(health.brain==="FRESH","بحث "+(health.brain==="FRESH"?"حديث":"متأخر"))+'</div>'+
      '<div class="lc-brain-metrics"><div><small>دورات بحث / 24 ساعة</small><strong>'+num(brain.cycles_24h,0)+'</strong></div>'+
      '<div><small>المرشحون المعتمدون</small><strong>'+num(brain.candidates,0)+'</strong></div>'+
      '<div><small>اختبارات Brain المسجلة</small><strong>'+num(brain.analyses,0)+'</strong></div></div>'+
      '<div class="lc-quality '+(quality?"lc-quality-alert":"")+'">'+
      '<span class="lc-quality-icon">!</span><div><strong>'+(quality?"جودة التكاليف التاريخية غير مكتملة":"نتائج البحث قيد المراجعة")+'</strong>'+
      '<p>'+ (quality?"آخر بيانات البحث تفتقد سبريد تاريخياً موثقاً؛ الفرضيات ليست استراتيجيات معتمدة.":
        "لا يجوز اعتبار الفرضيات البحثية أرباحاً أو صفقات تنفيذية.")+'</p></div></div>'+
      '<div class="lc-brain-footer"><span>المصدر <b>'+esc(brain.broker_selection||"غير محدد")+'</b></span>'+
      '<span>آخر دورة <b>'+esc(localTime(brain.updated_at))+'</b></span></div>'+
      '</section>';
  }
  function renderFeed(d){
    const events=d.events||[];
    return '<section class="lc-panel lc-feed-panel"><div class="lc-section-top"><div>'+
      '<span class="lc-kicker">ACTIVITY STREAM</span><h2>آخر أحداث النظام</h2>'+
      '<p>تحديثات حقيقية من المحرك والعقل والوسيط</p></div></div>'+
      '<div class="lc-feed">'+(events.length?events.map(e=>'<div class="lc-feed-event">'+
        '<span class="lc-event-point '+(e.type==="BROKER_CLOSED"?"lc-event-broker":"")+'"></span>'+
        '<div class="lc-event-copy"><strong>'+esc(e.label)+'</strong>'+
        '<p>'+esc(e.symbol?e.symbol+" · "+(e.detail||""):e.detail||"")+'</p>'+
        (e.net===undefined?"":'<small class="'+(e.net<0?"lc-loss":"lc-gain")+'">'+money(e.net,e.currency)+'</small>')+
        '</div><time>'+esc(localTime(e.at))+'</time></div>').join(""):
      '<div class="lc-empty">بانتظار أول أحداث موثقة</div>')+'</div></section>';
  }
  function render(){
    if(!snapshot){
      return '<div class="lc-root"><div class="lc-loading"><div class="lc-loading-shape"></div>'+
        '<h1>Sentinel Live Command Center</h1><p>'+
        esc(lastError||"جارٍ جلب أحدث بيانات Sentinel من Neon...")+
        '</p><button type="button" class="lc-button" data-lc-refresh>إعادة المحاولة</button></div></div>';
    }
    const d=snapshot,h=d.health||{},brain=d.brain||{},acc=d.account||{},
      auth=d.authorization||{},trades=d.trades||{},summary=(trades.net_by_currency||[])[0]||null,
      online=h.trader==="FRESH",researchLive=h.brain==="FRESH";
    const available=auth.enabled&&auth.expires_at&&Date.parse(auth.expires_at)>Date.now()&&
      h.execution_mode==="UNVERIFIED_DEMO_TRIAL";
    const pnl=summary?money(summary.net,summary.currency):"—";
    const pnlNote=summary?"صافي الصفقات المغلقة في السجل":"لا توجد نتائج مالية مؤكدة";
    return '<div class="lc-root"><section class="lc-hero">'+
      '<div class="lc-topline"><span class="lc-brandline"><span class="lc-light"></span>SENTINEL / COMMAND CENTER</span>'+
      '<span class="lc-release">V3.0 • BROKER-GROUNDED</span></div>'+
      '<div class="lc-hero-main"><div><p class="lc-kicker">LIVE OPERATIONS / MT5 DEMO</p>'+
      '<h1>كل السوق. قرار واحد.<br><em>صورة واضحة.</em></h1>'+
      '<p class="lc-hero-description">مراقبة تداول Fusion، حركة السوق، نشاط العقل والصفقات المنفذة — من قاعدة البيانات الفعلية.</p>'+
      '<div class="lc-hero-status">'+statusPill(online,"المحرك "+(online?"يتحدث بانتظام":"متأخر"))+
      statusPill(researchLive,"العقل "+(researchLive?"نشط":"متأخر"))+
      statusPill(available,"تنفيذ Demo "+(available?"مفعّل":"غير مفعّل"))+'</div></div>'+
      '<div class="lc-hero-aside"><span>ACCOUNT SESSION</span><strong>FUSION <i>DEMO</i></strong>'+
      '<p>MT5 / •••• '+esc(acc.last4||"—")+'</p>'+
      '<div class="lc-aside-separator"></div>'+
      '<small>آخر فحص من الوسيط</small><b>'+shortAge(h.trader_age_seconds)+'</b>'+
      '<small>موعد انتهاء التفويض</small><b>'+esc(localTime(auth.expires_at))+'</b></div></div>'+
      '<div class="lc-hero-footer"><span>Live dashboard refresh / 20s · Broker scans / 5min · Brain / 15min</span>'+
      '<button type="button" class="lc-button lc-refresh" data-lc-refresh '+(fetching?"disabled":"")+'>'+
      (fetching?"جارٍ التحديث...":"تحديث الآن ↗")+'</button></div></section>'+
      (lastError?'<div class="lc-offline-warning">تعذّر آخر تحديث، المعروض آخر بيانات متاحة: '+esc(lastError)+'</div>':"")+
      '<section class="lc-stats">'+
      stat("سجل الأوامر",num(trades.intents,0),"أوامر Sentinel المسجلة","blue")+
      stat("صفقات مغلقة",num(trades.closed,0),"مطابقة مع سجل الوسيط","violet")+
      stat("النتيجة المحققة",pnl,pnlNote,summary&&summary.net<0?"red":"green")+
      stat("استراتيجيات معتمدة",num(brain.candidates,0),"البحث لا يعني اعتماد التداول","neutral")+'</section>'+
      '<div class="lc-title-row"><div><span class="lc-kicker">MARKET OBSERVATORY</span><h2>الأسواق تحت المراقبة</h2>'+
      '<p>آخر عينات Bid/Ask الفعلية، وليست بثّ Tick-by-Tick</p></div>'+
      '<span class="lc-last-sync">آخر مزامنة '+esc(localTime(d.generated_at))+' (بلجيكا)</span></div>'+
      '<section class="lc-market-grid">'+(d.markets||[]).map(marketCard).join("")+'</section>'+
      '<div class="lc-content-columns"><div class="lc-primary-column">'+
      renderTrades(d)+renderBrain(d)+'</div><div class="lc-secondary-column">'+
      renderFeed(d)+
      '<section class="lc-panel lc-sources"><span class="lc-kicker">SYSTEM TRANSPARENCY</span>'+
      '<h2>حقيقة البيانات</h2><div class="lc-source-row"><span>مصدر التنفيذ</span><strong>TickerAll / MT5</strong></div>'+
      '<div class="lc-source-row"><span>قاعدة السجلات</span><strong>Neon</strong></div>'+
      '<div class="lc-source-row"><span>آخر دورة تداول</span><strong>'+esc(localTime(d.generated_at))+'</strong></div>'+
      '<div class="lc-source-row"><span>آخر تحديث للعقل</span><strong>'+esc(localTime(brain.updated_at))+'</strong></div>'+
      '<p>معدل تحديث الشاشة لا يعني وصول سعر جديد كل 20 ثانية. لا نعرض رأس مال أو P&L عائماً بدون توثيق.</p>'+
      '</section></div></div>'+
      '<div class="lc-footer-note">SENTINEL SYSTEM · Demo-only experiments. Strategy profitability is not established. No remote trade controls.</div>'+
      '</div>';
  }
  function rerender(){
    if(document.querySelector('.nav-item.active[data-nav="live"]')){
      const el=document.getElementById("page");if(el)el.innerHTML=render();
    }
  }
  async function refresh(){
    if(fetching)return;
    fetching=true;
    try{
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),13000);
      let response;
      try{response=await fetch("/api/live",{method:"GET",credentials:"same-origin",
        headers:{Accept:"application/json"},cache:"no-store",signal:controller.signal})}
      finally{clearTimeout(timer)}
      const data=await response.json();
      if(!response.ok||data?.ok!==true)throw Error(String(data?.error||"API unavailable").slice(0,100));
      snapshot=data;lastFetched=Date.now();lastError="";
    }catch(e){lastError="مصدر البيانات غير متاح حالياً";if(!snapshot)lastError+=" — "+String(e.name||"Error").slice(0,20)}
    finally{fetching=false;rerender()}
  }
  document.addEventListener("click",event=>{
    const refreshButton=event.target.closest("[data-lc-refresh]");
    if(refreshButton){event.preventDefault();void refresh();return}
    const tab=event.target.closest("[data-lc-tab]");
    if(tab){activeTab=tab.dataset.lcTab==="orders"?"orders":"fills";rerender()}
  });
  setInterval(()=>{
    if(document.visibilityState==="visible"&&
       document.querySelector('.nav-item.active[data-nav="live"]'))void refresh();
  },20000);
  void refresh();
  return {render,refresh,getSnapshot:()=>snapshot};
})();
