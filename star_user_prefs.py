"""
star_user_prefs.py
Star User Exchange Preferences Engine
Per-user exchange profile, personalized dashboard, chat context injection
Designed & Built by Sarah DeFer | ShekinahStar.io

PHILOSOPHY:
  Every user on Star lives in a different exchange world.
  A Binance trader and a Coinbase institutional client need
  completely different dashboards, signals, and chat context.
  Star learns each user's exchange universe and personalizes
  every interaction — dashboard, signals, chat, documentation —
  around exactly the venues they use.

  When a user asks "what is BTC doing?" Star answers with data
  from THEIR exchanges, not a generic market view.

WHAT THIS STORES PER USER:
  - Which exchanges they actively trade on
  - Which exchange is their primary venue
  - Their wallet addresses per exchange
  - Their preferred pairs/symbols
  - Their risk tolerance and position sizing
  - Their trading style (manual, mirror, signals-only)
  - Their notification preferences

REGISTER in flask_app.py:
  from star_user_prefs import prefs_bp, init_prefs_db, get_user_exchange_context
  app.register_blueprint(prefs_bp)
  with app.app_context():
      init_prefs_db()
"""

import os
import json
import sqlite3
import hashlib
import hmac
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

BASE     = '/home/ShekinahD'
PREFS_DB = os.path.join(BASE, 'star_prefs.db')
prefs_bp = Blueprint('prefs', __name__)

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

# ── Exchange metadata ────────────────────────────────────────────
EXCHANGE_META = {
    'binance': {
        'name':     'Binance',
        'icon':     '🟡',
        'type':     'CEX',
        'region':   'Global',
        'strength': 'Largest volume, spot + futures',
        'pairs':    'USDT pairs',
        'url':      'https://binance.com',
    },
    'coinbase': {
        'name':     'Coinbase',
        'icon':     '🔵',
        'type':     'CEX',
        'region':   'US/EU',
        'strength': 'Institutional benchmark, USD pairs',
        'pairs':    'USD pairs',
        'url':      'https://coinbase.com',
    },
    'bybit': {
        'name':     'Bybit',
        'icon':     '🟠',
        'type':     'CEX',
        'region':   'Global',
        'strength': 'Derivatives leader, funding authority',
        'pairs':    'USDT perpetuals',
        'url':      'https://bybit.com',
    },
    'kraken': {
        'name':     'Kraken',
        'icon':     '🟣',
        'type':     'CEX',
        'region':   'EU/US',
        'strength': 'European institutional, EUR pairs',
        'pairs':    'USD/EUR pairs',
        'url':      'https://kraken.com',
    },
    'hyperliquid': {
        'name':     'Hyperliquid',
        'icon':     '⭐',
        'type':     'DEX',
        'region':   'On-chain',
        'strength': "Star's native venue, on-chain transparency",
        'pairs':    'USDC perpetuals',
        'url':      'https://hyperliquid.xyz',
    },
    'okx': {
        'name':     'OKX',
        'icon':     '⚫',
        'type':     'CEX',
        'region':   'Global',
        'strength': 'Asian markets, options',
        'pairs':    'USDT/BTC pairs',
        'url':      'https://okx.com',
    },
    'kucoin': {
        'name':     'KuCoin',
        'icon':     '🟢',
        'type':     'CEX',
        'region':   'Global',
        'strength': 'Altcoin selection, smaller caps',
        'pairs':    'USDT/BTC pairs',
        'url':      'https://kucoin.com',
    },
    'dydx': {
        'name':     'dYdX',
        'icon':     '🔷',
        'type':     'DEX',
        'region':   'On-chain',
        'strength': 'Decentralized perpetuals',
        'pairs':    'USDC perpetuals',
        'url':      'https://dydx.exchange',
    },
}

# ── Trading style profiles ───────────────────────────────────────
TRADING_STYLES = {
    'signals_only':  'I review Star\'s signals and execute trades manually',
    'mirror':        'Star mirrors her trades on my connected wallet automatically',
    'manual':        'I trade independently and use Star for intelligence only',
    'hybrid':        'I mix manual trading with some automated mirror trading',
    'fund_manager':  'I manage multiple accounts/wallets using Star',
}


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_prefs_db():
    conn = sqlite3.connect(PREFS_DB)
    c = conn.cursor()

    # Master user preferences
    c.execute('''CREATE TABLE IF NOT EXISTS user_preferences (
        subscriber_id   TEXT PRIMARY KEY,
        email           TEXT UNIQUE,
        tier            TEXT DEFAULT 'observer',
        display_name    TEXT,

        -- Exchange preferences
        exchanges_used  TEXT DEFAULT '[]',      -- JSON array of exchange names
        primary_exchange TEXT DEFAULT 'hyperliquid',
        exchange_wallets TEXT DEFAULT '{}',     -- JSON {exchange: wallet_address}

        -- Trading preferences
        trading_style   TEXT DEFAULT 'signals_only',
        preferred_pairs TEXT DEFAULT '["BTC","ETH","SOL"]',  -- JSON array
        risk_tolerance  TEXT DEFAULT 'moderate',  -- conservative, moderate, aggressive
        position_size_pct REAL DEFAULT 2.0,       -- % of portfolio per trade

        -- Display preferences
        currency        TEXT DEFAULT 'USD',
        timezone        TEXT DEFAULT 'UTC',
        theme           TEXT DEFAULT 'dark',
        chart_style     TEXT DEFAULT 'candles',

        -- Notification preferences
        signal_alerts   INTEGER DEFAULT 1,
        price_alerts    INTEGER DEFAULT 1,
        email_frequency TEXT DEFAULT 'daily',

        -- Context for Star's chat
        exchange_context TEXT DEFAULT '',       -- injected into Star's system prompt

        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Per-exchange configuration per user
    c.execute('''CREATE TABLE IF NOT EXISTS user_exchange_config (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        subscriber_id   TEXT,
        exchange        TEXT,
        wallet_address  TEXT,
        account_label   TEXT,
        is_primary      INTEGER DEFAULT 0,
        api_key_hash    TEXT,    -- SHA-256 hash only, never plaintext
        notes           TEXT,
        active          INTEGER DEFAULT 1,
        added_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # User's custom watchlist
    c.execute('''CREATE TABLE IF NOT EXISTS user_watchlists (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        subscriber_id   TEXT,
        symbol          TEXT,
        exchange        TEXT,
        alert_above     REAL,
        alert_below     REAL,
        notes           TEXT,
        added_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print('✅ Star User Preferences Engine initialized')


# ══ PREFERENCE MANAGEMENT ══════════════════════════════════════════

def get_user_prefs(subscriber_id: str) -> dict:
    """Get all preferences for a user."""
    try:
        conn = sqlite3.connect(PREFS_DB)
        c = conn.cursor()
        c.execute('SELECT * FROM user_preferences WHERE subscriber_id=?', (subscriber_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            return _default_prefs(subscriber_id)

        cols = ['subscriber_id','email','tier','display_name',
                'exchanges_used','primary_exchange','exchange_wallets',
                'trading_style','preferred_pairs','risk_tolerance','position_size_pct',
                'currency','timezone','theme','chart_style',
                'signal_alerts','price_alerts','email_frequency',
                'exchange_context','created_at','updated_at']
        prefs = dict(zip(cols, row))

        # Parse JSON fields
        for field in ['exchanges_used','exchange_wallets','preferred_pairs']:
            try:
                prefs[field] = json.loads(prefs[field] or '[]')
            except Exception:
                prefs[field] = [] if field != 'exchange_wallets' else {}

        return prefs
    except Exception as e:
        return _default_prefs(subscriber_id)


def _default_prefs(subscriber_id: str) -> dict:
    return {
        'subscriber_id':    subscriber_id,
        'tier':             'observer',
        'exchanges_used':   [],
        'primary_exchange': 'hyperliquid',
        'exchange_wallets': {},
        'trading_style':    'signals_only',
        'preferred_pairs':  ['BTC', 'ETH', 'SOL'],
        'risk_tolerance':   'moderate',
        'position_size_pct': 2.0,
        'currency':         'USD',
        'timezone':         'UTC',
        'signal_alerts':    True,
        'price_alerts':     True,
        'email_frequency':  'daily',
    }


def save_user_prefs(subscriber_id: str, updates: dict) -> dict:
    """Save/update user preferences."""
    # Serialize JSON fields
    for field in ['exchanges_used', 'preferred_pairs']:
        if field in updates and isinstance(updates[field], list):
            updates[field] = json.dumps(updates[field])

    if 'exchange_wallets' in updates and isinstance(updates['exchange_wallets'], dict):
        updates['exchange_wallets'] = json.dumps(updates['exchange_wallets'])

    # Build exchange context for Star's chat
    if 'exchanges_used' in updates:
        exchanges = json.loads(updates['exchanges_used']) if isinstance(updates['exchanges_used'], str) else updates.get('exchanges_used', [])
        updates['exchange_context'] = build_exchange_context(
            subscriber_id,
            exchanges,
            updates.get('primary_exchange', 'hyperliquid'),
            updates.get('trading_style', 'signals_only'),
            json.loads(updates.get('preferred_pairs', '["BTC","ETH","SOL"]')) if isinstance(updates.get('preferred_pairs'), str) else updates.get('preferred_pairs', ['BTC','ETH','SOL'])
        )

    updates['updated_at'] = datetime.now(timezone.utc).isoformat()

    try:
        conn = sqlite3.connect(PREFS_DB)
        c = conn.cursor()

        # Check if exists
        c.execute('SELECT subscriber_id FROM user_preferences WHERE subscriber_id=?', (subscriber_id,))
        exists = c.fetchone()

        if exists:
            set_clause = ', '.join(f'{k}=?' for k in updates.keys())
            c.execute(f'UPDATE user_preferences SET {set_clause} WHERE subscriber_id=?',
                     list(updates.values()) + [subscriber_id])
        else:
            updates['subscriber_id'] = subscriber_id
            updates['created_at'] = datetime.now(timezone.utc).isoformat()
            cols   = ', '.join(updates.keys())
            places = ', '.join('?' * len(updates))
            c.execute(f'INSERT INTO user_preferences ({cols}) VALUES ({places})',
                     list(updates.values()))

        conn.commit()
        conn.close()
        return {'success': True, 'subscriber_id': subscriber_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def add_exchange_config(subscriber_id: str, exchange: str, wallet: str = '',
                        label: str = '', is_primary: bool = False) -> dict:
    """Add or update a user's exchange configuration."""
    try:
        conn = sqlite3.connect(PREFS_DB)
        c = conn.cursor()

        # If setting as primary, clear other primaries
        if is_primary:
            c.execute('UPDATE user_exchange_config SET is_primary=0 WHERE subscriber_id=?',
                     (subscriber_id,))

        c.execute('''INSERT OR REPLACE INTO user_exchange_config
            (subscriber_id, exchange, wallet_address, account_label, is_primary)
            VALUES (?,?,?,?,?)''',
            (subscriber_id, exchange, wallet, label, int(is_primary)))

        # Update master prefs
        prefs = get_user_prefs(subscriber_id)
        exchanges = prefs.get('exchanges_used', [])
        if exchange not in exchanges:
            exchanges.append(exchange)

        wallets = prefs.get('exchange_wallets', {})
        if wallet:
            wallets[exchange] = wallet

        save_user_prefs(subscriber_id, {
            'exchanges_used':   exchanges,
            'primary_exchange': exchange if is_primary else prefs.get('primary_exchange', 'hyperliquid'),
            'exchange_wallets': wallets,
        })

        conn.commit()
        conn.close()
        return {'success': True, 'exchange': exchange, 'is_primary': is_primary}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ══ CONTEXT GENERATION ═════════════════════════════════════════════

def build_exchange_context(subscriber_id: str, exchanges: list,
                           primary: str, style: str, pairs: list) -> str:
    """
    Build the exchange context string injected into Star's chat system prompt.
    This makes Star aware of exactly which exchanges this user lives on
    so she can personalize every response.
    """
    if not exchanges:
        return ''

    ex_details = []
    for ex in exchanges:
        meta = EXCHANGE_META.get(ex, {})
        mark = '★ PRIMARY' if ex == primary else ''
        ex_details.append(
            f"  • {meta.get('icon','◆')} {meta.get('name', ex.title())} ({meta.get('type','CEX')}) {mark} — {meta.get('strength','')}"
        )

    style_desc = TRADING_STYLES.get(style, style)
    pairs_str  = ', '.join(pairs[:6]) if pairs else 'BTC, ETH, SOL'
    primary_meta = EXCHANGE_META.get(primary, {})

    lines = [
        "USER EXCHANGE PROFILE:",
        f"  Primary exchange: {primary_meta.get('icon','⭐')} {primary_meta.get('name', primary.title())}",
        f"  Active exchanges:",
    ] + ex_details + [
        f"  Trading style: {style_desc}",
        f"  Preferred pairs: {pairs_str}",
        "",
        "When answering this user's market questions, Star should:",
        f"  - Lead with {primary_meta.get('name', primary.title())} data first",
        f"  - Reference cross-exchange signals from: {', '.join(ex.title() for ex in exchanges)}",
        f"  - Frame signals in terms of their preferred pairs: {pairs_str}",
        f"  - Match their trading style: {style}",
        "  - Always use /api/exchanges/* endpoints to pull their exchange data",
    ]

    return '\n'.join(lines)


def get_user_exchange_context(subscriber_id: str) -> str:
    """
    Get the exchange context string for injection into Star's chat system prompt.
    Call this in the chat proxy before building the system prompt.
    """
    prefs = get_user_prefs(subscriber_id)
    ctx   = prefs.get('exchange_context', '')
    if not ctx and prefs.get('exchanges_used'):
        ctx = build_exchange_context(
            subscriber_id,
            prefs['exchanges_used'],
            prefs.get('primary_exchange', 'hyperliquid'),
            prefs.get('trading_style', 'signals_only'),
            prefs.get('preferred_pairs', ['BTC', 'ETH', 'SOL']),
        )
    return ctx


# ══ PERSONALIZED MARKET DATA ════════════════════════════════════════

def get_personalized_prices(subscriber_id: str) -> dict:
    """
    Get prices from the user's specific exchanges for their preferred pairs.
    This is what powers their personalized dashboard.
    """
    prefs    = get_user_prefs(subscriber_id)
    exchanges = prefs.get('exchanges_used', ['hyperliquid'])
    pairs    = prefs.get('preferred_pairs', ['BTC', 'ETH', 'SOL'])
    primary  = prefs.get('primary_exchange', 'hyperliquid')

    try:
        from star_exchanges import (
            BinanceAdapter, CoinbaseAdapter, BybitAdapter,
            KrakenAdapter, HyperliquidAdapter
        )
        adapters = {
            'binance':    BinanceAdapter(),
            'coinbase':   CoinbaseAdapter(),
            'bybit':      BybitAdapter(),
            'kraken':     KrakenAdapter(),
            'hyperliquid': HyperliquidAdapter(),
        }

        results = {}
        for pair in pairs[:8]:
            results[pair] = {}
            for ex in exchanges:
                adapter = adapters.get(ex)
                if adapter:
                    try:
                        data = adapter.get_price(pair)
                        if 'error' not in data:
                            results[pair][ex] = data
                    except Exception:
                        pass

        # Primary exchange data highlighted
        primary_data = {}
        for pair in pairs[:8]:
            if primary in results.get(pair, {}):
                primary_data[pair] = results[pair][primary]

        return {
            'subscriber_id': subscriber_id,
            'primary_exchange': primary,
            'exchanges': exchanges,
            'primary_prices': primary_data,
            'all_prices': results,
            'pairs': pairs,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    except ImportError:
        return {
            'subscriber_id': subscriber_id,
            'error': 'Exchange module not loaded',
            'exchanges': exchanges,
        }


def get_user_watchlist(subscriber_id: str) -> list:
    """Get user's custom watchlist."""
    try:
        conn = sqlite3.connect(PREFS_DB)
        c = conn.cursor()
        c.execute('''SELECT symbol, exchange, alert_above, alert_below, notes
            FROM user_watchlists WHERE subscriber_id=? ORDER BY added_at DESC''',
            (subscriber_id,))
        rows = c.fetchall()
        conn.close()
        return [{'symbol': r[0], 'exchange': r[1], 'alert_above': r[2],
                 'alert_below': r[3], 'notes': r[4]} for r in rows]
    except Exception:
        return []


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

@prefs_bp.route('/api/prefs/<subscriber_id>', methods=['GET'])
def get_prefs(subscriber_id):
    """Get user preferences."""
    prefs = get_user_prefs(subscriber_id)
    return jsonify(prefs)


@prefs_bp.route('/api/prefs/<subscriber_id>', methods=['POST'])
def save_prefs(subscriber_id):
    """Save/update user preferences."""
    data   = request.get_json() or {}
    result = save_user_prefs(subscriber_id, data)
    return jsonify(result)


@prefs_bp.route('/api/prefs/<subscriber_id>/exchanges', methods=['POST'])
def add_exchange(subscriber_id):
    """Add an exchange to user's profile."""
    data    = request.get_json() or {}
    exchange = data.get('exchange', '')
    if not exchange or exchange not in EXCHANGE_META:
        return jsonify({'error': f'Unknown exchange: {exchange}. Valid: {list(EXCHANGE_META.keys())}'}), 400

    result = add_exchange_config(
        subscriber_id,
        exchange,
        wallet     = data.get('wallet', ''),
        label      = data.get('label', ''),
        is_primary = bool(data.get('is_primary', False)),
    )
    return jsonify(result)


@prefs_bp.route('/api/prefs/<subscriber_id>/exchanges/<exchange>', methods=['DELETE'])
def remove_exchange(subscriber_id, exchange):
    """Remove an exchange from user's profile."""
    prefs     = get_user_prefs(subscriber_id)
    exchanges = prefs.get('exchanges_used', [])
    if exchange in exchanges:
        exchanges.remove(exchange)
    wallets   = prefs.get('exchange_wallets', {})
    wallets.pop(exchange, None)

    result = save_user_prefs(subscriber_id, {
        'exchanges_used':   exchanges,
        'exchange_wallets': wallets,
    })
    return jsonify(result)


@prefs_bp.route('/api/prefs/<subscriber_id>/prices')
def personalized_prices(subscriber_id):
    """Get prices from user's specific exchanges for their preferred pairs."""
    data = get_personalized_prices(subscriber_id)
    return jsonify(data)


@prefs_bp.route('/api/prefs/<subscriber_id>/watchlist', methods=['GET'])
def get_watchlist(subscriber_id):
    """Get user's watchlist."""
    return jsonify({'watchlist': get_user_watchlist(subscriber_id)})


@prefs_bp.route('/api/prefs/<subscriber_id>/watchlist', methods=['POST'])
def add_to_watchlist(subscriber_id):
    """Add symbol to watchlist."""
    data   = request.get_json() or {}
    symbol = data.get('symbol', '').upper()
    if not symbol:
        return jsonify({'error': 'symbol required'}), 400
    try:
        conn = sqlite3.connect(PREFS_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO user_watchlists
            (subscriber_id, symbol, exchange, alert_above, alert_below, notes)
            VALUES (?,?,?,?,?,?)''',
            (subscriber_id, symbol,
             data.get('exchange', 'hyperliquid'),
             data.get('alert_above'),
             data.get('alert_below'),
             data.get('notes', '')))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'symbol': symbol})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@prefs_bp.route('/api/prefs/<subscriber_id>/context')
def user_context(subscriber_id):
    """Get Star's exchange context string for this user."""
    ctx = get_user_exchange_context(subscriber_id)
    return jsonify({'subscriber_id': subscriber_id, 'context': ctx})


@prefs_bp.route('/api/prefs/exchanges/list')
def list_exchanges():
    """List all supported exchanges with metadata."""
    return jsonify({'exchanges': EXCHANGE_META, 'trading_styles': TRADING_STYLES})


@prefs_bp.route('/api/prefs/status')
def prefs_status():
    try:
        conn = sqlite3.connect(PREFS_DB)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM user_preferences')
        total = c.fetchone()[0]
        c.execute('SELECT primary_exchange, COUNT(*) FROM user_preferences GROUP BY primary_exchange ORDER BY COUNT(*) DESC')
        by_exchange = dict(c.fetchall())
        conn.close()
        return jsonify({
            'status':        'active',
            'module':        'Star User Preferences v1.0',
            'total_users':   total,
            'by_primary_exchange': by_exchange,
            'supported_exchanges': list(EXCHANGE_META.keys()),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
