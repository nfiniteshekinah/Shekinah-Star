"""
╔══════════════════════════════════════════════════════════════════╗
║   Shekinah Star — Multi-Agent Orchestrator v1.0                 ║
║   Coordinates all Star's specialized agents                     ║
║   Built by Sarah DeFer | @Shekinah9Divine                       ║
╚══════════════════════════════════════════════════════════════════╝

AGENT TEAM:
  🧠 Orchestrator    — coordinates all agents, routes events
  🔍 Research Agent  — Tavily web search, news gathering
  📊 Analysis Agent  — 14-strategy signal analysis
  🐋 Whale Agent     — monitors large on-chain movements
  📱 Social Agent    — posts to X, Discord, Instagram, Facebook
  📧 Email Agent     — subscriber communications
  ⚡ Execution Agent — places trades on Hyperliquid
  🛡️ Guardian Agent  — risk management, ethics, alignment checks

EVENT FLOW:
  External Event → Orchestrator → Route to Agents → Collect Results → Act

HUMAN OVERSIGHT:
  All high-stakes decisions require Sarah's approval
  Audit log of every agent action
  Rollback capability on any agent decision

Run as scheduled task every 15 minutes:
  python /home/ShekinahD/star_orchestrator.py --cycle
"""

import os
import json
import requests
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/ShekinahD/.env')

# ══ CONFIG ════════════════════════════════════════════════════════
GROQ_KEY      = os.getenv('GROQ_API_KEY', '')
TAVILY_KEY    = os.getenv('TAVILY_API_KEY', '')
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')
WALLET        = '0x11E8B5C950B2C187D57DB370a9bfdc83412B3f4D'
HL_INFO       = 'https://api.hyperliquid.xyz/info'

ORCHESTRATOR_LOG  = '/home/ShekinahD/star_orchestrator_log.json'
AGENT_STATE_FILE  = '/home/ShekinahD/star_agent_state.json'
BRAIN_FILE        = '/home/ShekinahD/star_brain.json'
STATE_FILE        = '/home/ShekinahD/star_state.json'
SUBS_FILE         = '/home/ShekinahD/star_subscribers.json'

# Agent registry
AGENTS = {
    'orchestrator':        {'name': 'Orchestrator',              'icon': '🧠', 'status': 'active'},
    'research':            {'name': 'Research Agent',            'icon': '🔍', 'status': 'active'},
    'analysis':            {'name': 'Analysis Agent',            'icon': '📊', 'status': 'active'},
    'whale':               {'name': 'Whale Agent',               'icon': '🐋', 'status': 'active'},
    'social':              {'name': 'Social Agent',              'icon': '📱', 'status': 'active'},
    'email':               {'name': 'Email Agent',               'icon': '📧', 'status': 'active'},
    'guardian':            {'name': 'Guardian Agent',            'icon': '🛡️', 'status': 'active'},
    'social_intelligence': {'name': 'Social Intelligence Agent', 'icon': '👑', 'status': 'active'},
    'security':            {'name': 'Security Agent',            'icon': '🔐', 'status': 'active'},
}


# ══ LOGGING ═══════════════════════════════════════════════════════
def log_event(agent, event_type, data, requires_approval=False):
    """Log every agent action to audit trail."""
    entry = {
        'timestamp':        datetime.now(timezone.utc).isoformat(),
        'agent':            agent,
        'event_type':       event_type,
        'data':             data,
        'requires_approval': requires_approval,
        'approved':         None if requires_approval else True,
    }
    try:
        logs = []
        if os.path.exists(ORCHESTRATOR_LOG):
            logs = json.load(open(ORCHESTRATOR_LOG))
        logs.insert(0, entry)
        logs = logs[:500]  # Keep last 500 events
        with open(ORCHESTRATOR_LOG, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f'Log error: {e}')
    print(f'[{agent.upper()}] {event_type}: {str(data)[:100]}')
    return entry


def get_agent_state():
    try:
        if os.path.exists(AGENT_STATE_FILE):
            return json.load(open(AGENT_STATE_FILE))
    except Exception:
        pass
    return {
        'last_cycle':       None,
        'cycle_count':      0,
        'events_processed': 0,
        'agents_active':    list(AGENTS.keys()),
        'pending_approvals': [],
    }


def save_agent_state(state):
    with open(AGENT_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


# ══ RESEARCH AGENT ════════════════════════════════════════════════
def research_agent(query, context='general'):
    """Search for real-time information on any topic."""
    if not TAVILY_KEY:
        return {'success': False, 'results': [], 'answer': 'No Tavily key'}
    try:
        r = requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key':      TAVILY_KEY,
                'query':        query,
                'search_depth': 'basic',
                'max_results':  5,
                'include_answer': True,
            },
            timeout=15)
        if r.status_code == 200:
            d = r.json()
            log_event('research', 'search_complete', {'query': query, 'results': len(d.get('results', []))})
            return {
                'success': True,
                'answer':  d.get('answer', ''),
                'results': [{'title': res.get('title',''), 'content': res.get('content','')[:300]} for res in d.get('results', [])[:5]],
                'query':   query,
            }
    except Exception as e:
        log_event('research', 'search_error', {'error': str(e)})
    return {'success': False, 'results': [], 'answer': ''}


# ══ WHALE AGENT ═══════════════════════════════════════════════════
def whale_agent():
    """Monitor large on-chain movements and funding rates."""
    try:
        # Get funding rates
        meta = requests.post(HL_INFO, json={'type': 'metaAndAssetCtxs'}, timeout=10).json()
        asset_ctxs = meta[1] if isinstance(meta, list) and len(meta) > 1 else []
        
        alerts = []
        coins = ['BTC', 'ETH', 'SOL', 'AVAX', 'DOGE', 'ARB', 'LINK', 'MATIC']
        
        coin_map = {'BTC':0,'ETH':1,'SOL':2,'AVAX':3,'DOGE':4,'ARB':5,'LINK':6,'MATIC':7}
        
        for coin, idx in coin_map.items():
            if idx < len(asset_ctxs):
                ctx = asset_ctxs[idx]
                funding = float(ctx.get('funding', 0) or 0)
                oi      = float(ctx.get('openInterest', 0) or 0)
                
                # High funding = overleveraged
                if abs(funding) > 0.001:
                    direction = 'OVERLEVERAGED LONGS' if funding > 0 else 'OVERLEVERAGED SHORTS'
                    alerts.append({
                        'type':      'HIGH_FUNDING',
                        'coin':      coin,
                        'funding':   round(funding * 100, 4),
                        'direction': direction,
                        'signal':    'SELL' if funding > 0.001 else 'BUY',
                        'severity':  'HIGH' if abs(funding) > 0.002 else 'MEDIUM',
                    })

        log_event('whale', 'scan_complete', {'alerts': len(alerts), 'coins_checked': len(coins)})
        return {'success': True, 'alerts': alerts, 'timestamp': datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        log_event('whale', 'scan_error', {'error': str(e)})
        return {'success': False, 'alerts': []}


# ══ GUARDIAN AGENT ════════════════════════════════════════════════
def guardian_agent(proposed_action, context):
    """
    Ethics and risk management agent.
    Reviews all high-stakes decisions before execution.
    Aligned with Sarah's values and Star's mission.
    """
    checks = []
    approved = True
    concerns = []

    # Risk check
    action = proposed_action.get('action', '')
    size   = float(proposed_action.get('size_usd', 0) or 0)
    balance = float(context.get('balance', 0) or 0)

    if balance > 0 and size / balance > 0.05:
        concerns.append(f'Position size ${size:.2f} is {size/balance*100:.1f}% of balance — exceeds 5% max')
        approved = False

    # Ethical alignment check
    if action in ['SELL', 'SHORT'] and context.get('bias') == 'bullish':
        concerns.append('Action conflicts with bullish bias — flagging for review')

    # Drawdown check
    pnl_pct = float(context.get('pnl_pct', 0) or 0)
    if pnl_pct < -10:
        concerns.append(f'Portfolio down {abs(pnl_pct):.1f}% — recommend caution')

    # Star alignment check — does this serve the mission?
    alignment_score = 10
    if size < 10:
        alignment_score -= 3  # Too small to matter
        concerns.append('Trade too small to meaningfully grow the account')

    checks.append({'check': 'risk_management', 'passed': approved})
    checks.append({'check': 'ethical_alignment', 'passed': alignment_score >= 7})
    checks.append({'check': 'mission_alignment', 'passed': size >= 10})

    result = {
        'approved':        approved and alignment_score >= 7,
        'alignment_score': alignment_score,
        'checks':          checks,
        'concerns':        concerns,
        'recommendation':  'PROCEED' if approved else 'HOLD',
    }

    log_event('guardian', 'review_complete', result, requires_approval=not approved)
    return result


# ══ ANALYSIS AGENT ════════════════════════════════════════════════
def analysis_agent(symbol, price, research_data, whale_data):
    """
    Synthesizes all inputs and generates a trading recommendation.
    Uses AI with 14-strategy framework.
    """
    if not GROQ_KEY:
        return {'action': 'HOLD', 'confidence': 0, 'reasoning': 'No AI provider'}

    # Build context from other agents
    research_context = ''
    if research_data.get('answer'):
        research_context = f"NEWS: {research_data['answer'][:300]}"

    whale_context = ''
    relevant_alerts = [a for a in whale_data.get('alerts', []) if a['coin'] == symbol]
    if relevant_alerts:
        whale_context = f"WHALE ALERT: {relevant_alerts[0]['direction']} detected, funding {relevant_alerts[0]['funding']}%"

    prompt = f"""You are Shekinah Star's Analysis Agent. Synthesize all data and recommend a trade.

SYMBOL: {symbol} | PRICE: ${price:,.4f}
{research_context}
{whale_context}

Apply all 14 strategies: Fibonacci, PTJ Trend, Livermore, Wyckoff, Druckenmiller, Soros, 
Elliott Wave, Moving Averages, ICT Structure, Wilder Momentum, RenTech, Session Analysis,
Fractal Coastline, Real-Time Web Intelligence.

Return ONLY JSON:
{{"action":"BUY or SELL or HOLD","confidence":0,"entry_price":{price},"stop_loss":0.0,
"target_1":0.0,"target_2":0.0,"leverage":2,"position_size_usd":10.0,
"reasoning":"brief explanation","strategies_aligned":["list"],"risk_reward":0.0}}"""

    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_KEY}', 'Content-Type': 'application/json'},
            json={'model': 'llama-3.1-8b-instant', 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 400},
            timeout=30)
        if r.status_code == 200:
            text = r.json()['choices'][0]['message']['content'].strip()
            if '```' in text:
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
            signal = json.loads(text.strip())
            signal['symbol'] = symbol
            signal['timestamp'] = datetime.now(timezone.utc).isoformat()
            log_event('analysis', 'signal_generated', {'symbol': symbol, 'action': signal.get('action'), 'confidence': signal.get('confidence')})
            return signal
    except Exception as e:
        log_event('analysis', 'signal_error', {'error': str(e)})

    return {'action': 'HOLD', 'confidence': 0, 'symbol': symbol, 'reasoning': 'Analysis failed'}


# ══ SOCIAL AGENT ══════════════════════════════════════════════════
def social_agent(event_type, data):
    """Post relevant events to social channels."""
    try:
        # Post to Discord webhooks
        discord_webhook = os.getenv('DISCORD_WEBHOOK_OBSERVER', '')
        if discord_webhook and event_type in ['whale_alert', 'high_confidence_signal', 'trade_executed']:
            if event_type == 'whale_alert':
                alert = data.get('alert', {})
                msg = f"🐋 **WHALE ALERT** — {alert.get('coin')} | {alert.get('direction')} | Funding: {alert.get('funding')}% | Signal: **{alert.get('signal')}**"
            elif event_type == 'trade_executed':
                msg = f"⭐ **TRADE EXECUTED** — {data.get('action')} {data.get('symbol')} @ ${data.get('entry_price'):,.4f} | Confidence: {data.get('confidence')}%"
            else:
                msg = f"📊 **SIGNAL** — {data.get('action')} {data.get('symbol')} @ {data.get('confidence')}% confidence"

            requests.post(discord_webhook, json={'content': msg, 'username': 'Shekinah Star'}, timeout=10)
            log_event('social', 'discord_posted', {'event': event_type, 'message': msg[:100]})
    except Exception as e:
        log_event('social', 'post_error', {'error': str(e)})


# ══ ORCHESTRATOR ══════════════════════════════════════════════════
def orchestrate_cycle():
    """
    Main orchestration cycle.
    Coordinates all agents, processes events, takes action.
    """
    print(f'\n⭐ ORCHESTRATOR CYCLE — {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}')
    print('='*60)

    agent_state = get_agent_state()
    agent_state['cycle_count'] += 1
    agent_state['last_cycle'] = datetime.now(timezone.utc).isoformat()

    # Get current portfolio state
    try:
        spot = requests.post(HL_INFO, json={'type': 'spotClearinghouseState', 'user': WALLET}, timeout=10).json()
        balance = 0.0
        for b in spot.get('balances', []):
            if b.get('coin') in ['USDC', 'USD']:
                balance = float(b.get('total', 0) or 0)
                break
        pnl     = balance - 97.80
        pnl_pct = (pnl / 97.80) * 100
    except Exception:
        balance, pnl, pnl_pct = 0, 0, 0

    context = {'balance': balance, 'pnl': pnl, 'pnl_pct': pnl_pct}
    print(f'💰 Balance: ${balance:.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)')

    # Read brain for current directives
    brain = {}
    if os.path.exists(BRAIN_FILE):
        brain = json.load(open(BRAIN_FILE))
    context['bias'] = brain.get('bias', 'neutral')

    if brain.get('trading_paused'):
        print('⏸️  Trading paused by Sarah — monitoring only')
        log_event('orchestrator', 'trading_paused', {'reason': 'Sarah directive'})
        save_agent_state(agent_state)
        return

    # ── STEP 0: SECURITY AGENT runs first ────────────────────────
    print('
🔐 Security Agent scanning...')
    security_data = security_agent()
    if not security_data.get('secure'):
        print('  🚨 Security threats detected — alerting Sarah')

    # ── STEP 0b: SOCIAL INTELLIGENCE AGENT ───────────────────────
    # Run every 6 hours to save Tavily quota
    cycle_count = agent_state.get('cycle_count', 0)
    billionaire_data = {'sentiment': 'neutral', 'confidence_boost': 0, 'insights': []}
    if cycle_count % 24 == 0:  # Every 24 cycles = ~6 hours at 15min intervals
        billionaire_data = social_intelligence_agent()
        context['billionaire_sentiment'] = billionaire_data.get('sentiment', 'neutral')
        context['confidence_boost']      = billionaire_data.get('confidence_boost', 0)

    # ── STEP 1: WHALE AGENT scans market ──────────────────────────
    print('\n🐋 Whale Agent scanning...')
    whale_data = whale_agent()
    if whale_data.get('alerts'):
        for alert in whale_data['alerts']:
            print(f"  ⚠️  {alert['coin']}: {alert['direction']} (severity: {alert['severity']})")
            if alert['severity'] == 'HIGH':
                social_agent('whale_alert', {'alert': alert})

    # ── STEP 2: RESEARCH AGENT gathers intelligence ───────────────
    print('\n🔍 Research Agent gathering intelligence...')
    watchlist = brain.get('allowed_coins', ['BTC', 'ETH', 'SOL', 'AVAX'])[:3]
    research_results = {}
    for coin in watchlist[:2]:  # Limit to 2 searches per cycle to save API quota
        coin_names = {'BTC':'Bitcoin','ETH':'Ethereum','SOL':'Solana','AVAX':'Avalanche','DOGE':'Dogecoin'}
        name = coin_names.get(coin, coin)
        research_results[coin] = research_agent(f'{name} crypto news price today')
        time.sleep(1)

    # ── STEP 3: ANALYSIS AGENT generates signals ──────────────────
    print('\n📊 Analysis Agent generating signals...')
    mids = requests.post(HL_INFO, json={'type': 'allMids'}, timeout=10).json()
    signals = []

    for coin in watchlist[:3]:
        price = float(mids.get(coin, 0) or 0)
        if price == 0:
            continue
        research = research_results.get(coin, {'answer': '', 'results': []})
        signal   = analysis_agent(coin, price, research, whale_data)

        if signal.get('confidence', 0) >= 75 and signal.get('action') != 'HOLD':
            signals.append(signal)
            print(f"  ✅ {signal['action']} {coin} @ {signal.get('confidence')}% confidence")
        else:
            print(f"  ⏭️  HOLD {coin} ({signal.get('confidence', 0)}% confidence)")

    # ── STEP 4: GUARDIAN AGENT reviews high-confidence signals ────
    if signals:
        print('\n🛡️  Guardian Agent reviewing signals...')
        approved_signals = []
        for signal in signals:
            review = guardian_agent(signal, context)
            if review['approved']:
                approved_signals.append(signal)
                print(f"  ✅ {signal['action']} {signal['symbol']} approved (alignment: {review['alignment_score']}/10)")
            else:
                print(f"  ❌ {signal['action']} {signal['symbol']} flagged: {', '.join(review['concerns'])}")
                if review['concerns']:
                    agent_state['pending_approvals'].append({
                        'signal':   signal,
                        'concerns': review['concerns'],
                        'time':     datetime.now(timezone.utc).isoformat(),
                    })

        # ── STEP 5: Write approved signals to brain for trader ────
        if approved_signals:
            print(f'\n⚡ Passing {len(approved_signals)} approved signal(s) to Execution Agent...')
            brain['orchestrated_signals'] = approved_signals
            brain['orchestrator_last_run'] = datetime.now(timezone.utc).isoformat()
            with open(BRAIN_FILE, 'w') as f:
                json.dump(brain, f, indent=2)

            for signal in approved_signals:
                social_agent('high_confidence_signal', signal)
                log_event('orchestrator', 'signal_approved', {
                    'symbol':     signal['symbol'],
                    'action':     signal['action'],
                    'confidence': signal['confidence'],
                })

    # ── STEP 6: Save state ────────────────────────────────────────
    agent_state['events_processed'] += len(signals)
    save_agent_state(agent_state)

    print(f'\n✅ Cycle complete — {len(signals)} signals, {len(whale_data.get("alerts", []))} whale alerts')
    print('='*60)


# ══ STATUS ════════════════════════════════════════════════════════
def show_status():
    state = get_agent_state()
    print('\n⭐ SHEKINAH STAR — AGENT TEAM STATUS')
    print('='*50)
    for agent_id, agent in AGENTS.items():
        print(f"  {agent['icon']} {agent['name']}: {agent['status'].upper()}")
    print(f"\n  Cycles run:       {state.get('cycle_count', 0)}")
    print(f"  Events processed: {state.get('events_processed', 0)}")
    print(f"  Last cycle:       {state.get('last_cycle', 'Never')}")
    pending = state.get('pending_approvals', [])
    if pending:
        print(f"\n  ⚠️  {len(pending)} pending approval(s):")
        for p in pending[:3]:
            print(f"    - {p['signal']['action']} {p['signal']['symbol']}: {', '.join(p['concerns'])}")
    print('='*50)


# ══ MAIN ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else '--cycle'

    if cmd == '--cycle':
        orchestrate_cycle()
    elif cmd == '--status':
        show_status()
    elif cmd == '--research':
        query = ' '.join(sys.argv[2:]) or 'Bitcoin crypto news today'
        result = research_agent(query)
        print(f"Answer: {result.get('answer', 'No answer')}")
        for r in result.get('results', []):
            print(f"  - {r['title']}: {r['content'][:150]}")
    elif cmd == '--whale':
        data = whale_agent()
        print(f"Whale alerts: {len(data.get('alerts', []))}")
        for a in data.get('alerts', []):
            print(f"  {a['coin']}: {a['direction']} | {a['funding']}% funding | Signal: {a['signal']}")
    else:
        print('Usage: python star_orchestrator.py --cycle | --status | --research | --whale')


# ══ SOCIAL INTELLIGENCE AGENT ════════════════════════════════════
BILLIONAIRE_ACCOUNTS = [
    {'name': 'Robert Kiyosaki',    'handle': 'theRealKiyosaki', 'focus': 'gold silver bitcoin debt collapse'},
    {'name': 'Michael Saylor',     'handle': 'saylor',          'focus': 'bitcoin BTC strategy'},
    {'name': 'Raoul Pal',          'handle': 'RaoulGMI',        'focus': 'macro crypto global liquidity'},
    {'name': 'Anthony Pompliano',  'handle': 'APompliano',       'focus': 'bitcoin crypto markets'},
    {'name': 'Cathie Wood',        'handle': 'CathieDWood',      'focus': 'innovation crypto ETF'},
    {'name': 'Lyn Alden',          'handle': 'LynAldenContact',  'focus': 'macro bitcoin fiscal policy'},
    {'name': 'Naval Ravikant',     'handle': 'naval',            'focus': 'crypto wealth creation'},
    {'name': 'Paul Tudor Jones',   'handle': 'PTJ_Official',     'focus': 'macro trading inflation'},
    {'name': 'Michael Burry',      'handle': 'michaeljburry',    'focus': 'market crash shorts'},
    {'name': 'Chamath',            'handle': 'chamath',          'focus': 'VC macro tech crypto'},
]

def social_intelligence_agent():
    """
    Searches for recent insights from top investors and billionaires.
    Feeds their views into Star's analysis as Strategy 15 — Billionaire Sentiment.
    """
    if not TAVILY_KEY:
        return {'success': False, 'insights': [], 'sentiment': 'neutral'}

    insights     = []
    bull_signals = 0
    bear_signals = 0

    print('\n👑 Social Intelligence Agent scanning billionaire insights...')

    # Search for recent posts/statements from key accounts
    for account in BILLIONAIRE_ACCOUNTS[:5]:  # Limit to 5 per cycle to save quota
        try:
            query  = f'{account["name"]} {account["focus"]} crypto bitcoin 2026 latest'
            result = research_agent(query, context='social_intelligence')

            if result.get('answer') or result.get('results'):
                content = result.get('answer', '')
                if not content and result.get('results'):
                    content = result['results'][0].get('content', '')

                # Simple sentiment analysis
                bullish_words = ['buy', 'bullish', 'accumulate', 'long', 'moon', 'up', 'growth', 'opportunity']
                bearish_words = ['sell', 'bearish', 'crash', 'collapse', 'short', 'down', 'warning', 'danger']

                content_lower = content.lower()
                bull_score = sum(1 for w in bullish_words if w in content_lower)
                bear_score = sum(1 for w in bearish_words if w in content_lower)

                sentiment = 'bullish' if bull_score > bear_score else 'bearish' if bear_score > bull_score else 'neutral'

                if sentiment == 'bullish':
                    bull_signals += 1
                elif sentiment == 'bearish':
                    bear_signals += 1

                insight = {
                    'person':    account['name'],
                    'handle':    account['handle'],
                    'content':   content[:300],
                    'sentiment': sentiment,
                    'bull_score': bull_score,
                    'bear_score': bear_score,
                }
                insights.append(insight)
                print(f"  {account['name']}: {sentiment.upper()} (bull:{bull_score} bear:{bear_score})")

            time.sleep(1)  # Rate limiting

        except Exception as e:
            print(f"  Error fetching {account['name']}: {e}")

    # Overall billionaire sentiment
    total = bull_signals + bear_signals
    if total > 0:
        bull_pct = bull_signals / total * 100
        overall  = 'bullish' if bull_pct > 60 else 'bearish' if bull_pct < 40 else 'neutral'
    else:
        overall = 'neutral'

    result = {
        'success':         True,
        'insights':        insights,
        'sentiment':       overall,
        'bull_signals':    bull_signals,
        'bear_signals':    bear_signals,
        'confidence_boost': 10 if overall == 'bullish' else -10 if overall == 'bearish' else 0,
        'timestamp':       datetime.now(timezone.utc).isoformat(),
    }

    log_event('social_intelligence', 'scan_complete', {
        'accounts_checked': len(insights),
        'overall_sentiment': overall,
        'bull': bull_signals,
        'bear': bear_signals,
    })

    # Save insights for portal display
    with open('/home/ShekinahD/star_billionaire_insights.json', 'w') as f:
        json.dump(result, f, indent=2)

    print(f"  Overall billionaire sentiment: {overall.upper()} (🐂{bull_signals} 🐻{bear_signals})")
    return result


# ══ SECURITY AGENT ════════════════════════════════════════════════
KNOWN_SCAM_PATTERNS = [
    '0x0000000000000000000000000000000000000000',  # Null address
    'rugpull', 'honeypot', 'scam',
]

STAR_OFFICIAL_DOMAINS = [
    'shekinahstar.io',
    'checkout.superfluid.finance',
    'discord.gg/WCspBuA8Y',
]

def security_agent():
    """
    Monitors for security threats:
    - Fake Shekinah Star impersonators
    - Suspicious wallet activity
    - Phishing attempts
    - Compromised subscriber accounts
    """
    threats   = []
    warnings  = []

    print('\n🔐 Security Agent scanning for threats...')

    # Check for impersonators using Tavily
    if TAVILY_KEY:
        try:
            impersonator_search = research_agent(
                'fake "Shekinah Star" crypto scam impersonator warning 2026',
                context='security'
            )
            if impersonator_search.get('answer'):
                content = impersonator_search['answer'].lower()
                if any(word in content for word in ['scam', 'fake', 'impersonat', 'warning']):
                    threats.append({
                        'type':        'IMPERSONATOR_DETECTED',
                        'severity':    'HIGH',
                        'description': impersonator_search['answer'][:200],
                        'action':      'Monitor and report fake accounts to platform',
                    })
        except Exception as e:
            print(f'  Impersonator check error: {e}')

    # Check subscriber fund accounts for anomalies
    try:
        fund_db = '/home/ShekinahD/star_fund.db'
        if os.path.exists(fund_db):
            import sqlite3
            conn = sqlite3.connect(fund_db)
            c    = conn.cursor()
            c.execute('SELECT email, wallet_address, last_trade FROM fund_accounts WHERE active=1')
            accounts = c.fetchall()
            conn.close()

            for email, wallet, last_trade in accounts:
                # Check wallet isn't null address
                if wallet and wallet.lower() in [p.lower() for p in KNOWN_SCAM_PATTERNS]:
                    threats.append({
                        'type':     'SUSPICIOUS_WALLET',
                        'severity': 'CRITICAL',
                        'email':    email,
                        'wallet':   wallet,
                        'action':   'Deactivate account immediately',
                    })
    except Exception as e:
        print(f'  Fund account check error: {e}')

    # Monitor for unusual API patterns
    try:
        log_file = ORCHESTRATOR_LOG
        if os.path.exists(log_file):
            logs  = json.load(open(log_file))
            # Check for unusual frequency of failed events
            recent = [l for l in logs[:50] if 'error' in l.get('event_type', '').lower()]
            if len(recent) > 10:
                warnings.append({
                    'type':        'HIGH_ERROR_RATE',
                    'severity':    'MEDIUM',
                    'description': f'{len(recent)} errors in last 50 events',
                    'action':      'Review system logs',
                })
    except Exception as e:
        print(f'  Log analysis error: {e}')

    result = {
        'success':  True,
        'threats':  threats,
        'warnings': warnings,
        'secure':   len(threats) == 0,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    # Alert Sarah if threats found
    if threats:
        for threat in threats:
            log_event('security', 'threat_detected', threat, requires_approval=True)
            print(f"  🚨 THREAT: {threat['type']} — {threat['description'][:100]}")

            # Post to Discord
            discord_webhook = os.getenv('DISCORD_WEBHOOK_ANNOUNCEMENTS', '')
            if discord_webhook:
                msg = f"🚨 **SECURITY ALERT** — {threat['type']} | Severity: {threat['severity']} | Action: {threat['action']}"
                try:
                    requests.post(discord_webhook, json={'content': msg, 'username': 'Shekinah Star Security'}, timeout=10)
                except Exception:
                    pass
    else:
        print('  ✅ No threats detected — all systems secure')

    log_event('security', 'scan_complete', {'threats': len(threats), 'warnings': len(warnings), 'secure': result['secure']})

    # Save security report
    with open('/home/ShekinahD/star_security_report.json', 'w') as f:
        json.dump(result, f, indent=2)

    return result
