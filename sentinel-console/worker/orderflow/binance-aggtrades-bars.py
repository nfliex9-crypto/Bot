#!/usr/bin/env python3
"""Research-only Binance BTCUSDT aggTrades -> executed-trade Delta bars.
No cost model, no order routing. Verify official archive SHA256.
"""
import csv, hashlib, io, json, sys, urllib.request, zipfile
DATES = ["2026-10-20","2026-10-21","2026-10-22","2026-10-23","2026-10-24",
         "2026-11-13","2026-11-14","2026-11-15","2026-11-16","2026-11-17"]
P = {"M5":300000,"M15":900000}
bars = {k:[] for k in P}
source=[]
def start(b,t,p,price):
    return dict(openTime=t,closeTime=t+p,barMs=p,venue="BINANCE_SPOT",
      symbol="BTCUSDT",sessionId="BINANCE_SPOT_BTCUSDT_UTC",
      sourceQuality="VERIFIED_AGGRESSOR_TRADES",closed=True,
      open=price,high=price,low=price,close=price,volume=0,
      buyVolume=0,sellVolume=0,delta=0,maxIntrabarDelta=0,minIntrabarDelta=0,
      maxIntrabarDeltaAt=t,minIntrabarDeltaAt=t)
for day in DATES:
    url="https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-"+day+".zip"
    blob=urllib.request.urlopen(url,timeout=120).read()
    checksum=urllib.request.urlopen(url+".CHECKSUM",timeout=30).read().decode().split()[0].lower()
    sha=hashlib.sha256(blob).hexdigest()
    if sha != checksum: raise RuntimeError("OFFICIAL_SHA256_MISMATCH "+day)
    count,prev=0,-1
    current={k:None for k in P}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        members=[x for x in z.namelist() if x.endswith(".csv")]
        if len(members)!=1: raise RuntimeError("BAD_ARCHIVE_MEMBER_LIST")
        with z.open(members[0]) as stream:
            for row in csv.reader(io.TextIOWrapper(stream,encoding="utf-8-sig")):
                if not row or row[0].strip().lower() in ("agg_trade_id","aggtradeid"): continue
                price,qty,t=float(row[1]),float(row[2]),int(row[5])
                t=t//1000 if t>10**14 else t
                if t<prev or price<=0 or qty<=0: raise RuntimeError("INVALID_TAPE_ROW "+day)
                prev=t
                maker=row[6].strip().lower()
                if maker not in ("true","false","0","1"): raise RuntimeError("UNKNOWN_AGGRESSOR")
                signed=-qty if maker in ("true","1") else qty
                count+=1
                for k,p in P.items():
                    t0=t//p*p; b=current[k]
                    if b is None or b["openTime"]!=t0:
                        if b is not None:bars[k].append(b)
                        b=start(k,t0,p,price); current[k]=b
                    b["high"]=max(b["high"],price)
                    b["low"]=min(b["low"],price)
                    b["close"]=price
                    b["volume"]+=qty
                    b["delta"]+=signed
                    if signed>0:b["buyVolume"]+=qty
                    else:b["sellVolume"]+=qty
                    if b["delta"]>b["maxIntrabarDelta"]:b["maxIntrabarDelta"]=b["delta"];b["maxIntrabarDeltaAt"]=t
                    if b["delta"]<b["minIntrabarDelta"]:b["minIntrabarDelta"]=b["delta"];b["minIntrabarDeltaAt"]=t
    for k,b in current.items():
        if b is not None:bars[k].append(b)
    source.append({"date":day,"rows":count,"sha256":sha,"url":url})
    print("AUDITED",day,count,flush=True)
output={"bars":bars,"metadata":source,"transactionCostDeductions":0}
with open(sys.argv[1] if len(sys.argv)>1 else "bars.json","w") as f:json.dump(output,f,separators=(",",":"))
print("COMPLETE",{k:len(v) for k,v in bars.items()},sum(x["rows"] for x in source),flush=True)
