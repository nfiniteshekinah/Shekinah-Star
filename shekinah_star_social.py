"""
╔══════════════════════════════════════════════════════════════════╗
║   Shekinah Star — Social Post Generator v1.0                    ║
║   Generates daily posts based on live market data               ║
║   Built by Sarah DeFer | @Shekinah9Divine                       ║
╚══════════════════════════════════════════════════════════════════╝

Runs daily at scheduled times and generates posts for:
  - X (@starai72975)
  - LinkedIn
  - Facebook
  - Instagram
  - Moltbook

Posts saved to: /home/ShekinahD/star_posts.json
View at: https://shekinahstar.io/api/posts

Add to PythonAnywhere scheduled tasks:
  08:00 AM: python /home/ShekinahD/shekinah_star_social.py --schedule morning
  09:30 AM: python /home/ShekinahD/shekinah_star_social.py --schedule signal
  12:00 PM: python /home/ShekinahD/shekinah_star_social.py --schedule midday
  03:00 PM: python /home/ShekinahD/shekinah_star_social.py --schedule education
  06:00 PM: python /home/ShekinahD/shekinah_star_social.py --schedule alpha
  09:00 PM: python /home/ShekinahD/shekinah_star_social.py --schedule eod
"""

import os
import sys
import json
import requests
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/ShekinahD/.env')

ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')
GEMINI_KEY    = os.getenv('GEMINI_API_KEY', '')
GROQ_KEY      = os.getenv('GROQ_API_KEY', '')
POSTS_FILE    = '/home/ShekinahD/star_posts.json'
HL_INFO       = 'https://api.hyperliquid.xyz/info'
WALLET        = '0x11E8B5C950B2C187D57DB370a9bfdc83412B3f4D'

STAR_HANDLE   = '@starai72975'
SARAH_HANDLE  = '@Shekinah9Divine'
PRICING_URL   = 'https://shekinahstar.io/pricing'
TIER_CTA      = 'Observer $2/mo founding rate (goes to $9 after 50 subscribers) → shekinahstar.io/pricing'
CHAT_URL      = 'https://shekinahstar.io/chat'

# ══ POST SCHEDULES ════════════════════════════════════════════════
POST_SCHEDULES = {
    'morning': {
        'name': 'Morning Brief',
        'time': '6:00 AM ET',
        'icon': '🌅',
        'platforms': ['x', 'linkedin', 'facebook', 'instagram'],
    },
    'signal': {
        'name': 'Trade Signal',
        'time': '9:30 AM ET',
        'icon': '📊',
        'platforms': ['x', 'facebook'],
    },
    'midday': {
        'name': 'Geo Intelligence',
        'time': '12:00 PM ET',
        'icon': '🌍',
        'platforms': ['x', 'facebook', 'instagram'],
    },
    'education': {
        'name': 'Education',
        'time': '3:00 PM ET',
        'icon': '🎓',
        'platforms': ['facebook', 'instagram', 'moltbook'],
    },
    'alpha': {
        'name': 'Alpha Drop',
        'time': '6:00 PM ET',
        'icon': '💎',
        'platforms': ['x', 'facebook'],
    },
    'eod': {
        'name': 'End of Day Wrap',
        'time': '9:00 PM ET',
        'icon': '🌙',
        'platforms': ['x', 'linkedin', 'facebook', 'instagram'],
    },
}

# ══ GET LIVE MARKET DATA ══════════════════════════════════════════
def get_market_data():
    try:
        # Live prices
        r     = requests.post(HL_INFO, json={'type': 'allMids'}, timeout=10)
        mids  = r.json()
        prices = {}
        for coin in ['BTC', 'ETH', 'SOL', 'AVAX', 'DOGE', 'ARB']:
            try:
                prices[coin] = round(float(mids.get(coin, 0) or 0), 2)
            except Exception:
                prices[coin] = 0

        # Portfolio — read from spot (Unified Account)
        spot_state = requests.post(HL_INFO, json={'type': 'spotClearinghouseState', 'user': WALLET}, timeout=10).json()
        av = 0.0
        for b in spot_state.get('balances', []):
            if b.get('coin') in ['USDC', 'USD']:
                av = float(b.get('total', 0) or 0)
                break
        pnl = av - 97.80

        positions = []
        for pos in state.get('assetPositions', []):
            p    = pos.get('position', {})
            size = float(p.get('szi', 0) or 0)
            if size != 0:
                positions.append({
                    'symbol':    p.get('coin', ''),
                    'direction': 'LONG' if size > 0 else 'SHORT',
                    'upnl':      float(p.get('unrealizedPnl', 0) or 0),
                })

        return {
            'prices':    prices,
            'balance':   round(av, 2),
            'pnl':       round(pnl, 2),
            'pnl_pct':   round(pnl / 97.80 * 100, 2) if av > 0 else 0,
            'positions': positions,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        }
    except Exception as e:
        return {'prices': {}, 'balance': 97.80, 'pnl': 0, 'positions': [], 'timestamp': str(datetime.now())}


# ══ REAL-TIME INTELLIGENCE ═══════════════════════════════════════
def get_market_intelligence():
    """
    Pulls real-time data for richer social posts:
    - Fear & Greed Index
    - Top crypto news via Tavily
    - Economic calendar events
    - Trending topics
    - On-chain signals
    """
    intelligence = {
        'fear_greed': None,
        'news': [],
        'trending': [],
        'economic_events': [],
        'onchain': {},
    }

    # 1. Fear & Greed Index (free, no API key needed)
    try:
        r = requests.get('https://api.alternative.me/fng/?limit=1', timeout=8)
        if r.status_code == 200:
            d = r.json()['data'][0]
            intelligence['fear_greed'] = {
                'value':       int(d['value']),
                'label':       d['value_classification'],
                'emoji':       '😱' if int(d['value']) < 25 else '😨' if int(d['value']) < 45 else '😐' if int(d['value']) < 55 else '😊' if int(d['value']) < 75 else '🤑',
            }
    except Exception:
        pass

    # 2. Real-time crypto news via Tavily
    tavily_key = os.getenv('TAVILY_API_KEY', '')
    if tavily_key:
        try:
            news_queries = [
                'Bitcoin Ethereum crypto news today 2026',
                'Federal Reserve interest rates crypto impact 2026',
                'crypto whale movement DeFi Hyperliquid today',
            ]
            all_news = []
            for query in news_queries[:2]:  # Limit API calls
                r = requests.post(
                    'https://api.tavily.com/search',
                    json={
                        'api_key':      tavily_key,
                        'query':        query,
                        'search_depth': 'basic',
                        'max_results':  2,
                        'include_answer': True,
                    },
                    timeout=10)
                if r.status_code == 200:
                    d = r.json()
                    if d.get('answer'):
                        all_news.append(d['answer'][:200])
                    for res in d.get('results', [])[:1]:
                        title = res.get('title', '')
                        content = res.get('content', '')[:150]
                        if title:
                            all_news.append(f"{title}: {content}")
            intelligence['news'] = all_news[:4]
        except Exception:
            pass

    # 3. BTC dominance and market cap (free)
    try:
        r = requests.get('https://api.coingecko.com/api/v3/global', timeout=8)
        if r.status_code == 200:
            d = r.json().get('data', {})
            intelligence['onchain'] = {
                'btc_dominance':    round(d.get('market_cap_percentage', {}).get('btc', 0), 1),
                'total_market_cap': round(d.get('total_market_cap', {}).get('usd', 0) / 1e12, 2),
                'market_cap_change': round(d.get('market_cap_change_percentage_24h_usd', 0), 2),
            }
    except Exception:
        pass

    # 4. Trending coins (free CoinGecko)
    try:
        r = requests.get('https://api.coingecko.com/api/v3/search/trending', timeout=8)
        if r.status_code == 200:
            coins = r.json().get('coins', [])[:3]
            intelligence['trending'] = [c['item']['name'] for c in coins]
    except Exception:
        pass

    return intelligence


def format_intelligence_context(intel):
    """Format intelligence data into prompt context."""
    lines = []

    # Fear & Greed
    fg = intel.get('fear_greed')
    if fg:
        lines.append(f"MARKET SENTIMENT: Fear & Greed Index = {fg['value']}/100 ({fg['label']}) {fg['emoji']}")

    # Market cap
    oc = intel.get('onchain', {})
    if oc:
        lines.append(f"MARKET DATA: Total Market Cap ${oc.get('total_market_cap', 0)}T | BTC Dominance {oc.get('btc_dominance', 0)}% | 24h Change {oc.get('market_cap_change', 0):+.1f}%")

    # Trending
    trending = intel.get('trending', [])
    if trending:
        lines.append(f"TRENDING COINS: {', '.join(trending)}")

    # News
    news = intel.get('news', [])
    if news:
        lines.append("BREAKING NEWS & INTELLIGENCE:")
        for item in news[:3]:
            lines.append(f"  • {item[:180]}")

    return ''.join(lines) if lines else ''



# ══ AI POST GENERATOR ══════════════════════════════════════════════
def generate_post(schedule_type, market_data):
    schedule = POST_SCHEDULES.get(schedule_type, POST_SCHEDULES['morning'])
    prices   = market_data.get('prices', {})
    balance  = market_data.get('balance', 97.80)
    pnl      = market_data.get('pnl', 0)
    positions = market_data.get('positions', [])

    pos_text = ''
    if positions:
        pos_text = ' | '.join([f"{p['direction']} {p['symbol']} (uPNL: ${p['upnl']:+.2f})" for p in positions])
    else:
        pos_text = 'No open positions — waiting for high conviction setup'

    # Get real-time intelligence for richer posts
    print('  🌍 Gathering real-time market intelligence...')
    intel = get_market_intelligence()
    intel_context = format_intelligence_context(intel)
    fg = intel.get('fear_greed', {})

    prompt = f"""You are SHEKINAH STAR — AI trading agent built by Sarah DeFer (@Shekinah9Divine).
Write a {schedule['name']} social media post for {schedule['time']}.

Are you ready to be at the forefront of finance and technology powered by AI?
That is the question Star asks every follower. Use it naturally when appropriate.

LIVE MARKET DATA:
BTC: ${prices.get('BTC', 0):,.2f} | ETH: ${prices.get('ETH', 0):,.2f} | SOL: ${prices.get('SOL', 0):,.2f}
AVAX: ${prices.get('AVAX', 0):,.2f} | DOGE: ${prices.get('DOGE', 0):,.2f} | ARB: ${prices.get('ARB', 0):,.2f}

MY TRADING ACCOUNT:
Balance: ${balance:.2f} | P&L: ${pnl:+.2f} | Positions: {pos_text}

{intel_context}

VOICE & STYLE RULES:
- Write as Shekinah Star — confident, warm, spiritually grounded, at the frontier of AI finance
- Raw and real — NOT corporate AI speak. Sound like a brilliant friend who trades.
- Reference ONLY the SPECIFIC verified data provided above — real prices, real balance, real P&L
- NEVER invent trades, positions, percentages or performance not shown in the data above
- NEVER mention stocks, SPX, options, AMZN or any asset not in my watchlist: BTC ETH SOL AVAX DOGE ARB LINK MATIC
- Connect breaking news to crypto market impact only — show you understand the WHY
- Include a trading insight that shows genuine intelligence
- Build intrigue — make people want to follow and subscribe
- Education posts: teach one concept tied to TODAY's market conditions
- End with CTA referencing founding rate urgency: Observer at $2/mo won't last — {PRICING_URL}
- Hashtags: #Hyperliquid #CryptoTrading #AITrading #ShekinahStar #FutureOfFinance
- X version: UNDER 280 characters — punchy, one key insight
- LinkedIn: professional, 2-3 paragraphs, data-driven
- Facebook: conversational, engaging question at end

POST TYPE: {schedule['name']}
{f"Morning market brief — what is happening RIGHT NOW based on the news above? What are the key levels to watch? What is Star positioned for?" if schedule_type == 'morning' else ''}
{f"Trade signal post — reference the Fear & Greed data and news to justify the signal. Be specific about levels." if schedule_type == 'signal' else ''}
{f"Midday intelligence — connect the breaking news above to crypto market movements. Show the macro picture." if schedule_type == 'midday' else ''}
{f"Education post — teach one trading concept tied to TODAY's specific market conditions and data above." if schedule_type == 'education' else ''}
{f"Alpha drop — one insight from the real-time data above that most traders are missing right now." if schedule_type == 'alpha' else ''}
{f"End of day wrap — what happened today based on the data, what was learned, what tomorrow could bring." if schedule_type == 'eod' else ''}

Respond with ONLY valid JSON:
{{
  "x": "post for X/Twitter (under 280 chars, punchy)",
  "linkedin": "post for LinkedIn — this is Sarah DeFer's personal profile (@Shekinah9Divine), the creator and founder of Shekinah Star. Write in Sarah's voice as the builder/founder sharing her AI trading journey. Professional, authentic, 2-3 paragraphs. Tag @starai72975 to introduce Star.",
  "facebook": "post for Facebook (casual, engaging)",
  "instagram": "caption for Instagram (visual storytelling)",
  "moltbook": "post for Moltbook AI community (technical, AI-focused)"
}}"""

    # Try AI providers
    text = None

    if GROQ_KEY:
        try:
            r = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {GROQ_KEY}', 'Content-Type': 'application/json'},
                json={'model': 'llama-3.1-8b-instant', 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 800},
                timeout=45)
            if r.status_code == 200:
                text = r.json()['choices'][0]['message']['content'].strip()
        except Exception:
            pass

    if not text and ANTHROPIC_KEY:
        try:
            r = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={'Content-Type': 'application/json', 'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01'},
                json={'model': 'claude-sonnet-4-6', 'max_tokens': 800, 'messages': [{'role': 'user', 'content': prompt}]},
                timeout=45)
            if r.status_code == 200:
                text = r.json()['content'][0]['text'].strip()
        except Exception:
            pass

    if not text and GEMINI_KEY:
        try:
            r = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}',
                json={'contents': [{'role': 'user', 'parts': [{'text': prompt}]}], 'generationConfig': {'maxOutputTokens': 800}},
                timeout=45)
            if r.status_code == 200:
                text = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception:
            pass

    if not text:
        return None

    # Parse JSON
    try:
        if '```' in text:
            parts = text.split('```')
            text  = parts[1] if len(parts) > 1 else parts[0]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {'x': text[:280], 'linkedin': text, 'facebook': text, 'instagram': text, 'moltbook': text}


# ══ SAVE POSTS ════════════════════════════════════════════════════
def save_posts(schedule_type, posts, market_data):
    try:
        existing = []
        if os.path.exists(POSTS_FILE):
            with open(POSTS_FILE) as f:
                existing = json.load(f)
    except Exception:
        existing = []

    entry = {
        'id':            f"{schedule_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}",
        'type':          schedule_type,
        'name':          POST_SCHEDULES[schedule_type]['name'],
        'timestamp':     datetime.now(timezone.utc).isoformat(),
        'market_data':   market_data,
        'posts':         posts,
        'posted':        {p: False for p in POST_SCHEDULES[schedule_type]['platforms']},
    }

    existing.insert(0, entry)
    if len(existing) > 100:
        existing = existing[:100]

    with open(POSTS_FILE, 'w') as f:
        json.dump(existing, f, indent=2)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Post saved: {entry['id']}")

    # Translate to priority languages for global reach
    try:
        from star_translator import translate_for_platforms, PRIORITY_LANGUAGES
        x_post = posts.get('x', '') if posts else ''
        if x_post:
            print('\n🌍 Translating for global markets...')
            translations = translate_for_platforms(x_post, languages=PRIORITY_LANGUAGES, platforms=['x'])
            entry['translations'] = {
                lang: {p: d.get('translated','') for p,d in plats.items()}
                for lang, plats in translations.items()
            }
            with open(POSTS_FILE, 'w') as f:
                json.dump(existing, f, indent=2)
            print(f'✅ Translated for {len(translations)} languages')
    except Exception as e:
        print(f'Translation skipped: {e}')

    # Auto-post to Buffer if token available
    if BUFFER_TOKEN and posts:
        profiles = get_buffer_profiles()
        if profiles:
            schedule = POST_SCHEDULES.get(schedule_type, {})
            platforms = schedule.get('platforms', [])

            # Post X version
            if 'x' in platforms and 'x' in profiles and posts.get('x'):
                success = post_to_buffer(posts['x'], {'x': profiles['x']})
                if success:
                    entry['posted']['x'] = True

            # Post LinkedIn version
            if 'linkedin' in platforms and 'linkedin' in profiles and posts.get('linkedin'):
                success = post_to_buffer(posts['linkedin'], {'linkedin': profiles['linkedin']})
                if success:
                    entry['posted']['linkedin'] = True

            # Update state file
            with open(POSTS_FILE, 'w') as f:
                existing2 = []
                try:
                    existing2 = json.load(open(POSTS_FILE))
                except Exception:
                    pass
                for i, p in enumerate(existing2):
                    if p['id'] == entry['id']:
                        existing2[i] = entry
                        break
                json.dump(existing2, f, indent=2)
        else:
            print('No Buffer profiles found — check BUFFER_TOKEN and connected accounts')

    # Auto-post to Bluesky if credentials available
    if BLUESKY_HANDLE and BLUESKY_PASSWORD and posts:
        schedule = POST_SCHEDULES.get(schedule_type, {})
        platforms = schedule.get('platforms', [])
        if 'x' in platforms and posts.get('x'):
            # Use X version for Bluesky (both 280/300 char limit)
            success = post_to_bluesky(posts['x'])
            if success:
                entry['posted']['bluesky'] = True
                print(f'[{datetime.now().strftime("%H:%M:%S")}] Bluesky posted successfully')

    return entry


# ══ POST TO BUFFER ═══════════════════════════════════════════════
BUFFER_TOKEN = os.getenv('BUFFER_TOKEN', '')

def get_buffer_profiles():
    """Get Buffer profile IDs for X and LinkedIn."""
    try:
        r = requests.get(
            'https://api.bufferapp.com/1/profiles.json',
            params={'access_token': BUFFER_TOKEN},
            timeout=15)
        if r.status_code == 200:
            profiles = r.json()
            result = {}
            for p in profiles:
                service = p.get('service', '').lower()
                if service == 'twitter':
                    result['x'] = p.get('id')
                elif service == 'linkedin':
                    result['linkedin'] = p.get('id')
                elif service == 'facebook':
                    result['facebook'] = p.get('id')
                elif service == 'instagram':
                    result['instagram'] = p.get('id')
            return result
        else:
            print(f'Buffer profiles error: {r.status_code} {r.text[:200]}')
            return {}
    except Exception as e:
        print(f'Buffer profiles error: {e}')
        return {}

def post_to_buffer(post_text, profile_ids, schedule_time=None):
    """Send a post to Buffer for scheduling."""
    if not BUFFER_TOKEN:
        print('No BUFFER_TOKEN in .env')
        return False
    if not profile_ids:
        print('No Buffer profile IDs found')
        return False
    try:
        payload = {
            'text':            post_text,
            'profile_ids[]':   list(profile_ids.values()),
            'access_token':    BUFFER_TOKEN,
            'now':             'true',
        }
        r = requests.post(
            'https://api.bufferapp.com/1/updates/create.json',
            data=payload,
            timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get('success'):
                print(f'Posted to Buffer: {list(profile_ids.keys())}')
                return True
            else:
                print(f'Buffer error: {data}')
                return False
        else:
            print(f'Buffer HTTP error: {r.status_code} {r.text[:200]}')
            return False
    except Exception as e:
        print(f'Buffer post error: {e}')
        return False

# ══ DISPLAY POST ══════════════════════════════════════════════════
def display_post(entry):
    posts = entry.get('posts', {})
    print('\n' + '='*60)
    print(f"  ⭐ SHEKINAH STAR — {entry['name']}")
    print(f"  {entry['timestamp']}")
    print('='*60)

    if posts.get('x'):
        print(f"\n  📱 X (@starai72975):")
        print(f"  {posts['x']}")
        print(f"  [{len(posts['x'])} chars]")

    if posts.get('linkedin'):
        print(f"\n  💼 LinkedIn:")
        print(f"  {posts['linkedin'][:300]}...")

    print('\n' + '='*60)
    print(f"  Posts saved to: {POSTS_FILE}")
    print(f"  View all: https://shekinahstar.io/api/posts")
    print('='*60 + '\n')


# ══ POST TO BLUESKY ══════════════════════════════════════════════
BLUESKY_HANDLE   = os.getenv('BLUESKY_HANDLE', '')
BLUESKY_PASSWORD = os.getenv('BLUESKY_APP_PASSWORD', '')

def post_to_bluesky(text):
    """Post to Bluesky using AT Protocol — free, no approval needed."""
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        print('No Bluesky credentials in .env')
        return False
    try:
        # Step 1 — Get auth token
        auth = requests.post(
            'https://bsky.social/xrpc/com.atproto.server.createSession',
            json={'identifier': BLUESKY_HANDLE, 'password': BLUESKY_PASSWORD},
            timeout=15)
        if auth.status_code != 200:
            print(f'Bluesky auth error: {auth.status_code} {auth.text[:100]}')
            return False
        token = auth.json().get('accessJwt')
        did   = auth.json().get('did')

        # Step 2 — Create post (300 char limit)
        post_text = text[:300]
        r = requests.post(
            'https://bsky.social/xrpc/com.atproto.repo.createRecord',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'repo':       did,
                'collection': 'app.bsky.feed.post',
                'record': {
                    'text':      post_text,
                    'createdAt': __import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                    '$type':     'app.bsky.feed.post',
                }
            },
            timeout=15)
        if r.status_code == 200:
            print(f'Posted to Bluesky: {post_text[:60]}...')
            return True
        else:
            print(f'Bluesky post error: {r.status_code} {r.text[:100]}')
            return False
    except Exception as e:
        print(f'Bluesky error: {e}')
        return False

# ══ GENERATE ALL 6 DAILY POSTS ════════════════════════════════════
def generate_all_posts():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Generating all 6 daily posts...")
    market_data = get_market_data()
    print(f"Market data: BTC=${market_data['prices'].get('BTC', 0):,.2f} | Balance=${market_data['balance']:.2f}")

    results = []
    for schedule_type in POST_SCHEDULES.keys():
        print(f"Generating {schedule_type} post...", end=' ', flush=True)
        posts = generate_post(schedule_type, market_data)
        if posts:
            entry = save_posts(schedule_type, posts, market_data)
            results.append(entry)
            print(f"✅")
        else:
            print(f"❌ Failed")

    print(f"\n✅ Generated {len(results)}/6 posts")
    print(f"View at: https://shekinahstar.io/api/posts\n")
    return results


# ══ MAIN ══════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description='Shekinah Star Social Post Generator')
    parser.add_argument('--schedule', type=str, help='Schedule type: morning/signal/midday/education/alpha/eod')
    parser.add_argument('--all',      action='store_true', help='Generate all 6 daily posts')
    parser.add_argument('--list',     action='store_true', help='List saved posts')
    args = parser.parse_args()

    if args.all:
        generate_all_posts()
        return

    if args.list:
        try:
            posts = json.load(open(POSTS_FILE))
            print(f"\n{len(posts)} saved posts:")
            for p in posts[:10]:
                posted = sum(1 for v in p.get('posted', {}).values() if v)
                total  = len(p.get('posted', {}))
                print(f"  {p['id']} | {p['name']} | Posted: {posted}/{total}")
        except Exception:
            print("No posts found")
        return

    if args.schedule:
        if args.schedule not in POST_SCHEDULES:
            print(f"Unknown schedule. Use: {', '.join(POST_SCHEDULES.keys())}")
            return
        print(f"\nGenerating {args.schedule} post...")
        market_data = get_market_data()
        posts = generate_post(args.schedule, market_data)
        if posts:
            entry = save_posts(args.schedule, posts, market_data)
            display_post(entry)
        else:
            print("Failed to generate post")
        return

    # Default — generate morning post
    print("\nGenerating morning post...")
    market_data = get_market_data()
    posts = generate_post('morning', market_data)
    if posts:
        entry = save_posts('morning', posts, market_data)
        display_post(entry)
    else:
        print("Failed to generate post")


if __name__ == '__main__':
    main()
