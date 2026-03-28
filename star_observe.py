"""
star_observe.py
Star Observability Engine
Langfuse LLM Tracing | Vector Search Tracing | Signal Quality Scoring
Designed & Built by Sarah DeFer | ShekinahStar.io

WHAT THIS DOES:
  Every AI interaction Star has is traced, scored, and analyzed.
  Star can measure her own performance, improve her predictions,
  and give Sarah full visibility into what's happening inside
  the platform at all times.

LANGFUSE TRACES:
  - Every chat message: input, output, model, latency, tokens, cost
  - Every signal generated: symbol, direction, confidence, outcome
  - Every vector search: query, retrieved docs, similarity scores
  - Every KYC event: routing decision, outcome
  - Every AML screen: risk score, flags, decision

VECTOR TRACING:
  - Logs every ChromaDB query and its retrieved memories
  - Tracks similarity scores over time to measure retrieval quality
  - Identifies which memories are retrieved most often
  - Flags low-similarity retrievals for memory improvement

SIGNAL SCORING:
  - When Star predicts BULLISH on BTC, log it
  - When the price resolves 4 hours later, score the prediction
  - Feed accuracy back into Star's learning loop
  - Build Star's public track record transparently

SETUP:
  1. Create free account at langfuse.com
  2. Add to .env:
     LANGFUSE_PUBLIC_KEY=pk-lf-...
     LANGFUSE_SECRET_KEY=sk-lf-...
     LANGFUSE_HOST=https://cloud.langfuse.com  (or self-hosted URL)
  3. Install: /usr/bin/python3 -m pip install langfuse
  4. Register in flask_app.py (see bottom of file)
"""

import os
import json
import time
import hashlib
import sqlite3
import requests
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

BASE       = '/home/ShekinahD'
OBSERVE_DB = os.path.join(BASE, 'star_observe.db')
observe_bp = Blueprint('observe', __name__)

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

# ── Langfuse client (lazy init) ──────────────────────────────────
_langfuse = None

def get_langfuse():
    global _langfuse
    if _langfuse is not None:
        return _langfuse
    try:
        from langfuse import Langfuse
        pk   = _ENV.get('LANGFUSE_PUBLIC_KEY', '')
        sk   = _ENV.get('LANGFUSE_SECRET_KEY', '')
        host = _ENV.get('LANGFUSE_HOST', 'https://cloud.langfuse.com')
        if pk and sk:
            _langfuse = Langfuse(public_key=pk, secret_key=sk, host=host)
            print('✅ Langfuse observability connected')
        else:
            print('⚠️  Langfuse keys not set — add LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to .env')
    except ImportError:
        print('⚠️  Langfuse not installed — run: /usr/bin/python3 -m pip install langfuse')
    except Exception as e:
        print(f'⚠️  Langfuse init error: {e}')
    return _langfuse


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_observe_db():
    conn = sqlite3.connect(OBSERVE_DB)
    c = conn.cursor()

    # Chat trace log (local backup if Langfuse unavailable)
    c.execute('''CREATE TABLE IF NOT EXISTS chat_traces (
        trace_id        TEXT PRIMARY KEY,
        subscriber_id   TEXT,
        tier            TEXT,
        model           TEXT,
        input_preview   TEXT,
        output_preview  TEXT,
        input_tokens    INTEGER DEFAULT 0,
        output_tokens   INTEGER DEFAULT 0,
        latency_ms      INTEGER DEFAULT 0,
        cost_usd        REAL DEFAULT 0,
        groq_used       INTEGER DEFAULT 1,
        langfuse_id     TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Signal predictions (for accuracy tracking)
    c.execute('''CREATE TABLE IF NOT EXISTS signal_predictions (
        pred_id         TEXT PRIMARY KEY,
        subscriber_id   TEXT,
        symbol          TEXT,
        direction       TEXT,       -- BULLISH, BEARISH, NEUTRAL
        confidence      REAL,
        signals_used    TEXT,       -- JSON array of signal names
        exchanges_used  TEXT,       -- JSON array
        price_at_pred   REAL,
        resolved        INTEGER DEFAULT 0,
        resolve_hours   INTEGER DEFAULT 4,
        price_at_resolve REAL,
        outcome         TEXT,       -- correct, incorrect, neutral
        score           REAL,       -- 0-1 accuracy score
        langfuse_score_id TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at     TIMESTAMP
    )''')

    # Vector search traces
    c.execute('''CREATE TABLE IF NOT EXISTS vector_traces (
        trace_id        TEXT PRIMARY KEY,
        query           TEXT,
        query_preview   TEXT,
        results_count   INTEGER,
        top_similarity  REAL,
        avg_similarity  REAL,
        retrieved_ids   TEXT,       -- JSON array
        latency_ms      INTEGER,
        useful          INTEGER DEFAULT 1,  -- 0 if all similarities < 0.3
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Model performance metrics
    c.execute('''CREATE TABLE IF NOT EXISTS model_metrics (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date            TEXT,
        model           TEXT,
        total_calls     INTEGER DEFAULT 0,
        total_tokens    INTEGER DEFAULT 0,
        total_cost_usd  REAL DEFAULT 0,
        avg_latency_ms  REAL DEFAULT 0,
        errors          INTEGER DEFAULT 0
    )''')

    # Star accuracy track record (public)
    c.execute('''CREATE TABLE IF NOT EXISTS accuracy_record (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol          TEXT,
        direction       TEXT,
        correct         INTEGER,    -- 1 = correct, 0 = incorrect
        confidence      REAL,
        resolution_pct  REAL,       -- actual price move %
        period          TEXT,       -- '4h', '24h', etc
        date            TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print('✅ Star Observability Engine initialized')


# ══ CHAT TRACING ═══════════════════════════════════════════════════

def trace_chat(subscriber_id: str, tier: str, user_msg: str,
               star_response: str, model: str, latency_ms: int,
               input_tokens: int = 0, output_tokens: int = 0) -> str:
    """
    Trace a chat interaction to Langfuse + local DB.
    Returns trace_id for later scoring.
    """
    trace_id = hashlib.sha256(
        f"{subscriber_id}{user_msg[:50]}{time.time()}".encode()
    ).hexdigest()[:16]

    # Estimate cost (Groq is free, Anthropic ~$3/M input + $15/M output)
    cost = 0.0
    if 'claude' in model.lower():
        cost = (input_tokens / 1e6 * 3.0) + (output_tokens / 1e6 * 15.0)

    # Send to Langfuse
    lf = get_langfuse()
    langfuse_id = ''
    if lf:
        try:
            trace = lf.trace(
                id=trace_id,
                name='star_chat',
                user_id=subscriber_id,
                metadata={
                    'tier':      tier,
                    'model':     model,
                    'latency_ms': latency_ms,
                },
                tags=[tier, model.split('-')[0]],
            )
            trace.generation(
                name='chat_response',
                model=model,
                input=user_msg[:500],
                output=star_response[:500],
                usage={
                    'input':  input_tokens,
                    'output': output_tokens,
                    'unit':   'TOKENS',
                },
                start_time=datetime.now(timezone.utc) - timedelta(milliseconds=latency_ms),
                end_time=datetime.now(timezone.utc),
                metadata={'cost_usd': cost},
            )
            langfuse_id = trace_id
        except Exception as e:
            print(f'[Observe] Langfuse trace error: {e}')

    # Local DB backup
    try:
        conn = sqlite3.connect(OBSERVE_DB)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO chat_traces
            (trace_id, subscriber_id, tier, model, input_preview,
             output_preview, input_tokens, output_tokens, latency_ms,
             cost_usd, groq_used, langfuse_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (trace_id, subscriber_id, tier, model,
             user_msg[:200], star_response[:200],
             input_tokens, output_tokens, latency_ms, cost,
             1 if 'llama' in model.lower() else 0,
             langfuse_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[Observe] Local trace error: {e}')

    return trace_id


def score_chat(trace_id: str, score: float, comment: str = ''):
    """
    Score a chat interaction (0-1).
    Called when user gives thumbs up/down or when signal resolves.
    """
    lf = get_langfuse()
    if lf:
        try:
            lf.score(
                trace_id=trace_id,
                name='user_feedback',
                value=score,
                comment=comment,
            )
        except Exception as e:
            print(f'[Observe] Score error: {e}')


# ══ SIGNAL PREDICTION TRACKING ═════════════════════════════════════

def log_prediction(subscriber_id: str, symbol: str, direction: str,
                   confidence: float, signals_used: list,
                   exchanges_used: list, price: float,
                   resolve_hours: int = 4) -> str:
    """
    Log a trading signal prediction for later accuracy scoring.
    """
    pred_id = hashlib.sha256(
        f"{subscriber_id}{symbol}{direction}{time.time()}".encode()
    ).hexdigest()[:16]

    # Log to Langfuse
    lf = get_langfuse()
    if lf:
        try:
            trace = lf.trace(
                id=f"pred_{pred_id}",
                name='star_signal',
                user_id=subscriber_id,
                metadata={
                    'symbol':     symbol,
                    'direction':  direction,
                    'confidence': confidence,
                    'price':      price,
                    'signals':    signals_used,
                    'exchanges':  exchanges_used,
                },
                tags=[symbol, direction.lower()],
            )
        except Exception as e:
            print(f'[Observe] Prediction log error: {e}')

    # Local DB
    try:
        conn = sqlite3.connect(OBSERVE_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO signal_predictions
            (pred_id, subscriber_id, symbol, direction, confidence,
             signals_used, exchanges_used, price_at_pred, resolve_hours)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (pred_id, subscriber_id, symbol, direction, confidence,
             json.dumps(signals_used), json.dumps(exchanges_used),
             price, resolve_hours))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[Observe] Prediction DB error: {e}')

    return pred_id


def resolve_prediction(pred_id: str, current_price: float) -> dict:
    """
    Resolve a prediction against actual price movement.
    Updates accuracy record and scores the Langfuse trace.
    """
    try:
        conn = sqlite3.connect(OBSERVE_DB)
        c = conn.cursor()
        c.execute('SELECT * FROM signal_predictions WHERE pred_id=?', (pred_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return {'error': 'Prediction not found'}

        cols = [d[0] for d in c.description]
        pred = dict(zip(cols, row))

        entry_price = pred['price_at_pred']
        direction   = pred['direction']
        change_pct  = (current_price - entry_price) / entry_price * 100

        # Score the prediction
        if direction == 'BULLISH':
            correct = change_pct > 0.5
            score   = min(change_pct / 3.0, 1.0) if change_pct > 0 else max(change_pct / 3.0, 0.0)
        elif direction == 'BEARISH':
            correct = change_pct < -0.5
            score   = min(-change_pct / 3.0, 1.0) if change_pct < 0 else max(-change_pct / 3.0, 0.0)
        else:
            correct = abs(change_pct) < 1.0
            score   = 0.5

        score = max(0.0, min(1.0, score))
        outcome = 'correct' if correct else 'incorrect'

        # Update DB
        c.execute('''UPDATE signal_predictions SET
            resolved=1, price_at_resolve=?, outcome=?, score=?,
            resolved_at=?
            WHERE pred_id=?''',
            (current_price, outcome, score,
             datetime.now(timezone.utc).isoformat(), pred_id))

        # Update accuracy record
        c.execute('''INSERT INTO accuracy_record
            (symbol, direction, correct, confidence, resolution_pct, period, date)
            VALUES (?,?,?,?,?,?,?)''',
            (pred['symbol'], direction, int(correct),
             pred['confidence'], round(change_pct, 4),
             f"{pred['resolve_hours']}h",
             datetime.now(timezone.utc).strftime('%Y-%m-%d')))

        conn.commit()
        conn.close()

        # Score in Langfuse
        lf = get_langfuse()
        if lf:
            try:
                lf.score(
                    trace_id=f"pred_{pred_id}",
                    name='signal_accuracy',
                    value=score,
                    comment=f"{direction} {pred['symbol']} | Entry: ${entry_price:.2f} | Exit: ${current_price:.2f} | Move: {change_pct:.2f}% | {outcome.upper()}",
                )
            except Exception:
                pass

        return {
            'pred_id':   pred_id,
            'outcome':   outcome,
            'score':     round(score, 3),
            'correct':   correct,
            'change_pct': round(change_pct, 4),
            'entry':     entry_price,
            'exit':      current_price,
        }
    except Exception as e:
        return {'error': str(e)}


# ══ VECTOR SEARCH TRACING ══════════════════════════════════════════

def trace_vector_search(query: str, results: list, latency_ms: int) -> str:
    """
    Trace a vector DB search. Call this every time star_quant.py
    performs a similarity search.
    """
    trace_id = hashlib.sha256(
        f"{query}{time.time()}".encode()
    ).hexdigest()[:16]

    similarities = [r.get('similarity', 0) for r in results if 'similarity' in r]
    top_sim  = max(similarities) if similarities else 0
    avg_sim  = sum(similarities) / len(similarities) if similarities else 0
    useful   = top_sim >= 0.3

    retrieved_ids = [r.get('metadata', {}).get('id', '') or
                     r.get('document', '')[:30] for r in results]

    # Log to Langfuse
    lf = get_langfuse()
    if lf:
        try:
            trace = lf.trace(
                id=f"vec_{trace_id}",
                name='vector_search',
                metadata={
                    'query_preview':  query[:100],
                    'results_count':  len(results),
                    'top_similarity': round(top_sim, 4),
                    'avg_similarity': round(avg_sim, 4),
                    'latency_ms':     latency_ms,
                    'useful':         useful,
                },
                tags=['vector', 'chromadb'],
            )
            if not useful:
                lf.score(
                    trace_id=f"vec_{trace_id}",
                    name='retrieval_quality',
                    value=avg_sim,
                    comment=f'Low similarity retrieval — consider adding more memories for: {query[:50]}',
                )
        except Exception as e:
            print(f'[Observe] Vector trace error: {e}')

    # Local DB
    try:
        conn = sqlite3.connect(OBSERVE_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO vector_traces
            (trace_id, query, query_preview, results_count,
             top_similarity, avg_similarity, retrieved_ids, latency_ms, useful)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (trace_id, query[:500], query[:100], len(results),
             round(top_sim, 4), round(avg_sim, 4),
             json.dumps(retrieved_ids[:5]), latency_ms, int(useful)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[Observe] Vector DB error: {e}')

    return trace_id


# ══ ACCURACY DASHBOARD ═════════════════════════════════════════════

def get_accuracy_stats() -> dict:
    """Star's public track record — all predictions, wins and losses."""
    try:
        conn = sqlite3.connect(OBSERVE_DB)
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM accuracy_record')
        total = c.fetchone()[0]
        if total == 0:
            conn.close()
            return {'total': 0, 'message': 'No predictions resolved yet'}

        c.execute('SELECT COUNT(*) FROM accuracy_record WHERE correct=1')
        correct = c.fetchone()[0]

        c.execute('SELECT AVG(confidence) FROM signal_predictions WHERE resolved=1')
        avg_conf = c.fetchone()[0] or 0

        c.execute('SELECT AVG(score) FROM signal_predictions WHERE resolved=1')
        avg_score = c.fetchone()[0] or 0

        # By symbol
        c.execute('''SELECT symbol, COUNT(*), SUM(correct), AVG(resolution_pct)
            FROM accuracy_record GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 10''')
        by_symbol = [{'symbol': r[0], 'total': r[1], 'correct': r[2],
                     'win_rate': round(r[2]/r[1]*100,1),
                     'avg_move_pct': round(r[3],2)} for r in c.fetchall()]

        # By direction
        c.execute('''SELECT direction, COUNT(*), SUM(correct)
            FROM accuracy_record GROUP BY direction''')
        by_direction = {r[0]: {'total': r[1], 'correct': r[2],
                               'win_rate': round(r[2]/r[1]*100,1)}
                       for r in c.fetchall()}

        # Recent 10
        c.execute('''SELECT symbol, direction, correct, resolution_pct, date
            FROM accuracy_record ORDER BY id DESC LIMIT 10''')
        recent = [{'symbol': r[0], 'direction': r[1], 'correct': bool(r[2]),
                  'move_pct': r[3], 'date': r[4]} for r in c.fetchall()]

        conn.close()

        accuracy = round(correct / total * 100, 1) if total else 0

        return {
            'total_predictions':  total,
            'correct':            correct,
            'accuracy_pct':       accuracy,
            'avg_confidence':     round(avg_conf * 100, 1),
            'avg_score':          round(avg_score, 3),
            'by_symbol':          by_symbol,
            'by_direction':       by_direction,
            'recent':             recent,
            'note':               'Full track record — wins and losses. No cherry-picking.',
            'updated':            datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {'error': str(e)}


def get_cost_analytics(days: int = 7) -> dict:
    """Token usage and cost breakdown."""
    try:
        conn = sqlite3.connect(OBSERVE_DB)
        c = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        c.execute('''SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens),
            SUM(cost_usd), AVG(latency_ms), SUM(groq_used)
            FROM chat_traces WHERE created_at > ?''', (cutoff,))
        row = c.fetchone()
        total, in_tok, out_tok, cost, avg_lat, groq_calls = row

        c.execute('''SELECT model, COUNT(*), AVG(latency_ms), SUM(cost_usd)
            FROM chat_traces WHERE created_at > ?
            GROUP BY model ORDER BY COUNT(*) DESC''', (cutoff,))
        by_model = [{'model': r[0], 'calls': r[1],
                    'avg_latency_ms': round(r[2] or 0),
                    'cost_usd': round(r[3] or 0, 4)} for r in c.fetchall()]

        conn.close()
        return {
            'period_days':   days,
            'total_chats':   total or 0,
            'input_tokens':  in_tok or 0,
            'output_tokens': out_tok or 0,
            'total_cost_usd': round(cost or 0, 4),
            'avg_latency_ms': round(avg_lat or 0),
            'groq_calls':    groq_calls or 0,
            'anthropic_calls': (total or 0) - (groq_calls or 0),
            'by_model':      by_model,
        }
    except Exception as e:
        return {'error': str(e)}


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

def _verify_owner(token: str) -> bool:
    expected = _ENV.get('OWNER_TOKEN', '')
    import hmac
    return bool(expected) and hmac.compare_digest(str(token), str(expected))


@observe_bp.route('/api/observe/accuracy')
def accuracy_route():
    """Star's public accuracy track record."""
    return jsonify(get_accuracy_stats())


@observe_bp.route('/api/observe/resolve', methods=['POST'])
def resolve_route():
    """Resolve a prediction against actual price."""
    data  = request.get_json() or {}
    pid   = data.get('pred_id', '')
    price = float(data.get('current_price', 0))
    if not pid or not price:
        return jsonify({'error': 'pred_id and current_price required'}), 400
    return jsonify(resolve_prediction(pid, price))


@observe_bp.route('/api/observe/score', methods=['POST'])
def score_route():
    """Score a chat interaction."""
    data  = request.get_json() or {}
    tid   = data.get('trace_id', '')
    score = float(data.get('score', 0.5))
    comment = data.get('comment', '')
    if not tid:
        return jsonify({'error': 'trace_id required'}), 400
    score_chat(tid, score, comment)
    return jsonify({'scored': True, 'trace_id': tid})


@observe_bp.route('/api/observe/dashboard', methods=['POST'])
def observe_dashboard():
    """Owner observability dashboard."""
    data  = request.get_json() or {}
    token = data.get('owner_token', '')
    if not _verify_owner(token):
        return jsonify({'error': 'Unauthorized'}), 403

    accuracy = get_accuracy_stats()
    costs    = get_cost_analytics(days=data.get('days', 7))

    try:
        conn = sqlite3.connect(OBSERVE_DB)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM vector_traces')
        v_total = c.fetchone()[0]
        c.execute('SELECT AVG(top_similarity) FROM vector_traces')
        v_avg_sim = c.fetchone()[0] or 0
        c.execute('SELECT COUNT(*) FROM vector_traces WHERE useful=0')
        v_low = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM signal_predictions WHERE resolved=0')
        pending = c.fetchone()[0]
        conn.close()
    except Exception:
        v_total = v_avg_sim = v_low = pending = 0

    return jsonify({
        'accuracy':     accuracy,
        'costs':        costs,
        'vector_stats': {
            'total_searches': v_total,
            'avg_similarity': round(v_avg_sim, 4),
            'low_quality_searches': v_low,
        },
        'pending_predictions': pending,
        'langfuse_connected': _langfuse is not None,
        'langfuse_host': _ENV.get('LANGFUSE_HOST', 'not configured'),
    })


@observe_bp.route('/api/observe/vector/stats')
def vector_stats():
    """Vector search quality stats."""
    try:
        conn = sqlite3.connect(OBSERVE_DB)
        c = conn.cursor()
        c.execute('''SELECT query_preview, top_similarity, avg_similarity, latency_ms
            FROM vector_traces ORDER BY created_at DESC LIMIT 20''')
        recent = [{'query': r[0], 'top_sim': r[1], 'avg_sim': r[2], 'ms': r[3]}
                  for r in c.fetchall()]
        c.execute('SELECT AVG(top_similarity), MIN(top_similarity), MAX(top_similarity) FROM vector_traces')
        row = c.fetchone()
        conn.close()
        return jsonify({
            'avg_top_similarity': round(row[0] or 0, 4),
            'min_similarity':     round(row[1] or 0, 4),
            'max_similarity':     round(row[2] or 0, 4),
            'recent_searches':    recent,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@observe_bp.route('/api/observe/status')
def observe_status():
    lf = get_langfuse()
    return jsonify({
        'status':           'active',
        'module':           'Star Observability Engine v1.0',
        'langfuse_connected': lf is not None,
        'langfuse_host':    _ENV.get('LANGFUSE_HOST', 'not configured'),
        'tracking': [
            'Chat traces (input, output, tokens, latency, cost)',
            'Signal predictions (symbol, direction, confidence)',
            'Prediction resolution (accuracy scoring)',
            'Vector search traces (query, similarity, retrieval quality)',
            'Model cost analytics (Groq vs Anthropic breakdown)',
        ],
    })
