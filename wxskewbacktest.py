import urllib.request, json, math
from datetime import datetime, timezone

LAT=51.5048; LON=0.0495; ANC=9; CON=10; PHI=13; RATIO=60; R1=3.0
START=“2024-01-01”; END=“2026-02-27”

def fetch(url):
r=urllib.request.urlopen(urllib.request.Request(url,headers={“User-Agent”:“Mozilla/5.0”}),timeout=30)
return json.loads(r.read())

def fan(aT,hrs,deg,ratio):
return aT+hrs*ratio*math.tan(math.radians(deg))

print(“Fetching “+START+” to “+END+”…”)
url=(“https://archive-api.open-meteo.com/v1/archive”
“?latitude=51.5048&longitude=0.0495”
“&hourly=temperature_2m&daily=temperature_2m_max”
“&temperature_unit=celsius&timezone=UTC”
“&start_date=”+START+”&end_date=”+END)
d=fetch(url)
ht=d[“hourly”][“time”]; hv=d[“hourly”][“temperature_2m”]
dt=d[“daily”][“time”]; dv=d[“daily”][“temperature_2m_max”]
print(“Got “+str(len(dt))+” days”)
hr=[(datetime.fromisoformat(ht[i]),hv[i]) for i in range(len(ht)) if hv[i] is not None]
daily={dt[i]:dv[i] for i in range(len(dt)) if dv[i] is not None}

def fhr(t):
best=None; bd=float(“inf”)
for tt,v in hr:
diff=abs((tt.replace(tzinfo=None)-t.replace(tzinfo=None)).total_seconds())
if diff<bd: bd=diff; best=v
if diff>7200 and bd<3600: break
return best if bd<3600 else None

results=[]; monthly={}
for ds in dt:
ah=daily.get(ds)
if not ah: continue
p2=ds.split(”-”); yr,mo,dy=int(p2[0]),int(p2[1]),int(p2[2])
aT=fhr(datetime(yr,mo,dy,ANC)); cT=fhr(datetime(yr,mo,dy,CON))
if aT is None or cT is None: continue
ang=45 if aT<R1 else 27
bp=fan(aT,(PHI-ANC)/RATIO,ang,RATIO)
dev=cT-fan(aT,(CON-ANC)/RATIO,ang,RATIO)
bpred=bp+dev; berr=abs(ah-bpred)
bf=math.floor(bpred); bc=bf+1; abr=round(ah)
dn=abr in (bf,bc); up=abr in (bc,bc+1)
cs=“BOTH” if dn and up else “DOWN” if dn else “UP” if up else “NEITHER”
ch=“UP” if dev>0 else “DOWN”; chit=up if ch==“UP” else dn
mk=ds[:7]
if mk not in monthly: monthly[mk]={“n”:0,“berr”:0,“bw1”:0,“dn”:0,“up”:0,“dc”:0,“nei”:0}
m=monthly[mk]; m[“n”]+=1; m[“berr”]+=berr
if berr<=1: m[“bw1”]+=1
if dn: m[“dn”]+=1
if up: m[“up”]+=1
if chit: m[“dc”]+=1
if cs==“NEITHER”: m[“nei”]+=1
results.append({“dev”:dev,“dn”:dn,“up”:up,“cs”:cs,“ch”:ch,“chit”:chit,“berr”:berr})

n=len(results)
bw1=sum(1 for r in results if r[“berr”]<=1)
sdn=sum(1 for r in results if r[“dn”])
sup=sum(1 for r in results if r[“up”])
dc=sum(1 for r in results if r[“chit”])
nei=sum(1 for r in results if r[“cs”]==“NEITHER”)
ae=sum(r[“berr”] for r in results)/n
print(””)
print(“TOTAL DAYS: “+str(n))
print(“Avg error:     “+str(round(ae,2))+“C”)
print(“Within 1C:     “+str(bw1)+”/”+str(n)+” = “+str(round(bw1/n*100)))+”%”
print(“Skew DOWN hit: “+str(sdn)+”/”+str(n)+” = “+str(round(sdn/n*100))+”%”)
print(“Skew UP hit:   “+str(sup)+”/”+str(n)+” = “+str(round(sup/n*100))+”%”)
print(“NEITHER hit:   “+str(nei)+”/”+str(n)+” = “+str(round(nei/n*100))+”%”)
print(“Dev>0=UP rule: “+str(dc)+”/”+str(n)+” = “+str(round(dc/n*100))+”%”)
print(””)
print(“THRESHOLD SENSITIVITY:”)
print(“Thresh   Correct    Pct”)
for t in [-0.5,-0.25,0,0.1,0.25,0.5,0.75,1.0]:
c=sum(1 for r in results if (r[“up”] if r[“dev”]>t else r[“dn”]))
print(str(round(t,2)).ljust(8)+” “+str(c).ljust(10)+” “+str(round(c/n*100,1))+”%”)
print(””)
print(“MONTHLY:”)
print(“Month      Days  Err   W1C   DN%   UP%  DevRule  NEI”)
for mk in sorted(monthly):
m=monthly[mk]; nn=m[“n”]
print(mk+”  “+str(nn).rjust(4)+”  “+
str(round(m[“berr”]/nn,2)).rjust(5)+”  “+
str(round(m[“bw1”]/nn*100)).rjust(3)+”%  “+
str(round(m[“dn”]/nn*100)).rjust(3)+”%  “+
str(round(m[“up”]/nn*100)).rjust(3)+”%  “+
str(round(m[“dc”]/nn*100)).rjust(5)+”%  “+
str(round(m[“nei”]/nn*100)).rjust(3)+”%”)
print(””)
print(“DEV BY CORRECT SKEW:”)
for lbl,devs in [(“UP only”,[r[“dev”] for r in results if r[“cs”]==“UP”]),
(“DOWN only”,[r[“dev”] for r in results if r[“cs”]==“DOWN”]),
(“BOTH”,[r[“dev”] for r in results if r[“cs”]==“BOTH”]),
(“NEITHER”,[r[“dev”] for r in results if r[“cs”]==“NEITHER”])]:
if devs:
avg=sum(devs)/len(devs)
print(”  “+lbl.ljust(12)+”: n=”+str(len(devs)).rjust(4)+
“, avg=”+(”{:+.2f}”.format(avg))+“C”+
“, min=”+(”{:+.2f}”.format(min(devs)))+
“, max=”+(”{:+.2f}”.format(max(devs))))
print(“Done.”)