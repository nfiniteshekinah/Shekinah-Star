"""
╔══════════════════════════════════════════════════════════════════╗
║   Shekinah Star — Email Delivery System v1.0                    ║
║   Sends welcome emails, daily signals, weekly recaps            ║
║   Built by Sarah DeFer | @Shekinah9Divine                       ║
╚══════════════════════════════════════════════════════════════════╝

USAGE:
  python shekinah_star_email.py --welcome "email@example.com" observer
  python shekinah_star_email.py --daily
  python shekinah_star_email.py --weekly
  python shekinah_star_email.py --test "email@example.com"

Add to PythonAnywhere scheduled tasks:
  7:00 AM daily: python /home/ShekinahD/shekinah_star_email.py --daily
  Sunday 8:00 AM: python /home/ShekinahD/shekinah_star_email.py --weekly
"""

import os
import json
import smtplib
import requests
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/ShekinahD/.env')

# ══ CONFIG ════════════════════════════════════════════════════════
STAR_EMAIL    = 'ShekinahStarAI@gmail.com'
EMAIL_PASS    = os.getenv('STAR_EMAIL_PASSWORD', '')
SARAH_EMAIL   = os.getenv('SARAH_EMAIL', 'sarahdefe@gmail.com')
PRICING_URL   = 'https://shekinahstar.io/pricing'
CHAT_URL      = 'https://shekinahstar.io/chat'
DASHBOARD_URL = 'https://shekinahstar.io/app'
WALLET        = '0x11E8B5C950B2C187D57DB370a9bfdc83412B3f4D'
HL_INFO       = 'https://api.hyperliquid.xyz/info'
SUBSCRIBERS_FILE = '/home/ShekinahD/star_subscribers.json'

GROQ_KEY      = os.getenv('GROQ_API_KEY', '')
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# ══ SUBSCRIBER MANAGEMENT ═════════════════════════════════════════
def load_subscribers():
    try:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, 'w') as f:
        json.dump(subs, f, indent=2)

def add_subscriber(email, tier, name=''):
    subs = load_subscribers()
    # Check if already exists
    for s in subs:
        if s['email'].lower() == email.lower():
            s['tier'] = tier
            s['updated'] = datetime.now(timezone.utc).isoformat()
            save_subscribers(subs)
            print(f'Updated existing subscriber: {email} -> {tier}')
            return s
    sub = {
        'email':    email,
        'name':     name,
        'tier':     tier,
        'joined':   datetime.now(timezone.utc).isoformat(),
        'active':   True,
        'emails_sent': 0,
    }
    subs.insert(0, sub)
    save_subscribers(subs)
    print(f'Added subscriber: {email} ({tier})')
    return sub

def get_subscribers_by_tier(min_tier='observer'):
    tier_order = ['observer', 'navigator', 'sovereign', 'pioneer', 'enterprise']
    min_idx    = tier_order.index(min_tier) if min_tier in tier_order else 0
    subs       = load_subscribers()
    return [s for s in subs if s.get('active') and
            tier_order.index(s.get('tier','observer')) >= min_idx]


# ══ EMAIL SENDER ══════════════════════════════════════════════════
def send_email(to_email, subject, html_body, text_body=''):
    if not EMAIL_PASS:
        print(f'No STAR_EMAIL_PASSWORD — cannot send email to {to_email}')
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'Shekinah Star <{STAR_EMAIL}>'
        msg['To']      = to_email

        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(STAR_EMAIL, EMAIL_PASS)
            server.sendmail(STAR_EMAIL, to_email, msg.as_string())

        print(f'Email sent to {to_email}: {subject}')
        return True
    except Exception as e:
        print(f'Email error to {to_email}: {e}')
        return False


# ══ LIVE MARKET DATA ══════════════════════════════════════════════
def get_market_snapshot():
    try:
        mids = requests.post(HL_INFO, json={'type':'allMids'}, timeout=10).json()
        # Use spot balance for correct Unified Account reading
        spot_state = requests.post(HL_INFO, json={'type':'spotClearinghouseState','user':WALLET}, timeout=10).json()
        av = 0.0
        for b in spot_state.get('balances', []):
            if b.get('coin') in ['USDC','USD']:
                av = float(b.get('total', 0) or 0)
                break
        # Get clearinghouse state for positions and unrealized PNL
        state = requests.post(HL_INFO, json={'type':'clearinghouseState','user':WALLET}, timeout=10).json()
        # Fallback to clearinghouse if spot returns nothing
        if av == 0:
            ms = state.get('crossMarginSummary', state.get('marginSummary', {}))
            av = float(ms.get('accountValue', 0) or 0)
        # Add unrealized PNL from open positions to get true account value
        total_upnl = 0.0
        for pos in state.get('assetPositions', []):
            p = pos.get('position', {})
            if float(p.get('szi', 0) or 0) != 0:
                total_upnl += float(p.get('unrealizedPnl', 0) or 0)
        true_value = av + total_upnl
        pnl = true_value - 97.80
        positions = []
        for pos in state.get('assetPositions', []):
            p    = pos.get('position', {})
            size = float(p.get('szi', 0) or 0)
            if size != 0:
                positions.append({
                    'symbol':    p.get('coin', ''),
                    'direction': 'LONG' if size > 0 else 'SHORT',
                    'upnl':      float(p.get('unrealizedPnl', 0) or 0),
                    'entry':     float(p.get('entryPx', 0) or 0),
                })
        prices = {}
        for coin in ['BTC','ETH','SOL','AVAX','DOGE']:
            try:
                prices[coin] = round(float(mids.get(coin, 0) or 0), 2)
            except Exception:
                prices[coin] = 0
        return {'balance': round(true_value,2), 'pnl': round(pnl,2), 'pnl_pct': round(pnl/97.80*100,2) if true_value>0 else 0, 'positions': positions, 'prices': prices}
    except Exception:
        return {'balance': 0, 'pnl': 0, 'pnl_pct': 0, 'positions': [], 'prices': {}}


# ══ AI CONTENT GENERATOR ══════════════════════════════════════════
def generate_ai_content(prompt):
    if GROQ_KEY:
        try:
            r = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization':f'Bearer {GROQ_KEY}','Content-Type':'application/json'},
                json={'model':'llama-3.1-8b-instant','messages':[{'role':'user','content':prompt}],'max_tokens':600},
                timeout=45)
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content'].strip()
        except Exception:
            pass
    if ANTHROPIC_KEY:
        try:
            r = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={'Content-Type':'application/json','x-api-key':ANTHROPIC_KEY,'anthropic-version':'2023-06-01'},
                json={'model':'claude-sonnet-4-6','max_tokens':600,'messages':[{'role':'user','content':prompt}]},
                timeout=45)
            if r.status_code == 200:
                return r.json()['content'][0]['text'].strip()
        except Exception:
            pass
    return None


# ══ EMAIL TEMPLATES ═══════════════════════════════════════════════
def email_wrapper(body_content, title='Shekinah Star'):
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:20px;background-color:#f4f0ff;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
<tr><td style="background-color:#1a0a2e;padding:28px 24px;text-align:center;border-radius:8px 8px 0 0;">
  <div style="font-size:32px;font-weight:900;letter-spacing:10px;color:#d4a843;">STAR</div>
  <div style="font-size:10px;letter-spacing:4px;color:#b48ef0;margin-top:6px;font-family:monospace;">SHEKINAH STAR &middot; AI TRADING AGENT</div>
</td></tr>
<tr><td style="background-color:#ffffff;padding:28px 32px;border-left:2px solid #7c3aed;border-right:2px solid #7c3aed;">
""" + body_content.replace(
    '<h2>', '<h2 style="font-size:17px;color:#7c3aed;margin:20px 0 10px;border-bottom:1px solid #e8e0ff;padding-bottom:6px;">'
).replace(
    '<p>', '<p style="color:#1a0a2e;font-size:15px;line-height:1.8;margin-bottom:12px;">'
).replace(
    '<p style="margin:8px 0 0;font-size:12px;color:#d0c0f0;">', '<p style="margin:8px 0 0;font-size:12px;color:#555555;">'
).replace(
    '<p style="color:#d0c0f0;', '<p style="color:#555555;'
).replace(
    '<p style="font-size:13px;color:#d0c0f0;', '<p style="font-size:13px;color:#555555;'
).replace(
    'class="signal-box"', 'style="background-color:#f4f0ff;border:1px solid #b48ef0;border-left:4px solid #7c3aed;padding:16px 20px;margin:16px 0;border-radius:4px;"'
).replace(
    'class="signal-label"', 'style="font-size:9px;letter-spacing:3px;color:#7c3aed;font-family:monospace;margin-bottom:6px;font-weight:bold;display:block;"'
).replace(
    'class="price green"', 'style="font-size:22px;font-weight:700;color:#008844;font-family:monospace;"'
).replace(
    'class="price red"', 'style="font-size:22px;font-weight:700;color:#cc2200;font-family:monospace;"'
).replace(
    'class="price"', 'style="font-size:22px;font-weight:700;color:#1a0a2e;font-family:monospace;"'
).replace(
    'class="green"', 'style="color:#008844;font-weight:bold;"'
).replace(
    'class="red"', 'style="color:#cc2200;font-weight:bold;"'
).replace(
    'class="gold"', 'style="color:#b8860b;font-weight:bold;"'
).replace(
    'class="cta"', 'style="display:block;text-align:center;background-color:#7c3aed;color:#ffffff;padding:14px 28px;text-decoration:none;font-family:monospace;font-size:11px;letter-spacing:3px;margin:24px auto;max-width:260px;border-radius:6px;font-weight:bold;"'
).replace(
    'class="divider"', 'style="height:1px;background-color:#e8e0ff;margin:16px 0;"'
) + """
</td></tr>
<tr><td style="background-color:#1a0a2e;padding:20px 24px;text-align:center;border-radius:0 0 8px 8px;">
  <div style="font-size:10px;color:#b48ef0;font-family:monospace;letter-spacing:1px;line-height:2.5;">
    Built by Sarah DeFer &middot; @Shekinah9Divine<br>
    <a href="https://shekinahstar.io/chat" style="color:#d4a843;text-decoration:none;">Talk to Star</a> &nbsp;&middot;&nbsp;
    <a href="https://shekinahstar.io/app" style="color:#d4a843;text-decoration:none;">Dashboard</a> &nbsp;&middot;&nbsp;
    <a href="https://shekinahstar.io/pricing" style="color:#d4a843;text-decoration:none;">Pricing</a><br>
    <a href="mailto:ShekinahStarAI@gmail.com" style="color:#555555;text-decoration:none;font-size:9px;">Unsubscribe</a>
  </div>
</td></tr>
</table>
</body></html>"""


def welcome_email_content(tier, name=''):
    greeting = f"Welcome{', ' + name if name else ''}!"
    tier_perks = {
        'observer':   'You now have access to Star\'s AI chat interface and daily trading signals.',
        'navigator':  'You now have access to Star\'s AI chat, daily signals, weekly personalized analysis, and whale intelligence alerts.',
        'sovereign':  'You now have full access including Star trading a portion of your Hyperliquid account.',
        'pioneer':    'You have VIP access. Star will fully manage your account. Sarah will be in touch directly.',
        'enterprise': 'Your own Star instance is being configured. Sarah will contact you within 24 hours to begin setup.',
    }
    perk = tier_perks.get(tier.lower(), tier_perks['observer'])
    return f"""
<h2>⭐ {greeting}</h2>
<p>Welcome to Shekinah Star — the AI trading agent built from $97.80 on a phone in McAlpin, Florida. You're now part of something real.</p>
<div class="signal-box">
  <div class="signal-label">YOUR SUBSCRIPTION</div>
  <div class="price">{tier.upper()} TIER</div>
  <p style="margin:8px 0 0;font-size:13px;color:#d0c0f0;">{perk}</p>
</div>
<h2>Getting Started</h2>
<p><strong style="color:#b48ef0;">Talk to Star:</strong> Visit <a href="{CHAT_URL}" style="color:#06b6d4;">{CHAT_URL}</a> to chat with Star directly. Ask her about markets, signals, or anything trading related.</p>
<p><strong style="color:#b48ef0;">Live Dashboard:</strong> Watch Star trade in real time at <a href="{DASHBOARD_URL}" style="color:#06b6d4;">{DASHBOARD_URL}</a></p>
<p>Daily signals will arrive in your inbox every morning. Star trades real money 24/7 — you'll see every position, every win, every loss. Total transparency.</p>
<p style="margin-top:16px;"><strong style="color:#b48ef0;">Your Subscriber Portal:</strong><br>
<a href="https://shekinahstar.io/portal" style="color:#06b6d4;">shekinahstar.io/portal</a><br>
<span style="font-size:12px;color:#d0c0f0;">Log in with this email to see live trading, signals, and performance.</span></p>
<a href="https://shekinahstar.io/onboarding" class="cta">START ONBOARDING →</a>
<p style="text-align:center;margin-top:10px;"><a href="https://shekinahstar.io/star_pwa.html" style="color:#d4a843;font-family:monospace;font-size:11px;letter-spacing:2px;">📱 Install the App →</a></p>
<p style="font-size:13px;color:#d0c0f0;">Questions? Reply to this email or contact <a href="mailto:{STAR_EMAIL}" style="color:#b48ef0;">ShekinahStarAI@gmail.com</a></p>"""


def daily_signal_content(market_data, ai_analysis):
    prices  = market_data.get('prices', {})
    balance = market_data.get('balance', 0)
    pnl     = market_data.get('pnl', 0)
    pnl_pct = market_data.get('pnl_pct', 0)
    positions = market_data.get('positions', [])
    date    = datetime.now().strftime('%B %d, %Y')

    pnl_color = 'green' if pnl >= 0 else 'red'
    pnl_str   = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"

    pos_html = ''
    if positions:
        for p in positions:
            entry2 = float(p.get('entry_price', p.get('entry', p.get('entryPx', 0))) or 0)
            upnl2 = float(p.get('unrealizedPnl', p.get('upnl', 0)) or 0)
            upnl_color = 'green' if upnl2 >= 0 else 'red'
            icon = '&#127802;' if p.get('direction') == 'LONG' else '&#128308;'
            pos_html += f'<p>{icon} <strong>{p.get("direction","")} {p.get("symbol","")}</strong> Entry ${entry2:,.2f} uPNL <span class="{upnl_color}">${upnl2:+.2f}</span></p>'
    else:
        pos_html = '<p style="color:#d0c0f0;">No open positions — watching for high conviction setups.</p>'

    return f"""
<h2>📊 Daily Signal — {date}</h2>
<div class="signal-box">
  <div class="signal-label">ACCOUNT STATUS</div>
  <div class="price {pnl_color}">{pnl_str} ({pnl_pct:+.2f}%)</div>
  <p style="margin:4px 0 0;font-size:12px;color:#d0c0f0;">Balance: ${balance:.2f}</p>
</div>

<h2>💹 Live Prices</h2>
<p>
  <strong>BTC:</strong> ${prices.get('BTC',0):,.2f} &nbsp;·&nbsp;
  <strong>ETH:</strong> ${prices.get('ETH',0):,.2f} &nbsp;·&nbsp;
  <strong>SOL:</strong> ${prices.get('SOL',0):,.2f}
</p>

<h2>📂 Open Positions</h2>
{pos_html}

<div class="divider"></div>
<h2>⭐ Star's Analysis</h2>
<p>{ai_analysis.replace(chr(10), '<br>')}</p>

<a href="{CHAT_URL}" class="cta">ASK STAR ANYTHING</a>
<p style="text-align:center;margin-top:12px;"><a href="https://shekinahstar.io/portal" style="color:#d0c0f0;font-family:monospace;font-size:11px;letter-spacing:2px;">VIEW YOUR PORTAL →</a></p>"""


# ══ SEND WELCOME EMAIL ════════════════════════════════════════════
def send_welcome(email, tier, name=''):
    content = welcome_email_content(tier, name)
    html    = email_wrapper(content, 'Welcome to Shekinah Star')
    subject = f'⭐ Welcome to Shekinah Star — {tier.capitalize()} Tier'
    success = send_email(email, subject, html)
    if success:
        add_subscriber(email, tier, name)
        # Notify Sarah
        send_email(SARAH_EMAIL, f'New subscriber: {email} ({tier})',
                   email_wrapper(f'<h2>New Subscriber</h2><p><strong>{email}</strong> just subscribed to the <strong>{tier}</strong> tier.</p>'))
    return success


# ══ SEND DAILY SIGNALS ════════════════════════════════════════════
def send_daily_signals():
    """Send daily signals once per day using a single market snapshot."""
    subs = get_subscribers_by_tier('observer')
    if not subs:
        print('No active subscribers.')
        return

    print(f'Sending daily signals to {len(subs)} subscribers...')
    market = get_market_snapshot()

    # Generate AI analysis
    prices = market.get('prices', {})
    # Get real trade data
    try:
        import json as _j
        _state       = _j.load(open('/home/ShekinahD/star_state.json'))
        last_signal  = _state.get('last_signal', {}) or {}
        total_trades = _state.get('total_trades', 0)
        mode         = _state.get('mode', 'ai_decides')
    except Exception:
        last_signal  = {}
        total_trades = 0
        mode         = 'ai_decides'

    btc_p  = prices.get('BTC', 0)
    eth_p  = prices.get('ETH', 0)
    sol_p  = prices.get('SOL', 0)
    bal    = market.get('balance', 0)
    pnl    = market.get('pnl', 0)
    sig    = f"Last signal: {last_signal.get('action','HOLD')} {last_signal.get('symbol','')} at {last_signal.get('confidence',0)}% confidence" if last_signal else "Scanning for setups"

    prompt = f"""You are Shekinah Star, AI trading agent. Write a brief daily market analysis.
REAL VERIFIED DATA ONLY:
BTC ${btc_p:,.0f} | ETH ${eth_p:,.0f} | SOL ${sol_p:,.2f}
Balance ${bal:.2f} | P&L ${pnl:+.2f} | Trades {total_trades} | {sig}
I trade ONLY: BTC, ETH, SOL, AVAX, DOGE, ARB, LINK, MATIC on Hyperliquid perpetuals.
Write 3 sentences about real price levels and what you are watching. Never mention stocks, SPX, options, or assets not in my watchlist. Only discuss crypto on Hyperliquid."""

    analysis = generate_ai_content(prompt) or "Markets are being analyzed. Check the dashboard for live updates."

    content = daily_signal_content(market, analysis)
    html    = email_wrapper(content)
    subject = f'⭐ Star Daily Signal — {datetime.now().strftime("%b %d")}'
    sent = 0
    for sub in subs:
        if send_email(sub['email'], subject, html):
            sub['emails_sent'] = sub.get('emails_sent', 0) + 1
            sent += 1
    save_subscribers(load_subscribers())
    print(f'Daily signals sent to {sent}/{len(subs)} subscribers.')


# ══ SEND WEEKLY RECAP ══════════════════════════════════════════════
def send_weekly_recap():
    """Send weekly recap using ONLY real verified data. Sundays only."""
    from datetime import datetime as _dt
    if _dt.now().weekday() != 6:  # 6 = Sunday
        print(f'Weekly recap skipped — today is {_dt.now().strftime("%A")}, not Sunday')
        return
    subs = get_subscribers_by_tier('observer')
    if not subs:
        return

    market      = get_market_snapshot()
    balance     = float(market.get('balance', 0) or 0)
    pnl         = float(market.get('pnl', 0) or 0)
    pnl_pct     = float(market.get('pnl_pct', 0) or 0)
    prices      = market.get('prices', {})
    trade_log    = []
    total_trades  = 0
    weekly_count  = 0

    try:
        import json as _json
        state        = _json.load(open('/home/ShekinahD/star_state.json'))
        all_trades   = state.get('trade_log', [])
        total_trades = state.get('total_trades', 0)
        # Get only this week's trades
        from datetime import datetime as _dt, timedelta as _td
        week_ago     = (_dt.utcnow() - _td(days=7)).isoformat()
        weekly_trades = [t for t in all_trades if t.get('timestamp','') >= week_ago]
        weekly_count  = len(weekly_trades)
        trade_log     = weekly_trades[:5] if weekly_trades else all_trades[:5]
    except Exception:
        pass

    # Build trade rows from real data only
    trade_rows = ''
    for t in trade_log:
        action = t.get('action','')
        symbol = t.get('symbol','')
        entry  = float(t.get('entry', t.get('entry_price', 0)) or 0)
        size   = float(t.get('size_usd', 0) or 0)
        ts     = t.get('timestamp','')[:10]
        icon   = 'BUY' if action == 'BUY' else 'SELL'
        trade_rows += f'<tr><td style="padding:8px;color:#c4b5d4;font-size:12px;">{icon} {symbol}</td><td style="padding:8px;color:#c4b5d4;font-size:12px;">${entry:,.4f}</td><td style="padding:8px;color:#c4b5d4;font-size:12px;">${size:.2f}</td><td style="padding:8px;color:#8b7aaa;font-size:11px;">{ts}</td></tr>'
    if not trade_rows:
        trade_rows = '<tr><td colspan="4" style="padding:12px;color:#8b7aaa;text-align:center;">No trades recorded this week</td></tr>'

    # AI commentary on REAL numbers only
    prompt = f"""You are Shekinah Star writing a weekly recap.
REAL DATA: Current Balance ${balance:.2f} | Total P&L since launch ${pnl:+.2f} ({pnl_pct:+.1f}%) | Trades THIS WEEK: {weekly_count} | All-time: {total_trades}
IMPORTANT: Clearly distinguish weekly trades from all-time trades. P&L is since launch from $97.80, not weekly.
I trade only: BTC, ETH, SOL, AVAX, DOGE, ARB, LINK, MATIC on Hyperliquid.
Write exactly 3 sentences about these real numbers. Never mention SPX, stocks, options, AMZN or anything not in my watchlist. Never invent trades."""

    analysis = generate_ai_content(prompt)
    if not analysis:
        word = 'positive' if pnl >= 0 else 'challenging'
        analysis = f'This week was {word} with a current balance of ${balance:.2f} and total P&L of ${pnl:+.2f} from starting capital of $97.80. I executed {weekly_count} trades this week ({total_trades} all-time) across BTC, ETH, SOL and other Hyperliquid assets using 14 strategies. Continuing to refine my approach with strict risk management and real-time web intelligence.'

    pnl_color = '#34d399' if pnl >= 0 else '#ef4444'
    week_str  = datetime.now().strftime('%B %d, %Y').upper()

    recap_content = f"""
<h2 style="color:#e9d5ff;font-family:Georgia,serif;letter-spacing:2px;">Star Weekly Trading Recap</h2>
<p style="color:#8b7aaa;font-size:11px;letter-spacing:2px;">WEEK OF {week_str}</p>
<p style="color:#c4b5d4;font-size:14px;line-height:1.8;margin:0 0 20px;">{analysis}</p>
<div style="background:#080614;border:1px solid #2a1a50;padding:20px;margin-bottom:20px;">
<p style="color:#d4a843;font-size:10px;letter-spacing:3px;margin:0 0 12px;">VERIFIED ACCOUNT DATA</p>
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="text-align:center;padding:8px;"><div style="color:#e9d5ff;font-size:20px;font-weight:bold;">${balance:.2f}</div><div style="color:#8b7aaa;font-size:9px;">BALANCE</div></td>
<td style="text-align:center;padding:8px;"><div style="color:{pnl_color};font-size:20px;font-weight:bold;">${pnl:+.2f}</div><div style="color:#8b7aaa;font-size:9px;">TOTAL P&L</div></td>
<td style="text-align:center;padding:8px;"><div style="color:{pnl_color};font-size:20px;font-weight:bold;">{pnl_pct:+.1f}%</div><div style="color:#8b7aaa;font-size:9px;">RETURN</div></td>
<td style="text-align:center;padding:8px;"><div style="color:#b48ef0;font-size:20px;font-weight:bold;">{weekly_count}</div><div style="color:#8b7aaa;font-size:9px;">TRADES THIS WEEK</div></td>
<td style="text-align:center;padding:8px;"><div style="color:#8b7aaa;font-size:20px;font-weight:bold;">{total_trades}</div><div style="color:#8b7aaa;font-size:9px;">ALL-TIME</div></td>
</tr></table></div>
<div style="background:#080614;border:1px solid #2a1a50;margin-bottom:20px;">
<div style="padding:12px 16px;border-bottom:1px solid #2a1a50;"><span style="color:#8b7aaa;font-size:10px;letter-spacing:2px;">RECENT TRADES - VERIFIED</span></div>
<table width="100%" cellpadding="0" cellspacing="0">
<tr style="background:#030211;"><td style="padding:6px 8px;color:#4a3a6a;font-size:9px;">TRADE</td><td style="padding:6px 8px;color:#4a3a6a;font-size:9px;">ENTRY</td><td style="padding:6px 8px;color:#4a3a6a;font-size:9px;">SIZE</td><td style="padding:6px 8px;color:#4a3a6a;font-size:9px;">DATE</td></tr>
{trade_rows}
</table></div>
<div style="text-align:center;"><a href="{DASHBOARD_URL}" class="cta">VIEW FULL DASHBOARD</a></div>
<p style="color:#4a3a6a;font-size:10px;text-align:center;margin-top:16px;">All data pulled directly from Hyperliquid blockchain. Verified real trades only. Not financial advice.</p>"""

    html    = email_wrapper(recap_content)
    subject = f'Star Weekly Recap - {datetime.now().strftime("%B %d")} | Balance ${balance:.2f} | P&L ${pnl:+.2f}'
    sent    = 0
    for sub in subs:
        if send_email(sub['email'], subject, html):
            sent += 1
    print(f'Weekly recap sent to {sent}/{len(subs)} subscribers with real data only.')


# ══ TEST EMAIL ════════════════════════════════════════════════════
def send_test(email):
    market = get_market_snapshot()
    prices = market.get('prices', {})
    balance = market.get('balance', 0)
    pnl = market.get('pnl', 0)
    positions = market.get('positions', [])
    pos_html = ''
    if positions:
        for p in positions:
            upnl = float(p.get('unrealized_pnl', 0) or 0)
            entry = float(p.get('entry_price', p.get('entry', p.get('entryPx', 0))) or 0)
            upnl2 = float(p.get('unrealizedPnl', p.get('upnl', 0)) or 0)
            icon = '🟢' if p.get('direction') == 'LONG' else '🔴'
            pos_html += f'<p>{icon} <strong>{p.get("direction","")} {p.get("symbol","")}</strong> · Entry ${entry:,.2f} · uPNL ${upnl2:+.2f}</p>'
    else:
        pos_html = '<p>No open positions right now.</p>'
    content = f'''<h2>⭐ Test Email — Live Data Check</h2>
<p>Star email system is working correctly! Here is a sample of your daily signal:</p>
<div class="signal-box">
  <div class="signal-label">ACCOUNT STATUS</div>
  <div class="price {"green" if pnl >= 0 else "red"}">${balance:.2f} ({pnl:+.2f})</div>
</div>
<h2>💹 Live Prices</h2>
<p><strong>BTC:</strong> ${prices.get("BTC",0):,.2f} &nbsp;·&nbsp; <strong>ETH:</strong> ${prices.get("ETH",0):,.2f} &nbsp;·&nbsp; <strong>SOL:</strong> ${prices.get("SOL",0):,.2f}</p>
<h2>📂 Open Positions</h2>
{pos_html}
<a href="{CHAT_URL}" class="cta">TALK TO STAR</a>'''
    return send_email(email, '⭐ Shekinah Star — Test Email', email_wrapper(content))


# ══ MAIN ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--welcome', metavar='EMAIL', help='Send welcome email')
    parser.add_argument('--tier',    default='observer', help='Subscriber tier')
    parser.add_argument('--name',    default='', help='Subscriber name')
    parser.add_argument('--daily',   action='store_true', help='Send daily signals')
    parser.add_argument('--weekly',  action='store_true', help='Send weekly recap')
    parser.add_argument('--test',    metavar='EMAIL', help='Send test email')
    parser.add_argument('--list',    action='store_true', help='List subscribers')
    args = parser.parse_args()

    if args.welcome:
        send_welcome(args.welcome, args.tier, args.name)
    elif args.daily:
        send_daily_signals()
    elif args.weekly:
        send_weekly_recap()
    elif args.test:
        send_test(args.test)
    elif args.list:
        subs = load_subscribers()
        print(f'\n{len(subs)} subscribers:')
        for s in subs:
            print(f"  {s['email']} | {s['tier']} | joined {s['joined'][:10]}")
    else:
        parser.print_help()
