"""
star_user_profile.py
Star User Profile & Exchange Preference Engine
Personalizes dashboard, chat, signals, and documentation per subscriber.
Designed & Built by Sarah DeFer | ShekinahStar.io

PHILOSOPHY:
  Every Star subscriber is different. A Coinbase institutional trader
  needs different defaults than a Bybit derivatives specialist or a
  Hyperliquid on-chain native. Star learns each user's preferences,
  exchange relationships, trading style, and risk profile — then
  personalizes every interaction accordingly.

  When Star knows you trade on Bybit and Binance, she:
  - Shows your exchanges' prices FIRST in the dashboard
  - Pulls funding rates from YOUR venues in signals
  - References YOUR platform in chat explanations
  - Pre-fills YOUR exchange in execution recommendations
  - Remembers your preferred symbols and risk tolerance

REGISTER in flask_app.py:
  from star_user_profile import profile_bp, init_profile_db, get_user_context
  app.register_blueprint(profile_bp)
  with app.app_context():
      init_profile_db()
"""

import os
import json
import time
import hashlib
import sqlite3
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

BASE       = '/home/ShekinahD'
PROFILE_DB = os.path.join(BASE, 'star_profiles.db')
profile_bp = Blueprint('profile', __name__)

def _env():
    keys = {}
    try:
        with open(os.path.join(BASE, '.env')) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    keys[k.strip()] = v.strip()
    except Exception:
        pass
    return keys

_ENV = _env()

# ── All available exchanges ──────────────────────────────────────
ALL_EXCHANGES = {
    'hyperliquid': {
        'name':     'Hyperliquid',
        'type':     'dex_perp',
        'region':   'onchain',
        'products': ['perp_futures'],
        'kyc':      False,
        'icon':     '🌊',
        'best_for': 'On-chain perpetual futures, Star native venue',
    },
    'binance': {
        'name':     'Binance',
        'type':     'cex',
        'region':   'global',
        'products': ['spot', 'perp_futures', 'options'],
        'kyc':      True,
        'icon':     '🟡',
        'best_for': 'Highest volume, widest selection, spot + perps',
    },
    'coinbase': {
        'name':     'Coinbase',
        'type':     'cex',
        'region':   'us',
        'products': ['spot', 'perp_futures'],
        'kyc':      True,
        'icon':     '🔵',
        'best_for': 'US institutional, regulated, Bitcoin benchmark',
    },
    'bybit': {
        'name':     'Bybit',
        'type':     'cex',
        'region':   'global',
        'products': ['spot', 'perp_futures', 'options', 'copy_trading'],
        'kyc':      True,
        'icon':     '🟠',
        'best_for': 'Derivatives, funding data, long/short ratios',
    },
    'kraken': {
        'name':     'Kraken',
        'type':     'cex',
        'region':   'eu',
        'products': ['spot', 'perp_futures', 'staking'],
        'kyc':      True,
        'icon':     '🐙',
        'best_for': 'European institutional, EUR pairs, BTC custody',
    },
    'okx': {
        'name':     'OKX',
        'type':     'cex',
        'region':   'global',
        'products': ['spot', 'perp_futures', 'options', 'dex'],
        'kyc':      True,
        'icon':     '⚫',
        'best_for': 'Asian market access, deep options market',
    },
    'deribit': {
        'name':     'Deribit',
        'type':     'cex',
        'region':   'global',
        'products': ['options', 'perp_futures'],
        'kyc':      True,
        'icon':     '🎯',
        'best_for': 'Crypto options, volatility trading, BTC/ETH focus',
    },
    'kucoin': {
        'name':     'KuCoin',
        'type':     'cex',
        'region':   'global',
        'products': ['spot', 'perp_futures'],
        'kyc':      True,
        'icon':     '🟢',
        'best_for': 'Altcoin access, retail friendly',
    },
    'mexc': {
        'name':     'MEXC',
        'type':     'cex',
        'region':   'global',
        'products': ['spot', 'perp_futures'],
        'kyc':      False,
        'icon':     '🔷',
        'best_for': 'New token listings, low fees',
    },
    'uniswap': {
        'name':     'Uniswap',
        'type':     'dex_spot',
        'region':   'onchain',
        'products': ['spot'],
        'kyc':      False,
        'icon':     '🦄',
        'best_for': 'Ethereum DEX, long-tail tokens',
    },
}

# ── Trading style profiles ────────────────────────────────────────
TRADING_STYLES = {
    'scalper':     {'name': 'Scalper',     'timeframe': 'seconds-minutes', 'focus': 'spread, speed, funding'},
    'day_trader':  {'name': 'Day Trader',  'timeframe': 'minutes-hours',   'focus': 'momentum, volume, RSI'},
    'swing':       {'name': 'Swing Trader','timeframe': 'days-weeks',      'focus': 'trend, structure, macro'},
    'position':    {'name': 'Position',    'timeframe': 'weeks-months',    'focus': 'fundamentals, cycles, narratives'},
    'arbitrage':   {'name': 'Arbitrageur', 'timeframe': 'seconds-minutes', 'focus': 'cross-exchange divergence'},
    'yield':       {'name': 'Yield Farmer','timeframe': 'ongoing',         'focus': 'funding rates, staking, DeFi'},
    'investor':    {'name': 'Investor',    'timeframe': 'months-years',    'focus': 'portfolio allocation, risk management'},
    'algo':        {'name': 'Algo Trader', 'timeframe': 'variable',        'focus': 'systematic signals, quant models'},
}


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_profile_db():
    conn = sqlite3.connect(PROFILE_DB)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS user_profiles (
        subscriber_id       TEXT PRIMARY KEY,
        email               TEXT UNIQUE,
        tier                TEXT DEFAULT 'observer',
        display_name        TEXT,

        -- Exchange preferences
        primary_exchange    TEXT DEFAULT 'hyperliquid',
        exchanges_used      TEXT DEFAULT '["hyperliquid"]',  -- JSON array
        exchange_api_keys   TEXT DEFAULT '{}',               -- JSON {exchange: {key_hash, has_key}}

        -- Trading preferences
        trading_style       TEXT DEFAULT 'day_trader',
        preferred_symbols   TEXT DEFAULT '["BTC","ETH","SOL"]',  -- JSON array
        default_leverage    INTEGER DEFAULT 2,
        default_risk_pct    REAL DEFAULT 0.02,
        quote_currency      TEXT DEFAULT 'USDT',
        preferred_products  TEXT DEFAULT '["perp_futures"]',  -- JSON array

        -- Display preferences
        timezone            TEXT DEFAULT 'UTC',
        currency_display    TEXT DEFAULT 'USD',
        chart_theme         TEXT DEFAULT 'dark',
        compact_mode        INTEGER DEFAULT 0,
        show_usd_values     INTEGER DEFAULT 1,

        -- Dashboard layout
        dashboard_layout    TEXT DEFAULT '{}',  -- JSON widget positions
        pinned_symbols      TEXT DEFAULT '["BTC","ETH"]',

        -- Star chat preferences
        chat_verbosity      TEXT DEFAULT 'balanced',  -- brief, balanced, detailed
        explain_signals     INTEGER DEFAULT 1,
        show_confidence     INTEGER DEFAULT 1,
        language            TEXT DEFAULT 'en',

        -- Risk profile
        risk_tolerance      TEXT DEFAULT 'moderate',  -- conservative, moderate, aggressive
        max_drawdown_pct    REAL DEFAULT 0.10,
        preferred_stop_pct  REAL DEFAULT 0.02,

        -- Notification preferences
        notify_signals      INTEGER DEFAULT 1,
        notify_trades       INTEGER DEFAULT 1,
        notify_funding      INTEGER DEFAULT 0,
        notify_threshold    REAL DEFAULT 0.01,  -- funding rate threshold for alert

        -- Metadata
        onboarding_done     INTEGER DEFAULT 0,
        last_active         TIMESTAMP,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Exchange connection status per user
    c.execute('''CREATE TABLE IF NOT EXISTS user_exchanges (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        subscriber_id   TEXT,
        exchange        TEXT,
        connected       INTEGER DEFAULT 0,
        has_api_key     INTEGER DEFAULT 0,
        api_key_hash    TEXT,
        wallet_address  TEXT,
        account_type    TEXT,   -- spot, futures, unified
        is_primary      INTEGER DEFAULT 0,
        is_trading_venue INTEGER DEFAULT 0,  -- where Star executes
        notes           TEXT,
        connected_at    TIMESTAMP,
        UNIQUE(subscriber_id, exchange)
    )''')

    # Per-user signal preferences
    c.execute('''CREATE TABLE IF NOT EXISTS user_signal_prefs (
        subscriber_id   TEXT PRIMARY KEY,
        enabled_signals TEXT DEFAULT '["momentum","rsi","macd","funding","volatility"]',
        signal_weights  TEXT DEFAULT '{}',   -- custom weights per signal
        min_confidence  REAL DEFAULT 0.60,
        exchanges_for_signals TEXT DEFAULT '[]',  -- which exchanges to pull for signals
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print('✅ Star User Profile Engine initialized')


# ══ CORE PROFILE FUNCTIONS ══════════════════════════════════════════

def get_profile(subscriber_id: str) -> dict:
    """Get full user profile."""
    try:
        conn = sqlite3.connect(PROFILE_DB)
        c = conn.cursor()
        c.execute('SELECT * FROM user_profiles WHERE subscriber_id=?', (subscriber_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return {}
        cols = [d[0] for d in c.description]
        profile = dict(zip(cols, row))
        conn.close()

        # Parse JSON fields
        for field in ['exchanges_used', 'preferred_symbols', 'pinned_symbols',
                      'preferred_products', 'dashboard_layout', 'exchange_api_keys']:
            if profile.get(field):
                try:
                    profile[field] = json.loads(profile[field])
                except Exception:
                    pass

        return profile
    except Exception:
        return {}


def create_or_update_profile(subscriber_id: str, email: str,
                              tier: str = 'observer', data: dict = None) -> dict:
    """Create or update a user profile."""
    data = data or {}
    now  = datetime.now(timezone.utc).isoformat()

    # JSON-encode list/dict fields
    def enc(val, default):
        if isinstance(val, (list, dict)):
            return json.dumps(val)
        return val or default

    try:
        conn = sqlite3.connect(PROFILE_DB)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO user_profiles
            (subscriber_id, email, tier, created_at, updated_at)
            VALUES (?,?,?,?,?)''',
            (subscriber_id, email, tier, now, now))

        # Update fields if provided
        updates = {'updated_at': now}
        allowed = [
            'display_name', 'primary_exchange', 'exchanges_used',
            'trading_style', 'preferred_symbols', 'default_leverage',
            'default_risk_pct', 'quote_currency', 'preferred_products',
            'timezone', 'currency_display', 'chart_theme', 'compact_mode',
            'pinned_symbols', 'chat_verbosity', 'explain_signals',
            'show_confidence', 'language', 'risk_tolerance',
            'max_drawdown_pct', 'preferred_stop_pct', 'notify_signals',
            'notify_trades', 'notify_funding', 'notify_threshold',
            'onboarding_done', 'tier',
        ]
        for field in allowed:
            if field in data:
                val = data[field]
                if isinstance(val, (list, dict)):
                    val = json.dumps(val)
                updates[field] = val

        if len(updates) > 1:
            set_clause = ', '.join(f'{k}=?' for k in updates)
            c.execute(f'UPDATE user_profiles SET {set_clause} WHERE subscriber_id=?',
                      list(updates.values()) + [subscriber_id])

        conn.commit()
        conn.close()
        return {'success': True, 'subscriber_id': subscriber_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def update_exchange_preferences(subscriber_id: str, exchanges: list,
                                 primary: str = None) -> dict:
    """Update which exchanges a user uses."""
    try:
        conn = sqlite3.connect(PROFILE_DB)
        c = conn.cursor()

        # Update profile
        primary = primary or (exchanges[0] if exchanges else 'hyperliquid')
        c.execute('''UPDATE user_profiles SET
            exchanges_used=?, primary_exchange=?, updated_at=?
            WHERE subscriber_id=?''',
            (json.dumps(exchanges), primary,
             datetime.now(timezone.utc).isoformat(), subscriber_id))

        # Update exchange connection records
        for ex in exchanges:
            is_primary = 1 if ex == primary else 0
            c.execute('''INSERT OR REPLACE INTO user_exchanges
                (subscriber_id, exchange, connected, is_primary, connected_at)
                VALUES (?,?,1,?,?)''',
                (subscriber_id, ex, is_primary,
                 datetime.now(timezone.utc).isoformat()))

        conn.commit()
        conn.close()
        return {'success': True, 'exchanges': exchanges, 'primary': primary}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_user_exchanges(subscriber_id: str) -> list:
    """Get list of exchanges a user is connected to."""
    try:
        conn = sqlite3.connect(PROFILE_DB)
        c = conn.cursor()
        c.execute('''SELECT exchange, connected, is_primary, is_trading_venue,
            has_api_key, account_type FROM user_exchanges
            WHERE subscriber_id=? ORDER BY is_primary DESC, connected DESC''',
            (subscriber_id,))
        rows = c.fetchall()
        conn.close()
        return [{'exchange': r[0], 'connected': bool(r[1]),
                 'is_primary': bool(r[2]), 'is_trading_venue': bool(r[3]),
                 'has_api_key': bool(r[4]), 'account_type': r[5]} for r in rows]
    except Exception:
        return []


def get_user_context(subscriber_id: str) -> str:
    """
    Build a personalized context string for Star's chat system prompt.
    Star uses this to personalize every response to this specific user.
    """
    profile = get_profile(subscriber_id)
    if not profile:
        return ''

    exchanges = profile.get('exchanges_used', ['hyperliquid'])
    if isinstance(exchanges, str):
        try:
            exchanges = json.loads(exchanges)
        except Exception:
            exchanges = ['hyperliquid']

    primary    = profile.get('primary_exchange', 'hyperliquid')
    style      = profile.get('trading_style', 'day_trader')
    symbols    = profile.get('preferred_symbols', ['BTC', 'ETH'])
    if isinstance(symbols, str):
        try:
            symbols = json.loads(symbols)
        except Exception:
            symbols = ['BTC', 'ETH']

    risk       = profile.get('risk_tolerance', 'moderate')
    verbosity  = profile.get('chat_verbosity', 'balanced')
    leverage   = profile.get('default_leverage', 2)
    tier       = profile.get('tier', 'observer')
    name       = profile.get('display_name', '')

    exchange_names = [ALL_EXCHANGES.get(ex, {}).get('name', ex.title()) for ex in exchanges]

    lines = [
        f"USER PROFILE — Personalize all responses for this subscriber:",
        f"Name: {name or 'Subscriber'} | Tier: {tier.upper()}",
        f"Primary exchange: {ALL_EXCHANGES.get(primary, {}).get('name', primary.title())}",
        f"All exchanges used: {', '.join(exchange_names)}",
        f"Trading style: {TRADING_STYLES.get(style, {}).get('name', style)}",
        f"Preferred symbols: {', '.join(symbols) if symbols else 'BTC, ETH'}",
        f"Risk tolerance: {risk} | Default leverage: {leverage}x",
        f"Response verbosity: {verbosity}",
        "",
        f"PERSONALIZATION RULES:",
        f"- When discussing prices, show {ALL_EXCHANGES.get(primary, {}).get('name', primary)} price FIRST",
        f"- When explaining signals, reference {' and '.join(exchange_names)} specifically",
        f"- When recommending execution, default to {ALL_EXCHANGES.get(primary, {}).get('name', primary)}",
        f"- Match {verbosity} verbosity — {'be concise' if verbosity == 'brief' else 'be thorough' if verbosity == 'detailed' else 'balance detail and brevity'}",
        f"- This user trades {TRADING_STYLES.get(style, {}).get('timeframe', 'variable')} timeframes",
    ]

    if len(exchanges) > 1:
        lines.append(f"- Highlight cross-exchange divergence between {' and '.join(exchange_names)} when relevant")

    return '\n'.join(lines)


def get_personalized_signal_config(subscriber_id: str) -> dict:
    """
    Get signal configuration personalized for this user's exchanges and style.
    Used by star_quant.py to weight signals appropriately.
    """
    profile = get_profile(subscriber_id)
    if not profile:
        return {'exchanges': ['hyperliquid'], 'style': 'day_trader'}

    exchanges = profile.get('exchanges_used', ['hyperliquid'])
    if isinstance(exchanges, str):
        try:
            exchanges = json.loads(exchanges)
        except Exception:
            exchanges = ['hyperliquid']

    style = profile.get('trading_style', 'day_trader')

    # Adjust signal weights based on trading style
    weights = {
        'scalper':    {'momentum': 1.5, 'rsi': 0.8, 'macd': 0.5, 'funding': 1.8, 'volatility': 1.5},
        'day_trader': {'momentum': 1.2, 'rsi': 1.2, 'macd': 1.0, 'funding': 1.0, 'volatility': 1.0},
        'swing':      {'momentum': 1.0, 'rsi': 1.0, 'macd': 1.5, 'funding': 0.8, 'volatility': 1.2},
        'position':   {'momentum': 0.8, 'rsi': 0.8, 'macd': 1.2, 'funding': 0.5, 'volatility': 0.8},
        'arbitrage':  {'momentum': 0.5, 'rsi': 0.5, 'macd': 0.5, 'funding': 2.0, 'volatility': 1.5},
        'yield':      {'momentum': 0.3, 'rsi': 0.3, 'macd': 0.3, 'funding': 3.0, 'volatility': 0.5},
    }

    return {
        'exchanges':      exchanges,
        'primary':        profile.get('primary_exchange', 'hyperliquid'),
        'style':          style,
        'signal_weights': weights.get(style, weights['day_trader']),
        'symbols':        profile.get('preferred_symbols', ['BTC', 'ETH']),
        'risk_pct':       profile.get('default_risk_pct', 0.02),
        'leverage':       profile.get('default_leverage', 2),
    }


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

@profile_bp.route('/api/profile/<subscriber_id>', methods=['GET'])
def get_profile_route(subscriber_id):
    """Get user profile."""
    profile = get_profile(subscriber_id)
    if not profile:
        return jsonify({'found': False, 'subscriber_id': subscriber_id})
    # Don't expose sensitive fields
    safe = {k: v for k, v in profile.items()
            if k not in ('exchange_api_keys',)}
    return jsonify({'found': True, **safe})


@profile_bp.route('/api/profile/<subscriber_id>', methods=['POST'])
def update_profile_route(subscriber_id):
    """Create or update user profile."""
    data  = request.get_json() or {}
    email = data.get('email', '')
    tier  = data.get('tier', 'observer')
    result = create_or_update_profile(subscriber_id, email, tier, data)
    return jsonify(result)


@profile_bp.route('/api/profile/<subscriber_id>/exchanges', methods=['POST'])
def update_exchanges_route(subscriber_id):
    """Update user's exchange preferences."""
    data      = request.get_json() or {}
    exchanges = data.get('exchanges', ['hyperliquid'])
    primary   = data.get('primary', exchanges[0] if exchanges else 'hyperliquid')

    # Validate exchanges
    valid = [ex for ex in exchanges if ex in ALL_EXCHANGES]
    if not valid:
        return jsonify({'error': 'No valid exchanges provided'}), 400

    result = update_exchange_preferences(subscriber_id, valid, primary)
    return jsonify(result)


@profile_bp.route('/api/profile/<subscriber_id>/exchanges', methods=['GET'])
def get_exchanges_route(subscriber_id):
    """Get user's exchange connections."""
    exchanges = get_user_exchanges(subscriber_id)
    profile   = get_profile(subscriber_id)
    primary   = profile.get('primary_exchange', 'hyperliquid')

    # Enrich with exchange metadata
    enriched = []
    for ex in exchanges:
        meta = ALL_EXCHANGES.get(ex['exchange'], {})
        enriched.append({**ex, **meta})

    return jsonify({
        'subscriber_id': subscriber_id,
        'primary':       primary,
        'exchanges':     enriched,
        'available':     ALL_EXCHANGES,
    })


@profile_bp.route('/api/profile/<subscriber_id>/context')
def user_context_route(subscriber_id):
    """Get Star's personalized system context for this user."""
    context = get_user_context(subscriber_id)
    config  = get_personalized_signal_config(subscriber_id)
    return jsonify({'context': context, 'signal_config': config})


@profile_bp.route('/api/profile/<subscriber_id>/signals', methods=['POST'])
def update_signal_prefs(subscriber_id):
    """Update signal preferences for this user."""
    data = request.get_json() or {}
    try:
        conn = sqlite3.connect(PROFILE_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO user_signal_prefs
            (subscriber_id, enabled_signals, signal_weights,
             min_confidence, exchanges_for_signals, updated_at)
            VALUES (?,?,?,?,?,?)''',
            (subscriber_id,
             json.dumps(data.get('enabled_signals', [])),
             json.dumps(data.get('signal_weights', {})),
             data.get('min_confidence', 0.60),
             json.dumps(data.get('exchanges_for_signals', [])),
             datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@profile_bp.route('/api/profile/onboarding/<subscriber_id>', methods=['POST'])
def complete_onboarding(subscriber_id):
    """Mark onboarding complete after user sets preferences."""
    data = request.get_json() or {}

    # Save all onboarding data at once
    result = create_or_update_profile(
        subscriber_id,
        data.get('email', ''),
        data.get('tier', 'observer'),
        {**data, 'onboarding_done': 1}
    )

    # Save exchange preferences
    exchanges = data.get('exchanges_used', ['hyperliquid'])
    primary   = data.get('primary_exchange', exchanges[0] if exchanges else 'hyperliquid')
    update_exchange_preferences(subscriber_id, exchanges, primary)

    return jsonify({**result, 'onboarding_complete': True})


@profile_bp.route('/api/exchanges/available')
def available_exchanges():
    """List all supported exchanges with metadata."""
    return jsonify({
        'exchanges': ALL_EXCHANGES,
        'count':     len(ALL_EXCHANGES),
        'by_type': {
            'cex':      [k for k, v in ALL_EXCHANGES.items() if v['type'] == 'cex'],
            'dex_perp': [k for k, v in ALL_EXCHANGES.items() if v['type'] == 'dex_perp'],
            'dex_spot': [k for k, v in ALL_EXCHANGES.items() if v['type'] == 'dex_spot'],
        },
    })


@profile_bp.route('/api/profile/status')
def profile_status():
    try:
        conn = sqlite3.connect(PROFILE_DB)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM user_profiles')
        total = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM user_exchanges')
        connections = c.fetchone()[0]
        conn.close()
        return jsonify({
            'status':          'active',
            'module':          'Star User Profile Engine v1.0',
            'total_profiles':  total,
            'exchange_connections': connections,
            'supported_exchanges': len(ALL_EXCHANGES),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
