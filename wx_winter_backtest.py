import urllib.request,json,math
from datetime import datetime

LAT=51.5048;LON=0.0495;ANC=9;CON=10;PHI=13;RATIO=60;R1=3.0
START=‘2022-10-01’;END=‘2026-02-27’
WINTER_MONTHS=[10,11,12,1,2]

def fetch(url):
req=urllib.request.Request(url,headers={‘User-Agent’:‘x’})
return json.loads(urllib.request.urlopen(req,timeout=30).read())

def fan(aT,hrs,deg,ratio):
return aT+hrs*ratio*math.tan(math.radians(deg))

def fhr(hr,t):
best=None;bd=float(‘inf’)
for tt,v in hr:
diff=abs((tt-t).total_seconds())
if diff<bd:bd=diff;best=v
if diff>7200 and bd<3600:break
return best if bd<3600 else None

print(‘Fetching ‘+START+’ to ‘+END+’…’)
url=(‘https://archive-api.open-meteo.com/v1/archive’
‘?latitude=51.5048&longitude=0.0495’
‘&hourly=temperature_2m&daily=temperature_2m_max’
‘&temperature_unit=celsius&timezone=UTC’
‘&start_date=’+START+’&end_date=’+END)
d=fetch(url)
ht=d[‘hourly’][‘time’];hv=d[‘hourly’][‘temperature_2m’]
dt=d[‘daily’][‘time’];dv=d[‘daily’][‘temperature_2m_max’]
print(‘Got ‘+str(len(dt))+’ days, filtering to winter months…’)
hr=[(datetime.fromisoformat(ht[i]),hv[i]) for i in range(len(ht)) if hv[i] is not None]
daily={dt[i]:dv[i] for i in range(len(dt)) if dv[i] is not None}

# Filter to winter months only

winter_days=[ds for ds in dt if int(ds[5:7]) in WINTER_MONTHS and daily.get(ds) is not None]
print(’Winter days: ’+str(len(winter_days)))

# Grid search: angles x ratios x phi hours x confirm hours

angles=[27,30,33,36,40,45]
ratios=[40,50,60,70,80,100]
phi_hours=[12,13,14]
con_hours=[10,11]

print(‘Grid searching ‘+str(len(angles)*len(ratios)*len(phi_hours)*len(con_hours))+’ combos…’)

best_err=float(‘inf’)
best_cfg=None
best_w1=0

results_cache={}

def run(ang,ratio,phi,con):
key=(ang,ratio,phi,con)
if key in results_cache:
return results_cache[key]
results=[]
for ds in winter_days:
ah=daily.get(ds)
if not ah:continue
p2=ds.split(’-’);yr,mo,dy=int(p2[0]),int(p2[1]),int(p2[2])
aT=fhr(hr,datetime(yr,mo,dy,ANC))
cT=fhr(hr,datetime(yr,mo,dy,con))
if aT is None or cT is None:continue
bp=fan(aT,(phi-ANC)/ratio,ang,ratio)
dev=cT-fan(aT,(con-ANC)/ratio,ang,ratio)
bpred=bp+dev
berr=abs(ah-bpred)
bf=math.floor(bpred);bc=bf+1;abr=round(ah)
dn=abr in(bf,bc);up=abr in(bc,bc+1)
results.append({‘berr’:berr,‘dn’:dn,‘up’:up,‘aT’:aT,‘ds’:ds,‘pred’:bpred,‘actual’:ah})
results_cache[key]=results
return results

for ang in angles:
for ratio in ratios:
for phi in phi_hours:
for con in con_hours:
res=run(ang,ratio,phi,con)
if not res:continue
n=len(res)
ae=sum(r[‘berr’] for r in res)/n
w1=sum(1 for r in res if r[‘berr’]<=1)
if ae<best_err:
best_err=ae
best_cfg=(ang,ratio,phi,con)
best_w1=w1

print(’’)
print(‘BEST CONFIG BY AVG ERROR:’)
ang,ratio,phi,con=best_cfg
print(’  Angle: +’+str(ang))
print(’  Ratio: ‘+str(ratio))
print(’  Predict Hi Hour: ‘+str(phi)+‘H UTC’)
print(’  Confirm Hour: ‘+str(con)+‘H UTC’)
print(’  Avg Error: ‘+str(round(best_err,3))+‘C’)
print(’  Within 1C: ‘+str(best_w1)+’/’+str(len(run(*best_cfg)))+’ = ‘+str(round(best_w1/len(run(*best_cfg))*100))+’%’)

# Also find best by w1c

best_w1c=0;best_cfg_w1=None
for ang in angles:
for ratio in ratios:
for phi in phi_hours:
for con in con_hours:
res=run(ang,ratio,phi,con)
if not res:continue
w1=sum(1 for r in res if r[‘berr’]<=1)
if w1>best_w1c:best_w1c=w1;best_cfg_w1=(ang,ratio,phi,con)

print(’’)
print(‘BEST CONFIG BY WITHIN-1C:’)
ang,ratio,phi,con=best_cfg_w1
res=run(*best_cfg_w1)
n=len(res)
ae=sum(r[‘berr’] for r in res)/n
w1=sum(1 for r in res if r[‘berr’]<=1)
dual=sum(1 for r in res if r[‘dn’])
print(’  Angle: +’+str(ang))
print(’  Ratio: ‘+str(ratio))
print(’  Predict Hi Hour: ‘+str(phi)+‘H UTC’)
print(’  Confirm Hour: ‘+str(con)+‘H UTC’)
print(’  Avg Error: ‘+str(round(ae,3))+‘C’)
print(’  Within 1C: ‘+str(w1)+’/’+str(n)+’ = ’+str(round(w1/n*100))+’%’)
print(’  Dual Bracket: ‘+str(dual)+’/’+str(n)+’ = ‘+str(round(dual/n*100))+’%’)

# Monthly breakdown for best w1c config

print(’’)
print(‘MONTHLY BREAKDOWN (best config):’)
print(‘Month      n    err   w1c   dual’)
monthly={}
for r in res:
mk=r[‘ds’][:7]
if mk not in monthly:monthly[mk]={‘n’:0,‘err’:0,‘w1’:0,‘dual’:0}
m=monthly[mk];m[‘n’]+=1;m[‘err’]+=r[‘berr’]
if r[‘berr’]<=1:m[‘w1’]+=1
if r[‘dn’]:m[‘dual’]+=1
for mk in sorted(monthly):
m=monthly[mk];nn=m[‘n’]
print(mk+’  ‘+str(nn).rjust(3)+’  ‘+str(round(m[‘err’]/nn,2)).rjust(5)+’  ‘+str(round(m[‘w1’]/nn*100)).rjust(3)+’%  ’+str(round(m[‘dual’]/nn*100)).rjust(3)+’%’)

# Anchor temp breakdown

print(’’)
print(‘BY ANCHOR TEMP (best config):’)
bands=[(0,3,’<3C’),(3,5,‘3-5C’),(5,8,‘5-8C’),(8,99,’>=8C’)]
for lo,hi,lbl in bands:
sub=[r for r in res if lo<=r[‘aT’]<hi]
if not sub:continue
nn=len(sub)
ae2=sum(r[‘berr’] for r in sub)/nn
w1=sum(1 for r in sub if r[‘berr’]<=1)
dual=sum(1 for r in sub if r[‘dn’])
print(lbl+’ n=’+str(nn)+’ err=’+str(round(ae2,2))+‘C w1c=’+str(round(w1/nn*100))+’% dual=’+str(round(dual/nn*100))+’%’)

print(’’)
print(‘Done.’)