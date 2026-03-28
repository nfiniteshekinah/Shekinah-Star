"""
star_exchanges.py
Star Multi-Exchange Connectivity Engine
Binance | Coinbase | Bybit | Kraken | Hyperliquid
Designed & Built by Sarah DeFer | ShekinahStar.io

WHAT THIS DOES:
  Connects Star to every major exchange simultaneously.
  Pulls live price, volume, orderbook, and funding data.
  Cross-exchange analysis detects arbitrage, divergence,
  and institutional flow signals that single-exchange
  platforms can never see.

EXCHANGES:
  1. Binance       — largest CEX by volume, spot + futures
  2. Coinbase       — institutional benchmark, BTC/ETH
  3. Bybit          — derivatives leader, funding data
  4. Kraken         — European institutional, EUR pairs
  5. Hyperliquid    — on-chain DEX, Star's trading venue

SIGNALS GENERATED:
  - Cross-exchange price divergence (arbitrage windows)
  - Volume imbalance (where the real money is moving)
  - Funding rate delta (Bybit vs HL — crowd positioning)
  - Exchange flow (CEX → DEX = bullish, DEX → CEX = cautious)
  - Liquidity depth comparison
  - Best execution venue for each trade

REGISTER in flask_app.py:
  from star_exchanges import exchanges_bp, init_exchanges
  app.register_blueprint(exchanges_bp)
  with app.app_context():
      init_exchanges()
"""

import os
import json
import time
import hmac
import hashlib
import sqlite3
import requests
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

BASE         = '/home/ShekinahD'
EXCHANGE_DB  = os.path.join(BASE, 'star_exchanges.db')
exchanges_bp = Blueprint('exchanges', __name__)

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

# ── Default watchlist ────────────────────────────────────────────
WATCHLIST = ['BTC', 'ETH', 'SOL', 'AVAX', 'DOGE', 'LINK', 'ARB', 'OP']

# ── Exchange configs ─────────────────────────────────────────────
EXCHANGES = {
    'binance': {
        'name':     'Binance',
        'base_url': 'https://api.binance.com',
        'futures':  'https://fapi.binance.com',
        'type':     'cex',
        'region':   'global',
    },
    'coinbase': {
        'name':     'Coinbase',
        'base_url': 'https://api.exchange.coinbase.com',
        'adv_url':  'https://api.coinbase.com/api/v3/brokerage',
        'type':     'cex',
        'region':   'us',
    },
    'bybit': {
        'name':     'Bybit',
        'base_url': 'https://api.bybit.com',
        'type':     'cex',
        'region':   'global',
    },
    'kraken': {
        'name':     'Kraken',
        'base_url': 'https://api.kraken.com',
        'type':     'cex',
        'region':   'eu',
    },
    'hyperliquid': {
        'name':     'Hyperliquid',
        'base_url': 'https://api.hyperliquid.xyz/info',
        'type':     'dex',
        'region':   'onchain',
    },
}


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_exchanges():
    conn = sqlite3.connect(EXCHANGE_DB)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS price_snapshots (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        exchange    TEXT,
        symbol      TEXT,
        price       REAL,
        volume_24h  REAL,
        bid         REAL,
        ask         REAL,
        spread_pct  REAL,
        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS funding_rates (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        exchange    TEXT,
        symbol      TEXT,
        rate        REAL,
        rate_pct    REAL,
        next_funding TIMESTAMP,
        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cross_signals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_type TEXT,
        symbol      TEXT,
        detail      TEXT,
        strength    REAL,
        direction   TEXT,
        exchanges   TEXT,
        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print('✅ Star Exchange Connectivity Engine initialized')


# ══ INDIVIDUAL EXCHANGE ADAPTERS ═══════════════════════════════════

class BinanceAdapter:
    """Binance — largest CEX, spot + perpetual futures."""

    BASE    = 'https://api.binance.com'
    FUTURES = 'https://fapi.binance.com'

    def get_price(self, symbol: str) -> dict:
        sym = symbol.upper() + 'USDT'
        try:
            r = requests.get(f'{self.BASE}/api/v3/ticker/24hr',
                           params={'symbol': sym}, timeout=8)
            d = r.json()
            price   = float(d.get('lastPrice', 0))
            vol     = float(d.get('quoteVolume', 0))
            bid     = float(d.get('bidPrice', 0))
            ask     = float(d.get('askPrice', 0))
            spread  = round((ask - bid) / price * 100, 4) if price else 0
            return {
                'exchange':   'binance',
                'symbol':     symbol,
                'price':      price,
                'volume_24h': round(vol / 1e6, 2),  # in millions USD
                'bid':        bid,
                'ask':        ask,
                'spread_pct': spread,
                'change_24h': float(d.get('priceChangePercent', 0)),
                'high_24h':   float(d.get('highPrice', 0)),
                'low_24h':    float(d.get('lowPrice', 0)),
            }
        except Exception as e:
            return {'exchange': 'binance', 'symbol': symbol, 'error': str(e)}

    def get_funding_rate(self, symbol: str) -> dict:
        sym = symbol.upper() + 'USDT'
        try:
            r = requests.get(f'{self.FUTURES}/fapi/v1/fundingRate',
                           params={'symbol': sym, 'limit': 1}, timeout=8)
            d = r.json()
            if isinstance(d, list) and d:
                rate = float(d[0].get('fundingRate', 0))
                return {
                    'exchange': 'binance',
                    'symbol':   symbol,
                    'rate':     rate,
                    'rate_pct': round(rate * 100, 6),
                    'annual_pct': round(rate * 100 * 3 * 365, 2),
                }
        except Exception as e:
            return {'exchange': 'binance', 'symbol': symbol, 'error': str(e)}
        return {'exchange': 'binance', 'symbol': symbol, 'rate': 0}

    def get_orderbook_depth(self, symbol: str, levels: int = 5) -> dict:
        sym = symbol.upper() + 'USDT'
        try:
            r = requests.get(f'{self.BASE}/api/v3/depth',
                           params={'symbol': sym, 'limit': levels}, timeout=8)
            d = r.json()
            bids = [[float(p), float(q)] for p, q in d.get('bids', [])]
            asks = [[float(p), float(q)] for p, q in d.get('asks', [])]
            bid_vol = sum(p * q for p, q in bids)
            ask_vol = sum(p * q for p, q in asks)
            return {
                'exchange':     'binance',
                'symbol':       symbol,
                'bid_liquidity': round(bid_vol / 1000, 1),  # in $K
                'ask_liquidity': round(ask_vol / 1000, 1),
                'buy_pressure': round(bid_vol / (bid_vol + ask_vol) * 100, 1) if (bid_vol + ask_vol) else 50,
                'top_bid':      bids[0][0] if bids else 0,
                'top_ask':      asks[0][0] if asks else 0,
            }
        except Exception as e:
            return {'exchange': 'binance', 'symbol': symbol, 'error': str(e)}

    def get_open_interest(self, symbol: str) -> dict:
        sym = symbol.upper() + 'USDT'
        try:
            r = requests.get(f'{self.FUTURES}/fapi/v1/openInterest',
                           params={'symbol': sym}, timeout=8)
            d = r.json()
            return {
                'exchange':      'binance',
                'symbol':        symbol,
                'open_interest': round(float(d.get('openInterest', 0)), 2),
            }
        except Exception as e:
            return {'exchange': 'binance', 'symbol': symbol, 'error': str(e)}


class CoinbaseAdapter:
    """Coinbase — institutional benchmark, USD pairs."""

    BASE = 'https://api.exchange.coinbase.com'

    def get_price(self, symbol: str) -> dict:
        pair = symbol.upper() + '-USD'
        try:
            # Stats (24h)
            r = requests.get(f'{self.BASE}/products/{pair}/stats', timeout=8)
            s = r.json()
            # Ticker
            t = requests.get(f'{self.BASE}/products/{pair}/ticker', timeout=8).json()

            price   = float(t.get('price', 0))
            vol     = float(s.get('volume', 0))
            bid     = float(t.get('bid', 0))
            ask     = float(t.get('ask', 0))
            spread  = round((ask - bid) / price * 100, 4) if price else 0
            open_p  = float(s.get('open', price))
            change  = round((price - open_p) / open_p * 100, 2) if open_p else 0

            return {
                'exchange':   'coinbase',
                'symbol':     symbol,
                'price':      price,
                'volume_24h': round(vol * price / 1e6, 2),
                'bid':        bid,
                'ask':        ask,
                'spread_pct': spread,
                'change_24h': change,
                'high_24h':   float(s.get('high', 0)),
                'low_24h':    float(s.get('low', 0)),
            }
        except Exception as e:
            return {'exchange': 'coinbase', 'symbol': symbol, 'error': str(e)}

    def get_orderbook_depth(self, symbol: str, levels: int = 5) -> dict:
        pair = symbol.upper() + '-USD'
        try:
            r = requests.get(f'{self.BASE}/products/{pair}/book',
                           params={'level': 2}, timeout=8)
            d = r.json()
            bids = [[float(p), float(q), int(n)] for p, q, n in d.get('bids', [])[:levels]]
            asks = [[float(p), float(q), int(n)] for p, q, n in d.get('asks', [])[:levels]]
            bid_vol = sum(p * q for p, q, _ in bids)
            ask_vol = sum(p * q for p, q, _ in asks)
            return {
                'exchange':     'coinbase',
                'symbol':       symbol,
                'bid_liquidity': round(bid_vol / 1000, 1),
                'ask_liquidity': round(ask_vol / 1000, 1),
                'buy_pressure': round(bid_vol / (bid_vol + ask_vol) * 100, 1) if (bid_vol + ask_vol) else 50,
                'top_bid':      bids[0][0] if bids else 0,
                'top_ask':      asks[0][0] if asks else 0,
            }
        except Exception as e:
            return {'exchange': 'coinbase', 'symbol': symbol, 'error': str(e)}


class BybitAdapter:
    """Bybit — derivatives leader, funding rate authority."""

    BASE = 'https://api.bybit.com'

    def get_price(self, symbol: str) -> dict:
        sym = symbol.upper() + 'USDT'
        try:
            r = requests.get(f'{self.BASE}/v5/market/tickers',
                           params={'category': 'linear', 'symbol': sym}, timeout=8)
            d = r.json()
            item = d.get('result', {}).get('list', [{}])[0]
            price   = float(item.get('lastPrice', 0))
            vol     = float(item.get('turnover24h', 0))
            bid     = float(item.get('bid1Price', 0))
            ask     = float(item.get('ask1Price', 0))
            spread  = round((ask - bid) / price * 100, 4) if price else 0
            change  = float(item.get('price24hPcnt', 0)) * 100
            return {
                'exchange':      'bybit',
                'symbol':        symbol,
                'price':         price,
                'volume_24h':    round(vol / 1e6, 2),
                'bid':           bid,
                'ask':           ask,
                'spread_pct':    spread,
                'change_24h':    round(change, 2),
                'high_24h':      float(item.get('highPrice24h', 0)),
                'low_24h':       float(item.get('lowPrice24h', 0)),
                'open_interest': float(item.get('openInterest', 0)),
                'funding_rate':  float(item.get('fundingRate', 0)),
            }
        except Exception as e:
            return {'exchange': 'bybit', 'symbol': symbol, 'error': str(e)}

    def get_funding_rate(self, symbol: str) -> dict:
        sym = symbol.upper() + 'USDT'
        try:
            r = requests.get(f'{self.BASE}/v5/market/funding/history',
                           params={'category': 'linear', 'symbol': sym, 'limit': 1}, timeout=8)
            d = r.json()
            items = d.get('result', {}).get('list', [])
            if items:
                rate = float(items[0].get('fundingRate', 0))
                ts   = int(items[0].get('fundingRateTimestamp', 0)) / 1000
                return {
                    'exchange':   'bybit',
                    'symbol':     symbol,
                    'rate':       rate,
                    'rate_pct':   round(rate * 100, 6),
                    'annual_pct': round(rate * 100 * 3 * 365, 2),
                    'timestamp':  datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                }
        except Exception as e:
            return {'exchange': 'bybit', 'symbol': symbol, 'error': str(e)}
        return {'exchange': 'bybit', 'symbol': symbol, 'rate': 0}

    def get_long_short_ratio(self, symbol: str) -> dict:
        sym = symbol.upper() + 'USDT'
        try:
            r = requests.get(f'{self.BASE}/v5/market/account-ratio',
                           params={'category': 'linear', 'symbol': sym,
                                   'period': '1h', 'limit': 1}, timeout=8)
            d = r.json()
            items = d.get('result', {}).get('list', [])
            if items:
                buy_ratio = float(items[0].get('buyRatio', 0.5))
                return {
                    'exchange':    'bybit',
                    'symbol':      symbol,
                    'long_pct':    round(buy_ratio * 100, 1),
                    'short_pct':   round((1 - buy_ratio) * 100, 1),
                    'crowd_bias':  'long' if buy_ratio > 0.55 else 'short' if buy_ratio < 0.45 else 'neutral',
                    'contrarian':  'bearish' if buy_ratio > 0.6 else 'bullish' if buy_ratio < 0.4 else 'neutral',
                }
        except Exception as e:
            return {'exchange': 'bybit', 'symbol': symbol, 'error': str(e)}
        return {'exchange': 'bybit', 'symbol': symbol, 'long_pct': 50}


class KrakenAdapter:
    """Kraken — European institutional, EUR pairs, strong BTC signal."""

    BASE = 'https://api.kraken.com'

    KRAKEN_PAIRS = {
        'BTC':  'XXBTZUSD',
        'ETH':  'XETHZUSD',
        'SOL':  'SOLUSD',
        'AVAX': 'AVAXUSD',
        'DOGE': 'XDGUSD',
        'LINK': 'LINKUSD',
        'ARB':  'ARBUSD',
        'DOT':  'DOTUSD',
        'ADA':  'ADAUSD',
        'MATIC':'MATICUSD',
    }

    def get_price(self, symbol: str) -> dict:
        pair = self.KRAKEN_PAIRS.get(symbol.upper(), symbol.upper() + 'USD')
        try:
            r = requests.get(f'{self.BASE}/0/public/Ticker',
                           params={'pair': pair}, timeout=8)
            d = r.json()
            if d.get('error'):
                return {'exchange': 'kraken', 'symbol': symbol, 'error': d['error']}
            result = d.get('result', {})
            key = list(result.keys())[0] if result else None
            if not key:
                return {'exchange': 'kraken', 'symbol': symbol, 'error': 'No data'}
            item    = result[key]
            price   = float(item['c'][0])
            bid     = float(item['b'][0])
            ask     = float(item['a'][0])
            vol     = float(item['v'][1])    # 24h volume
            open_p  = float(item['o'])
            change  = round((price - open_p) / open_p * 100, 2) if open_p else 0
            spread  = round((ask - bid) / price * 100, 4) if price else 0
            return {
                'exchange':   'kraken',
                'symbol':     symbol,
                'price':      price,
                'volume_24h': round(vol * price / 1e6, 2),
                'bid':        bid,
                'ask':        ask,
                'spread_pct': spread,
                'change_24h': change,
                'high_24h':   float(item['h'][1]),
                'low_24h':    float(item['l'][1]),
                'trades_24h': int(item['t'][1]),
            }
        except Exception as e:
            return {'exchange': 'kraken', 'symbol': symbol, 'error': str(e)}

    def get_eur_price(self, symbol: str) -> dict:
        """EUR price — unique signal for European institutional demand."""
        eur_pairs = {
            'BTC': 'XXBTZEUR',
            'ETH': 'XETHZEUR',
            'SOL': 'SOLEUR',
        }
        pair = eur_pairs.get(symbol.upper())
        if not pair:
            return {}
        try:
            r = requests.get(f'{self.BASE}/0/public/Ticker',
                           params={'pair': pair}, timeout=8)
            d = r.json()
            result = d.get('result', {})
            key = list(result.keys())[0] if result else None
            if not key:
                return {}
            item  = result[key]
            price = float(item['c'][0])
            return {
                'exchange':  'kraken',
                'symbol':    symbol,
                'eur_price': price,
                'currency':  'EUR',
            }
        except Exception:
            return {}


class HyperliquidAdapter:
    """Hyperliquid — Star's on-chain trading venue."""

    BASE = 'https://api.hyperliquid.xyz/info'

    def _post(self, payload):
        try:
            r = requests.post(self.BASE, json=payload, timeout=8)
            return r.json()
        except Exception:
            return {}

    def get_price(self, symbol: str) -> dict:
        try:
            mids = self._post({'type': 'allMids'})
            price = float(mids.get(symbol.upper(), 0) or 0)

            # Get meta for funding
            meta = self._post({'type': 'meta'})
            funding = 0
            for asset in meta.get('universe', []):
                if asset.get('name') == symbol.upper():
                    funding = float(asset.get('funding', 0) or 0)
                    break

            return {
                'exchange':    'hyperliquid',
                'symbol':      symbol,
                'price':       price,
                'funding_rate': funding,
                'funding_pct': round(funding * 100, 6),
                'type':        'dex_perp',
            }
        except Exception as e:
            return {'exchange': 'hyperliquid', 'symbol': symbol, 'error': str(e)}

    def get_open_interest(self, symbol: str) -> dict:
        try:
            ctx = self._post({'type': 'metaAndAssetCtxs'})
            universe = ctx[0].get('universe', []) if isinstance(ctx, list) else []
            asset_ctx = ctx[1] if isinstance(ctx, list) and len(ctx) > 1 else []
            for i, asset in enumerate(universe):
                if asset.get('name') == symbol.upper() and i < len(asset_ctx):
                    oi = float(asset_ctx[i].get('openInterest', 0) or 0)
                    price = float(asset_ctx[i].get('markPx', 0) or 0)
                    return {
                        'exchange':      'hyperliquid',
                        'symbol':        symbol,
                        'open_interest': round(oi, 2),
                        'oi_usd':        round(oi * price / 1e6, 2),
                        'mark_price':    price,
                    }
        except Exception as e:
            return {'exchange': 'hyperliquid', 'symbol': symbol, 'error': str(e)}
        return {'exchange': 'hyperliquid', 'symbol': symbol, 'open_interest': 0}


# ══ CROSS-EXCHANGE INTELLIGENCE ENGINE ═════════════════════════════

class CrossExchangeIntelligence:
    """
    Analyzes data across all 5 exchanges simultaneously.
    Generates signals that no single-exchange platform can see.
    """

    def __init__(self):
        self.binance    = BinanceAdapter()
        self.coinbase   = CoinbaseAdapter()
        self.bybit      = BybitAdapter()
        self.kraken     = KrakenAdapter()
        self.hl         = HyperliquidAdapter()

    def get_all_prices(self, symbol: str) -> dict:
        """Pull price from all 5 exchanges simultaneously."""
        results = {}
        adapters = [
            ('binance',    self.binance.get_price),
            ('coinbase',   self.coinbase.get_price),
            ('bybit',      self.bybit.get_price),
            ('kraken',     self.kraken.get_price),
            ('hyperliquid', self.hl.get_price),
        ]
        for name, fn in adapters:
            try:
                results[name] = fn(symbol)
            except Exception as e:
                results[name] = {'exchange': name, 'symbol': symbol, 'error': str(e)}

        return results

    def price_divergence_signal(self, symbol: str) -> dict:
        """
        Detect price divergence across exchanges.
        Large spread between CEX prices = arbitrage window or manipulation.
        CEX vs DEX divergence = directional signal.
        """
        prices_raw = self.get_all_prices(symbol)
        prices = {}
        for ex, data in prices_raw.items():
            p = data.get('price', 0)
            if p and p > 0 and 'error' not in data:
                prices[ex] = p

        if len(prices) < 2:
            return {'signal': 'insufficient_data', 'symbol': symbol}

        vals     = list(prices.values())
        max_p    = max(vals)
        min_p    = min(vals)
        avg_p    = sum(vals) / len(vals)
        spread   = round((max_p - min_p) / avg_p * 100, 4)

        high_ex  = max(prices, key=prices.get)
        low_ex   = min(prices, key=prices.get)

        # CEX vs DEX comparison
        cex_prices = {k: v for k, v in prices.items() if k != 'hyperliquid'}
        dex_price  = prices.get('hyperliquid', 0)
        cex_avg    = sum(cex_prices.values()) / len(cex_prices) if cex_prices else 0
        cex_dex_div = round((dex_price - cex_avg) / cex_avg * 100, 4) if cex_avg and dex_price else 0

        # Signal interpretation
        if spread > 0.5:
            signal    = 'significant_divergence'
            strength  = min(spread / 1.0, 1.0)
            direction = 'bullish' if cex_dex_div < 0 else 'bearish'
            # DEX premium = smart money buying on-chain = bullish
            # DEX discount = smart money selling on-chain = bearish
        elif spread > 0.2:
            signal    = 'moderate_divergence'
            strength  = spread / 0.5
            direction = 'bullish' if cex_dex_div < 0 else 'neutral'
        else:
            signal    = 'price_consensus'
            strength  = 0.1
            direction = 'neutral'

        return {
            'symbol':        symbol,
            'signal':        signal,
            'direction':     direction,
            'strength':      round(strength, 3),
            'spread_pct':    spread,
            'highest_price': {'exchange': high_ex, 'price': max_p},
            'lowest_price':  {'exchange': low_ex,  'price': min_p},
            'avg_price':     round(avg_p, 4),
            'cex_avg':       round(cex_avg, 4),
            'dex_price':     round(dex_price, 4),
            'cex_dex_divergence_pct': cex_dex_div,
            'interpretation': (
                f'DEX trading at {abs(cex_dex_div):.2f}% {"premium" if cex_dex_div > 0 else "discount"} to CEX average. '
                f'{"Smart money accumulating on-chain — bullish signal." if cex_dex_div < -0.1 else "On-chain premium — potential sell pressure incoming." if cex_dex_div > 0.1 else "Price in consensus across venues."}'
            ),
            'prices': prices_raw,
        }

    def volume_imbalance_signal(self, symbol: str) -> dict:
        """
        Compare 24h volume across exchanges.
        Unusual volume on specific exchanges = institutional flow signal.
        """
        all_prices = self.get_all_prices(symbol)
        volumes = {}
        for ex, data in all_prices.items():
            v = data.get('volume_24h', 0)
            if v and v > 0:
                volumes[ex] = v

        if not volumes:
            return {'signal': 'no_volume_data', 'symbol': symbol}

        total      = sum(volumes.values())
        shares     = {ex: round(v / total * 100, 1) for ex, v in volumes.items()}
        dominant   = max(volumes, key=volumes.get)
        dom_share  = shares[dominant]

        # Historical norm: Binance ~60%, Bybit ~20%, Coinbase ~10%, Kraken ~5%, HL ~5%
        NORMS = {'binance': 60, 'bybit': 20, 'coinbase': 10, 'kraken': 5, 'hyperliquid': 5}
        anomalies = {}
        for ex, share in shares.items():
            norm = NORMS.get(ex, 10)
            delta = share - norm
            if abs(delta) > 5:
                anomalies[ex] = {'share': share, 'normal': norm, 'delta': delta}

        direction = 'neutral'
        if anomalies:
            if any(ex in ('coinbase', 'kraken') and a['delta'] > 5 for ex, a in anomalies.items()):
                direction = 'bullish'  # Institutional venues gaining share
            elif anomalies.get('hyperliquid', {}).get('delta', 0) > 5:
                direction = 'bullish'  # On-chain volume surge = smart money

        return {
            'symbol':        symbol,
            'total_volume_m': round(total, 1),
            'volume_shares': shares,
            'dominant_exchange': dominant,
            'anomalies':     anomalies,
            'direction':     direction,
            'interpretation': (
                f'Total 24h volume ${total:.1f}M. '
                f'{dominant.title()} dominant at {dom_share:.1f}%. '
                f'{"Anomalous volume on: " + ", ".join(anomalies.keys()) + " — monitor for institutional activity." if anomalies else "Volume distribution normal."}'
            ),
        }

    def funding_rate_delta(self, symbol: str) -> dict:
        """
        Compare funding rates across Binance, Bybit, and Hyperliquid.
        Rate divergence = positioning imbalance = contrarian opportunity.
        """
        binance_f = self.binance.get_funding_rate(symbol)
        bybit_f   = self.bybit.get_funding_rate(symbol)
        hl_f      = self.hl.get_price(symbol)

        rates = {}
        if 'error' not in binance_f:
            rates['binance'] = binance_f.get('rate', 0)
        if 'error' not in bybit_f:
            rates['bybit'] = bybit_f.get('rate', 0)
        if 'error' not in hl_f:
            rates['hyperliquid'] = hl_f.get('funding_rate', 0)

        if not rates:
            return {'signal': 'no_funding_data', 'symbol': symbol}

        avg_rate   = sum(rates.values()) / len(rates)
        max_rate   = max(rates.values())
        min_rate   = min(rates.values())
        delta      = max_rate - min_rate

        high_ex    = max(rates, key=rates.get)
        low_ex     = min(rates, key=rates.get)

        # Interpretation
        if avg_rate > 0.0001:
            crowd_bias = 'long_crowded'
            contrarian = 'bearish'
        elif avg_rate < -0.0001:
            crowd_bias = 'short_crowded'
            contrarian = 'bullish'
        else:
            crowd_bias = 'balanced'
            contrarian = 'neutral'

        # Divergence between venues = potential squeeze
        squeeze_risk = delta > 0.0003

        return {
            'symbol':      symbol,
            'rates':       {k: round(v * 100, 6) for k, v in rates.items()},
            'avg_rate_pct': round(avg_rate * 100, 6),
            'annual_rate': round(avg_rate * 100 * 3 * 365, 2),
            'crowd_bias':  crowd_bias,
            'contrarian_signal': contrarian,
            'delta_pct':   round(delta * 100, 6),
            'squeeze_risk': squeeze_risk,
            'highest':     {'exchange': high_ex, 'rate_pct': round(rates.get(high_ex, 0) * 100, 6)},
            'lowest':      {'exchange': low_ex,  'rate_pct': round(rates.get(low_ex, 0) * 100, 6)},
            'interpretation': (
                f'Avg funding {avg_rate*100:.4f}%/8hr ({avg_rate*100*3*365:.1f}% annualized). '
                f'{"Crowded longs — contrarian bearish signal." if contrarian == "bearish" else "Crowded shorts — contrarian bullish signal." if contrarian == "bullish" else "Balanced positioning."}'
                f'{" Funding divergence detected — squeeze risk elevated." if squeeze_risk else ""}'
            ),
        }

    def best_execution_venue(self, symbol: str, side: str = 'buy', size_usd: float = 10000) -> dict:
        """
        Determine the best exchange to execute a trade for minimum slippage.
        Considers: spread, liquidity depth, funding (for perps).
        """
        all_prices = self.get_all_prices(symbol)
        scores = {}

        for ex, data in all_prices.items():
            if 'error' in data or not data.get('price'):
                continue
            price   = data.get('price', 0)
            spread  = data.get('spread_pct', 0.1)
            vol     = data.get('volume_24h', 0)
            funding = abs(data.get('funding_rate', 0) or 0) * 100

            # Score: lower spread = better, higher volume = better, lower funding = better for perps
            score = 100 - (spread * 20) + min(vol / 100, 20) - (funding * 1000)
            scores[ex] = {
                'score':   round(score, 1),
                'price':   price,
                'spread':  spread,
                'vol_m':   vol,
                'funding': round(funding, 6) if ex != 'coinbase' else 'n/a',
            }

        if not scores:
            return {'symbol': symbol, 'recommendation': 'hyperliquid'}

        best = max(scores, key=lambda x: scores[x]['score'])

        return {
            'symbol':         symbol,
            'side':           side,
            'size_usd':       size_usd,
            'recommendation': best,
            'reason':         f'Best spread/liquidity combination for {side} {symbol}',
            'scores':         scores,
            'star_default':   'hyperliquid',
            'note':           'Star always executes on Hyperliquid for on-chain transparency. Use this analysis to benchmark pricing.',
        }

    def full_market_scan(self, symbols: list = None) -> dict:
        """
        Full cross-exchange market scan.
        Returns the most actionable signals across all symbols.
        """
        symbols = symbols or ['BTC', 'ETH', 'SOL']
        results = {}

        for symbol in symbols:
            try:
                divergence = self.price_divergence_signal(symbol)
                funding    = self.funding_rate_delta(symbol)
                results[symbol] = {
                    'price_divergence': divergence,
                    'funding_delta':    funding,
                    'timestamp':        datetime.now(timezone.utc).isoformat(),
                }
            except Exception as e:
                results[symbol] = {'error': str(e)}

        # Find most actionable signal
        top_signals = []
        for sym, data in results.items():
            div = data.get('price_divergence', {})
            fund = data.get('funding_delta', {})
            if div.get('spread_pct', 0) > 0.3:
                top_signals.append({'symbol': sym, 'type': 'price_divergence', 'strength': div['spread_pct']})
            if fund.get('contrarian_signal') in ('bullish', 'bearish'):
                top_signals.append({'symbol': sym, 'type': 'funding_contrarian', 'direction': fund['contrarian_signal']})

        top_signals.sort(key=lambda x: x.get('strength', 0.5), reverse=True)

        return {
            'scan_time':    datetime.now(timezone.utc).isoformat(),
            'symbols':      symbols,
            'results':      results,
            'top_signals':  top_signals[:3],
            'exchanges':    list(EXCHANGES.keys()),
        }


# ── Module init ──────────────────────────────────────────────────
_intel = None

def init_exchanges():
    global _intel
    _intel = CrossExchangeIntelligence()

    conn = sqlite3.connect(EXCHANGE_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS price_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exchange TEXT, symbol TEXT, price REAL,
        volume_24h REAL, spread_pct REAL,
        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS funding_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exchange TEXT, symbol TEXT, rate REAL,
        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print('✅ Star Exchange Connectivity Engine initialized — Binance | Coinbase | Bybit | Kraken | Hyperliquid')


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

@exchanges_bp.route('/api/exchanges/prices/<symbol>')
def exchange_prices(symbol):
    """Live prices from all 5 exchanges."""
    if not _intel:
        return jsonify({'error': 'Engine not initialized'}), 503
    data = _intel.get_all_prices(symbol.upper())
    return jsonify({'symbol': symbol.upper(), 'prices': data,
                    'timestamp': datetime.now(timezone.utc).isoformat()})


@exchanges_bp.route('/api/exchanges/divergence/<symbol>')
def exchange_divergence(symbol):
    """Price divergence signal across all exchanges."""
    if not _intel:
        return jsonify({'error': 'Engine not initialized'}), 503
    return jsonify(_intel.price_divergence_signal(symbol.upper()))


@exchanges_bp.route('/api/exchanges/volume/<symbol>')
def exchange_volume(symbol):
    """Volume imbalance signal."""
    if not _intel:
        return jsonify({'error': 'Engine not initialized'}), 503
    return jsonify(_intel.volume_imbalance_signal(symbol.upper()))


@exchanges_bp.route('/api/exchanges/funding/<symbol>')
def exchange_funding(symbol):
    """Cross-exchange funding rate delta."""
    if not _intel:
        return jsonify({'error': 'Engine not initialized'}), 503
    return jsonify(_intel.funding_rate_delta(symbol.upper()))


@exchanges_bp.route('/api/exchanges/execution/<symbol>')
def exchange_execution(symbol):
    """Best execution venue recommendation."""
    if not _intel:
        return jsonify({'error': 'Engine not initialized'}), 503
    side     = request.args.get('side', 'buy')
    size_usd = float(request.args.get('size', 10000))
    return jsonify(_intel.best_execution_venue(symbol.upper(), side, size_usd))


@exchanges_bp.route('/api/exchanges/scan', methods=['POST'])
def exchange_scan():
    """Full cross-exchange market scan."""
    if not _intel:
        return jsonify({'error': 'Engine not initialized'}), 503
    data    = request.get_json() or {}
    symbols = data.get('symbols', ['BTC', 'ETH', 'SOL'])
    symbols = [s.upper() for s in symbols[:5]]  # max 5 at a time
    return jsonify(_intel.full_market_scan(symbols))


@exchanges_bp.route('/api/exchanges/bybit/longshort/<symbol>')
def bybit_longshort(symbol):
    """Bybit long/short ratio — crowd positioning."""
    adapter = BybitAdapter()
    return jsonify(adapter.get_long_short_ratio(symbol.upper()))


@exchanges_bp.route('/api/exchanges/kraken/eur/<symbol>')
def kraken_eur(symbol):
    """Kraken EUR price — European institutional demand signal."""
    adapter = KrakenAdapter()
    return jsonify(adapter.get_eur_price(symbol.upper()))


@exchanges_bp.route('/api/exchanges/binance/oi/<symbol>')
def binance_oi(symbol):
    """Binance open interest."""
    adapter = BinanceAdapter()
    return jsonify(adapter.get_open_interest(symbol.upper()))


@exchanges_bp.route('/api/exchanges/hl/oi/<symbol>')
def hl_oi(symbol):
    """Hyperliquid open interest."""
    adapter = HyperliquidAdapter()
    return jsonify(adapter.get_open_interest(symbol.upper()))


@exchanges_bp.route('/api/exchanges/status')
def exchange_status():
    """Exchange engine health check."""
    return jsonify({
        'status':    'active' if _intel else 'not_initialized',
        'module':    'Star Exchange Connectivity v1.0',
        'exchanges': [
            {'name': 'Binance',     'type': 'CEX', 'data': ['price','volume','orderbook','funding','open_interest']},
            {'name': 'Coinbase',    'type': 'CEX', 'data': ['price','volume','orderbook']},
            {'name': 'Bybit',       'type': 'CEX', 'data': ['price','volume','funding','long_short_ratio']},
            {'name': 'Kraken',      'type': 'CEX', 'data': ['price','volume','eur_pairs']},
            {'name': 'Hyperliquid', 'type': 'DEX', 'data': ['price','funding','open_interest']},
        ],
        'cross_signals': [
            'price_divergence',
            'volume_imbalance',
            'funding_rate_delta',
            'best_execution_venue',
            'full_market_scan',
        ],
        'api_keys_required': {
            'binance':    'Optional — public endpoints used (BINANCE_API_KEY for private)',
            'coinbase':   'Optional — public endpoints used (COINBASE_API_KEY for private)',
            'bybit':      'Optional — public endpoints used (BYBIT_API_KEY for private)',
            'kraken':     'Optional — public endpoints used (KRAKEN_API_KEY for private)',
            'hyperliquid':'No key needed — public DEX',
        },
    })
