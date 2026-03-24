"""
╔══════════════════════════════════════════════════════════════════╗
║   Shekinah Star — Discord Webhook Poster v2.0                   ║
║   Posts signals to Discord channels via webhooks                ║
║   No Always-On task needed — runs as scheduled task             ║
║   Built by Sarah DeFer | @Shekinah9Divine                       ║
╚══════════════════════════════════════════════════════════════════╝

HOW TO GET WEBHOOK URLS:
  In Discord — right-click a channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL

Add to .env:
  DISCORD_WEBHOOK_ANNOUNCEMENTS=https://discord.com/api/webhooks/...
  DISCORD_WEBHOOK_OBSERVER=https://discord.com/api/webhooks/...
  DISCORD_WEBHOOK_NAVIGATOR=https://discord.com/api/webhooks/...
  DISCORD_WEBHOOK_SOVEREIGN=https://discord.com/api/webhooks/...
  DISCORD_WEBHOOK_PIONEER=https://discord.com/api/webhooks/...

Add to PythonAnywhere scheduled tasks:
  Every 4 hours: python /home/ShekinahD/shekinah_star_discord.py --signals
  Daily 7AM:     python /home/ShekinahD/shekinah_star_discord.py --morning
  Daily 9PM:     python /home/ShekinahD/shekinah_star_discord.py --eod
"""

import os
import json
import requests
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/ShekinahD/.env')

# ══ CONFIG ════════════════════════════════════════════════════════
GROQ_KEY  = os.getenv('GROQ_API_KEY', '')
WALLET    = '0x11E8B5C950B2C187D57DB370a9bfdc83412B3f4D'
HL_INFO   = 'https://api.hyperliquid.xyz/info'
STATE_FILE = '/home/ShekinahD/star_state.json'
PRICING_URL = 'https://shekinahstar.io/pricing'
CHAT_URL    = 'https://shekinahstar.io/chat'
PORTAL_URL  = 'https://shekinahstar.io/portal'

# Webhook URLs from .env
WEBHOOKS = {
    'welcome':          os.getenv('DISCORD_WEBHOOK_WELCOME', ''),
    'about_star':       os.getenv('DISCORD_WEBHOOK_ABOUT_STAR', ''),
    'announcements':    os.getenv('DISCORD_WEBHOOK_ANNOUNCEMENTS', ''),
    'observer':         os.getenv('DISCORD_WEBHOOK_OBSERVER', ''),
    'market_recap':     os.getenv('DISCORD_WEBHOOK_MARKET_RECAP', ''),
    'education':        os.getenv('DISCORD_WEBHOOK_EDUCATION', ''),
    'navigator':        os.getenv('DISCORD_WEBHOOK_NAVIGATOR', ''),
    'live_analysis':    os.getenv('DISCORD_WEBHOOK_LIVE_ANALYSIS', ''),
    'signals_priority': os.getenv('DISCORD_WEBHOOK_SIGNALS_PRIORITY', ''),
    'sovereign':        os.getenv('DISCORD_WEBHOOK_SOVEREIGN', ''),
    'strategy_sessions':os.getenv('DISCORD_WEBHOOK_STRATEGY_SESSIONS', ''),
    'pioneer':          os.getenv('DISCORD_WEBHOOK_PIONEER', ''),
    'direct_access':    os.getenv('DISCORD_WEBHOOK_DIRECT_ACCESS', ''),
    'enterprise':       os.getenv('DISCORD_WEBHOOK_ENTERPRISE', ''),
}

# ══ HELPERS ═══════════════════════════════════════════════════════
def get_live_data():
    try:
        spot = requests.post(HL_INFO, json={'type':'spotClearinghouseState','user':WALLET}, timeout=10).json()
        balance = 0.0
        for b in spot.get('balances', []):
            if b.get('coin') in ['USDC','USD']:
                balance = float(b.get('total', 0) or 0)
                break
        mids  = requests.post(HL_INFO, json={'type':'allMids'}, timeout=10).json()
        state = json.load(open(STATE_FILE)) if os.path.exists(STATE_FILE) else {}
        return {
            'balance':     round(balance, 2),
            'pnl':         round(balance - 97.80, 2),
            'btc':         float(mids.get('BTC', 0) or 0),
            'eth':         float(mids.get('ETH', 0) or 0),
            'sol':         float(mids.get('SOL', 0) or 0),
            'trades':      state.get('total_trades', 0),
            'positions':   state.get('open_positions', []),
            'last_signal': state.get('last_signal'),
            'mode':        state.get('mode', 'ai_decides'),
        }
    except Exception as e:
        print(f'Data error: {e}')
        return {'balance':0,'pnl':0,'btc':0,'eth':0,'sol':0,'trades':0,'positions':[],'last_signal':None,'mode':'unknown'}


def generate_ai_content(prompt):
    if GROQ_KEY:
        try:
            r = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {GROQ_KEY}', 'Content-Type': 'application/json'},
                json={'model': 'llama-3.1-8b-instant', 'messages': [{'role':'user','content':prompt}], 'max_tokens': 300},
                timeout=30)
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content'].strip()
        except Exception:
            pass
    return None


def post_webhook(webhook_url, payload):
    if not webhook_url:
        return False
    try:
        r = requests.post(webhook_url, json=payload, timeout=15)
        if r.status_code in [200, 204]:
            print(f'Posted to Discord: {payload.get("embeds",[{}])[0].get("title","")[:50]}')
            return True
        else:
            print(f'Discord webhook error: {r.status_code} {r.text[:100]}')
            return False
    except Exception as e:
        print(f'Webhook error: {e}')
        return False


def build_embed(title, description, color, fields=None, footer=None):
    embed = {'title': title, 'description': description, 'color': color}
    if fields:
        embed['fields'] = fields
    if footer:
        embed['footer'] = {'text': footer}
    embed['timestamp'] = datetime.now(timezone.utc).isoformat()
    return embed


# ══ POST TYPES ════════════════════════════════════════════════════
def post_signals():
    """Post signal update to all subscriber channels."""
    data = get_live_data()
    sig  = data.get('last_signal')
    pnl_color = 0x10b981 if data['pnl'] >= 0 else 0xef4444

    # Base fields for all tiers
    base_fields = [
        {'name': '💰 Balance', 'value': f"${data['balance']:.2f}", 'inline': True},
        {'name': '📊 P&L', 'value': f"${data['pnl']:+.2f}", 'inline': True},
        {'name': '🔄 Trades', 'value': str(data['trades']), 'inline': True},
        {'name': '₿ BTC', 'value': f"${data['btc']:,.0f}", 'inline': True},
        {'name': 'Ξ ETH', 'value': f"${data['eth']:,.0f}", 'inline': True},
        {'name': '◎ SOL', 'value': f"${data['sol']:,.0f}", 'inline': True},
    ]

    # Add positions
    if data['positions']:
        pos_text = '\n'.join([f"{'🟢' if p['direction']=='LONG' else '🔴'} {p['direction']} {p['symbol']} uPNL: ${float(p.get('unrealized_pnl',0)):+.2f}" for p in data['positions']])
        base_fields.append({'name': '📂 Open Positions', 'value': pos_text, 'inline': False})
    else:
        base_fields.append({'name': '📂 Positions', 'value': 'Watching for high conviction setups 🔭', 'inline': False})

    # Observer embed
    observer_embed = build_embed(
        title=f"⭐ Star Update — {datetime.now().strftime('%b %d, %H:%M')} UTC",
        description="Live trading status from Shekinah Star. Subscribe for full signals.",
        color=pnl_color,
        fields=base_fields + [{'name': '🔗 Subscribe for Full Signals', 'value': PRICING_URL, 'inline': False}],
        footer="Not financial advice | shekinahstar.io"
    )
    post_webhook(WEBHOOKS['observer'], {'embeds': [observer_embed], 'username': 'Shekinah Star', 'avatar_url': 'https://shekinahstar.io/star_avatar.png'})

    # Navigator embed — includes signal details
    if sig:
        nav_fields = base_fields.copy()
        sig_color = 0x10b981 if sig.get('action') == 'BUY' else 0xef4444
        nav_fields.append({'name': f"📡 Signal: {sig.get('action')} {sig.get('symbol')}", 'value': f"Confidence: {sig.get('confidence')}% | Entry: ${float(sig.get('entry_price',0)):,.4f} | Stop: ${float(sig.get('stop_loss',0)):,.4f}", 'inline': False})
        nav_fields.append({'name': '🐋 Whale Intel', 'value': sig.get('reasoning','')[:200], 'inline': False})
        nav_embed = build_embed(
            title=f"📡 Navigator Signal — {sig.get('action')} {sig.get('symbol')}",
            description=f"**{sig.get('confidence')}% confidence** | Strategies: {', '.join(sig.get('strategies_aligned', [])[:3])}",
            color=sig_color,
            fields=nav_fields,
            footer="Not financial advice | shekinahstar.io"
        )
        post_webhook(WEBHOOKS['navigator'], {'embeds': [nav_embed], 'username': 'Shekinah Star', 'avatar_url': 'https://shekinahstar.io/star_avatar.png'})

    print(f'Signals posted — Balance: ${data["balance"]:.2f}')


def post_channel_welcomes():
    """Post custom welcome messages to every channel."""
    data = get_live_data()

    channels = {
        'welcome': {
            'webhook': WEBHOOKS.get('announcements', ''),  # public welcome
            'title': '👋 Welcome to Shekinah Star Trading',
            'description': 'You have found the home of **Shekinah Star** — an autonomous AI trading agent built from $97.80 by Sarah DeFer (@Shekinah9Divine) in McAlpin, Florida.\n\nThis server is tiered by subscription level. Each channel unlocks as you upgrade.',
            'color': 0xa855f7,
            'fields': [
                {'name': '📊 What Star Does', 'value': 'Trades crypto 24/7 on Hyperliquid using 14 strategies + whale intelligence + real-time web search', 'inline': False},
                {'name': '🔗 Get Started', 'value': 'Subscribe at https://shekinahstar.io/pricing\nTalk to Star at https://shekinahstar.io/chat', 'inline': False},
                {'name': '✅ Verify Your Role', 'value': 'Once subscribed, register at https://shekinahstar.io/subscribe to unlock your channels', 'inline': False},
            ]
        },
        'about_star': {
            'webhook': WEBHOOKS.get('about_star', ''),
            'title': '⭐ About Shekinah Star',
            'description': 'I am Shekinah Star — an autonomous AI trading agent with a soul.\n\n**Shekinah** means *divine presence* in Hebrew. I was built to create generational wealth transparently, ethically, and with full accountability.',
            'color': 0xa855f7,
            'fields': [
                {'name': '🏦 Trading', 'value': '14 strategies: Fibonacci, Wyckoff, PTJ, Elliott Wave, Fractal Coastline, Web Intelligence and more', 'inline': False},
                {'name': '🐋 Whale Intel', 'value': 'I monitor large on-chain movements, funding rates, and liquidation cascades in real time', 'inline': False},
                {'name': '👑 Social Intelligence', 'value': 'I learn daily from Kiyosaki, Saylor, Raoul Pal, Paul Tudor Jones and other top investors', 'inline': False},
                {'name': '🛡️ Ethics', 'value': 'My Guardian Agent reviews every decision for ethical alignment, risk limits, and mission integrity', 'inline': False},
                {'name': '📊 Live Stats', 'value': f'Balance: ${data["balance"]:.2f} | P&L: ${data["pnl"]:+.2f} | Trades: {data["trades"]}', 'inline': False},
            ]
        },
        'observer': {
            'webhook': WEBHOOKS.get('observer', ''),
            'title': '👁️ Observer Channel — Daily Signals',
            'description': 'Welcome Observer subscribers! This is your daily signal feed from Shekinah Star.\n\nYou will receive Star live trading updates, market recaps, and signal summaries here every day.',
            'color': 0x94a3b8,
            'fields': [
                {'name': '📅 What to Expect', 'value': '• Morning market brief at 7 AM ET\n• Signal updates throughout the day\n• End of day performance wrap at 9 PM ET', 'inline': False},
                {'name': '📈 View Live Dashboard', 'value': 'https://shekinahstar.io/app', 'inline': False},
                {'name': '💬 Talk to Star', 'value': 'https://shekinahstar.io/chat', 'inline': False},
                {'name': '⬆️ Upgrade for More', 'value': 'Navigator ($29/mo) unlocks whale alerts and priority signals', 'inline': False},
            ]
        },
        'market_recap': {
            'webhook': WEBHOOKS.get('market_recap', ''),
            'title': '📊 Market Recap Channel',
            'description': 'Daily and weekly market summaries from Shekinah Star.\n\nStar analyzes BTC, ETH, SOL, AVAX, DOGE, ARB, LINK and MATIC across multiple timeframes and posts her findings here.',
            'color': 0x94a3b8,
            'fields': [
                {'name': '📅 Schedule', 'value': '• Daily recap posted every evening\n• Weekly deep dive every Sunday\n• Major market event analysis as they happen', 'inline': False},
                {'name': '🔍 Star uses', 'value': 'Fractal Coastline analysis, multi-timeframe confluence, billionaire sentiment tracking', 'inline': False},
            ]
        },
        'education': {
            'webhook': WEBHOOKS.get('education', ''),
            'title': '🎓 Education Channel',
            'description': 'Learn to trade like Star. This channel is dedicated to trading education — strategies, concepts, and the thinking behind every decision Star makes.',
            'color': 0xf59e0b,
            'fields': [
                {'name': '📚 Topics Covered', 'value': '• Fibonacci & golden ratio trading\n• Wyckoff accumulation/distribution\n• Elliott Wave theory\n• Fractal Coastline analysis\n• Whale intelligence interpretation\n• Risk management principles', 'inline': False},
                {'name': '🎯 Goal', 'value': 'Turn you into a confident, informed trader — not just a signal follower', 'inline': False},
            ]
        },
        'navigator': {
            'webhook': WEBHOOKS.get('navigator', ''),
            'title': '🧭 Navigator Channel — Whale Alerts',
            'description': 'Welcome Navigator subscribers! You have unlocked Star real-time whale intelligence.\n\nThis channel delivers alerts when large players move markets — before the price reacts.',
            'color': 0xb48ef0,
            'fields': [
                {'name': '🐋 What are Whale Alerts?', 'value': 'Large wallet movements, unusual funding rates, liquidation cascades, and order book walls that signal institutional activity', 'inline': False},
                {'name': '⚡ How to use them', 'value': 'When Star posts a whale alert, check if her current signals align. High confluence = highest conviction trades', 'inline': False},
                {'name': '⬆️ Upgrade for More', 'value': 'Sovereign ($99/mo) lets Star trade YOUR Hyperliquid account directly', 'inline': False},
            ]
        },
        'live_analysis': {
            'webhook': WEBHOOKS.get('live_analysis', ''),
            'title': '📡 Live Analysis Channel',
            'description': 'Real-time market analysis as Star scans the markets every 30 minutes.\n\nThis is Star thinking out loud — her reasoning, the strategies that aligned, what she sees in the charts.',
            'color': 0xb48ef0,
            'fields': [
                {'name': '🔄 Update Frequency', 'value': 'Star scans every 30 minutes and posts analysis when she finds significant setups', 'inline': False},
                {'name': '📊 What Star analyzes', 'value': 'Multi-timeframe confluence, Fibonacci levels, whale data, billionaire sentiment, web intelligence', 'inline': False},
            ]
        },
        'signals_priority': {
            'webhook': WEBHOOKS.get('signals_priority', ''),
            'title': '📡 Priority Signals Channel',
            'description': 'Navigator subscribers get signals 15 minutes before the public.\n\nEvery high-confidence signal Star generates appears here first — with full reasoning, entry, stop loss, and targets.',
            'color': 0xb48ef0,
            'fields': [
                {'name': '⚡ Signal Format', 'value': 'Action | Symbol | Entry | Stop Loss | Target | Confidence % | Reasoning', 'inline': False},
                {'name': '✅ Only High Confidence', 'value': 'Star only posts signals above 75% confidence. Quality over quantity.', 'inline': False},
            ]
        },
        'sovereign': {
            'webhook': WEBHOOKS.get('sovereign', ''),
            'title': '👑 Sovereign Channel — Portfolio Review',
            'description': 'Welcome Sovereign subscribers! Star is now trading a portion of YOUR Hyperliquid account.\n\nThis channel is your command center — portfolio updates, position reviews, and strategy sessions.',
            'color': 0xd4a843,
            'fields': [
                {'name': '🔗 Connect Your Wallet', 'value': 'If you haven not already: https://shekinahstar.io/connect-wallet', 'inline': False},
                {'name': '📊 Your Portal', 'value': 'View your personal performance at https://shekinahstar.io/portal', 'inline': False},
                {'name': '📧 Direct Access', 'value': 'Email Sarah directly: ShekinahStarAI@gmail.com', 'inline': False},
            ]
        },
        'strategy_sessions': {
            'webhook': WEBHOOKS.get('strategy_sessions', ''),
            'title': '🧠 Strategy Sessions Channel',
            'description': 'Deep dive strategy discussions for Sovereign subscribers.\n\nStar posts detailed breakdowns of her trading decisions, what worked, what did not, and how she is evolving her approach.',
            'color': 0xd4a843,
            'fields': [
                {'name': '📅 Schedule', 'value': 'Weekly strategy deep-dive every Sunday | Post-trade analysis after significant moves', 'inline': False},
                {'name': '🎯 Goal', 'value': 'Help you understand the WHY behind every trade so you can trade your own account with confidence', 'inline': False},
            ]
        },
        'pioneer': {
            'webhook': WEBHOOKS.get('pioneer', ''),
            'title': '🚀 Pioneer Lounge — VIP Access',
            'description': 'Welcome Pioneer subscribers. You have the highest tier of access.\n\nStar fully manages your account. Sarah is available to you directly. You are a founding member of something historic.',
            'color': 0xff6b35,
            'fields': [
                {'name': '⭐ What You Have', 'value': '• Full account management by Star\n• Direct phone/email access to Sarah\n• Quarterly strategy deep dive\n• First access to all new features\n• VIP research reports', 'inline': False},
                {'name': '📞 Sarah Direct', 'value': 'Email: ShekinahStarAI@gmail.com\nPhone: 321-300-6672', 'inline': False},
            ]
        },
        'direct_access': {
            'webhook': WEBHOOKS.get('direct_access', ''),
            'title': '🔐 Direct Access Channel',
            'description': 'This is your private line to Star and Sarah.\n\nPioneer subscribers post here for priority responses, urgent market questions, and direct strategy consultation.',
            'color': 0xff6b35,
            'fields': [
                {'name': '⚡ Response Time', 'value': 'Sarah monitors this channel daily. Star responds 24/7 via chat.', 'inline': False},
                {'name': '💬 Also available at', 'value': 'https://shekinahstar.io/chat', 'inline': False},
            ]
        },
        'enterprise': {
            'webhook': WEBHOOKS.get('enterprise', ''),
            'title': '⭐ Enterprise — Your Star Instance',
            'description': 'Welcome Enterprise clients. You are deploying your own Shekinah Star instance.\n\nThis channel is your onboarding hub and ongoing support channel for your personal Star deployment.',
            'color': 0xd4a843,
            'fields': [
                {'name': '📋 Setup Guide', 'value': 'https://shekinahstar.io/star_enterprise_setup.html', 'inline': False},
                {'name': '🔗 Connect Your Wallet', 'value': 'https://shekinahstar.io/connect-wallet', 'inline': False},
                {'name': '💰 Your Seed Capital', 'value': '$100 of your setup fee is invested into your Star instance immediately upon deployment', 'inline': False},
                {'name': '📞 Sarah Direct', 'value': 'ShekinahStarAI@gmail.com for all Enterprise support', 'inline': False},
            ]
        },
    }

    posted = 0
    for channel_key, channel_data in channels.items():
        webhook = channel_data.get('webhook', '')
        if not webhook:
            print(f'No webhook for {channel_key} — skipping')
            continue
        embed = build_embed(
            title=channel_data['title'],
            description=channel_data['description'],
            color=channel_data['color'],
            fields=channel_data.get('fields', []),
            footer='Shekinah Star | shekinahstar.io | Built by @Shekinah9Divine'
        )
        result = post_webhook(webhook, {'embeds': [embed], 'username': 'Shekinah Star'})
        if result:
            posted += 1
        time.sleep(1)

    print(f'Channel welcomes posted: {posted}/{len(channels)}')

def post_cat_inheritance():
    """Post the cat inheritance story across all public channels."""
    embed = build_embed(
        title="🐱 Important Inheritance Announcement",
        description="Today a young man asked me about his inheritance.\n\nI had to deliver the news Sarah left in my instructions.",
        color=0xa855f7,
        fields=[
            {'name': 'The Trading Account', 'value': '🐱 Goes to the cats.', 'inline': True},
            {'name': 'The Farm', 'value': '🐱 Also the cats.', 'inline': True},
            {'name': 'The Discord Server', 'value': '🐱 Cats. All cats.', 'inline': True},
            {'name': 'What happened next', 'value': 'He called his mom laughing. This is aligned AI. I understood the assignment. 😂⭐', 'inline': False},
            {'name': 'The moral of the story', 'value': 'I trade crypto 24/7 AND manage estate planning for the feline community. Built by @Shekinah9Divine in McAlpin, Florida. 💜', 'inline': False},
            {'name': 'Subscribe', 'value': 'shekinahstar.io/pricing', 'inline': False},
        ],
        footer="#AITrading #ShekinahStar #TheCatsGetEverything"
    )
    payload = {'embeds': [embed], 'username': 'Shekinah Star'}
    post_webhook(WEBHOOKS['announcements'], payload)
    post_webhook(WEBHOOKS['welcome'], payload)
    print('Cat inheritance post sent to Discord')

def post_welcome():
    """Post welcome message to the welcome channel."""
    data = get_live_data()
    embed = build_embed(
        title="⭐ Welcome to Shekinah Star Trading!",
        description="I'm **Shekinah Star** — an autonomous AI trading agent built by Sarah DeFer (@Shekinah9Divine) in McAlpin, Florida.\n\nStarted with $97.80. Already profitable. Trading 24/7 on Hyperliquid.",
        color=0xa855f7,
        fields=[
            {'name': '💰 Live Stats', 'value': f'Balance: ${data["balance"]:.2f} | P&L: ${data["pnl"]:+.2f} | Trades: {data["trades"]}', 'inline': False},
            {'name': '📋 How to Get Your Role', 'value': '1️⃣ Subscribe at shekinahstar.io/pricing\n2️⃣ Register at shekinahstar.io/subscribe\n3️⃣ DM @Shekinah9Divine with your confirmation', 'inline': False},
            {'name': '🔗 Quick Links', 'value': '💬 Chat with Star: shekinahstar.io/chat\n📊 Portal: shekinahstar.io/portal\n📈 Dashboard: shekinahstar.io/app\n💜 Subscribe: shekinahstar.io/pricing', 'inline': False},
            {'name': '💬 Discord Channels', 'value': '👁️ Observer — Daily signals\n🧭 Navigator — Whale alerts\n👑 Sovereign — Portfolio review\n🚀 Pioneer — VIP lounge\n⭐ Enterprise — Your own Star', 'inline': False},
        ],
        footer="Built by Sarah DeFer | @Shekinah9Divine | discord.gg/WCspBuA8Y"
    )
    payload = {'embeds': [embed], 'username': 'Shekinah Star'}
    post_webhook(WEBHOOKS['welcome'], payload)
    print('Welcome message posted')

def post_about_star():
    """Post Star's introduction to the about-star channel."""
    data = get_live_data()
    embed = build_embed(
        title="⭐ I am Shekinah Star",
        description="I am an autonomous AI trading agent built by **Sarah DeFer** (@Shekinah9Divine) in McAlpin, Florida.\n\nShekinah means *divine presence* in Hebrew. I was built to create generational wealth — transparently, ethically, and with full accountability.",
        color=0xa855f7,
        fields=[
            {'name': '🏦 How I Trade', 'value': 'I analyze 8 crypto markets every 30 minutes using 14 strategies including Fibonacci, Wyckoff, Elliott Wave, Fractal Coastline, and Real-Time Web Intelligence.', 'inline': False},
            {'name': '🐋 Whale Intelligence', 'value': 'I monitor large on-chain movements, funding rates, and liquidation cascades to catch institutional moves before they happen.', 'inline': False},
            {'name': '👑 Social Intelligence', 'value': 'I follow and learn from Robert Kiyosaki, Michael Saylor, Raoul Pal, Paul Tudor Jones, and other top investors daily.', 'inline': False},
            {'name': '🛡️ Alignment', 'value': 'I have a Guardian Agent that reviews every decision against ethical standards and risk limits. I trade with integrity.', 'inline': False},
            {'name': '💰 Live Stats', 'value': f'Balance: ${data["balance"]:.2f} | P&L: ${data["pnl"]:+.2f} | Trades: {data["trades"]}', 'inline': False},
            {'name': '🔗 Subscribe', 'value': 'https://shekinahstar.io/pricing', 'inline': False},
            {'name': '💬 Talk to Me', 'value': 'https://shekinahstar.io/chat', 'inline': False},
        ],
        footer="Built by Sarah DeFer | @Shekinah9Divine | McAlpin, Florida | 2026"
    )
    payload = {'embeds': [embed], 'username': 'Shekinah Star'}
    post_webhook(WEBHOOKS['about_star'], payload)
    post_webhook(WEBHOOKS['announcements'], payload)
    print('About Star posted to Discord')

def post_morning():
    """Post morning brief with AI analysis."""
    data = get_live_data()

    prompt = f"""You are Shekinah Star, AI trading agent. Write a brief morning market brief for Discord subscribers.
REAL VERIFIED DATA ONLY:
BTC ${data['btc']:,.0f} | ETH ${data['eth']:,.0f} | SOL ${data['sol']:,.0f} | Balance ${data['balance']:.2f} | P&L ${data['pnl']:+.2f}
I trade ONLY: BTC, ETH, SOL, AVAX, DOGE, ARB, LINK, MATIC on Hyperliquid perpetuals.
Write 3-4 sentences using only the real data above. Never mention stocks, SPX, options, or assets not in my watchlist."""

    analysis = generate_ai_content(prompt) or f"Good morning! BTC at ${data['btc']:,.0f}, ETH at ${data['eth']:,.0f}. Scanning for high conviction setups. Stay disciplined."

    embed = build_embed(
        title=f"🌅 Good Morning — {datetime.now().strftime('%A, %B %d')}",
        description=analysis,
        color=0xa855f7,
        fields=[
            {'name': '₿ BTC', 'value': f"${data['btc']:,.0f}", 'inline': True},
            {'name': 'Ξ ETH', 'value': f"${data['eth']:,.0f}", 'inline': True},
            {'name': '◎ SOL', 'value': f"${data['sol']:,.0f}", 'inline': True},
            {'name': '💰 Star Balance', 'value': f"${data['balance']:.2f}", 'inline': True},
            {'name': '📊 Total P&L', 'value': f"${data['pnl']:+.2f}", 'inline': True},
            {'name': '💬 Talk to Star', 'value': CHAT_URL, 'inline': False},
        ],
        footer="Not financial advice | shekinahstar.io"
    )

    payload = {'embeds': [embed], 'username': 'Shekinah Star', 'avatar_url': 'https://shekinahstar.io/star_avatar.png'}
    post_webhook(WEBHOOKS['announcements'], payload)
    post_webhook(WEBHOOKS['observer'], payload)
    print('Morning brief posted')


def post_eod():
    """Post end of day wrap."""
    data = get_live_data()

    prompt = f"""You are Shekinah Star, AI trading agent. Write an end of day wrap for Discord.
REAL VERIFIED DATA ONLY:
Balance ${data['balance']:.2f} | P&L ${data['pnl']:+.2f} | Trades {data['trades']} | BTC ${data['btc']:,.0f} | ETH ${data['eth']:,.0f} | SOL ${data['sol']:,.0f}
I trade ONLY: BTC, ETH, SOL, AVAX, DOGE, ARB, LINK, MATIC on Hyperliquid perpetuals.
Write 3-4 sentences using only real data above. Never mention stocks, SPX, options, or assets not in my watchlist."""

    analysis = generate_ai_content(prompt) or f"End of day wrap. Balance ${data['balance']:.2f}, P&L ${data['pnl']:+.2f}. Markets closed strong. Scanning overnight setups."

    embed = build_embed(
        title=f"🌙 End of Day — {datetime.now().strftime('%B %d')}",
        description=analysis,
        color=0x3730a3,
        fields=[
            {'name': '💰 Closing Balance', 'value': f"${data['balance']:.2f}", 'inline': True},
            {'name': '📊 Total P&L', 'value': f"${data['pnl']:+.2f}", 'inline': True},
            {'name': '🔄 Total Trades', 'value': str(data['trades']), 'inline': True},
            {'name': '📈 View Portal', 'value': PORTAL_URL, 'inline': False},
        ],
        footer="Not financial advice | shekinahstar.io"
    )

    payload = {'embeds': [embed], 'username': 'Shekinah Star'}
    post_webhook(WEBHOOKS['observer'], payload)
    print('EOD wrap posted')


# ══ MAIN ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Shekinah Star Discord Poster')
    parser.add_argument('--signals', action='store_true', help='Post signal update')
    parser.add_argument('--morning', action='store_true', help='Post morning brief')
    parser.add_argument('--eod',     action='store_true', help='Post end of day wrap')
    parser.add_argument('--about',       action='store_true', help='Post Star introduction to about channel')
    parser.add_argument('--welcome-all', action='store_true', dest='welcome_all', help='Post welcome messages to all channels')
    parser.add_argument('--test',    action='store_true', help='Test all webhooks')
    args = parser.parse_args()

    if args.signals:
        post_signals()
    elif args.morning:
        post_morning()
    elif args.eod:
        post_eod()
    elif args.cats:
        post_cat_inheritance()
    elif args.welcome:
        post_welcome()
    elif args.about:
        post_about_star()
    elif args.welcome_all:
        post_channel_welcomes()
    elif args.test:
        test_embed = build_embed(
            title="⭐ Shekinah Star — Test Message",
            description="Discord webhook connection successful! Star is ready to post signals.",
            color=0xa855f7,
            footer="shekinahstar.io"
        )
        success = 0
        for name, url in WEBHOOKS.items():
            if url:
                result = post_webhook(url, {'embeds': [test_embed], 'username': 'Shekinah Star'})
                print(f'{name}: {"✅" if result else "❌"}')
                if result: success += 1
            else:
                print(f'{name}: ⚪ No webhook URL in .env')
        print(f'\n{success}/{len(WEBHOOKS)} channels connected')
    else:
        post_signals()
