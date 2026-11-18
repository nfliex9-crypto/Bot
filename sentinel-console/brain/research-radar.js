"use strict";
/*
 * Literature radar: fixed-source bibliography from Crossref metadata.
 * No arbitrary URL fetch, no scraping of proprietary content, no LLM-controlled
 * shell/code execution, no unreviewed paper-derived live trading signals.
 */
const TOPICS=[
 {name:"gold_microstructure",query:"intraday gold price seasonality volatility microstructure"},
 {name:"fx_order_flow",query:"foreign exchange order flow imbalance intraday predictability"},
 {name:"bitcoin_regimes",query:"bitcoin intraday momentum volatility regimes"},
 {name:"pattern_validation",query:"technical trading candlestick patterns out of sample empirical"}
];
const maxLen=(x,n)=>String(x??"").replace(/<[^>]*>/g,"").replace(/[\x00-\x1f]/g," ").trim().slice(0,n);
const validDoi=x=>/^10\.\d{4,9}\/[A-Za-z0-9._;()/:+-]{3,190}$/i.test(String(x||""));
function parseCrossref(payload,topic){
 const items=Array.isArray(payload?.message?.items)?payload.message.items:[];
 return items.slice(0,8).filter(x=>validDoi(x.DOI)).map(x=>{
   const title=maxLen(Array.isArray(x.title)?x.title[0]:x.title,240);
   const year=Number(x.published?.["date-parts"]?.[0]?.[0]||0);
   if(!title||year<2015||year>2100)return null;
   const doi=String(x.DOI).toLowerCase();
   return {doi,title,year,topic:topic.name,
     source_url:"https://doi.org/"+encodeURI(doi),found_from:"Crossref metadata",
     source_kind:"BIBLIOGRAPHIC_METADATA_NOT_VERIFIED_STRATEGY",
     integration:"IDEA_ONLY_REQUIRES_OOS_BACKTEST"};
 }).filter(Boolean);
}
async function researchRadar({fetchJSON,topics=TOPICS}={}){
 if(typeof fetchJSON!=="function")throw Error("FETCH_JSON_REQUIRED");
 const found=[],failures=[];
 for(const t of topics.slice(0,4)){
  const query=new URLSearchParams({"query.bibliographic":t.query,rows:"6",select:"DOI,title,published"});
  try{
   const body=await fetchJSON("https://api.crossref.org/works?"+query.toString());
   found.push(...parseCrossref(body,t));
  }catch(e){failures.push({topic:t.name,code:String(e?.message||"SOURCE_UNAVAILABLE").slice(0,70)})}
 }
 return {provider:"Crossref",items:[...new Map(found.map(r=>[r.doi,r])).values()],
  failures,not_used_for_orders:true,warning:"Paper metadata only; not verified reading or empirical evidence of strategy profitability."};
}
module.exports={TOPICS,parseCrossref,researchRadar};
