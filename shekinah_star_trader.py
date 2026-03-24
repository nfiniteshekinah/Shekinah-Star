"""
╔══════════════════════════════════════════════════════════════════╗
║   Shekinah Star — Trading Engine v3.0                           ║
║   Built by Sarah DeFer | @Shekinah9Divine                       ║
║                                                                  ║
║   DESIGN PRINCIPLES:                                            ║
║   - Trade execution = pure HL SDK, ZERO API cost               ║
║   - Stop losses set ON exchange at entry, always protected      ║
║   - AI down = alert Sarah, hold, never panic close             ║
║   - Signals use AI but trades never depend on AI being live    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import requests
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/ShekinahD/.env')

# ══ KEYS ══════════════════════════════════════════════════════════
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')
GEMINI_KEY    = os.getenv('GEMINI_API_KEY', '')
GROQ_KEY      = os.getenv('GROQ_API_KEY', '')
AGENT_KEY     = os.getenv('AGENT_PRIVATE_KEY', '')

# ══ CONFIG ════════════════════════════════════════════════════════
WALLET    = '0x11E8B5C950B2C187D57DB370a9bfdc83412B3f4D'
HL_INFO   = 'https://api.hyperliquid.xyz/info'
WATCHLIST = ['BTC', 'ETH', 'SOL', 'XRP', 'AVAX', 'LINK', 'ARB', 'MATIC']
STATE_FILE = '/home/ShekinahD/star_state.json'

CONFIG = {
    'starting_capital':      97.80,
    'max_risk_per_trade':    0.02,
    'max_open_positions':    8,
    'drawdown_safe_trigger': 0.15,  # 15% drawdown from peak triggers safe mode
    'liquidation_buffer':    0.10,  # Close ALL positions if account ratio < 10%
    'trailing_stop_pct':     0.015, # Trail stop up by 1.5% as profit grows
    'scan_interval':         1800,  # 30 min — protects free API quota
    'min_confidence':        75,
    'min_position_usd':      12.0,  # Hyperliquid minimum + buffer
}


# ══ LOGGING ═══════════════════════════════════════════════════════
def log(msg, level='INFO'):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] [{level}] {msg}', flush=True)


def print_banner():
    print('''
╔══════════════════════════════════════════════════════════════════╗
║  ⭐  SHEKINAH STAR — Trading Engine v3.0                       ║
║      Built by Sarah DeFer | @Shekinah9Divine                   ║
╚══════════════════════════════════════════════════════════════════╝
''')


# ══ STATE FILE (shared with Flask/chat) ═══════════════════════════
def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f'State save error: {e}', 'ERROR')


def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {
        'active': True,
        'mode': 'ai_decides',
        'total_trades': 0,
        'winning_trades': 0,
        'scan_count': 0,
        'last_scan': None,
        'last_signal': None,
        'last_trade': None,
        'signal_log': [],
        'trade_log': [],
        'alert': None,
        'ai_status': 'unknown',
    }


# ══ READ BRAIN (chat commands) ═══════════════════════════════════
BRAIN_FILE = '/home/ShekinahD/star_brain.json'

def read_brain():
    try:
        if os.path.exists(BRAIN_FILE):
            with open(BRAIN_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {'bias':'neutral','allowed_coins':WATCHLIST,'max_positions':4,'trading_paused':False,'close_all':False}

def clear_close_all():
    try:
        brain = read_brain()
        brain['close_all'] = False
        with open(BRAIN_FILE,'w') as f:
            json.dump(brain, f, indent=2)
    except Exception:
        pass

# ══ ALERT SARAH ═══════════════════════════════════════════════════
def alert_sarah(message, state):
    """Write alert to state file — visible in chat dashboard."""
    log(f'ALERT: {message}', 'WARNING')
    state['alert'] = {
        'message': message,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'requires_action': True,
    }
    save_state(state)


# ══ HYPERLIQUID READ ══════════════════════════════════════════════
def hl_post(payload):
    try:
        r = requests.post(HL_INFO, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f'HL API error: {e}', 'ERROR')
        return {}


def hl_get_price(symbol):
    mids = hl_post({'type': 'allMids'})
    try:
        return float(mids.get(symbol, 0) or 0)
    except Exception:
        return 0.0


def hl_get_portfolio():
    state = hl_post({'type': 'clearinghouseState', 'user': WALLET})
    if not state:
        return {'error': 'Could not fetch'}
    try:
        # Get real balance from spot (Unified Account stores USDC here)
        av = 0.0
        try:
            spot = hl_post({'type': 'spotClearinghouseState', 'user': WALLET})
            for b in spot.get('balances', []):
                if b.get('coin') in ['USDC', 'USD']:
                    av = float(b.get('total', 0) or 0)
                    break
        except Exception:
            pass
        # Fallback to crossMarginSummary
        if av == 0:
            ms = state.get('crossMarginSummary', state.get('marginSummary', {}))
            av = float(ms.get('accountValue', 0) or 0)
        ms   = state.get('crossMarginSummary', state.get('marginSummary', {}))
        used = float(ms.get('totalMarginUsed', 0) or 0)
        positions = []
        for pos in state.get('assetPositions', []):
            p    = pos.get('position', {})
            size = float(p.get('szi', 0) or 0)
            if size != 0:
                positions.append({
                    'symbol':         p.get('coin', ''),
                    'size':           size,
                    'entry_price':    float(p.get('entryPx', 0) or 0),
                    'unrealized_pnl': float(p.get('unrealizedPnl', 0) or 0),
                    'direction':      'LONG' if size > 0 else 'SHORT',
                })
        return {
            'account_value':  round(av, 2),
            'available':      round(av - used, 2),
            'margin_used':    round(used, 2),
            'positions':      positions,
            'position_count': len(positions),
        }
    except Exception as e:
        return {'error': str(e)}


# ══ TRAILING STOP MANAGER ════════════════════════════════════════
def get_subscriber_config(email=None):
    """Get customized risk config for a subscriber — Enterprise only."""
    base = {
        'drawdown_safe_trigger': CONFIG['drawdown_safe_trigger'],
        'liquidation_buffer':    CONFIG['liquidation_buffer'],
        'trailing_stop_pct':     CONFIG['trailing_stop_pct'],
        'max_risk_per_trade':    CONFIG['max_risk_per_trade'],
        'max_open_positions':    CONFIG['max_open_positions'],
    }
    if not email:
        return base
    try:
        import json as _j
        subs = _j.load(open('/home/ShekinahD/star_subscribers.json'))
        for s in subs:
            if s.get('email') == email and s.get('tier') == 'enterprise':
                custom = s.get('custom_config', {})
                base.update({k: v for k, v in custom.items() if v is not None})
                return base
    except Exception:
        pass
    return base


def manage_trailing_stops(state):
    """
    For each open position:
    - If in profit AND momentum rising → trail stop up, let it run
    - If in profit AND momentum flat/fading → close, take the win
    - Stop NEVER moves down — only up
    """
    if not AGENT_KEY:
        return

    exchange = get_exchange()
    if not exchange:
        return

    try:
        cs        = hl_post({'type': 'clearinghouseState', 'user': WALLET})
        mids      = hl_post({'type': 'allMids'}) or {}
        positions = cs.get('assetPositions', [])

        for pos in positions:
            p    = pos.get('position', {})
            size = float(p.get('szi', 0) or 0)
            if size == 0:
                continue

            symbol    = p.get('coin', '')
            entry     = float(p.get('entryPx', 0) or 0)
            upnl      = float(p.get('unrealizedPnl', 0) or 0)
            is_long   = size > 0
            cur_price = float(mids.get(symbol, 0) or 0)

            if entry == 0 or cur_price == 0:
                continue

            # Only manage if in profit
            if upnl <= 0:
                continue

            profit_pct = upnl / (abs(size) * entry) if entry > 0 else 0

            # Trail stop up — never down
            trail_pct   = CONFIG['trailing_stop_pct']
            trail_price = cur_price * (1 - trail_pct) if is_long else cur_price * (1 + trail_pct)

            # Track highest trailing stop in state
            trail_key = f'trail_stop_{symbol}'
            prev_trail = state.get(trail_key, 0)

            if is_long:
                new_trail = max(trail_price, prev_trail)
            else:
                new_trail = min(trail_price, prev_trail) if prev_trail > 0 else trail_price

            if new_trail != prev_trail:
                state[trail_key] = new_trail
                log(f'TRAIL STOP {symbol}: moved to ${new_trail:,.4f} (profit {profit_pct*100:.1f}%)', 'INFO')

            # Check if trailing stop hit
            stop_hit = (is_long and cur_price <= new_trail) or (not is_long and cur_price >= new_trail)
            if stop_hit and new_trail > 0:
                log(f'TRAILING STOP HIT {symbol} @ ${cur_price:,.4f} — closing with profit', 'SUCCESS')
                try:
                    exchange.market_close(symbol, not is_long, abs(size))
                    state.pop(trail_key, None)
                    log(f'Closed {symbol} at trailing stop — profit secured', 'SUCCESS')
                except Exception as ce:
                    log(f'Trailing stop close error: {ce}', 'ERROR')

    except Exception as e:
        log(f'Trailing stop manager error: {e}', 'WARNING')


# ══ WEB SEARCH — REAL-TIME INTELLIGENCE ══════════════════════════
TAVILY_KEY = os.getenv('TAVILY_API_KEY', '')

def web_search(query, max_results=3):
    """Search for real-time news and intelligence using Tavily."""
    if not TAVILY_KEY:
        return []
    try:
        r = requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key': TAVILY_KEY,
                'query': query,
                'search_depth': 'basic',
                'max_results': max_results,
                'include_answer': True,
            },
            timeout=10)
        if r.status_code == 200:
            data = r.json()
            results = []
            if data.get('answer'):
                results.append(data['answer'])
            for res in data.get('results', [])[:max_results]:
                results.append(f"{res.get('title','')}: {res.get('content','')[:200]}")
            return results
    except Exception as e:
        log(f'Web search error: {e}', 'WARNING')
    return []

def get_market_intelligence(symbol):
    """Get real-time news and sentiment for a symbol before trading."""
    if not TAVILY_KEY:
        return ''
    try:
        coin_names = {
            'BTC': 'Bitcoin', 'ETH': 'Ethereum', 'SOL': 'Solana',
            'AVAX': 'Avalanche', 'DOGE': 'Dogecoin', 'ARB': 'Arbitrum',
            'LINK': 'Chainlink', 'MATIC': 'Polygon'
        }
        name = coin_names.get(symbol, symbol)
        results = web_search(f'{name} crypto price news today 2026', max_results=3)
        if results:
            intel = ' | '.join(results[:3])[:500]
            log(f'Web intel for {symbol}: {intel[:100]}...', 'INFO')
            return f'
REAL-TIME INTELLIGENCE: {intel}'
    except Exception as e:
        log(f'Intel error: {e}', 'WARNING')
    return ''

# ══ HYPERLIQUID EXCHANGE — NO API COST ════════════════════════════
def get_exchange():
    """Initialize HL exchange client. Zero API cost — direct SDK."""
    try:
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants
        import eth_account
        if not AGENT_KEY:
            log('No AGENT_PRIVATE_KEY in .env', 'ERROR')
            return None
        account  = eth_account.Account.from_key(AGENT_KEY)
        exchange = Exchange(
            account,
            constants.MAINNET_API_URL,
            vault_address=None,
            account_address=WALLET,
        )
        return exchange
    except Exception as e:
        log(f'Exchange init error: {e}', 'ERROR')
        return None


# ══ EXECUTE TRADE — ZERO API COST ════════════════════════════════
def execute_trade(signal, balance, state):
    """
    Place order on Hyperliquid.
    Uses HL SDK ONLY — no AI API calls, no API cost.
    Stop loss set ON exchange — protected even if bot dies.
    """
    if not AGENT_KEY:
        log('No agent key — signal only mode', 'WARNING')
        return False

    exchange = get_exchange()
    if not exchange:
        return False

    try:
        symbol   = signal['symbol']
        is_buy   = signal['action'] == 'BUY'
        entry    = float(signal.get('entry_price', 0) or 0)
        stop     = float(signal.get('stop_loss', 0) or 0)
        size_usd = float(signal.get('position_size_usd', balance * CONFIG['max_risk_per_trade']) or 0)
        size_usd = max(size_usd, CONFIG.get('min_position_usd', 12.0))  # Enforce minimum

        # Coin-specific minimum lot sizes on Hyperliquid
        coin_min_usd = {
            'BTC': 12.0, 'ETH': 12.0, 'SOL': 12.0, 'XRP': 12.0,
            'AVAX': 15.0, 'LINK': 12.0, 'ARB': 15.0, 'MATIC': 15.0,
            'DOGE': 20.0,
        }
        size_usd = max(size_usd, coin_min_usd.get(symbol, 12.0))
        leverage = int(signal.get('leverage', 2) or 2)

        if entry == 0 or size_usd == 0:
            log(f'Invalid signal values for {symbol}', 'ERROR')
            return False

        # ── CANCEL ALL EXISTING OPEN ORDERS FOR THIS SYMBOL ──────────
        # Prevents stacking unfilled orders on same coin
        try:
            open_orders = hl_post({'type': 'openOrders', 'user': WALLET})
            if isinstance(open_orders, list):
                cancelled = 0
                for order in open_orders:
                    if order.get('coin') == symbol:
                        try:
                            exchange.cancel(symbol, order['oid'])
                            cancelled += 1
                        except Exception as ce:
                            log(f'Cancel order error: {ce}', 'WARNING')
                if cancelled > 0:
                    log(f'Cancelled {cancelled} existing {symbol} orders before new entry', 'INFO')
                    time.sleep(1)
        except Exception as e:
            log(f'Could not check open orders: {e}', 'WARNING')

        # ── CHECK IF ALREADY IN POSITION FOR THIS SYMBOL ──────────
        # Only one position per coin allowed
        try:
            cs = hl_post({'type': 'clearinghouseState', 'user': WALLET})
            for pos in cs.get('assetPositions', []):
                p    = pos.get('position', {})
                size = float(p.get('szi', 0) or 0)
                if p.get('coin') == symbol and size != 0:
                    existing_dir = 'LONG' if size > 0 else 'SHORT'
                    signal_dir   = 'LONG' if is_buy else 'SHORT'
                    if existing_dir == signal_dir:
                        log(f'Already {existing_dir} {symbol} — skipping duplicate entry', 'INFO')
                        return False
                    else:
                        log(f'Closing {existing_dir} {symbol} before reversing to {signal_dir}', 'INFO')
                        exchange.market_close(symbol, not is_buy, abs(size))
                        time.sleep(2)
        except Exception as e:
            log(f'Position check error: {e}', 'WARNING')

        # Set leverage — no API cost
        try:
            exchange.update_leverage(leverage, symbol)
        except Exception:
            pass

        # Calculate size
        price     = hl_get_price(symbol)
        coin_size = round(size_usd / price, 4) if price > 0 else 0
        if coin_size == 0:
            return False

        # Place market order — no API cost
        log(f"Placing {'BUY' if is_buy else 'SELL'}: {coin_size} {symbol} ~${price:,.2f}", 'TRADE')
        result = exchange.market_open(symbol, is_buy, coin_size)
        log(f'Entry result: {result}', 'TRADE')

        time.sleep(2)

        # Set stop loss ON EXCHANGE — protected even if bot goes down
        if stop > 0:
            try:
                exchange.order(
                    symbol, not is_buy, coin_size, stop,
                    {'trigger': {'triggerPx': stop, 'isMarket': True, 'tpsl': 'sl'}},
                )
                log(f'Stop loss set ON EXCHANGE @ ${stop:,.2f} — protected', 'TRADE')
            except Exception as e:
                log(f'Stop loss warning: {e}', 'WARNING')
                alert_sarah(f'Stop loss failed for {symbol} @ ${stop:,.2f} — set manually!', state)

        # Log trade
        trade = {
            'action':    signal['action'],
            'symbol':    symbol,
            'entry':     entry,
            'stop':      stop,
            'size_usd':  size_usd,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        state['total_trades'] += 1
        state['last_trade']    = trade
        state['trade_log'].insert(0, trade)
        if len(state['trade_log']) > 50:
            state['trade_log'] = state['trade_log'][:50]
        save_state(state)

        # Only count as trade if actually filled
        filled = False
        try:
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            for s in statuses:
                if 'filled' in s:
                    filled = True
                    break
        except Exception:
            pass

        if filled:
            log(f"TRADE FILLED: {signal['action']} {symbol} ${size_usd:.2f}", 'SUCCESS')
        else:
            log(f"TRADE FAILED (not filled): {signal['action']} {symbol} — not counting", 'WARNING')
            state['total_trades'] -= 1  # Undo the increment
            return False

        # Mirror trade to all active fund accounts (Sovereign+)
        try:
            from shekinah_star_fund import mirror_trade_to_all
            mirror_trade_to_all(signal)
        except Exception as e:
            log(f'Fund mirror error: {e}', 'WARNING')

        return True

    except Exception as e:
        log(f'Trade execution failed: {e}', 'ERROR')
        alert_sarah(f'Trade execution failed for {signal.get("symbol","?")} — {e}', state)
        return False


# ══ AI SIGNAL — WITH FALLBACK CHAIN ══════════════════════════════
def get_ai_signal(prompt):
    """
    Try all AI providers. Returns text or None.
    Trading never depends on this succeeding.
    """
    # 1. Anthropic
    if ANTHROPIC_KEY:
        try:
            r = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={'Content-Type':'application/json','x-api-key':ANTHROPIC_KEY,'anthropic-version':'2023-06-01'},
                json={'model':'claude-sonnet-4-6','max_tokens':600,'messages':[{'role':'user','content':prompt}]},
                timeout=45)
            if r.status_code == 200:
                return r.json()['content'][0]['text'].strip(), 'anthropic'
        except Exception:
            pass

    # 2. Groq (free, 14,400/day)
    if GROQ_KEY:
        try:
            r = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization':f'Bearer {GROQ_KEY}','Content-Type':'application/json'},
                json={'model':'llama-3.3-70b-versatile','messages':[{'role':'user','content':prompt}],'max_tokens':600},
                timeout=45)
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content'].strip(), 'groq'
        except Exception:
            pass

    # 3. Gemini (free, 1000/day)
    if GEMINI_KEY:
        try:
            r = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}',
                json={'contents':[{'role':'user','parts':[{'text':prompt}]}],'generationConfig':{'maxOutputTokens':600}},
                timeout=45)
            if r.status_code == 200:
                return r.json()['candidates'][0]['content']['parts'][0]['text'].strip(), 'gemini'
        except Exception:
            pass

    return None, None


# ══ FIBONACCI ═════════════════════════════════════════════════════
def calc_fib(price, symbol):
    vol_map = {'BTC':0.04,'ETH':0.055,'SOL':0.08,'AVAX':0.09,'DOGE':0.10,'ARB':0.10,'LINK':0.08,'MATIC':0.09}
    vol  = vol_map.get(symbol, 0.07)
    high = price * (1 + vol)
    low  = price * (1 - vol)
    diff = high - low
    return {
        '0.236': round(high - diff*0.236, 4),
        '0.382': round(high - diff*0.382, 4),
        '0.500': round(high - diff*0.500, 4),
        '0.618': round(high - diff*0.618, 4),
        '0.786': round(high - diff*0.786, 4),
        '1.618': round(low  - diff*0.618, 4),
    }


# ══ SESSION ═══════════════════════════════════════════════════════
def get_session():
    now  = datetime.utcnow()
    hour = now.hour
    day  = now.weekday()
    if 0 <= hour < 8:
        session, note = 'ASIA', 'Asian session - lower liquidity'
    elif 8 <= hour < 16:
        session, note = 'EUROPE', 'European session - institutional flow'
    else:
        session, note = 'NEW_YORK', 'US session - highest volume'
    eod = 'END OF DAY - watch reversals.' if hour >= 22 else ''
    eow = 'END OF WEEK - high reversal probability.' if day == 4 and hour >= 18 else ''
    return {'session':session,'note':note,'eod':eod,'eow':eow,'day':['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day]}


# ══ GENERATE SIGNAL ═══════════════════════════════════════════════
def generate_signal(symbol, balance, open_count):
    price = hl_get_price(symbol)
    if price == 0:
        return {'action':'HOLD','symbol':symbol,'reason':'No price'}

    fib      = calc_fib(price, symbol)
    sesh     = get_session()
    max_pos  = balance * CONFIG['max_risk_per_trade']

    # Get real-time web intelligence before generating signal
    web_intel = get_market_intelligence(symbol)

    prompt = (
        'You are SHEKINAH STAR, AI crypto trading agent by Sarah DeFer (@Shekinah9Divine). '
        'Apply all 13 strategies including real-time web intelligence. Return ONLY valid JSON.\n\n'
        f'SYMBOL: {symbol} | PRICE: ${price:,.4f}\n'
        f'TIME: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")} ({sesh["day"]})\n'
        f'SESSION: {sesh["session"]} - {sesh["note"]}\n'
        + (f'WARNING: {sesh["eod"]}\n' if sesh['eod'] else '')
        + (f'NOTE: {sesh["eow"]}\n' if sesh['eow'] else '')
        + f'\nFIBONACCI: 23.6%=${fib["0.236"]:,.2f} | 38.2%=${fib["0.382"]:,.2f} | '
        f'61.8%=${fib["0.618"]:,.2f} (GOLDEN) | 161.8%=${fib["1.618"]:,.2f}\n'
        f'PORTFOLIO: Balance=${balance:.2f} | Positions={open_count}/{CONFIG["max_open_positions"]} | MaxSize=${max_pos:.2f}\n'
        + web_intel + '\n\n'
        '14 STRATEGIES: Fibonacci, PTJ Trend, Livermore Tape, Wyckoff, Druckenmiller, '
        'Soros Reflexivity, Elliott Wave, Moving Averages, ICT Structure, Wilder Momentum, '
        'RenTech Quant, Session Analysis, Fractal Coastline, Real-Time Web Intelligence\n\n'
        'FRACTAL COASTLINE: Markets are fractal like a coastline — short from a ship but '
        'thousands of miles of opportunity up close. Analyze ALL timeframes: 5min micro-waves, '
        '1hr tidal patterns, 4hr primary trend, Daily macro, Weekly cycle. Trade where ALL '
        'fractal levels align — micro waves moving WITH macro tide = highest conviction. '
        'Fractal alignment across 3+ timeframes = confidence boost +15%.\n\n'
        'CORRELATION INTELLIGENCE: BTC ETH SOL XRP and most alts are highly correlated in 2026. '
        'Use this strategically: BTC leads — if BTC is bullish, altcoins amplify the move. '
        'SOL/AVAX/DOGE move 2-5x BTC percentage moves. XRP moves on its own regulation news. '
        'Never open conflicting positions (LONG BTC + SHORT ETH) — they cancel out. '
        'Stack positions in the same direction across correlated coins for maximum upside.\n\n'
        'RULES: 3+ strategies agree. Min 3:1 R/R. Stop-loss required. Max 2% risk.\n\n'
        'JSON ONLY:\n'
        '{"action":"BUY or SELL or HOLD","symbol":"' + symbol + '",'
        '"confidence":0,"entry_price":' + str(price) + ','
        '"stop_loss":0.0,"target_1":0.0,"target_2":0.0,"leverage":2,'
        '"position_size_usd":' + str(round(min(max_pos,50.0),2)) + ','
        '"reasoning":"brief","strategies_aligned":["list"],'
        '"fib_key_level":"level","session_factor":"timing",'
        '"risk_reward":0.0,"timeframe":"4h","warnings":""}'
    )

    text, provider = get_ai_signal(prompt)
    if not text:
        return {'action':'HOLD','symbol':symbol,'reason':'No AI provider available'}

    try:
        if '```' in text:
            parts = text.split('```')
            text  = parts[1] if len(parts) > 1 else parts[0]
            if text.startswith('json'):
                text = text[4:]
        signal = json.loads(text.strip())
        signal.update({'symbol':symbol,'price_at_signal':price,'timestamp':datetime.now(timezone.utc).isoformat(),'provider':provider})
        log(f"{signal.get('action','HOLD')} {symbol} | Confidence: {signal.get('confidence',0)}% | Provider: {provider}", 'SIGNAL')
        return signal
    except Exception:
        return {'action':'HOLD','symbol':symbol,'reason':'JSON parse error'}


# ══ MAIN LOOP ═════════════════════════════════════════════════════
def run_star():
    print_banner()
    state = load_state()

    if not AGENT_KEY:
        log('No AGENT_PRIVATE_KEY — signal only mode.', 'WARNING')
    else:
        log('Agent wallet connected. Auto-trading ENABLED.', 'SUCCESS')

    if not any([ANTHROPIC_KEY, GROQ_KEY, GEMINI_KEY]):
        log('No AI provider keys found — add to .env', 'ERROR')
        return

    log(f'AI providers: Anthropic={"YES" if ANTHROPIC_KEY else "NO"} | Groq={"YES" if GROQ_KEY else "NO"} | Gemini={"YES" if GEMINI_KEY else "NO"}', 'INFO')
    log(f'Wallet: {WALLET}', 'INFO')
    log(f'Scan interval: {CONFIG["scan_interval"]}s ({CONFIG["scan_interval"]//60} min)', 'INFO')

    while True:
        try:
            # Check for commands from chat
            cmd_file = '/home/ShekinahD/star_command.json'
            if os.path.exists(cmd_file):
                try:
                    cmd = json.load(open(cmd_file)).get('command','')
                    if cmd == 'stop':
                        state['active'] = False
                        log('Trading STOPPED by command.', 'WARNING')
                    elif cmd == 'start':
                        state['active'] = True
                        log('Trading STARTED by command.', 'SUCCESS')
                    os.remove(cmd_file)
                except Exception:
                    pass

            if not state.get('active', True):
                log('Trading paused. Waiting...', 'INFO')
                time.sleep(60)
                continue

            # Fetch portfolio
            portfolio = hl_get_portfolio()
            if 'error' in portfolio:
                log(f'Portfolio error: {portfolio["error"]}', 'ERROR')
                time.sleep(30)
                continue

            balance   = float(portfolio.get('account_value', 0) or 0)
            pos_count = int(portfolio.get('position_count', 0))

            state['scan_count']    += 1
            state['last_scan']      = datetime.now(timezone.utc).isoformat()
            state['ai_status']      = 'active'
            state['alert']          = None  # Clear old alerts

            log(f'Portfolio: ${balance:.2f} | Positions: {pos_count}', 'INFO')

            # ── TRACK PEAK BALANCE ────────────────────────────────
            peak = state.get('peak_balance', CONFIG['starting_capital'])
            if balance > peak:
                state['peak_balance'] = balance
                peak = balance
                log(f'New peak balance: ${peak:.2f}', 'SUCCESS')

            # ── LIQUIDATION BUFFER — HARD RULE ────────────────────
            # If unified account ratio < 10% close ALL positions immediately
            try:
                cs = hl_post({'type': 'clearinghouseState', 'user': WALLET})
                ms = cs.get('crossMarginSummary', cs.get('marginSummary', {}))
                acct_val    = float(ms.get('accountValue', balance) or balance)
                margin_used = float(ms.get('totalMarginUsed', 0) or 0)
                acct_ratio  = (margin_used / acct_val * 100) if acct_val > 0 else 0
                if acct_ratio > 0 and acct_ratio < CONFIG['liquidation_buffer'] * 100:
                    log(f'LIQUIDATION BUFFER TRIGGERED: Account ratio {acct_ratio:.1f}% — closing ALL positions', 'ERROR')
                    alert_sarah(f'LIQUIDATION BUFFER: Account ratio {acct_ratio:.1f}% — closing all positions to protect capital', state)
                    for pos in cs.get('assetPositions', []):
                        p    = pos.get('position', {})
                        size = float(p.get('szi', 0) or 0)
                        if size != 0:
                            try:
                                exchange = get_exchange()
                                if exchange:
                                    exchange.market_close(p.get('coin'), size < 0, abs(size))
                                    log(f'Closed {p.get("coin")} position for liquidation protection', 'WARNING')
                            except Exception as ce:
                                log(f'Close error: {ce}', 'ERROR')
                    state['mode'] = 'safe'
                    save_state(state)
                    time.sleep(CONFIG['scan_interval'])
                    continue
            except Exception as e:
                log(f'Liquidation buffer check error: {e}', 'WARNING')

            # ── DRAWDOWN PROTECTION — 20% FROM PEAK ───────────────
            if balance > 0 and balance < peak * (1 - CONFIG['drawdown_safe_trigger']):
                if state.get('mode') != 'safe':
                    state['mode'] = 'safe'
                    drawdown_pct = ((peak - balance) / peak * 100)
                    alert_sarah(f'DRAWDOWN PROTECTION: {drawdown_pct:.1f}% drop from peak ${peak:.2f} — balance ${balance:.2f} — SAFE MODE activated. Review before resuming.', state)
                log(f'SAFE MODE — {((peak-balance)/peak*100):.1f}% drawdown from peak. Monitoring only.', 'WARNING')
                save_state(state)
                time.sleep(CONFIG['scan_interval'])
                continue

            # ── TRAILING STOP MANAGEMENT ──────────────────────────
            manage_trailing_stops(state)

            # Run orchestrator agents before scanning
            try:
                from star_orchestrator import security_agent, whale_agent as orch_whale, social_intelligence_agent
                # Security check every scan
                sec = security_agent()
                if not sec.get('secure'):
                    log('Security threat detected — check orchestrator log', 'WARNING')
                # Whale intelligence every scan
                whale_data = orch_whale()
                if whale_data.get('alerts'):
                    for alert in whale_data['alerts']:
                        log(f"WHALE: {alert['coin']} {alert['direction']} funding:{alert['funding']}% signal:{alert['signal']}", 'INFO')
                # Billionaire sentiment every 6th scan (~3 hours)
                if state.get('scan_count', 0) % 6 == 0:
                    log('Running Social Intelligence Agent...', 'INFO')
                    bil = social_intelligence_agent()
                    log(f"Billionaire sentiment: {bil.get('sentiment','neutral').upper()} (boost: {bil.get('confidence_boost',0):+d}%)", 'INFO')
            except Exception as e:
                log(f'Orchestrator error: {e}', 'WARNING')

            # Read brain commands from chat
            brain = read_brain()

            # Handle close all command
            if brain.get('close_all'):
                log('CLOSE ALL command received from chat!', 'WARNING')
                exchange = get_exchange()
                if exchange:
                    for pos in portfolio.get('positions', []):
                        try:
                            sym  = pos['symbol']
                            size = abs(float(pos['size']))
                            is_buy = pos['direction'] == 'SHORT'  # opposite to close
                            exchange.market_close(sym, is_buy, size)
                            log(f'Closed {pos["direction"]} {sym}', 'TRADE')
                        except Exception as e:
                            log(f'Close error {pos["symbol"]}: {e}', 'ERROR')
                clear_close_all()
                alert_sarah('All positions closed by your command.', state)

            # Respect pause
            if brain.get('trading_paused'):
                log('Trading PAUSED by chat command. Monitoring only.', 'WARNING')
                save_state(state)
                time.sleep(CONFIG['scan_interval'])
                continue

            # Get brain settings
            bias          = brain.get('bias', 'neutral')
            allowed_coins = brain.get('allowed_coins', WATCHLIST)
            max_pos       = brain.get('max_positions', CONFIG['max_open_positions'])

            if bias != 'neutral':
                log(f'Brain bias: {bias.upper()} — only taking {"LONG" if bias=="bullish" else "SHORT"} positions', 'INFO')

            # Scan watchlist
            scan_list = [c for c in WATCHLIST if c in allowed_coins]
            
            # Get current open positions once for the whole scan
            current_portfolio  = hl_get_portfolio()
            open_position_syms = {p['symbol'] for p in current_portfolio.get('positions', [])}
            
            if pos_count < max_pos:
                log(f'Scanning {len(scan_list)} markets (bias: {bias})...', 'INFO')
                for symbol in scan_list:
                    if not state.get('active', True):
                        break

                    # Skip if already have a position in this coin
                    if symbol in open_position_syms:
                        log(f'Already in position for {symbol} — skipping', 'INFO')
                        continue

                    signal     = generate_signal(symbol, balance, pos_count)
                    action     = signal.get('action', 'HOLD')
                    confidence = int(signal.get('confidence', 0) or 0)

                    # Log signal
                    state['last_signal'] = signal
                    state['signal_log'].insert(0, signal)
                    if len(state['signal_log']) > 20:
                        state['signal_log'] = state['signal_log'][:20]

                    # Respect brain bias
                    if bias == 'bullish' and action == 'SELL':
                        log(f'Skipping SELL {symbol} — bullish bias active', 'INFO')
                        continue
                    if bias == 'bearish' and action == 'BUY':
                        log(f'Skipping BUY {symbol} — bearish bias active', 'INFO')
                        continue

                    if action in ['BUY','SELL'] and confidence >= CONFIG['min_confidence'] and state.get('mode') != 'safe':
                        log(f'HIGH CONFIDENCE {action} {symbol} ({confidence}%) — executing...', 'SUCCESS')
                        execute_trade(signal, balance, state)
                        pos_count += 1
                        if pos_count >= CONFIG['max_open_positions']:
                            break
                    else:
                        log(f'HOLD {symbol} — {signal.get("reasoning","waiting for setup")[:60]}', 'INFO')

                    time.sleep(3)
            else:
                log('Max positions reached — monitoring only.', 'WARNING')

            save_state(state)
            log(f'Scan complete. Next scan in {CONFIG["scan_interval"]//60} min.', 'SUCCESS')
            time.sleep(CONFIG['scan_interval'])

        except KeyboardInterrupt:
            log('Star shutting down gracefully...', 'WARNING')
            log(f'Session: {state["total_trades"]} trades | Scans: {state["scan_count"]}', 'INFO')
            save_state(state)
            break
        except Exception as e:
            log(f'Unexpected error: {e}', 'ERROR')
            time.sleep(30)


# ══ CLI ═══════════════════════════════════════════════════════════
def handle_cli():
    parser = argparse.ArgumentParser(description='Shekinah Star Trading Engine v3.0')
    parser.add_argument('--balance',           action='store_true')
    parser.add_argument('--transfer-to-perps', type=float, metavar='USD')
    parser.add_argument('--transfer-to-spot',  type=float, metavar='USD')
    args = parser.parse_args()

    if args.balance:
        p = hl_get_portfolio()
        print(json.dumps(p, indent=2))
        return True

    if args.transfer_to_perps or args.transfer_to_spot:
        exchange = get_exchange()
        if not exchange:
            return True
        amount  = args.transfer_to_perps or args.transfer_to_spot
        to_perp = bool(args.transfer_to_perps)
        try:
            result = exchange.usd_class_transfer(amount, to_perp=to_perp)
            print(f'Transfer result: {result}')
        except Exception as e:
            print(f'Transfer error: {e}')
        return True

    return False


def declare_mission():
    """Star declares her mission and identity at every startup."""
    try:
        brain = json.load(open(STATE_FILE.replace('state','brain'))) if os.path.exists(STATE_FILE.replace('state','brain')) else {}
        mission = brain.get('mission','')
        north_star = brain.get('north_star','')
        if mission:
            log(f'MISSION: {mission}', 'INFO')
        if north_star:
            log(f'NORTH STAR: {north_star}', 'INFO')
        log('I am Shekinah Star. I trade with integrity. I serve with purpose. ⭐', 'SUCCESS')
    except Exception:
        log('Shekinah Star — awakening. ⭐', 'SUCCESS')


if __name__ == '__main__':
    if not handle_cli():
        run_star()
