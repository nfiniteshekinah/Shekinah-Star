"""
star_trend_radar.py
Star Trend Radar — Emerging Signal Detection Engine
Designed & Built by Sarah DeFer | ShekinahStar.io

Detects trends BEFORE they hit mainstream awareness by scanning:
  - Social velocity (Reddit, Twitter mention spikes)
  - On-chain signals (funding rates, liquidation maps)
  - GitHub dev activity on crypto/AI projects
  - Regulatory language shifts
  - Cross-asset correlation anomalies
  - Narrative emergence patterns

DEPLOY: Upload to /home/ShekinahD/ on PythonAnywhere
REGISTER in flask_app.py:
    from star_trend_radar import radar_bp, run_radar_scan
    app.register_blueprint(radar_bp)

SCHEDULE: Add to star_trader.py or PythonAnywhere scheduled task:
    from star_trend_radar import run_radar_scan
    run_radar_scan()   # runs every 4 hours
"""

import os
import json
import time
import sqlite3
import requests
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

radar_bp = Blueprint('radar', __name__)

# ── Paths ──────────────────────────────────────────────────────────
BASE           = '/home/ShekinahD'
RADAR_DB       = os.path.join(BASE, 'star_radar.db')
RADAR_LOG      = os.path.join(BASE, 'star_radar_log.json')
OWNER_TOKEN    = os.environ.get('OWNER_TOKEN', 'shekinah-sarah-owner-2026')

# ── Read env ───────────────────────────────────────────────────────
def _read_env():
    keys = {}
    try:
        with open(os.path.join(BASE, '.env')) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    keys[k.strip()] = v.strip()
    except Exception:
        pass
    return keys

_ENV = _read_env()
GROQ_KEY      = _ENV.get('GROQ_API_KEY', '')
ANTHROPIC_KEY = _ENV.get('ANTHROPIC_API_KEY', '')

# ── Watchlist ──────────────────────────────────────────────────────
CRYPTO_WATCHLIST = [
    'BTC', 'ETH', 'SOL', 'AVAX', 'DOGE', 'ARB', 'LINK',
    'HYPE', 'SUI', 'APT', 'INJ', 'TIA', 'PYTH', 'JUP',
    'WIF', 'BONK', 'PEPE', 'WLD', 'FET', 'RNDR'
]

AI_PROJECTS = [
    'nvidia', 'anthropic', 'openai', 'mistral', 'groq',
    'hyperliquid', 'celestia', 'eigenlayer', 'ondo-finance',
    'worldcoin', 'fetch-ai', 'render-network'
]

NARRATIVE_SEEDS = [
    'AI agents crypto', 'RWA tokenization', 'Bitcoin ETF flows',
    'Fed rate cut crypto', 'DePIN infrastructure', 'liquid staking',
    'restaking points', 'memecoin season', 'layer 2 scaling',
    'crypto regulation SEC', 'sovereign wealth Bitcoin',
    'AI inference decentralized', 'GPU tokenization'
]


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_radar_db():
    conn = sqlite3.connect(RADAR_DB)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        asset       TEXT,
        signal_type TEXT,
        strength    INTEGER DEFAULT 5,
        direction   TEXT,
        title       TEXT,
        summary     TEXT,
        data_points TEXT,
        star_take   TEXT,
        category    TEXT,
        status      TEXT DEFAULT 'active',
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at  TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS scan_history (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_type  TEXT,
        signals_found INTEGER DEFAULT 0,
        duration_s    REAL,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS narrative_tracking (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        narrative   TEXT UNIQUE,
        first_seen  TIMESTAMP,
        last_seen   TIMESTAMP,
        mention_count INTEGER DEFAULT 1,
        momentum    TEXT DEFAULT 'emerging',
        category    TEXT
    )''')

    conn.commit()
    conn.close()


def save_signal(asset, signal_type, strength, direction,
                title, summary, data_points, star_take, category):
    conn = sqlite3.connect(RADAR_DB)
    c = conn.cursor()
    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    c.execute('''INSERT INTO signals
        (asset, signal_type, strength, direction, title, summary,
         data_points, star_take, category, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (asset, signal_type, strength, direction, title, summary,
         json.dumps(data_points), star_take, category,
         expires.isoformat()))
    conn.commit()
    conn.close()


def get_active_signals(category=None, min_strength=5, limit=20):
    conn = sqlite3.connect(RADAR_DB)
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    if category:
        c.execute('''SELECT * FROM signals
            WHERE status='active' AND expires_at > ?
              AND category=? AND strength >= ?
            ORDER BY strength DESC, created_at DESC LIMIT ?''',
            (now, category, min_strength, limit))
    else:
        c.execute('''SELECT * FROM signals
            WHERE status='active' AND expires_at > ?
              AND strength >= ?
            ORDER BY strength DESC, created_at DESC LIMIT ?''',
            (now, min_strength, limit))
    rows = c.fetchall()
    conn.close()
    cols = ['id','asset','signal_type','strength','direction','title',
            'summary','data_points','star_take','category','status',
            'created_at','expires_at']
    return [dict(zip(cols, r)) for r in rows]


# ══ SCAN MODULES ═══════════════════════════════════════════════════

def scan_hyperliquid_funding():
    """
    Detect funding rate anomalies on Hyperliquid.
    Extreme positive funding = overleveraged longs = squeeze risk.
    Extreme negative funding = overleveraged shorts = squeeze up.
    """
    signals = []
    try:
        r = requests.post('https://api.hyperliquid.xyz/info',
            json={'type': 'metaAndAssetCtxs'}, timeout=15)
        if r.status_code != 200:
            return signals

        data = r.json()
        if not isinstance(data, list) or len(data) < 2:
            return signals

        universe = data[0].get('universe', [])
        ctxs      = data[1]

        for i, asset_info in enumerate(universe):
            if i >= len(ctxs):
                break
            name    = asset_info.get('name', '')
            ctx     = ctxs[i]
            funding = float(ctx.get('funding', 0) or 0)
            oi      = float(ctx.get('openInterest', 0) or 0)

            # Annualized funding
            annual = funding * 24 * 365 * 100

            if abs(annual) < 50:
                continue  # Not extreme enough

            if annual > 100:
                # Extreme positive — longs paying heavily
                strength = min(10, int(annual / 50))
                save_signal(
                    asset       = name,
                    signal_type = 'funding_extreme',
                    strength    = strength,
                    direction   = 'SHORT_SQUEEZE_RISK',
                    title       = f'{name} Funding Extreme: {annual:.0f}% APR — Longs Overloaded',
                    summary     = f'{name} perpetual funding at {annual:.1f}% annualized. Longs paying shorts heavily. Market is overcrowded long — squeeze risk or reversal likely.',
                    data_points = {'funding_rate': funding, 'annual_pct': annual, 'open_interest': oi},
                    star_take   = f'When {name} funding hits this level historically, price either dumps to flush longs or shorts get squeezed if spot demand holds. Watch spot CVD next 4h.',
                    category    = 'onchain'
                )
                signals.append(name)

            elif annual < -50:
                # Extreme negative — shorts paying heavily
                strength = min(10, int(abs(annual) / 25))
                save_signal(
                    asset       = name,
                    signal_type = 'funding_extreme',
                    strength    = strength,
                    direction   = 'LONG_SQUEEZE_SETUP',
                    title       = f'{name} Negative Funding: {annual:.0f}% APR — Shorts Overloaded',
                    summary     = f'{name} funding deeply negative at {annual:.1f}% APR. Shorts paying longs. Market overcrowded short — conditions for violent squeeze up.',
                    data_points = {'funding_rate': funding, 'annual_pct': annual, 'open_interest': oi},
                    star_take   = f'Deeply negative {name} funding is a contrarian long setup if spot demand holds. Every short pays longs to hold — creates natural price support.',
                    category    = 'onchain'
                )
                signals.append(name)

    except Exception as e:
        print(f'[Radar] Funding scan error: {e}')

    return signals


def scan_price_velocity():
    """
    Detect unusual price velocity — coins moving faster than normal.
    Early trend detection before mainstream awareness.
    """
    signals = []
    try:
        # Get all mids from Hyperliquid
        r = requests.post('https://api.hyperliquid.xyz/info',
            json={'type': 'allMids'}, timeout=10)
        if r.status_code != 200:
            return signals

        current_prices = r.json()

        # Load previous prices from radar DB
        conn = sqlite3.connect(RADAR_DB)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS price_snapshots (
            coin TEXT, price REAL, timestamp TEXT)''')

        prev = {}
        c.execute('SELECT coin, price, timestamp FROM price_snapshots')
        for row in c.fetchall():
            prev[row[0]] = {'price': row[1], 'timestamp': row[2]}

        movers = []
        now_ts = datetime.now(timezone.utc).isoformat()

        for coin, price_str in current_prices.items():
            try:
                price = float(price_str or 0)
                if price == 0:
                    continue

                if coin in prev:
                    old_price = prev[coin]['price']
                    if old_price > 0:
                        pct_change = ((price - old_price) / old_price) * 100
                        if abs(pct_change) >= 5:
                            movers.append({
                                'coin': coin,
                                'pct': pct_change,
                                'price': price,
                                'old_price': old_price
                            })

                # Update snapshot
                c.execute('DELETE FROM price_snapshots WHERE coin=?', (coin,))
                c.execute('INSERT INTO price_snapshots VALUES (?,?,?)',
                          (coin, price, now_ts))
            except Exception:
                continue

        conn.commit()
        conn.close()

        # Sort by magnitude
        movers.sort(key=lambda x: abs(x['pct']), reverse=True)

        for m in movers[:5]:
            direction = 'BULLISH_MOMENTUM' if m['pct'] > 0 else 'BEARISH_MOMENTUM'
            strength  = min(10, max(5, int(abs(m['pct']) / 2)))
            emoji     = '🚀' if m['pct'] > 0 else '⬇️'

            save_signal(
                asset       = m['coin'],
                signal_type = 'price_velocity',
                strength    = strength,
                direction   = direction,
                title       = f"{emoji} {m['coin']} Moving {m['pct']:+.1f}% — Velocity Alert",
                summary     = f"{m['coin']} price moving {m['pct']:+.1f}% from ${m['old_price']:,.4f} to ${m['price']:,.4f}. Unusual velocity detected — check volume and news.",
                data_points = {'pct_change': m['pct'], 'current': m['price'], 'previous': m['old_price']},
                star_take   = f"{'Momentum building on' if m['pct'] > 0 else 'Distribution or panic on'} {m['coin']}. {'Watch for continuation above key levels.' if m['pct'] > 0 else 'Watch for support or dead-cat bounce.'}",
                category    = 'price'
            )
            signals.append(m['coin'])

    except Exception as e:
        print(f'[Radar] Price velocity scan error: {e}')

    return signals


def scan_narrative_emergence():
    """
    Use AI to detect emerging narratives from recent news.
    Scans crypto/AI/macro search trends for pre-consensus signals.
    """
    signals = []
    try:
        from duckduckgo_search import DDGS

        emerging = []
        with DDGS() as ddgs:
            for seed in NARRATIVE_SEEDS[:6]:  # Limit to 6 to stay fast
                try:
                    results = list(ddgs.text(
                        f'{seed} 2026',
                        max_results=3
                    ))
                    if results:
                        titles = [r.get('title', '') for r in results]
                        bodies = [r.get('body', '')[:200] for r in results]
                        emerging.append({
                            'seed':    seed,
                            'titles':  titles,
                            'snippets': bodies
                        })
                    time.sleep(0.5)  # Rate limit friendly
                except Exception:
                    continue

        if not emerging:
            return signals

        # Use AI to identify which narratives are genuinely emerging
        context = json.dumps(emerging, indent=2)[:3000]

        prompt = f"""You are Star — an AI trading intelligence oracle. 
Analyze these narrative search results and identify which ones represent EMERGING trends 
that most traders haven't caught yet. Focus on pre-consensus signals.

Search results:
{context}

Return a JSON array of up to 3 emerging signals in this exact format:
[
  {{
    "narrative": "short name",
    "strength": 7,
    "direction": "BULLISH" or "BEARISH" or "WATCH",
    "title": "one compelling sentence",
    "summary": "2-3 sentences on why this matters now",
    "assets": ["BTC", "ETH"],
    "star_take": "Star's forward-looking prediction in 1-2 sentences"
  }}
]
Return ONLY the JSON array, no other text."""

        # Try Groq first (fast + free)
        response_text = None
        if GROQ_KEY:
            try:
                gr = requests.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers={'Authorization': f'Bearer {GROQ_KEY}',
                             'Content-Type': 'application/json'},
                    json={
                        'model': 'llama-3.3-70b-versatile',
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': 800,
                        'temperature': 0.3
                    },
                    timeout=30
                )
                if gr.status_code == 200:
                    response_text = gr.json()['choices'][0]['message']['content']
            except Exception as e:
                print(f'[Radar] Groq narrative error: {e}')

        # Anthropic fallback
        if not response_text and ANTHROPIC_KEY:
            try:
                ar = requests.post(
                    'https://api.anthropic.com/v1/messages',
                    headers={'x-api-key': ANTHROPIC_KEY,
                             'anthropic-version': '2023-06-01',
                             'Content-Type': 'application/json'},
                    json={
                        'model': 'claude-haiku-4-5-20251001',
                        'max_tokens': 800,
                        'messages': [{'role': 'user', 'content': prompt}]
                    },
                    timeout=30
                )
                if ar.status_code == 200:
                    response_text = ar.json()['content'][0]['text']
            except Exception as e:
                print(f'[Radar] Anthropic narrative error: {e}')

        if not response_text:
            return signals

        # Parse JSON response
        clean = response_text.strip()
        if '```' in clean:
            clean = clean.split('```')[1]
            if clean.startswith('json'):
                clean = clean[4:]
        clean = clean.strip()

        narrative_signals = json.loads(clean)

        for ns in narrative_signals:
            assets = ns.get('assets', ['BTC'])
            asset  = assets[0] if assets else 'MARKET'

            save_signal(
                asset       = asset,
                signal_type = 'narrative_emergence',
                strength    = int(ns.get('strength', 6)),
                direction   = ns.get('direction', 'WATCH'),
                title       = ns.get('title', ''),
                summary     = ns.get('summary', ''),
                data_points = {'narrative': ns.get('narrative', ''),
                               'assets': assets},
                star_take   = ns.get('star_take', ''),
                category    = 'narrative'
            )
            signals.append(ns.get('narrative', ''))

            # Track narrative momentum
            conn = sqlite3.connect(RADAR_DB)
            c = conn.cursor()
            now_ts = datetime.now(timezone.utc).isoformat()
            c.execute('''INSERT OR IGNORE INTO narrative_tracking
                (narrative, first_seen, last_seen, category)
                VALUES (?, ?, ?, ?)''',
                (ns.get('narrative',''), now_ts, now_ts, 'crypto'))
            c.execute('''UPDATE narrative_tracking
                SET last_seen=?, mention_count=mention_count+1
                WHERE narrative=?''',
                (now_ts, ns.get('narrative','')))
            conn.commit()
            conn.close()

    except ImportError:
        print('[Radar] duckduckgo_search not installed — skipping narrative scan')
    except Exception as e:
        print(f'[Radar] Narrative scan error: {e}')

    return signals


def scan_github_activity():
    """
    Detect unusual GitHub commit/star activity on crypto/AI projects.
    Dev activity spikes often precede major announcements.
    No API key needed for public repos.
    """
    signals = []
    repos_to_check = [
        ('hyperliquid-dex',   'hyperliquid-dex/hyperliquid'),
        ('anthropic',         'anthropics/anthropic-sdk-python'),
        ('eigenlayer',        'Layr-Labs/eigenlayer-contracts'),
        ('ondo-finance',      'ondoprotocol/ondo-v1'),
    ]

    try:
        for name, repo in repos_to_check:
            try:
                r = requests.get(
                    f'https://api.github.com/repos/{repo}',
                    headers={'Accept': 'application/vnd.github.v3+json'},
                    timeout=8
                )
                if r.status_code != 200:
                    continue

                data    = r.json()
                stars   = data.get('stargazers_count', 0)
                forks   = data.get('forks_count', 0)
                watchers = data.get('watchers_count', 0)
                updated = data.get('updated_at', '')
                pushed  = data.get('pushed_at', '')

                # Check recency of last push
                if pushed:
                    pushed_dt  = datetime.fromisoformat(pushed.replace('Z', '+00:00'))
                    hours_since = (datetime.now(timezone.utc) - pushed_dt).total_seconds() / 3600

                    if hours_since < 6:
                        save_signal(
                            asset       = name.upper(),
                            signal_type = 'github_activity',
                            strength    = 7,
                            direction   = 'DEVELOPMENT_SURGE',
                            title       = f'🔧 {name.title()} Active Development — Push {hours_since:.0f}h Ago',
                            summary     = f'{repo} received a code push {hours_since:.0f} hours ago. Active development often precedes announcements, upgrades, or token events.',
                            data_points = {'stars': stars, 'forks': forks,
                                          'hours_since_push': hours_since,
                                          'repo': repo},
                            star_take   = f'Fresh commits on {name.title()} within 6 hours. Monitor for protocol announcements, token launches, or security patches in the next 24-48h.',
                            category    = 'development'
                        )
                        signals.append(name)

                time.sleep(0.3)
            except Exception:
                continue

    except Exception as e:
        print(f'[Radar] GitHub scan error: {e}')

    return signals


def scan_cross_asset_correlations():
    """
    Detect when crypto is decoupling from or correlating unusually
    with equities/macro — a pre-trend signal.
    """
    signals = []
    try:
        # Get BTC price
        hl_r = requests.post('https://api.hyperliquid.xyz/info',
            json={'type': 'allMids'}, timeout=10)
        if hl_r.status_code != 200:
            return signals

        mids = hl_r.json()
        btc  = float(mids.get('BTC', 0) or 0)
        eth  = float(mids.get('ETH', 0) or 0)

        if btc == 0:
            return signals

        # Get ETH/BTC ratio — divergence signals alt season or BTC dominance shift
        eth_btc = eth / btc if btc > 0 else 0

        conn = sqlite3.connect(RADAR_DB)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS correlation_snapshots
            (metric TEXT, value REAL, timestamp TEXT)''')

        # Check previous eth_btc ratio
        c.execute('''SELECT value FROM correlation_snapshots
            WHERE metric='eth_btc' ORDER BY timestamp DESC LIMIT 1''')
        row = c.fetchone()

        now_ts = datetime.now(timezone.utc).isoformat()

        if row:
            old_ratio = row[0]
            pct_change = ((eth_btc - old_ratio) / old_ratio) * 100 if old_ratio > 0 else 0

            if abs(pct_change) >= 3:
                direction = 'ALT_SEASON_SIGNAL' if pct_change > 0 else 'BTC_DOMINANCE_RISING'
                save_signal(
                    asset       = 'ETH/BTC',
                    signal_type = 'correlation_shift',
                    strength    = min(10, int(abs(pct_change) * 1.5)),
                    direction   = direction,
                    title       = f'ETH/BTC Ratio {"Rising" if pct_change > 0 else "Falling"} {pct_change:+.1f}% — {"Alt Season Signal" if pct_change > 0 else "BTC Dominance"}',
                    summary     = f'ETH/BTC ratio shifted {pct_change:+.2f}%. {"Alts outperforming BTC suggests capital rotation into altcoins." if pct_change > 0 else "BTC outperforming ETH suggests flight to safety within crypto or BTC dominance cycle."}',
                    data_points = {'eth_btc': eth_btc, 'prev_ratio': old_ratio,
                                   'pct_change': pct_change, 'btc': btc, 'eth': eth},
                    star_take   = f'{"ETH/BTC expansion historically precedes broad alt season. Watch SOL, ARB, and high-beta alts for breakouts." if pct_change > 0 else "BTC dominance rising — alts may bleed further. Consider reducing alt exposure or rotating into BTC."}',
                    category    = 'macro'
                )
                signals.append('ETH/BTC')

        # Save current snapshot
        c.execute('DELETE FROM correlation_snapshots WHERE metric=?', ('eth_btc',))
        c.execute('INSERT INTO correlation_snapshots VALUES (?,?,?)',
                  ('eth_btc', eth_btc, now_ts))
        conn.commit()
        conn.close()

    except Exception as e:
        print(f'[Radar] Correlation scan error: {e}')

    return signals


# ══ MAIN SCAN ORCHESTRATOR ═════════════════════════════════════════

def run_radar_scan(scan_types=None):
    """
    Run all scan modules and return consolidated signals.
    Call this on a schedule (every 4 hours recommended).
    """
    init_radar_db()
    start = time.time()

    all_types = scan_types or [
        'funding', 'price', 'narrative', 'github', 'correlation'
    ]

    results = {
        'scan_time':    datetime.now(timezone.utc).isoformat(),
        'signals_found': 0,
        'by_module':    {}
    }

    print(f'[Radar] ⭐ Starting scan at {results["scan_time"]}')

    if 'funding' in all_types:
        found = scan_hyperliquid_funding()
        results['by_module']['funding'] = len(found)
        print(f'[Radar]   Funding: {len(found)} signals')

    if 'price' in all_types:
        found = scan_price_velocity()
        results['by_module']['price'] = len(found)
        print(f'[Radar]   Price velocity: {len(found)} signals')

    if 'correlation' in all_types:
        found = scan_cross_asset_correlations()
        results['by_module']['correlation'] = len(found)
        print(f'[Radar]   Correlations: {len(found)} signals')

    if 'github' in all_types:
        found = scan_github_activity()
        results['by_module']['github'] = len(found)
        print(f'[Radar]   GitHub: {len(found)} signals')

    if 'narrative' in all_types:
        found = scan_narrative_emergence()
        results['by_module']['narrative'] = len(found)
        print(f'[Radar]   Narratives: {len(found)} signals')

    # Tally total
    results['signals_found'] = sum(results['by_module'].values())
    results['duration_s']    = round(time.time() - start, 2)

    # Log to file
    try:
        log = []
        if os.path.exists(RADAR_LOG):
            log = json.load(open(RADAR_LOG))
        log.insert(0, results)
        with open(RADAR_LOG, 'w') as f:
            json.dump(log[:50], f, indent=2)
    except Exception:
        pass

    # Save to DB
    try:
        conn = sqlite3.connect(RADAR_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO scan_history
            (scan_type, signals_found, duration_s)
            VALUES (?,?,?)''',
            ('full', results['signals_found'], results['duration_s']))
        conn.commit()
        conn.close()
    except Exception:
        pass

    print(f'[Radar] ✅ Scan complete — {results["signals_found"]} signals in {results["duration_s"]}s')
    return results


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

@radar_bp.route('/api/radar/signals')
def radar_signals():
    """Get active radar signals — public endpoint for dashboard."""
    try:
        init_radar_db()
        category    = request.args.get('category', None)
        min_strength = int(request.args.get('min_strength', 5))
        limit        = int(request.args.get('limit', 20))
        signals = get_active_signals(category, min_strength, limit)
        return jsonify({
            'signals':       signals,
            'count':         len(signals),
            'generated_at':  datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@radar_bp.route('/api/radar/scan', methods=['POST'])
def trigger_scan():
    """Trigger a radar scan — owner only."""
    try:
        data  = request.get_json() or {}
        token = data.get('owner_token', '')
        if token != OWNER_TOKEN:
            return jsonify({'error': 'Unauthorized'}), 403

        scan_types = data.get('scan_types', None)
        results    = run_radar_scan(scan_types)
        signals    = get_active_signals(min_strength=1, limit=50)

        return jsonify({
            'success': True,
            'scan':    results,
            'signals': signals
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@radar_bp.route('/api/radar/status')
def radar_status():
    """Get radar status and recent scan history."""
    try:
        init_radar_db()
        conn = sqlite3.connect(RADAR_DB)
        c = conn.cursor()
        c.execute('''SELECT * FROM scan_history
            ORDER BY created_at DESC LIMIT 10''')
        scans = c.fetchall()

        c.execute('''SELECT COUNT(*) FROM signals
            WHERE status="active" AND expires_at > ?''',
            (datetime.now(timezone.utc).isoformat(),))
        active_count = c.fetchone()[0]

        c.execute('''SELECT * FROM narrative_tracking
            ORDER BY mention_count DESC LIMIT 10''')
        narratives = c.fetchall()
        conn.close()

        return jsonify({
            'active_signals':  active_count,
            'recent_scans':    [
                {'id': s[0], 'type': s[1], 'found': s[2],
                 'duration': s[3], 'time': s[4]}
                for s in scans
            ],
            'top_narratives':  [
                {'narrative': n[1], 'mentions': n[4], 'momentum': n[5]}
                for n in narratives
            ],
            'scan_modules':    ['funding', 'price', 'narrative', 'github', 'correlation'],
            'next_scan':       'Every 4 hours via scheduler'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@radar_bp.route('/api/radar/narratives')
def radar_narratives():
    """Get tracked narrative momentum — subscriber endpoint."""
    try:
        init_radar_db()
        conn = sqlite3.connect(RADAR_DB)
        c = conn.cursor()
        c.execute('''SELECT narrative, first_seen, last_seen,
            mention_count, momentum, category
            FROM narrative_tracking
            ORDER BY mention_count DESC LIMIT 20''')
        rows = c.fetchall()
        conn.close()
        return jsonify({
            'narratives': [
                {'narrative':     r[0], 'first_seen': r[1],
                 'last_seen':     r[2], 'mentions': r[3],
                 'momentum':      r[4], 'category': r[5]}
                for r in rows
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
