from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from api.routes import controls, dashboard, trades
from config.settings import settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Trading Bot",
        description="Automated Forex & Crypto Trading System",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(dashboard.router)
    app.include_router(trades.router)
    app.include_router(controls.router)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return _dashboard_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": settings.trading_mode.value}

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled API error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


def _dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Trading Bot</title>
<style>
  :root{--bg:#0f1117;--card:#1a1d28;--border:#2a2d3a;--text:#e4e4e7;--muted:#71717a;
    --green:#22c55e;--red:#ef4444;--blue:#3b82f6;--yellow:#eab308;}
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Inter',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
  .header{background:var(--card);border-bottom:1px solid var(--border);padding:1rem 2rem;display:flex;align-items:center;justify-content:space-between}
  .header h1{font-size:1.25rem;font-weight:700}
  .badge{padding:.25rem .75rem;border-radius:9999px;font-size:.75rem;font-weight:600}
  .badge-paper{background:rgba(234,179,8,.15);color:var(--yellow)}
  .badge-live{background:rgba(239,68,68,.15);color:var(--red)}
  .container{max-width:1400px;margin:0 auto;padding:1.5rem}
  .grid{display:grid;gap:1rem}
  .grid-4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
  .grid-2{grid-template-columns:repeat(auto-fit,minmax(400px,1fr))}
  .card{background:var(--card);border:1px solid var(--border);border-radius:.75rem;padding:1.25rem}
  .card h3{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem}
  .card .value{font-size:1.75rem;font-weight:700}
  .green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}
  table{width:100%;border-collapse:collapse;margin-top:1rem}
  th,td{text-align:left;padding:.6rem .8rem;border-bottom:1px solid var(--border);font-size:.85rem}
  th{color:var(--muted);font-weight:500;font-size:.75rem;text-transform:uppercase}
  .btn{padding:.5rem 1rem;border:none;border-radius:.5rem;cursor:pointer;font-size:.85rem;font-weight:600}
  .btn-red{background:rgba(239,68,68,.15);color:var(--red)}.btn-red:hover{background:rgba(239,68,68,.25)}
  .btn-blue{background:rgba(59,130,246,.15);color:var(--blue)}.btn-blue:hover{background:rgba(59,130,246,.25)}
  .status-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:.5rem}
  .dot-green{background:var(--green)}.dot-red{background:var(--red)}.dot-yellow{background:var(--yellow)}
  #refresh-time{color:var(--muted);font-size:.75rem}
</style>
</head>
<body>
<div class="header">
  <div style="display:flex;align-items:center;gap:1rem">
    <h1>AI Trading Bot</h1>
    <span class="badge" id="mode-badge">...</span>
  </div>
  <div style="display:flex;align-items:center;gap:1rem">
    <span id="refresh-time"></span>
    <button class="btn btn-blue" onclick="refresh()">Refresh</button>
    <button class="btn btn-red" onclick="closeAll()">Close All</button>
  </div>
</div>
<div class="container">
  <div class="grid grid-4" id="stats"></div>
  <div class="grid grid-2" style="margin-top:1rem">
    <div class="card"><h3>Open Trades</h3><div id="open-trades">Loading...</div></div>
    <div class="card"><h3>Recent Signals</h3><div id="signals">Loading...</div></div>
  </div>
  <div class="card" style="margin-top:1rem"><h3>Closed Trades</h3><div id="closed-trades">Loading...</div></div>
</div>
<script>
const API = '';
function $(s){return document.querySelector(s)}
function fmt(n,d=2){return Number(n).toFixed(d)}

async function refresh(){
  try{
    const [status,open,closed,signals]=await Promise.all([
      fetch(API+'/api/controls/status').then(r=>r.json()),
      fetch(API+'/api/trades/open').then(r=>r.json()),
      fetch(API+'/api/trades/closed?limit=20').then(r=>r.json()),
      fetch(API+'/api/dashboard/recent-signals?limit=15').then(r=>r.json()),
    ]);
    renderStatus(status);
    renderOpen(open);
    renderClosed(closed);
    renderSignals(signals);
    $('#refresh-time').textContent='Updated: '+new Date().toLocaleTimeString();
  }catch(e){console.error(e)}
}

function renderStatus(s){
  const a=s.account||{};
  const mode=s.mode||'paper';
  const b=$('#mode-badge');
  b.textContent=mode.toUpperCase();
  b.className='badge badge-'+mode;
  const pnlClass=a.total_pnl>=0?'green':'red';
  $('#stats').innerHTML=`
    <div class="card"><h3>Balance</h3><div class="value">$${fmt(a.balance)}</div></div>
    <div class="card"><h3>Total P&L</h3><div class="value ${pnlClass}">$${fmt(a.total_pnl)}</div></div>
    <div class="card"><h3>Drawdown</h3><div class="value ${a.drawdown_pct>10?'red':'green'}">${fmt(a.drawdown_pct,1)}%</div></div>
    <div class="card"><h3>Win Rate</h3><div class="value blue">${fmt(a.win_rate,1)}%</div></div>
    <div class="card"><h3>Open Trades</h3><div class="value">${a.open_trades||0}</div></div>
    <div class="card"><h3>Total Trades</h3><div class="value">${a.total_trades||0}</div></div>
    <div class="card"><h3>Session</h3><div class="value" style="font-size:1.1rem">${s.session||'-'}</div></div>
    <div class="card"><h3>AI Trained</h3><div class="value" style="font-size:1.1rem">${s.ai_trained?'Yes':'No'}</div></div>
  `;
}

function renderOpen(trades){
  if(!trades.length){$('#open-trades').innerHTML='<p style="color:var(--muted)">No open trades</p>';return}
  let h='<table><tr><th>Symbol</th><th>Dir</th><th>Entry</th><th>SL</th><th>TP1</th><th>TP2</th><th>TP3</th><th>P&L</th></tr>';
  trades.forEach(t=>{
    const c=t.pnl>=0?'green':'red';
    h+=`<tr><td>${t.symbol}</td><td>${t.direction}</td><td>${fmt(t.entry_price,5)}</td><td>${fmt(t.stop_loss,5)}</td><td>${fmt(t.tp1,5)}</td><td>${fmt(t.tp2,5)}</td><td>${fmt(t.tp3,5)}</td><td class="${c}">$${fmt(t.pnl)}</td></tr>`;
  });
  h+='</table>';
  $('#open-trades').innerHTML=h;
}

function renderClosed(trades){
  if(!trades.length){$('#closed-trades').innerHTML='<p style="color:var(--muted)">No closed trades</p>';return}
  let h='<table><tr><th>Symbol</th><th>Dir</th><th>Entry</th><th>Reason</th><th>P&L</th><th>Closed</th></tr>';
  trades.forEach(t=>{
    const c=t.pnl>=0?'green':'red';
    h+=`<tr><td>${t.symbol}</td><td>${t.direction}</td><td>${fmt(t.entry_price,5)}</td><td>${t.close_reason}</td><td class="${c}">$${fmt(t.pnl)}</td><td>${t.closed_at||'-'}</td></tr>`;
  });
  h+='</table>';
  $('#closed-trades').innerHTML=h;
}

function renderSignals(sigs){
  if(!sigs.length){$('#signals').innerHTML='<p style="color:var(--muted)">No signals yet</p>';return}
  let h='<table><tr><th>Symbol</th><th>Type</th><th>Dir</th><th>Conf</th><th>Accepted</th></tr>';
  sigs.forEach(s=>{
    const ac=s.accepted?'<span class="green">Yes</span>':'<span class="red">No</span>';
    h+=`<tr><td>${s.symbol}</td><td>${s.signal_type}</td><td>${s.direction}</td><td>${fmt(s.confidence,3)}</td><td>${ac}</td></tr>`;
  });
  h+='</table>';
  $('#signals').innerHTML=h;
}

async function closeAll(){
  if(!confirm('Close ALL open trades?'))return;
  const r=await fetch(API+'/api/controls/close-all',{method:'POST'});
  const d=await r.json();
  alert(d.message);
  refresh();
}

refresh();
setInterval(refresh,30000);
</script>
</body>
</html>"""
