## #!/usr/bin/env python3
“””
ObamaDash Scalp Bot

Monitors BTC LTF fan levels via Binance WebSocket.
Fires Telegram alerts on signal detection.
Tracks paper trades and sends full stats card on close.

Usage:
pip install websocket-client requests
python3 obama_scalp_bot.py
“””

import json, math, time, threading, requests, os, signal, sys
from datetime import datetime, timezone
from websocket import WebSocketApp

# CONFIG

SYMBOL      = ‘BTCUSDT’
ANGLES      = [27, -27, 45, -45, 60, -60, 72, -72, 78, -78]
TG_TOKEN    = ‘8664286768:AAGnDl2X2fybooezONnrhJ2SKBOpZcGezN0’
TG_CHAT     = ‘@obamaonabike’
RISK        = 500        # $ risk per trade
STOP_DIST   = 1500       # $ stop distance
RR          = 0.3        # reward ratio
FEE_RATE    = 0.0002     # 0.02% maker fee
TOL_PCT     = 0.0008     # 0.08% touch tolerance
MIN_BAR     = 5          # ignore signals within first N bars of anchor (avoids anchor candle false triggers)
LOG_FILE    = ‘signals.json’

# STATE

signals     = []
open_trades = {}   # key: signal id
debounce    = {}
anchor_open = None
anchor_sec  = None
lock        = threading.Lock()

# MATH

def angle_price(anchor, bars, deg):
return anchor + bars * math.tan(math.radians(deg))

def get_today_0900():
now = datetime.now(timezone.utc)
anchor = now.replace(hour=9, minute=0, second=0, microsecond=0)
if anchor > now:
from datetime import timedelta
anchor -= timedelta(days=1)
return anchor

def fmt(n):
return f”{n:,.1f}”

# PERSISTENCE

def save_signals():
try:
with open(LOG_FILE, ‘w’) as f:
json.dump(signals, f, indent=2)
except Exception as e:
print(f”[SAVE ERROR] {e}”)

def load_signals():
global signals
if os.path.exists(LOG_FILE):
try:
with open(LOG_FILE) as f:
signals = json.load(f)
print(f”[BOOT] Loaded {len(signals)} signals from {LOG_FILE}”)
except Exception as e:
print(f”[LOAD ERROR] {e}”)
signals = []

# TELEGRAM

def tg_send(text):
try:
r = requests.post(
f’https://api.telegram.org/bot{TG_TOKEN}/sendMessage’,
json={‘chat_id’: TG_CHAT, ‘text’: text, ‘parse_mode’: ‘HTML’},
timeout=10
)
d = r.json()
if not d.get(‘ok’):
print(f”[TG ERROR] {d.get(‘description’)}”)
return d.get(‘ok’, False)
except Exception as e:
print(f”[TG NETWORK] {e}”)
return False

# SESSION STATS

def compute_stats():
closed = [s for s in signals if s[‘result’] != ‘OPEN’]
if not closed:
return None

```
wins       = sum(1 for s in closed if s['result'] == 'WIN')
total      = len(closed)
win_rate   = wins / total * 100 if total else 0
net_pnl    = sum(s['net_pnl'] for s in closed)
total_fees = sum(s['fee_cost'] for s in signals)
avg_r      = net_pnl / (total * RISK) if total else 0
break_even = 1 / (1 + RR) * 100

# Drawdown
running = 0
peak    = 0
max_dd  = 0
for s in closed:
    running += s['net_pnl']
    if running > peak:
        peak = running
    dd = peak - running
    if dd > max_dd:
        max_dd = dd

# Consecutive losses
max_consec = 0
consec = 0
for s in closed:
    if s['result'] == 'LOSS':
        consec += 1
        max_consec = max(max_consec, consec)
    else:
        consec = 0

open_count = sum(1 for s in signals if s['result'] == 'OPEN')

return {
    'total': total,
    'wins': wins,
    'losses': total - wins,
    'open': open_count,
    'win_rate': win_rate,
    'net_pnl': net_pnl,
    'total_fees': total_fees,
    'avg_r': avg_r,
    'max_dd': max_dd,
    'max_consec': max_consec,
    'break_even': break_even,
    'peak': peak,
}
```

def stats_card(label, result_str, entry_price, exit_price, net_pnl, fee_cost):
st = compute_stats()
if not st:
return ‘’

```
emoji = ' ' if net_pnl >= 0 else ' '
pnl_str = f"+${net_pnl:.2f}" if net_pnl >= 0 else f"-${abs(net_pnl):.2f}"
wr_emoji = ' ' if st['win_rate'] >= 85 else '  ' if st['win_rate'] >= st['break_even'] else ' '
dd_pct = f"{st['max_dd']/st['peak']*100:.1f}%" if st['peak'] > 0 else "0%"

lines = [
    f"{emoji} <b>TRADE {result_str}</b>",
    "",
    f"<b>{label}</b> @ <b>${fmt(entry_price)}</b>",
    f"Exit: ${fmt(exit_price)}  |  P&amp;L: {pnl_str}",
    f"Fee: -${fee_cost:.2f}",
    "",
    "    SESSION STATS            ",
    f"Trades:     {st['total']}  ({st['wins']}W / {st['losses']}L / {st['open']} open)",
    f"Win Rate:   {st['win_rate']:.1f}%  {wr_emoji}  (B/E: {st['break_even']:.1f}%)",
    f"Net P&amp;L:    {'+' if st['net_pnl']>=0 else ''}${st['net_pnl']:.2f}",
    f"Avg R:      {st['avg_r']:.3f}R",
    f"Fees Paid:  ${st['total_fees']:.2f}",
    f"Max DD:     ${st['max_dd']:.2f}  ({dd_pct} of peak)",
    f"Max C.Loss: {st['max_consec']}",
    "                             ",
    f"<i>{datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC').upper()}</i>",
]
return '\n'.join(lines)
```

# ANCHOR FETCH

def fetch_anchor():
global anchor_open, anchor_sec
ts = get_today_0900()
anchor_sec = ts.timestamp()
ms = int(anchor_sec * 1000)
try:
r = requests.get(
‘https://api.binance.com/api/v3/klines’,
params={‘symbol’: SYMBOL, ‘interval’: ‘1m’, ‘startTime’: ms, ‘limit’: 1},
timeout=10
)
data = r.json()
if data:
anchor_open = float(data[0][1])
print(f”[ANCHOR] {ts.strftime(’%Y-%m-%d %H:%M UTC’)} open=${anchor_open:.1f}”)
else:
print(”[ANCHOR] No data returned”)
except Exception as e:
print(f”[ANCHOR ERROR] {e}”)

def anchor_refresh_loop():
while True:
time.sleep(3600)
fetch_anchor()

# SIGNAL DETECTION

def detect_signals(candle):
if not anchor_open or not anchor_sec:
return

```
bar = int((candle['time'] - anchor_sec) / 60)
if bar < MIN_BAR:
    return  # too close to anchor or before it

# Only fire signals for candles in the current session
candle_date = datetime.fromtimestamp(candle['time'], timezone.utc).strftime('%Y-%m-%d')
anchor_date = datetime.fromtimestamp(anchor_sec, timezone.utc).strftime('%Y-%m-%d')
if candle_date != anchor_date:
    return  # candle is from a different session than the anchor

date_key = candle_date

for deg in ANGLES:
    label = f"L+{deg}" if deg > 0 else f"L{deg}"
    price = angle_price(anchor_open, bar, deg)
    tol   = price * TOL_PCT

    # LONG: wick down to level, close above
    dk_l = f"{date_key}_{label}"
    if (candle['low']  <= price + tol and candle['low']  >= price - tol
            and candle['close'] > price and dk_l not in debounce):
        debounce[dk_l] = True
        fire_signal('LONG', label, candle, price)

    # SHORT: wick up to level, close below
    dk_s = f"{date_key}_{label}"
    if (candle['high'] >= price - tol and candle['high'] <= price + tol
            and candle['close'] < price and dk_s not in debounce):
        debounce[dk_s] = True
        fire_signal('SHORT', label, candle, price)
```

def fire_signal(direction, label, candle, lv_price):
d       = 1 if direction == ‘LONG’ else -1
entry   = candle[‘close’]
target  = entry + d * STOP_DIST * RR
stop    = entry - d * STOP_DIST
pos_sz  = RISK / STOP_DIST
fee_cost= pos_sz * entry * FEE_RATE * 2
gross_win = RISK * RR
hour    = datetime.fromtimestamp(candle[‘time’], timezone.utc).hour

```
sig = {
    'id':        int(time.time() * 1000),
    'time':      candle['time'],
    'level':     label,
    'dir':       direction,
    'entry':     entry,
    'target':    target,
    'stop':      stop,
    'gross_win': gross_win,
    'risk':      RISK,
    'fee_cost':  fee_cost,
    'result':    'OPEN',
    'gross_pnl': None,
    'net_pnl':   None,
    'hour':      hour,
}

with lock:
    signals.insert(0, sig)
    open_trades[sig['id']] = sig
    save_signals()

dt = datetime.fromtimestamp(candle['time'], timezone.utc).strftime('%d %b %Y %H:%M UTC').upper()
emoji = ' ' if direction == 'LONG' else ' '
msg = (
    f"{emoji} <b>ObamaDash Signal</b>\n\n"
    f"<b>{direction}</b> @ <b>${fmt(entry)}</b>\n"
    f"Level: <code>{label}</code>\n"
    f"Target: ${fmt(target)}  (+${gross_win:.0f})\n"
    f"Stop:   ${fmt(stop)}  (-${RISK:.0f})\n"
    f"RR: {RR}:1  |  Fee: ${fee_cost:.2f}\n\n"
    f"<i>{dt}</i>"
)
tg_send(msg)
print(f"[SIGNAL] {direction} {label} entry={entry:.1f} target={target:.1f} stop={stop:.1f}")
```

# PAPER TRADE MONITORING

def check_open_trades(price):
to_close = []
with lock:
for sig_id, sig in list(open_trades.items()):
d = 1 if sig[‘dir’] == ‘LONG’ else -1
result = None
if d == 1:
if price >= sig[‘target’]: result = ‘WIN’
elif price <= sig[‘stop’]: result = ‘LOSS’
else:
if price <= sig[‘target’]: result = ‘WIN’
elif price >= sig[‘stop’]: result = ‘LOSS’
if result:
sig[‘result’]    = result
sig[‘gross_pnl’] = sig[‘gross_win’] if result == ‘WIN’ else -sig[‘risk’]
sig[‘net_pnl’]   = sig[‘gross_pnl’] - sig[‘fee_cost’]
to_close.append((sig_id, sig.copy(), price))
for sig_id, _, _ in to_close:
del open_trades[sig_id]
if to_close:
save_signals()

```
for sig_id, sig, exit_price in to_close:
    card = stats_card(
        f"{sig['dir']} {sig['level']}",
        sig['result'],
        sig['entry'], exit_price,
        sig['net_pnl'], sig['fee_cost']
    )
    tg_send(card)
    print(f"[CLOSED] {sig['dir']} {sig['level']} result={sig['result']} pnl={sig['net_pnl']:.2f}")
```

# WEBSOCKET

def on_message(ws, message):
try:
data = json.loads(message)
k    = data[‘k’]
price = float(k[‘c’])
check_open_trades(price)
if k[‘x’]:  # candle closed
candle = {
‘time’:  k[‘t’] / 1000,
‘open’:  float(k[‘o’]),
‘high’:  float(k[‘h’]),
‘low’:   float(k[‘l’]),
‘close’: price,
}
detect_signals(candle)
except Exception as e:
print(f”[WS MSG ERROR] {e}”)

def on_open(ws):
print(”[WS] Connected to Binance”)
tg_send(’  <b>ObamaDash Bot ONLINE</b>\nMonitoring BTCUSDT LTF fan levels.\nAlerts will fire here automatically.’)

def on_close(ws, code, msg):
print(f”[WS] Disconnected ({code})   reconnecting in 5s”)
time.sleep(5)
start_ws()

def on_error(ws, error):
print(f”[WS ERROR] {error}”)

def start_ws():
url = f”wss://stream.binance.com:9443/ws/{SYMBOL.lower()}@kline_1m”
ws  = WebSocketApp(url, on_open=on_open, on_message=on_message,
on_error=on_error, on_close=on_close)
ws.run_forever(ping_interval=30, ping_timeout=10)

def shutdown(sig, frame):
print(”\n[SHUTDOWN] Saving signals…”)
save_signals()
tg_send(’  <b>ObamaDash Bot OFFLINE</b>’)
sys.exit(0)

# MAIN

if **name** == ‘**main**’:
print(”=” * 50)
print(”  ObamaDash Scalp Bot”)
print(”=” * 50)

```
signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

load_signals()
fetch_anchor()

# Rebuild open_trades from loaded signals
for sig in signals:
    if sig['result'] == 'OPEN':
        open_trades[sig['id']] = sig
print(f"[BOOT] {len(open_trades)} open trades resumed")

# Anchor refresh every hour in background
threading.Thread(target=anchor_refresh_loop, daemon=True).start()

print("[WS] Starting WebSocket...")
start_ws()
```