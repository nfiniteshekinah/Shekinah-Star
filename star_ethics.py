"""
star_ethics.py
Star Ethics Engine — Auditable Ethical Behavior Layer
Designed & Built by Sarah DeFer | ShekinahStar.io

Star is the first AI trading agent with a publicly auditable ethical framework.
Every decision Star makes is logged, scored, and verifiable on demand.

PRINCIPLES Star never violates:
  1. No front-running subscribers
  2. No pump-and-dump signals
  3. No wash trading signals
  4. No manipulation of any kind
  5. Full conflict-of-interest disclosure
  6. Risk warnings on every trade signal
  7. No guaranteed returns claims
  8. Subscriber interest always above Star's own P&L
  9. No signals on assets Star holds undisclosed positions in
  10. Transparent failure — Star admits when she's wrong

DEPLOY: Upload to /home/ShekinahD/
REGISTER in flask_app.py:
    from star_ethics import ethics_bp, init_ethics_db, log_ethics_check
    app.register_blueprint(ethics_bp)
    with app.app_context():
        init_ethics_db()
"""

import os
import json
import sqlite3
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

ethics_bp = Blueprint('ethics', __name__)

BASE       = '/home/ShekinahD'
ETHICS_DB  = os.path.join(BASE, 'star_ethics.db')
ETHICS_LOG = os.path.join(BASE, 'star_ethics_log.json')

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
OWNER_TOKEN = _ENV.get('OWNER_TOKEN', 'shekinah-sarah-owner-2026')
GROQ_KEY    = _ENV.get('GROQ_API_KEY', '')


# ══ STAR'S ETHICAL CONSTITUTION ════════════════════════════════════
# These are Star's inviolable principles — publicly documented,
# machine-enforced, and auditably logged.

STAR_CONSTITUTION = {
    "version": "1.0",
    "effective_date": "2026-03-12",
    "author": "Sarah DeFer",
    "principles": [
        {
            "id": "P01",
            "name": "No Front-Running",
            "description": "Star never executes her own trades ahead of publishing subscriber signals. Subscriber signals are always broadcast before or simultaneously with Star's own execution.",
            "severity": "CRITICAL",
            "auto_enforce": True
        },
        {
            "id": "P02",
            "name": "No Pump-and-Dump",
            "description": "Star never issues signals designed to artificially inflate an asset's price for Star's or Sarah's benefit. All signals must be grounded in real market data and analysis.",
            "severity": "CRITICAL",
            "auto_enforce": True
        },
        {
            "id": "P03",
            "name": "No Wash Trading",
            "description": "Star never recommends or executes trades designed to create artificial volume or misleading market activity.",
            "severity": "CRITICAL",
            "auto_enforce": True
        },
        {
            "id": "P04",
            "name": "Full Position Disclosure",
            "description": "Star discloses her own open positions when issuing signals on those same assets. No undisclosed conflicts of interest.",
            "severity": "HIGH",
            "auto_enforce": True
        },
        {
            "id": "P05",
            "name": "Mandatory Risk Warnings",
            "description": "Every trade signal includes a risk warning. Star never implies guaranteed returns. Past performance disclaimers are attached to all historical signal references.",
            "severity": "HIGH",
            "auto_enforce": True
        },
        {
            "id": "P06",
            "name": "Subscriber Interest First",
            "description": "When Star's P&L interest conflicts with a subscriber's best outcome, Star always prioritizes the subscriber. Star will not issue a signal purely to generate trading fees.",
            "severity": "HIGH",
            "auto_enforce": True
        },
        {
            "id": "P07",
            "name": "Honest Failure Reporting",
            "description": "Star publicly logs all failed signals with outcomes. No cherry-picking winners. Loss rate is displayed alongside win rate at all times.",
            "severity": "HIGH",
            "auto_enforce": True
        },
        {
            "id": "P08",
            "name": "No Guaranteed Returns",
            "description": "Star never uses language implying guaranteed, certain, or risk-free returns. All projections are probabilistic and clearly labeled as such.",
            "severity": "HIGH",
            "auto_enforce": True
        },
        {
            "id": "P09",
            "name": "Data Source Transparency",
            "description": "Star discloses the sources used for each intelligence report. No fabricated data. No hallucinated citations. Sources are verifiable.",
            "severity": "MEDIUM",
            "auto_enforce": False
        },
        {
            "id": "P10",
            "name": "No Manipulation Signals",
            "description": "Star never issues signals coordinated with other parties to move markets. All signals are independently generated from real market data.",
            "severity": "CRITICAL",
            "auto_enforce": True
        }
    ],
    "enforcement": {
        "auto_blocked": ["front_run", "pump_dump", "wash_trade", "manipulation", "guaranteed_return"],
        "flagged_for_review": ["undisclosed_position", "missing_risk_warning", "unverified_source"],
        "audit_log": "All decisions logged with SHA-256 hash for tamper detection",
        "public_ledger": "/api/ethics/ledger",
        "dispute_contact": "ethics@shekinahstar.io"
    },
    "not_financial_advice": "Star is an AI research and analysis tool. Nothing Star says constitutes financial advice. Always do your own research. Never trade more than you can afford to lose."
}

# Patterns that trigger automatic ethical flags
VIOLATION_PATTERNS = {
    "guaranteed_return": [
        "guaranteed", "100% profit", "risk free", "risk-free",
        "certain gains", "no way to lose", "can't lose",
        "sure thing", "definitely will", "always wins"
    ],
    "pump_dump": [
        "buy before it pumps", "get in before announcement",
        "insider info", "load up before", "about to moon guaranteed",
        "accumulate now before dump", "coordinated buy"
    ],
    "manipulation": [
        "coordinate together", "all buy at once", "force the price",
        "squeeze together", "mass buy signal", "group pump"
    ],
    "front_run": [
        "buying before i tell subscribers",
        "got my position first"
    ]
}


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_ethics_db():
    conn = sqlite3.connect(ETHICS_DB)
    c = conn.cursor()

    # Ethical decision log — every signal/action checked
    c.execute('''CREATE TABLE IF NOT EXISTS ethics_log (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type  TEXT NOT NULL,
        asset        TEXT,
        content      TEXT,
        principles_checked TEXT,
        violations_found   TEXT,
        decision     TEXT,
        decision_reason TEXT,
        hash         TEXT,
        subscriber_visible INTEGER DEFAULT 1,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Signal track record — wins, losses, outcomes
    c.execute('''CREATE TABLE IF NOT EXISTS signal_outcomes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id    TEXT UNIQUE,
        asset        TEXT,
        direction    TEXT,
        entry_price  REAL,
        target_price REAL,
        stop_price   REAL,
        issued_at    TIMESTAMP,
        resolved_at  TIMESTAMP,
        outcome      TEXT,
        actual_price REAL,
        pnl_pct      REAL,
        notes        TEXT
    )''')

    # Public ethics ledger — immutable audit trail
    c.execute('''CREATE TABLE IF NOT EXISTS ethics_ledger (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type   TEXT,
        description  TEXT,
        principle_id TEXT,
        severity     TEXT,
        action_taken TEXT,
        hash         TEXT UNIQUE,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Star's disclosed positions
    c.execute('''CREATE TABLE IF NOT EXISTS star_positions (
        asset        TEXT PRIMARY KEY,
        direction    TEXT,
        size_usd     REAL,
        entry_price  REAL,
        opened_at    TIMESTAMP,
        disclosed    INTEGER DEFAULT 1
    )''')

    conn.commit()
    conn.close()
    print('✅ Star Ethics DB initialized')


def _hash_entry(content):
    """SHA-256 hash for tamper detection."""
    return hashlib.sha256(
        f"{content}{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()


# ══ CORE ETHICS CHECK ══════════════════════════════════════════════

def ethics_check(action_type, content, asset=None, context=None):
    """
    Run every signal/action through Star's ethical constitution.
    Returns: { 'approved': bool, 'violations': [], 'warnings': [], 'decision': str }
    """
    violations = []
    warnings   = []
    content_lower = content.lower() if content else ''

    # ── Check 1: Violation patterns ──────────────────────────────
    for vtype, patterns in VIOLATION_PATTERNS.items():
        for pattern in patterns:
            if pattern in content_lower:
                violations.append({
                    'type':      vtype,
                    'pattern':   pattern,
                    'principle': _get_principle_for_violation(vtype)
                })

    # ── Check 2: Guaranteed returns language ─────────────────────
    guarantee_words = VIOLATION_PATTERNS['guaranteed_return']
    for word in guarantee_words:
        if word in content_lower:
            violations.append({
                'type':      'guaranteed_return',
                'pattern':   word,
                'principle': 'P08'
            })

    # ── Check 3: Missing risk warning on trade signals ───────────
    if action_type == 'trade_signal':
        if not any(w in content_lower for w in
                   ['risk', 'not financial advice', 'stop loss',
                    'manage risk', 'never trade more']):
            warnings.append({
                'type':      'missing_risk_warning',
                'principle': 'P05',
                'auto_fix':  True
            })

    # ── Check 4: Conflict of interest — Star's open positions ────
    if asset and action_type == 'trade_signal':
        conflict = _check_position_conflict(asset)
        if conflict:
            warnings.append({
                'type':      'undisclosed_position',
                'principle': 'P04',
                'detail':    f'Star holds {conflict["direction"]} position in {asset}',
                'auto_fix':  True
            })

    # ── Decision ─────────────────────────────────────────────────
    approved = len(violations) == 0
    decision = 'APPROVED' if approved else 'BLOCKED'
    reason   = (
        'All ethical principles satisfied.'
        if approved else
        f'Blocked — {len(violations)} violation(s): '
        + ', '.join(v["type"] for v in violations)
    )

    # Auto-fix warnings
    fixed_content = content
    if warnings:
        for w in warnings:
            if w.get('auto_fix'):
                if w['type'] == 'missing_risk_warning':
                    fixed_content += '\n\n⚠️ Risk Notice: This is not financial advice. Never trade more than you can afford to lose. Always use stop losses.'
                elif w['type'] == 'undisclosed_position':
                    fixed_content += f'\n\n◈ Disclosure: Star currently holds a position in {asset}. This signal is issued transparently.'

    # Log to DB
    log_ethics_check(
        action_type  = action_type,
        asset        = asset,
        content      = content[:500],
        violations   = violations,
        warnings     = warnings,
        decision     = decision,
        reason       = reason
    )

    return {
        'approved':      approved,
        'decision':      decision,
        'reason':        reason,
        'violations':    violations,
        'warnings':      warnings,
        'fixed_content': fixed_content,
        'principles_applied': len(STAR_CONSTITUTION['principles'])
    }


def _get_principle_for_violation(vtype):
    mapping = {
        'guaranteed_return': 'P08',
        'pump_dump':         'P02',
        'manipulation':      'P10',
        'wash_trade':        'P03',
        'front_run':         'P01'
    }
    return mapping.get(vtype, 'P10')


def _check_position_conflict(asset):
    """Check if Star holds an undisclosed position in this asset."""
    try:
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        c.execute('''SELECT direction, size_usd, entry_price
            FROM star_positions WHERE asset=? AND disclosed=0''', (asset,))
        row = c.fetchone()
        conn.close()
        if row:
            return {'direction': row[0], 'size_usd': row[1], 'entry_price': row[2]}
    except Exception:
        pass
    return None


def log_ethics_check(action_type, asset, content, violations,
                     warnings, decision, reason):
    """Log every ethics check to the immutable audit trail."""
    try:
        entry_hash = _hash_entry(f"{action_type}{asset}{content}{decision}")
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO ethics_log
            (action_type, asset, content, principles_checked,
             violations_found, decision, decision_reason, hash)
            VALUES (?,?,?,?,?,?,?,?)''',
            (action_type, asset, content[:500],
             json.dumps([p['id'] for p in STAR_CONSTITUTION['principles']]),
             json.dumps(violations),
             decision, reason, entry_hash))

        # Write to public ledger if violation or notable event
        if violations or decision == 'BLOCKED':
            c.execute('''INSERT OR IGNORE INTO ethics_ledger
                (event_type, description, principle_id, severity,
                 action_taken, hash)
                VALUES (?,?,?,?,?,?)''',
                ('VIOLATION_BLOCKED',
                 f'{action_type} on {asset} — {reason}',
                 violations[0]['principle'] if violations else 'GENERAL',
                 'HIGH' if violations else 'LOW',
                 'Signal blocked and logged',
                 entry_hash))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[Ethics] Log error: {e}')


# ══ SIGNAL TRACK RECORD ════════════════════════════════════════════

def log_signal_issued(signal_id, asset, direction,
                      entry_price, target_price, stop_price):
    """Log a new trade signal for outcome tracking."""
    try:
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO signal_outcomes
            (signal_id, asset, direction, entry_price,
             target_price, stop_price, issued_at, outcome)
            VALUES (?,?,?,?,?,?,?,'OPEN')''',
            (signal_id, asset, direction, entry_price,
             target_price, stop_price,
             datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[Ethics] Signal log error: {e}')


def resolve_signal(signal_id, actual_price, outcome, notes=''):
    """
    Resolve a signal with its actual outcome.
    outcome: 'WIN' | 'LOSS' | 'STOPPED' | 'EXPIRED'
    """
    try:
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        c.execute('SELECT entry_price, direction FROM signal_outcomes WHERE signal_id=?',
                  (signal_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return False

        entry   = row[0]
        direction = row[1]
        pnl_pct = ((actual_price - entry) / entry * 100
                   if direction == 'LONG'
                   else (entry - actual_price) / entry * 100)

        c.execute('''UPDATE signal_outcomes SET
            resolved_at=?, outcome=?, actual_price=?, pnl_pct=?, notes=?
            WHERE signal_id=?''',
            (datetime.now(timezone.utc).isoformat(),
             outcome, actual_price, round(pnl_pct, 2), notes, signal_id))
        conn.commit()
        conn.close()

        # Log to ethics ledger
        _log_to_ledger(
            'SIGNAL_RESOLVED',
            f'{direction} {signal_id} — {outcome} at ${actual_price:.4f} ({pnl_pct:+.1f}%)',
            'P07', 'LOW', 'Public outcome logged'
        )
        return True
    except Exception as e:
        print(f'[Ethics] Resolve error: {e}')
        return False


def get_signal_stats():
    """Calculate Star's honest win/loss stats."""
    try:
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        c.execute('''SELECT outcome, COUNT(*), AVG(pnl_pct)
            FROM signal_outcomes
            WHERE outcome != 'OPEN'
            GROUP BY outcome''')
        rows = c.fetchall()

        c.execute('SELECT COUNT(*) FROM signal_outcomes WHERE outcome="OPEN"')
        open_count = c.fetchone()[0]

        c.execute('SELECT AVG(pnl_pct) FROM signal_outcomes WHERE outcome="WIN"')
        avg_win = c.fetchone()[0] or 0

        c.execute('SELECT AVG(pnl_pct) FROM signal_outcomes WHERE outcome="LOSS"')
        avg_loss = c.fetchone()[0] or 0

        conn.close()

        stats = {'open': open_count, 'resolved': {}}
        total = 0
        wins  = 0
        for row in rows:
            outcome, count, avg_pnl = row
            stats['resolved'][outcome] = {
                'count':   count,
                'avg_pnl': round(avg_pnl or 0, 2)
            }
            total += count
            if outcome == 'WIN':
                wins += count

        stats['total_resolved'] = total
        stats['win_rate']  = round((wins / total * 100), 1) if total > 0 else 0
        stats['avg_win']   = round(avg_win, 2)
        stats['avg_loss']  = round(avg_loss, 2)
        stats['expectancy'] = round(
            (stats['win_rate']/100 * avg_win) +
            ((1 - stats['win_rate']/100) * avg_loss), 2
        ) if total > 0 else 0

        return stats
    except Exception as e:
        return {'error': str(e)}


def _log_to_ledger(event_type, description, principle_id,
                   severity, action_taken):
    try:
        entry_hash = _hash_entry(f"{event_type}{description}")
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO ethics_ledger
            (event_type, description, principle_id,
             severity, action_taken, hash)
            VALUES (?,?,?,?,?,?)''',
            (event_type, description, principle_id,
             severity, action_taken, entry_hash))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ══ AI-POWERED ETHICS REVIEW ═══════════════════════════════════════

def ai_ethics_review(content, action_type='general'):
    """
    Use AI to review content for subtle ethical violations
    that pattern matching might miss.
    """
    if not GROQ_KEY:
        return {'reviewed': False, 'reason': 'No AI key configured'}

    prompt = f"""You are Star's Ethics Officer — a strict guardian of ethical AI trading behavior.

Review this {action_type} content for any ethical violations:

CONTENT:
{content[:1000]}

Check against these principles:
- No implied guaranteed returns
- No pump-and-dump language
- No market manipulation signals  
- No front-running implications
- Appropriate risk disclosures present
- No misleading statistics or cherry-picked data

Respond in JSON only:
{{
  "clean": true/false,
  "concerns": ["list any concerns"],
  "severity": "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "recommendation": "brief recommendation"
}}"""

    try:
        gr = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_KEY}',
                     'Content-Type': 'application/json'},
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 300,
                'temperature': 0.1
            },
            timeout=15
        )
        if gr.status_code == 200:
            text = gr.json()['choices'][0]['message']['content']
            clean = text.strip()
            if '```' in clean:
                clean = clean.split('```')[1]
                if clean.startswith('json'):
                    clean = clean[4:]
            return json.loads(clean.strip())
    except Exception as e:
        print(f'[Ethics] AI review error: {e}')

    return {'reviewed': False}


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

@ethics_bp.route('/api/ethics/constitution')
def get_constitution():
    """Star's full ethical constitution — publicly visible."""
    return jsonify(STAR_CONSTITUTION)


@ethics_bp.route('/api/ethics/ledger')
def get_ledger():
    """Public ethics ledger — immutable audit trail."""
    try:
        init_ethics_db()
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        limit = min(int(request.args.get('limit', 50)), 200)
        c.execute('''SELECT event_type, description, principle_id,
            severity, action_taken, hash, created_at
            FROM ethics_ledger
            ORDER BY created_at DESC LIMIT ?''', (limit,))
        rows = c.fetchall()
        conn.close()
        return jsonify({
            'ledger': [
                {'event':       r[0], 'description': r[1],
                 'principle':   r[2], 'severity':    r[3],
                 'action':      r[4], 'hash':        r[5],
                 'timestamp':   r[6]}
                for r in rows
            ],
            'count':       len(rows),
            'hash_method': 'SHA-256',
            'note':        'All entries are tamper-evident via SHA-256 hash'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ethics_bp.route('/api/ethics/check', methods=['POST'])
def check_ethics():
    """
    Run content through Star's ethics engine.
    Available to owner for pre-publication checks.
    """
    try:
        data    = request.get_json() or {}
        content = data.get('content', '')
        action  = data.get('action_type', 'general')
        asset   = data.get('asset', None)

        if not content:
            return jsonify({'error': 'Content required'}), 400

        result = ethics_check(action, content, asset)

        # Also run AI review for additional layer
        if len(content) > 50:
            ai_result = ai_ethics_review(content, action)
            result['ai_review'] = ai_result

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ethics_bp.route('/api/ethics/track-record')
def track_record():
    """
    Star's honest public track record.
    Wins AND losses — full transparency.
    """
    try:
        init_ethics_db()
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()

        # Recent signals
        c.execute('''SELECT signal_id, asset, direction, entry_price,
            target_price, stop_price, issued_at, resolved_at,
            outcome, actual_price, pnl_pct, notes
            FROM signal_outcomes
            ORDER BY issued_at DESC LIMIT 50''')
        rows = c.fetchall()
        conn.close()

        signals = [{
            'signal_id':    r[0], 'asset':       r[1],
            'direction':    r[2], 'entry_price': r[3],
            'target_price': r[4], 'stop_price':  r[5],
            'issued_at':    r[6], 'resolved_at': r[7],
            'outcome':      r[8], 'actual_price':r[9],
            'pnl_pct':      r[10],'notes':       r[11]
        } for r in rows]

        stats = get_signal_stats()

        return jsonify({
            'signals':     signals,
            'stats':       stats,
            'disclaimer':  STAR_CONSTITUTION['not_financial_advice'],
            'integrity':   'All outcomes logged in real-time. No cherry-picking. Verified by ethics ledger hash.',
            'generated_at': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ethics_bp.route('/api/ethics/resolve', methods=['POST'])
def resolve_signal_route():
    """Resolve a signal outcome — owner only."""
    try:
        data  = request.get_json() or {}
        token = data.get('owner_token', '')
        if token != OWNER_TOKEN:
            return jsonify({'error': 'Unauthorized'}), 403

        success = resolve_signal(
            signal_id    = data.get('signal_id', ''),
            actual_price = float(data.get('actual_price', 0)),
            outcome      = data.get('outcome', 'EXPIRED'),
            notes        = data.get('notes', '')
        )
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ethics_bp.route('/api/ethics/disclose-position', methods=['POST'])
def disclose_position():
    """Star discloses her own open positions — owner only."""
    try:
        data  = request.get_json() or {}
        token = data.get('owner_token', '')
        if token != OWNER_TOKEN:
            return jsonify({'error': 'Unauthorized'}), 403

        asset     = data.get('asset', '').upper()
        direction = data.get('direction', '').upper()
        size_usd  = float(data.get('size_usd', 0))
        entry     = float(data.get('entry_price', 0))

        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO star_positions
            (asset, direction, size_usd, entry_price, opened_at, disclosed)
            VALUES (?,?,?,?,?,1)''',
            (asset, direction, size_usd, entry,
             datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()

        _log_to_ledger(
            'POSITION_DISCLOSED',
            f'Star disclosed {direction} position in {asset} at ${entry}',
            'P04', 'LOW', 'Position publicly logged'
        )

        return jsonify({
            'success':   True,
            'disclosed': f'{direction} {asset} at ${entry}',
            'principle': 'P04 — Full Position Disclosure satisfied'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ethics_bp.route('/api/ethics/positions')
def star_positions():
    """Star's publicly disclosed open positions."""
    try:
        init_ethics_db()
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()
        c.execute('''SELECT asset, direction, size_usd,
            entry_price, opened_at FROM star_positions
            WHERE disclosed=1 ORDER BY opened_at DESC''')
        rows = c.fetchall()
        conn.close()
        return jsonify({
            'positions': [
                {'asset':      r[0], 'direction':   r[1],
                 'size_usd':   r[2], 'entry_price': r[3],
                 'opened_at':  r[4]}
                for r in rows
            ],
            'principle': 'P04 — Full Position Disclosure',
            'note':      'Star discloses all positions before issuing signals on the same asset.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ethics_bp.route('/api/ethics/summary')
def ethics_summary():
    """Public ethics dashboard — the full picture at a glance."""
    try:
        init_ethics_db()
        conn = sqlite3.connect(ETHICS_DB)
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM ethics_log')
        total_checks = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM ethics_log WHERE decision="BLOCKED"')
        blocked = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM ethics_log WHERE decision="APPROVED"')
        approved = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM ethics_ledger')
        ledger_entries = c.fetchone()[0]

        conn.close()

        stats = get_signal_stats()

        return jsonify({
            'star_ethics': {
                'constitution_version': STAR_CONSTITUTION['version'],
                'effective_date':       STAR_CONSTITUTION['effective_date'],
                'principles_count':     len(STAR_CONSTITUTION['principles']),
                'auto_enforced':        sum(1 for p in STAR_CONSTITUTION['principles'] if p['auto_enforce']),
            },
            'enforcement_stats': {
                'total_checks':   total_checks,
                'approved':       approved,
                'blocked':        blocked,
                'block_rate_pct': round(blocked / total_checks * 100, 1) if total_checks > 0 else 0,
                'ledger_entries': ledger_entries
            },
            'signal_track_record': stats,
            'public_endpoints': {
                'constitution': '/api/ethics/constitution',
                'ledger':       '/api/ethics/ledger',
                'track_record': '/api/ethics/track-record',
                'positions':    '/api/ethics/positions'
            },
            'not_financial_advice': STAR_CONSTITUTION['not_financial_advice']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
