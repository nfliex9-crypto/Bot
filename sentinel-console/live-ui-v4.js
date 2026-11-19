"use strict";
/* Sentinel V4: broker-grounded read-only trading terminal. No simulated data. */
window.SentinelLive=(()=>{
  let snapshot=null,error="",fetching=false,lastSuccess=0;
  let selected="XAUUSD",rangeHours=4,ledgerTab="fills";
  const safe=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const n=(v,d=2)=>{
    if(v===null||v===undefined||v==="")return "—";
    const x=Number(v);
    return Number.isFinite(x)?new Intl.NumberFormat("en-GB",{maximumFractionDigits:d}).format(x):"—";
  };
  const money=(v,c)=>{
    if(v===null||v===undefined||!c||!Number.isFinite(Number(v)))return "—";
    try{return new Intl.NumberFormat("en-GB",{style:"currency",currency:c,maximumFractionDigits:2}).format(Number(v))}
    catch(_){return n(v)+" "+safe(c)}
  };
  const date=v=>{
    const x=new Date(v);
    return v&&!Number.isNaN(x.getTime())?new Intl.DateTimeFormat("ar-BE",{timeZone:"Europe/Brussels",
      month:"short",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(x):"—";
  };
  const age=s=>{
    if(s===null||s===undefined||!Number.isFinite(Number(s)))return "غير معروف";
    return s<60?Math.floor(s)+" ث":s<3600?Math.floor(s/60)+" د":Math.floor(s/3600)+" س";
  };
  const status=(ok,label,unknown=false)=>"<span class='sc-chip "+(unknown?"sc-chip-muted":ok?"sc-chip-good":"sc-chip-warn")+
    "'><i></i>"+safe(label)+"</span>";
  const titles={XAUUSD:"الذهب",BTCUSD:"بيتكوين",NAS100:"ناسداك",EURUSD:"يورو / دولار"};
  const labels={
    NO_VALID_CLOSED_BAR_SIGNAL:"بانتظار إشارة",
    BROKER_CONTRACT_VERIFIED:"عقد موثّق",
    BROKER_CONTRACT_READ_FAILED:"تعذّر فحص العقد",
    BROKER_CONTRACT_VALUE_UNKNOWN:"مواصفات ناقصة",
    ACCOUNT_HAS_EXISTING_POSITION_OR_ORDER:"مركز / أمر قائم",
    BROKER_SHADOW_RESEARCH_ONLY:"مراقبة فقط",
    ACK_PENDING_RECONCILIATION:"بانتظار تأكيد الوسيط",
    NO_VERIFIED_BRAIN_EVIDENCE:"بدون دليل معتمد",
    BROKER_DATA_QUALITY_GATE:"نقص تكاليف تاريخية",
    COMPLETED:"مكتمل"
  };
  const label=x=>labels[x]||String(x||"غير معروف").replace(/_/g," ");
  const sourceMarket=s=>snapshot?.markets?.find(m=>m.symbol===s)||null;
  const currentMarket=()=>{
    if(sourceMarket(selected))return sourceMarket(selected);
    return snapshot?.markets?.[0]||null;
  };
  const isFresh=m=>m?.contract_status==="BROKER_CONTRACT_VERIFIED"&&m.quote_ready===true&&
    m.quote!==null&&m.quote_age_seconds!==null&&Number(m.quote_age_seconds)<=600;
  const series=m=>{
    const now=Date.now(),min=now-rangeHours*3600000;
    return (m?.history||[]).filter(p=>Number.isFinite(Number(p.mid))&&
      Number.isFinite(Date.parse(p.at))&&Date.parse(p.at)>=min).sort((a,b)=>Date.parse(a.at)-Date.parse(b.at));
  };
  function chart(m){
    const pts=series(m);
    if(pts.length<2)return "<div class='sc-chart-empty'><span class='sc-empty-icon'>⌁</span>"+
      "<strong>ما في عينات كافية لهالفترة</strong><small>الرسم يظهر فقط أسعار الوسيط المسجّلة. جرّب فترة أطول.</small></div>";
    const values=pts.map(x=>Number(x.mid)),lo=Math.min(...values),hi=Math.max(...values);
    const pad=Math.max((hi-lo)*.14,Math.max(Math.abs(hi),1)*.000002);
    const bottom=lo-pad,top=hi+pad,denom=Math.max(top-bottom,1e-12);
    const coords=values.map((v,i)=>({x:52+i/(values.length-1)*856,
      y:235-(v-bottom)/denom*203}));
    const line=coords.map((p,i)=>(i?"L":"M")+p.x.toFixed(2)+" "+p.y.toFixed(2)).join(" ");
    const fill=line+" L908 244 L52 244 Z";
    const up=values[values.length-1]>=values[0],last=coords[coords.length-1];
    const axis=[0,1,2,3].map(i=>{
      const y=33+i*67.5,v=top-(top-bottom)*i/3;
      return "<line x1='52' y1='"+y+"' x2='908' y2='"+y+"' class='sc-chart-gridline'/>"+
        "<text x='45' y='"+(y+4)+"' text-anchor='end' class='sc-chart-label'>"+safe(n(v,m.symbol==="EURUSD"?5:2))+"</text>";
    }).join("");
    const times=[0,Math.floor((pts.length-1)/2),pts.length-1].map((i,k)=>
      "<text x='"+[52,480,908][k]+"' y='266' text-anchor='"+["start","middle","end"][k]+
      "' class='sc-chart-label'>"+safe(date(pts[i].at))+"</text>").join("");
    return "<div class='sc-chart-canvas "+(up?"sc-up":"sc-down")+"'>"+
      "<svg viewBox='0 0 960 282' preserveAspectRatio='none' role='img' aria-label='حركة منتصف سعر الوسيط من عينات Bid وAsk الفعلية'>"+
      "<defs><linearGradient id='sc-chart-fill' x1='0' x2='0' y1='0' y2='1'><stop offset='0' stop-color='currentColor' stop-opacity='.27'/><stop offset='1' stop-color='currentColor' stop-opacity='0'/></linearGradient></defs>"+
      axis+"<path d='"+fill+"' fill='url(#sc-chart-fill)'/>"+
      "<path d='"+line+"' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round' vector-effect='non-scaling-stroke'/>"+
      "<circle cx='"+last.x.toFixed(2)+"' cy='"+last.y.toFixed(2)+"' r='6' fill='currentColor' stroke='#101a25' stroke-width='3'/>"+
      times+"</svg><div class='sc-chart-sample'>"+pts.length+" عينات موثّقة خلال الفترة المختارة</div></div>";
  }
  function metric(k,v,sub,tone){
    return "<article class='sc-metric "+(tone||"")+"'><div class='sc-metric-label'>"+safe(k)+
      "</div><strong dir='ltr'>"+v+"</strong><span>"+safe(sub)+"</span></article>";
  }
  function watch(m){
    const q=m.quote||{},valid=isFresh(m),history=series(m);
    const a=history[0]?.mid,b=history[history.length-1]?.mid;
    const delta=history.length>1&&a?((b-a)/a*100):null;
    return "<button type='button' data-sc-market='"+safe(m.symbol)+"' class='sc-watch-row "+
      (selected===m.symbol?"selected ":"")+(valid?"ready":"limited")+"' aria-pressed='"+
      (selected===m.symbol?"true":"false")+"'>"+
      "<span class='sc-watch-icon'>"+safe({XAUUSD:"Au",BTCUSD:"₿",NAS100:"NQ",EURUSD:"€"}[m.symbol]||"FX")+"</span>"+
      "<span class='sc-watch-identity'><strong>"+safe(m.symbol)+"</strong><small>"+safe(titles[m.symbol]||m.symbol)+"</small></span>"+
      "<span class='sc-watch-values'><b dir='ltr'>"+(valid?n(q.mid,m.symbol==="EURUSD"?5:2):"—")+
      "</b><small class='"+(delta===null?"":delta>=0?"sc-positive":"sc-negative")+"' dir='ltr'>"+
      (delta===null?"—":(delta>=0?"+":"")+n(delta,3)+"%")+"</small></span>"+
      "<span class='sc-watch-led' title='"+safe(valid?"سعر حديث":"سعر غير متاح أو غير موثق")+"' aria-hidden='true'></span></button>";
  }
  function hero(d){
    const h=d.health||{},a=d.account||{},auth=d.authorization||{};
    const online=h.trader==="FRESH",brain=h.brain==="FRESH";
    const armed=auth.enabled===true&&Date.parse(auth.expires_at)>Date.now()&&
      h.execution_mode==="UNVERIFIED_DEMO_TRIAL";
    return "<section class='sc-hero'><div class='sc-hero-top'><span class='sc-eyebrow'><i class='sc-pulse'></i> SENTINEL / TRADING INTELLIGENCE</span>"+
      "<span class='sc-build'>TERMINAL V4.0 <span>•</span> READ-ONLY CONTROL PLANE</span></div>"+
      "<div class='sc-hero-body'><div class='sc-hero-copy'><div class='sc-overline'>OPERATIONS OVERVIEW</div>"+
      "<h1>السوق تحت المراقبة<span>.</span><br><em>كل قرار إلو دليل.</em></h1>"+
      "<p>لوحة عمليات مرتبطة بسجلات Fusion وNeon: أسعار فعلية، دورات تداول، صفقات الوسيط، وتقدّم العقل — بدون بيانات تجريبية مصطنعة.</p>"+
      "<div class='sc-hero-pills'>"+status(online,"محرك التداول "+(online?"متصل":"متأخر"))+
      status(brain,"العقل "+(brain?"نشط":"متأخر"))+
      status(armed,"Demo "+(armed?"مصرّح":"غير مصرّح"))+"</div></div>"+
      "<div class='sc-account'><div class='sc-account-head'><span>CONNECTED ACCOUNT</span><span class='sc-account-badge'>DEMO ONLY</span></div>"+
      "<strong>FUSION <i>MARKETS</i></strong><div class='sc-account-number'>MT5 <span>•••• "+safe(a.last4||"—")+"</span></div>"+
      "<div class='sc-account-rule'></div><div class='sc-account-row'><span>آخر فحص</span><b>"+safe(age(h.trader_age_seconds))+"</b></div>"+
      "<div class='sc-account-row'><span>مخاطرة الصفقة</span><b dir='ltr'>"+n(auth.risk_pct,2)+"%</b></div>"+
      "<div class='sc-account-row'><span>انتهاء التفويض</span><b>"+safe(date(auth.expires_at))+"</b></div></div></div>"+
      "<div class='sc-hero-bottom'><div class='sc-cadence'><span>LIVE SNAPSHOT</span><i></i><span>تحديث الواجهة كل 20 ثانية</span><i></i><span>فحص الوسيط كل 5 دقائق تقريباً</span></div>"+
      "<button type='button' data-sc-refresh class='sc-refresh' "+(fetching?"disabled":"")+">"+
      "<span class='sc-refresh-glyph'>↻</span> "+(fetching?"جارٍ التحديث":"تحديث البيانات")+"</button></div></section>";
  }
  function markets(d){
    const m=currentMarket(),q=m?.quote||{},valid=isFresh(m),pts=series(m);
    const a=pts[0]?.mid,b=pts[pts.length-1]?.mid;
    const change=pts.length>1&&a?((b-a)/a*100):null;
    return "<section class='sc-market-workspace'><article class='sc-panel sc-chart-panel'>"+
      "<div class='sc-section-header'><div><div class='sc-overline'>MARKET INTELLIGENCE / REAL BROKER SAMPLES</div>"+
      "<h2>"+safe(titles[m?.symbol]||m?.symbol||"السوق")+" <span class='sc-symbol'>"+safe(m?.symbol||"—")+"</span></h2></div>"+
      status(valid,valid?"السعر حديث":"البيانات محدودة")+"</div>"+
      "<div class='sc-price-line'><div class='sc-big-price' dir='ltr'>"+(valid?n(q.mid,m?.symbol==="EURUSD"?5:2):"—")+
      "</div><div class='sc-price-change "+(change===null?"":change>=0?"sc-positive":"sc-negative")+"' dir='ltr'>"+
      (change===null?"—":(change>=0?"+":"")+n(change,3)+"%")+"</div>"+
      "<div class='sc-price-meaning'>منتصف آخر Bid / Ask موثّق<br>وليس بث Tick مباشر</div></div>"+
      "<div class='sc-chart-controls'><div class='sc-chart-legend'><i></i> سعر الوسيط المسجّل</div>"+
      "<div class='sc-segments' role='group' aria-label='فترة الرسم'>"+
      [1,4,8].map(h=>"<button type='button' data-sc-range='"+h+"' class='"+(rangeHours===h?"active":"")+
      "' aria-pressed='"+(rangeHours===h)+"'>"+h+"H</button>").join("")+"</div></div>"+
      chart(m)+
      "<div class='sc-quote-strip'><div><small>BID</small><strong dir='ltr'>"+(valid?n(q.bid,m?.symbol==="EURUSD"?5:2):"—")+
      "</strong></div><div><small>ASK</small><strong dir='ltr'>"+(valid?n(q.ask,m?.symbol==="EURUSD"?5:2):"—")+
      "</strong></div><div><small>SPREAD</small><strong dir='ltr'>"+(valid?n(m.spread_bps,3)+" bps":"—")+
      "</strong></div><div><small>آخر عينة</small><strong>"+safe(age(m?.quote_age_seconds))+"</strong></div></div>"+
      "<div class='sc-decision-strip'><div><span>آخر قرار للمحرك</span><strong>"+safe(label(m?.status))+"</strong></div>"+
      "<div><span>الاستراتيجية</span><strong dir='ltr'>"+safe(m?.strategy||"—")+"</strong></div>"+
      "<div><span>تقييم العقل</span><strong>"+safe(m?.brain_status?label(m.brain_status):"لا يوجد تقييم جديد")+"</strong></div>"+
      "<div><span>أوامر هذه الدورة</span><strong>"+n(m?.trades_submitted,0)+"</strong></div></div></article>"+
      "<aside class='sc-panel sc-watchlist'><div class='sc-watch-header'><div class='sc-overline'>MARKET WATCH</div><h2>الأسواق</h2>"+
      "<p>اختار السوق لتشوف عيناته الفعلية</p></div><div class='sc-watch-rows'>"+
      (d.markets||[]).map(watch).join("")+"</div>"+
      "<div class='sc-watch-footer'><span class='sc-watch-legend'><i></i> موثّق وحديث</span>"+
      "<span>المصدر TickerAll / MT5</span></div></aside></section>";
  }
  function ledger(d){
    const t=d.trades||{},fills=t.recent||[],orders=t.orders||[],rows=ledgerTab==="fills"?
      fills.map(f=>"<tr><td><b dir='ltr'>"+safe(f.symbol)+"</b><small>"+safe(f.family)+"</small></td>"+
        "<td><span class='sc-order-side'>"+safe(f.side)+"</span></td>"+
        "<td class='"+(f.net<0?"sc-negative":"sc-positive")+"' dir='ltr'>"+money(f.net,f.currency)+"</td>"+
        "<td>"+safe(date(f.closed_at))+"</td><td><span class='sc-verified'>سجل الوسيط</span></td></tr>").join(""):
      orders.map(o=>"<tr><td><b dir='ltr'>"+safe(o.symbol)+"</b><small>"+safe(o.family)+"</small></td>"+
        "<td><span class='sc-order-side'>"+safe(o.side)+"</span></td><td colspan='2'>"+safe(label(o.status))+
        "</td><td>"+safe(date(o.updated_at))+"</td></tr>").join("");
    return "<section class='sc-panel sc-ledger'><div class='sc-section-header'><div>"+
      "<div class='sc-overline'>EXECUTION / BROKER JOURNAL</div><h2>سجل التداول</h2>"+
      "<p>الأوامر والصفقات المغلقة التي أمكن مطابقتها مع الوسيط</p></div>"+
      "<div class='sc-segments'><button data-sc-ledger='fills' class='"+(ledgerTab==="fills"?"active":"")+"'>الصفقات</button>"+
      "<button data-sc-ledger='orders' class='"+(ledgerTab==="orders"?"active":"")+"'>الأوامر</button></div></div>"+
      "<div class='sc-table-scroll'><table class='sc-table'><thead><tr><th>السوق / الاستراتيجية</th>"+
      "<th>الاتجاه</th><th>"+(ledgerTab==="fills"?"النتيجة المحققة":"الحالة")+"</th>"+
      "<th>"+(ledgerTab==="fills"?"وقت الإغلاق":"")+"</th><th>التحقق</th></tr></thead><tbody>"+
      (rows||"<tr><td colspan='5' class='sc-empty-row'>لا يوجد سجل مؤكد من هذا النوع حتى الآن</td></tr>")+
      "</tbody></table></div></section>";
  }
  function brainPanel(d){
    const brain=d.brain||{},last=brain.last_market||{},missing=Number(last.missing_spread_ratio);
    const gated=last.reason==="BROKER_DATA_QUALITY_GATE"||missing===1;
    const feedback=brain.forward_broker_feedback||null;
    const closed=Math.max(0,Number(feedback?.closed)||0);
    const minimum=Math.max(1,Number(feedback?.minimum_closed_for_review)||30);

    const feedbackDetails=(feedback?.strategies||[]).slice(0,3).map(x=>
      "<div class='sc-feedback-strategy'><span>"+safe(x.symbol)+" · "+safe(x.family)+
      "</span><strong class='"+(Number(x.booked_net)<0?"sc-negative":"sc-positive")+"' dir='ltr'>"+
      money(x.booked_net,x.currency)+"</strong></div>").join("");
    const feedbackPanel="<div class='sc-feedback'><div class='sc-feedback-heading'><span>FORWARD / BROKER-VERIFIED DEMO</span>"+
      "<strong>"+closed+" / "+minimum+"</strong></div>"+
      "<progress class='sc-feedback-track' aria-label='عدد صفقات الديمو المغلقة اللازمة لبدء مراجعة الأدلة' value='"+Math.min(closed,minimum)+
      "' max='"+minimum+"'></progress>"+
      "<p>صفقات Demo مغلقة وموثّقة. "+minimum+" حد أدنى لمراجعة العينة فقط، وليس دليلاً على الربحية. لا يوجد اعتماد تلقائي.</p>"+
      feedbackDetails+"</div>";
    const research=(d.research_history||[]).slice(0,5).map(x=>
      "<div class='sc-research-row'><span class='sc-research-dot'></span><div><b>"+
      safe(x.symbol||"بحث")+"</b><small>"+safe(label(x.reason||x.status))+"</small></div>"+
      "<span>"+safe(date(x.at))+"</span></div>").join("");
    return "<section class='sc-panel sc-brain'><div class='sc-section-header'><div>"+
      "<div class='sc-overline'>RESEARCH / STRATEGY FACTORY</div><h2>عقل Sentinel</h2>"+
      "<p>البحث المستمر، الفرضيات وجودة الأدلة</p></div>"+
      status(d.health?.brain==="FRESH",d.health?.brain==="FRESH"?"بحث نشط":"بحث متأخر")+"</div>"+
      "<div class='sc-brain-stats'><div><span>دورات / 24 ساعة</span><strong>"+n(brain.cycles_24h,0)+"</strong></div>"+
      "<div><span>فرضيات آخر دورة</span><strong>"+n(last.hypotheses,0)+"</strong></div>"+
      "<div><span>مرشحون معتمدون</span><strong>"+n(brain.candidates,0)+"</strong></div></div>"+
      "<div class='sc-research-gate "+(gated?"is-gated":"")+"'><div class='sc-gate-icon'>!</div>"+
      "<div><strong>"+(gated?"البحث التاريخي محجوب بجودة البيانات":"جودة الأبحاث قيد التحقق")+"</strong>"+
      "<p>"+(gated?"سبريد الأسعار الحي متاح، لكن الشموع التاريخية ما زالت تفتقد تكاليف تنفيذ موثّقة. الفرضيات ليست استراتيجيات معتمدة.":
      "لا تُعتمد أي استراتيجية تلقائياً بدون اختبار مستقل وتكاليف تنفيذ موثّقة.")+"</p></div></div>"+
      feedbackPanel+
      "<div class='sc-research-title'>آخر دورات البحث <span>"+safe(date(brain.updated_at))+"</span></div>"+
      "<div class='sc-research-list'>"+(research||"<div class='sc-empty-inline'>لا يوجد سجل بحث بعد</div>")+"</div></section>";
  }
  function edgePanel(d){
    const runs=Array.isArray(d.edge_lab)?d.edge_lab:[];
    const rows=runs.map(run=>{
      const families=(run.families||[]).map(f=>
        "<div class='sc-edge-family'><div><b>"+safe(f.family)+"</b>"+
        "<span>"+safe(f.status==="SHADOW_REVIEW_ELIGIBLE"?"مرشح لمراجعة ظلّية فقط":"غير مثبت")+
        "</span></div><div class='sc-edge-figures'><small>VALID "+n(f.validation_n,0)+"</small>"+
        "<strong dir='ltr'>"+n(f.validation_expectancy_r,3)+" R</strong>"+
        "<small>2× spread "+n(f.stressed_expectancy_r,3)+" R</small></div></div>").join("");
      return "<div class='sc-edge-market'><div class='sc-edge-market-title'><strong>"+safe(run.symbol)+"</strong>"+
        "<span>"+safe(date(run.at))+" · "+n(run.bar_count,0)+" M15 bars</span></div>"+
        (families||"<div class='sc-empty-inline'>لا يوجد تقييم لهذه البيانات</div>")+"</div>";
    }).join("");
    return "<section class='sc-panel sc-edge-panel'><div class='sc-section-header'><div>"+
      "<div class='sc-overline'>EDGE LAB / SHADOW RESEARCH ONLY</div><h2>مختبر استراتيجيات جديد</h2>"+
      "<p>تجربة فشل الاختراق واندفاع ما بعد الانضغاط — بدون إرسال أوامر</p></div>"+
      "<span class='sc-chip sc-chip-muted'><i></i>غير معتمد</span></div>"+
      "<div class='sc-edge-info'>الاختبارات زمنية (Train / Validation / Holdout)، ونتائج Holdout للعرض فقط. التكاليف تقديرية من عينات السبريد الحديثة؛ ليست سبريد تاريخياً ولا إثباتاً لربحية.</div>"+
      "<div class='sc-edge-rows'>"+(rows||"<div class='sc-empty-inline'>بانتظار تشغيل أول دورة بحث مستقلة</div>")+
      "</div></section>";
  }
  function cycles(d){
    const rows=(d.scan_history||[]).slice().reverse();
    const bars=rows.map(x=>{
      const className=x.orders_sent>0?"sc-cycle-trade":x.status!=="COMPLETED"?"sc-cycle-error":
        x.signals>0?"sc-cycle-signal":"sc-cycle-ok";
      return "<div class='sc-cycle-bar "+className+"' title='"+safe(date(x.at)+" · "+label(x.status)+
        " · أوامر "+x.orders_sent)+"' role='img' aria-label='"+safe(date(x.at)+", "+label(x.status))+"'></div>";
    }).join("");
    const recent=rows[rows.length-1]||null;
    return "<section class='sc-panel sc-cycle-panel'><div class='sc-section-header'><div>"+
      "<div class='sc-overline'>AUTOMATION / VERIFIED CYCLES</div><h2>نبض محرك التداول</h2>"+
      "<p>آخر "+rows.length+" دورات مسجلة في Neon</p></div>"+
      status(d.health?.trader==="FRESH",d.health?.trader==="FRESH"?"الدورات حديثة":"الدورات متأخرة")+"</div>"+
      "<div class='sc-cycle-body'><div class='sc-cycle-bars'>"+(bars||"<span class='sc-empty-inline'>لا توجد دورات</span>")+"</div>"+
      "<div class='sc-cycle-legend'><span><i class='sc-cycle-ok'></i> فحص مكتمل</span>"+
      "<span><i class='sc-cycle-signal'></i> إشارة</span><span><i class='sc-cycle-trade'></i> أمر</span>"+
      "<span><i class='sc-cycle-error'></i> مشكلة</span></div>"+
      "<div class='sc-cycle-detail'><span>آخر دورة</span><strong>"+safe(date(recent?.at))+"</strong>"+
      "<span>أوامر في آخر دورة</span><strong>"+n(recent?.orders_sent,0)+"</strong></div></div></section>";
  }
  function feed(d){
    const events=(d.events||[]).slice(0,8);
    return "<section class='sc-panel sc-activity'><div class='sc-section-header'><div>"+
      "<div class='sc-overline'>SYSTEM / ACTIVITY FEED</div><h2>الأحداث الأخيرة</h2>"+
      "<p>من سجل التداول والبحث، مو أحداث افتراضية</p></div></div><div class='sc-feed'>"+
      (events.map(e=>"<div class='sc-event'><span class='sc-event-marker "+(e.type==="BROKER_CLOSED"?"filled":"")+
        "'></span><div class='sc-event-copy'><strong>"+safe(e.label)+"</strong><p>"+
        safe((e.symbol?e.symbol+" · ":"")+(e.detail||""))+"</p>"+
        (e.net===undefined?"":"<small class='"+(e.net<0?"sc-negative":"sc-positive")+"'>"+
          money(e.net,e.currency)+"</small>")+"</div><time>"+safe(date(e.at))+"</time></div>").join("")||
      "<div class='sc-empty-inline'>بانتظار أول أحداث موثّقة</div>")+"</div></section>";
  }
  function render(){
    if(!snapshot)return "<div class='sc-root'><div class='sc-loading'><div class='sc-spinner'></div>"+
      "<h1>Sentinel Terminal</h1><p>"+safe(error||"جارٍ تحميل بيانات الوسيط الفعلية...")+"</p>"+
      "<button type='button' data-sc-refresh class='sc-refresh'>إعادة المحاولة</button></div></div>";
    const d=snapshot,t=d.trades||{},b=d.brain||{},totals=t.net_by_currency||[],
      net=totals.length===1?money(totals[0].net,totals[0].currency):"—";
    return "<div class='sc-root'>"+hero(d)+
      (error?"<div class='sc-warning' role='status'>تعذّر التحديث الأخير؛ البيانات المعروضة هي آخر نسخة ناجحة. "+safe(error)+"</div>":"")+
      "<div class='sc-metrics'>"+
      metric("دورات التداول / 24 ساعة",n(b.trade_cycles_24h,0),"دورات من سجل Neon","")+
      metric("دورات العقل / 24 ساعة",n(b.cycles_24h,0),"بحث مستقل عن التنفيذ","")+
      metric("صفقات مغلقة",n(t.closed,0),"مطابقة مع الوسيط","")+
      metric("صافي محقّق",net,totals.length===1?"سجل صفقات Sentinel فقط":"لا يوجد صافي موحّد","sc-accent")+
      metric("استراتيجيات معتمدة",n(b.candidates,0),"لا نخلط الفرضيات بالاعتماد","")+"</div>"+
      markets(d)+"<div class='sc-content-grid'><div class='sc-main-column'>"+
      ledger(d)+cycles(d)+"</div><div class='sc-side-column'>"+
      brainPanel(d)+edgePanel(d)+feed(d)+"</div></div>"+
      "<div class='sc-provenance'><span>SENTINEL / DATA INTEGRITY</span>"+
      "<p>الأسعار لقطات دورية من TickerAll / MT5، وليست بث Tick لحظياً. نتائج الصفقات من سجل الوسيط المطابق في Neon. لا تُعرض أرباح غير محققة أو رصيد غير موثّق. لا توجد أوامر تداول من المتصفح.</p>"+
      "<span>آخر تحديث للبيانات: "+safe(date(d.generated_at))+" بتوقيت بلجيكا</span></div></div>";
  }
  function redraw(){
    if(document.querySelector(".nav-item.active[data-nav='live']")){
      const page=document.getElementById("page");
      if(page)page.innerHTML=render();
    }
    if(typeof renderHeader==="function")renderHeader();
  }
  async function refresh(){
    if(fetching)return;
    fetching=true;
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),13000);
    try{
      const res=await fetch("/api/live",{method:"GET",credentials:"same-origin",
        headers:{Accept:"application/json"},cache:"no-store",signal:controller.signal});
      const body=await res.json();
      if(!res.ok||body?.ok!==true)throw Error(String(body?.error||"LIVE_API_UNAVAILABLE").slice(0,90));
      snapshot=body;lastSuccess=Date.now();error="";
      if(!sourceMarket(selected))selected=body.markets?.[0]?.symbol||"XAUUSD";
    }catch(e){error="آخر محاولة لم تنجح";if(!snapshot)error+=" ("+String(e?.name||"Error").slice(0,22)+")"}
    finally{clearTimeout(timeout);fetching=false;redraw()}
  }
  document.addEventListener("click",e=>{
    const market=e.target.closest("[data-sc-market]");
    if(market){selected=market.dataset.scMarket;redraw();return}
    const range=e.target.closest("[data-sc-range]");
    if(range){rangeHours=[1,4,8].includes(Number(range.dataset.scRange))?Number(range.dataset.scRange):4;redraw();return}
    const tab=e.target.closest("[data-sc-ledger]");
    if(tab){ledgerTab=tab.dataset.scLedger==="orders"?"orders":"fills";redraw();return}
    if(e.target.closest("[data-sc-refresh]")){void refresh()}
  });
  setInterval(()=>{
    if(document.visibilityState==="visible"&&document.querySelector(".nav-item.active[data-nav='live']"))void refresh();
  },20000);
  void refresh();
  return {render,refresh,getSnapshot:()=>snapshot};
})();
