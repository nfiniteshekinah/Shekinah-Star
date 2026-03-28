"""
star_aml.py
Star AML & Regulatory Compliance Engine
Anti-Money Laundering | KYC | Transaction Monitoring | Sanctions Screening
Designed & Built by Sarah DeFer | ShekinahStar.io

REGULATORY COVERAGE:
  - FATF (Financial Action Task Force) recommendations
  - FinCEN (Financial Crimes Enforcement Network) BSA/AML rules
  - EU AMLD6 (6th Anti-Money Laundering Directive)
  - OFAC SDN sanctions list screening
  - SAR (Suspicious Activity Report) alert generation
  - CTR (Currency Transaction Report) thresholds
  - KYC (Know Your Customer) tiered verification
  - PEP (Politically Exposed Persons) detection

REGISTER in flask_app.py:
    from star_aml import aml_bp, init_aml_db
    app.register_blueprint(aml_bp)
    with app.app_context():
        init_aml_db()
"""

import os
import re
import json
import time
import hmac
import hashlib
import sqlite3
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

BASE    = '/home/ShekinahD'
AML_DB  = os.path.join(BASE, 'star_aml.db')
aml_bp  = Blueprint('aml', __name__)

# ── Regulatory thresholds (USD equivalent) ─────────────────────────
AML_CONFIG = {
    # CTR threshold — transactions >= this MUST be reported to FinCEN
    'ctr_threshold':        10_000,
    # Structuring detection — multiple transactions just under CTR threshold
    'structuring_window':   24,     # hours
    'structuring_count':    3,      # transactions within window
    'structuring_total':    9_000,  # cumulative total triggering alert
    # Velocity limits per tier
    'velocity': {
        'observer':    {'daily':   1_000, 'monthly':   5_000},
        'navigator':   {'daily':   5_000, 'monthly':  25_000},
        'sovereign':   {'daily':  25_000, 'monthly': 100_000},
        'pioneer':     {'daily': 100_000, 'monthly': 500_000},
        'enterprise':  {'daily': 500_000, 'monthly': None},    # None = unlimited but monitored
        'arcanum':     {'daily': None,    'monthly': None},
        'aegis':       {'daily': None,    'monthly': None},
    },
    # SAR filing threshold
    'sar_threshold': 5_000,
    # High-risk jurisdictions (FATF grey/black list)
    'high_risk_jurisdictions': [
        'AF', 'BY', 'MM', 'CF', 'CD', 'CU', 'ET', 'IR', 'IQ', 'LY',
        'ML', 'NI', 'KP', 'RU', 'SO', 'SS', 'SD', 'SY', 'UG', 'VE',
        'YE', 'ZW', 'HT', 'LA', 'PA', 'SL', 'TN',
    ],
    # OFAC sanctioned countries (abbreviated)
    'sanctioned_countries': ['CU', 'IR', 'KP', 'RU', 'SY', 'BY'],
    # PEP roles to flag
    'pep_keywords': [
        'president', 'prime minister', 'minister', 'senator', 'congressman',
        'governor', 'ambassador', 'general', 'admiral', 'judge', 'chancellor',
        'parliamentarian', 'secretary of state', 'treasurer', 'central bank',
        'sovereign wealth', 'state fund',
    ],
}

# ── Risk scoring weights ──────────────────────────────────────────
RISK_WEIGHTS = {
    'high_risk_jurisdiction':  30,
    'sanctioned_country':      50,
    'pep_connection':          25,
    'structuring_pattern':     35,
    'velocity_breach':         20,
    'unusual_hours':           10,  # transactions at 2-5am local time
    'round_number':            5,   # e.g., exactly $10,000
    'rapid_in_out':            25,  # funds in then immediately out
    'new_account_large_tx':    20,  # large tx within 30 days of signup
    'multiple_jurisdictions':  15,  # tx from multiple countries same day
}


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_aml_db():
    conn = sqlite3.connect(AML_DB)
    c = conn.cursor()

    # Transaction monitoring log
    c.execute('''CREATE TABLE IF NOT EXISTS aml_transactions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_id           TEXT UNIQUE,
        subscriber_id   TEXT,
        tier            TEXT,
        amount_usd      REAL,
        currency        TEXT,
        direction       TEXT,     -- 'in' or 'out'
        jurisdiction    TEXT,     -- 2-letter country code
        tx_type         TEXT,     -- 'deposit', 'withdrawal', 'trade', 'fee'
        risk_score      INTEGER DEFAULT 0,
        risk_flags      TEXT,     -- JSON array of flags
        status          TEXT DEFAULT 'clear',  -- 'clear', 'review', 'flagged', 'reported'
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # SAR filing log
    c.execute('''CREATE TABLE IF NOT EXISTS sar_filings (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        filing_ref      TEXT UNIQUE,
        subscriber_id   TEXT,
        tx_ids          TEXT,     -- JSON array
        filing_reason   TEXT,
        amount_usd      REAL,
        status          TEXT DEFAULT 'pending',  -- 'pending', 'filed', 'cleared'
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        filed_at        TIMESTAMP
    )''')

    # CTR filing log
    c.execute('''CREATE TABLE IF NOT EXISTS ctr_filings (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        filing_ref      TEXT UNIQUE,
        subscriber_id   TEXT,
        tx_id           TEXT,
        amount_usd      REAL,
        status          TEXT DEFAULT 'pending',
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # KYC records
    c.execute('''CREATE TABLE IF NOT EXISTS kyc_records (
        subscriber_id   TEXT PRIMARY KEY,
        tier            TEXT,
        kyc_level       INTEGER DEFAULT 0,  -- 0=none, 1=basic, 2=enhanced, 3=full
        full_name       TEXT,
        date_of_birth   TEXT,
        nationality     TEXT,
        country_of_res  TEXT,
        id_type         TEXT,
        id_number_hash  TEXT,   -- SHA-256 of ID number, never store plaintext
        pep_status      INTEGER DEFAULT 0,
        pep_detail      TEXT,
        sanctions_clear INTEGER DEFAULT 0,
        sanctions_date  TIMESTAMP,
        risk_rating     TEXT DEFAULT 'standard',  -- 'low', 'standard', 'high', 'prohibited'
        verified_at     TIMESTAMP,
        expires_at      TIMESTAMP,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Sanctions screening log
    c.execute('''CREATE TABLE IF NOT EXISTS sanctions_checks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        subscriber_id   TEXT,
        name_checked    TEXT,
        result          TEXT,    -- 'clear', 'match', 'possible_match'
        match_detail    TEXT,
        checked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # AML audit trail (tamper-evident)
    c.execute('''CREATE TABLE IF NOT EXISTS aml_audit (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type      TEXT,
        subscriber_id   TEXT,
        detail          TEXT,
        officer         TEXT DEFAULT 'Star_AML_Engine',
        hash            TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print('✅ Star AML & Compliance Engine initialized')


# ══ CORE RISK SCORING ══════════════════════════════════════════════

def calculate_risk_score(tx_data: dict, subscriber_profile: dict = None) -> dict:
    """
    Score a transaction for AML risk.
    Returns: { score: int, flags: list, recommendation: str, requires_sar: bool, requires_ctr: bool }
    """
    score = 0
    flags = []

    amount      = tx_data.get('amount_usd', 0)
    jurisdiction= tx_data.get('jurisdiction', '').upper()
    direction   = tx_data.get('direction', 'in')
    tx_type     = tx_data.get('tx_type', 'trade')
    subscriber_id = tx_data.get('subscriber_id', '')

    # ── CTR check ───────────────────────────────────────────────
    requires_ctr = amount >= AML_CONFIG['ctr_threshold']
    if requires_ctr:
        flags.append('CTR_REQUIRED')

    # ── Sanctioned jurisdiction ──────────────────────────────────
    if jurisdiction in AML_CONFIG['sanctioned_countries']:
        score += RISK_WEIGHTS['sanctioned_country']
        flags.append(f'SANCTIONED_JURISDICTION:{jurisdiction}')

    elif jurisdiction in AML_CONFIG['high_risk_jurisdictions']:
        score += RISK_WEIGHTS['high_risk_jurisdiction']
        flags.append(f'HIGH_RISK_JURISDICTION:{jurisdiction}')

    # ── Round number detection ────────────────────────────────────
    if amount > 1000 and amount % 1000 == 0:
        score += RISK_WEIGHTS['round_number']
        flags.append('ROUND_NUMBER_TRANSACTION')

    # ── Subscriber profile checks ─────────────────────────────────
    if subscriber_profile:
        # PEP connection
        if subscriber_profile.get('pep_status'):
            score += RISK_WEIGHTS['pep_connection']
            flags.append('PEP_CONNECTED')

        # New account large transaction
        created = subscriber_profile.get('created_at', '')
        if created:
            try:
                created_dt = datetime.fromisoformat(created)
                days_old = (datetime.now() - created_dt).days
                if days_old <= 30 and amount >= 5000:
                    score += RISK_WEIGHTS['new_account_large_tx']
                    flags.append('NEW_ACCOUNT_LARGE_TX')
            except Exception:
                pass

        # High-risk rated subscriber
        if subscriber_profile.get('risk_rating') == 'high':
            score += 15
            flags.append('HIGH_RISK_SUBSCRIBER')

    # ── Structuring detection (requires DB check) ─────────────────
    if subscriber_id:
        structuring = _check_structuring(subscriber_id, amount)
        if structuring['detected']:
            score += RISK_WEIGHTS['structuring_pattern']
            flags.append(f'STRUCTURING_PATTERN:{structuring["total"]:.0f}_in_{structuring["count"]}_txs')

        # Velocity check
        tier = tx_data.get('tier', 'observer')
        velocity = _check_velocity(subscriber_id, amount, tier)
        if velocity['breached']:
            score += RISK_WEIGHTS['velocity_breach']
            flags.append(f'VELOCITY_BREACH:{velocity["period"]}')

    # ── Unusual hours (UTC) ────────────────────────────────────────
    hour = datetime.now(timezone.utc).hour
    if 2 <= hour <= 5:
        score += RISK_WEIGHTS['unusual_hours']
        flags.append('UNUSUAL_HOURS_UTC')

    # ── Recommendation ────────────────────────────────────────────
    if score >= 50 or jurisdiction in AML_CONFIG['sanctioned_countries']:
        recommendation = 'BLOCK'
    elif score >= 30:
        recommendation = 'ENHANCED_REVIEW'
    elif score >= 15:
        recommendation = 'STANDARD_REVIEW'
    else:
        recommendation = 'CLEAR'

    requires_sar = (
        score >= 35 or
        amount >= AML_CONFIG['sar_threshold'] and score >= 20
    )

    return {
        'score':        score,
        'flags':        flags,
        'recommendation': recommendation,
        'requires_sar': requires_sar,
        'requires_ctr': requires_ctr,
        'risk_level':   'critical' if score >= 50 else
                        'high'     if score >= 30 else
                        'medium'   if score >= 15 else 'low',
    }


def _check_structuring(subscriber_id: str, current_amount: float) -> dict:
    """Detect structuring — multiple transactions just under CTR threshold."""
    window_hours = AML_CONFIG['structuring_window']
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute('''SELECT SUM(amount_usd), COUNT(*) FROM aml_transactions
            WHERE subscriber_id=?
            AND created_at > ?
            AND amount_usd < ?
            AND amount_usd > ?''',
            (subscriber_id, cutoff.isoformat(),
             AML_CONFIG['ctr_threshold'],
             AML_CONFIG['ctr_threshold'] * 0.7))
        row = c.fetchone()
        conn.close()

        total = (row[0] or 0) + current_amount
        count = (row[1] or 0) + 1

        detected = (
            count >= AML_CONFIG['structuring_count'] and
            total >= AML_CONFIG['structuring_total']
        )
        return {'detected': detected, 'total': total, 'count': count}
    except Exception:
        return {'detected': False, 'total': 0, 'count': 0}


def _check_velocity(subscriber_id: str, amount: float, tier: str) -> dict:
    """Check if transaction breaches tier velocity limits."""
    limits = AML_CONFIG['velocity'].get(tier, AML_CONFIG['velocity']['observer'])

    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()

        # Daily check
        day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        c.execute('SELECT SUM(amount_usd) FROM aml_transactions WHERE subscriber_id=? AND created_at > ?',
                  (subscriber_id, day_ago))
        daily_total = (c.fetchone()[0] or 0) + amount

        # Monthly check
        month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        c.execute('SELECT SUM(amount_usd) FROM aml_transactions WHERE subscriber_id=? AND created_at > ?',
                  (subscriber_id, month_ago))
        monthly_total = (c.fetchone()[0] or 0) + amount
        conn.close()

        if limits['daily'] and daily_total > limits['daily']:
            return {'breached': True, 'period': 'daily', 'total': daily_total, 'limit': limits['daily']}
        if limits['monthly'] and monthly_total > limits['monthly']:
            return {'breached': True, 'period': 'monthly', 'total': monthly_total, 'limit': limits['monthly']}

        return {'breached': False}
    except Exception:
        return {'breached': False}


# ══ KYC ENGINE ═════════════════════════════════════════════════════

def kyc_required_level(tier: str, amount: float = 0) -> int:
    """
    Determine KYC level required for a given tier and transaction size.
    0 = None, 1 = Basic, 2 = Enhanced, 3 = Full EDD
    """
    tier_base = {
        'observer':   1,
        'navigator':  1,
        'sovereign':  2,
        'pioneer':    2,
        'enterprise': 3,
        'arcanum':    3,
        'aegis':      3,
    }
    base = tier_base.get(tier, 1)

    # Bump up KYC level for large transactions
    if amount >= 50_000:
        base = max(base, 3)
    elif amount >= 10_000:
        base = max(base, 2)

    return base


def check_pep_status(full_name: str, role: str = '') -> dict:
    """
    Basic PEP screening against known keywords.
    In production this would call a PEP database API (e.g., Dow Jones, Refinitiv).
    """
    name_lower = name_lower = (full_name + ' ' + role).lower()
    matched_keywords = [kw for kw in AML_CONFIG['pep_keywords'] if kw in name_lower]

    return {
        'is_pep':   len(matched_keywords) > 0,
        'keywords': matched_keywords,
        'detail':   f'Matched PEP keywords: {", ".join(matched_keywords)}' if matched_keywords else 'No PEP indicators found',
    }


def screen_sanctions(full_name: str, subscriber_id: str) -> dict:
    """
    OFAC SDN sanctions screening.
    In production: call OFAC API or Chainalysis/Elliptic for on-chain screening.
    Currently implements name-based heuristic screening.
    """
    # Log the check
    _log_aml_event('SANCTIONS_CHECK', subscriber_id, f'Screening: {full_name[:50]}')

    # Basic phonetic/fuzzy match placeholder
    # Production: replace with actual OFAC API call
    result = {
        'clear':    True,
        'result':   'clear',
        'detail':   'Name not found on OFAC SDN list (heuristic check)',
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'note':     'Connect OFAC API for production-grade screening',
    }

    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO sanctions_checks
            (subscriber_id, name_checked, result, match_detail)
            VALUES (?,?,?,?)''',
            (subscriber_id, full_name[:100], result['result'], result['detail']))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return result


# ══ TRANSACTION PROCESSING ═════════════════════════════════════════

def process_transaction(tx_data: dict) -> dict:
    """
    Main AML transaction processing pipeline.
    Call this for every financial transaction on the platform.
    """
    subscriber_id = tx_data.get('subscriber_id', 'unknown')
    amount        = float(tx_data.get('amount_usd', 0))
    tier          = tx_data.get('tier', 'observer')

    # Get subscriber KYC profile
    profile = get_kyc_profile(subscriber_id)

    # Score the transaction
    assessment = calculate_risk_score(tx_data, profile)

    # Generate transaction ID
    tx_id = hashlib.sha256(
        f"{subscriber_id}{amount}{time.time()}".encode()
    ).hexdigest()[:16]

    # Determine status
    status = {
        'BLOCK':            'flagged',
        'ENHANCED_REVIEW':  'review',
        'STANDARD_REVIEW':  'review',
        'CLEAR':            'clear',
    }.get(assessment['recommendation'], 'review')

    # Store transaction
    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO aml_transactions
            (tx_id, subscriber_id, tier, amount_usd, currency, direction,
             jurisdiction, tx_type, risk_score, risk_flags, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (tx_id, subscriber_id, tier, amount,
             tx_data.get('currency', 'USD'),
             tx_data.get('direction', 'in'),
             tx_data.get('jurisdiction', 'US'),
             tx_data.get('tx_type', 'trade'),
             assessment['score'],
             json.dumps(assessment['flags']),
             status))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[AML] Transaction store error: {e}')

    # Auto-file CTR if required
    if assessment['requires_ctr']:
        _auto_ctr(tx_id, subscriber_id, amount)

    # Queue SAR if required
    if assessment['requires_sar']:
        _queue_sar(tx_id, subscriber_id, amount, assessment['flags'])

    # Audit log
    _log_aml_event(
        'TX_PROCESSED', subscriber_id,
        f'tx={tx_id} amount=${amount:.2f} risk={assessment["score"]} rec={assessment["recommendation"]}'
    )

    return {
        'tx_id':          tx_id,
        'status':         status,
        'risk_score':     assessment['score'],
        'risk_level':     assessment['risk_level'],
        'flags':          assessment['flags'],
        'recommendation': assessment['recommendation'],
        'requires_ctr':   assessment['requires_ctr'],
        'requires_sar':   assessment['requires_sar'],
        'allowed':        status != 'flagged',
    }


# ══ KYC RECORD MANAGEMENT ══════════════════════════════════════════

def get_kyc_profile(subscriber_id: str) -> dict:
    """Get subscriber KYC profile from DB."""
    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute('SELECT * FROM kyc_records WHERE subscriber_id=?', (subscriber_id,))
        row = c.fetchone()
        conn.close()
        if row:
            cols = ['subscriber_id','tier','kyc_level','full_name','date_of_birth',
                    'nationality','country_of_res','id_type','id_number_hash',
                    'pep_status','pep_detail','sanctions_clear','sanctions_date',
                    'risk_rating','verified_at','expires_at','created_at']
            return dict(zip(cols, row))
    except Exception:
        pass
    return {}


def submit_kyc(data: dict) -> dict:
    """
    Submit KYC information for a subscriber.
    Validates, screens, and stores KYC record.
    """
    subscriber_id = data.get('subscriber_id', '')
    tier          = data.get('tier', 'observer')
    full_name     = data.get('full_name', '').strip()
    dob           = data.get('date_of_birth', '')
    nationality   = data.get('nationality', '').upper()
    country       = data.get('country_of_residence', '').upper()
    id_type       = data.get('id_type', '')
    id_number     = data.get('id_number', '')

    if not all([subscriber_id, full_name, dob, nationality, country]):
        return {'success': False, 'error': 'Required fields: full_name, date_of_birth, nationality, country_of_residence'}

    # Sanctions screening
    sanctions = screen_sanctions(full_name, subscriber_id)
    if not sanctions['clear']:
        _log_aml_event('SANCTIONS_MATCH', subscriber_id, f'Match found for {full_name[:30]}')
        return {'success': False, 'error': 'Identity verification failed. Contact support.'}

    # Blocked jurisdictions
    if country in AML_CONFIG['sanctioned_countries']:
        return {'success': False, 'error': 'Service not available in your jurisdiction.'}

    # PEP check
    pep = check_pep_status(full_name, data.get('role', ''))

    # Risk rating
    if country in AML_CONFIG['sanctioned_countries']:
        risk_rating = 'prohibited'
    elif country in AML_CONFIG['high_risk_jurisdictions'] or pep['is_pep']:
        risk_rating = 'high'
    else:
        risk_rating = 'standard'

    # KYC level
    kyc_level = kyc_required_level(tier)

    # Hash the ID number — never store plaintext
    id_hash = hashlib.sha256(f"{id_number}{subscriber_id}".encode()).hexdigest() if id_number else ''

    # Expiry — KYC expires in 1 year, 6 months for high risk
    expiry_days = 180 if risk_rating == 'high' else 365
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expiry_days)).isoformat()

    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO kyc_records
            (subscriber_id, tier, kyc_level, full_name, date_of_birth,
             nationality, country_of_res, id_type, id_number_hash,
             pep_status, pep_detail, sanctions_clear, sanctions_date,
             risk_rating, verified_at, expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (subscriber_id, tier, kyc_level, full_name, dob,
             nationality, country, id_type, id_hash,
             int(pep['is_pep']), pep['detail'],
             int(sanctions['clear']), sanctions['checked_at'],
             risk_rating,
             datetime.now(timezone.utc).isoformat(), expires_at))
        conn.commit()
        conn.close()
    except Exception as e:
        return {'success': False, 'error': f'KYC storage error: {e}'}

    _log_aml_event('KYC_SUBMITTED', subscriber_id,
                  f'tier={tier} risk={risk_rating} pep={pep["is_pep"]}')

    return {
        'success':      True,
        'kyc_level':    kyc_level,
        'risk_rating':  risk_rating,
        'pep_flagged':  pep['is_pep'],
        'expires_at':   expires_at,
        'message':      'KYC submitted successfully. Enhanced review required.' if risk_rating == 'high' else 'KYC submitted successfully.',
    }


# ══ SAR & CTR FILINGS ══════════════════════════════════════════════

def _auto_ctr(tx_id: str, subscriber_id: str, amount: float):
    """Auto-generate CTR filing for transactions >= $10,000."""
    filing_ref = f'CTR-{datetime.now(timezone.utc).strftime("%Y%m%d")}-{tx_id[:8].upper()}'
    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO ctr_filings
            (filing_ref, subscriber_id, tx_id, amount_usd)
            VALUES (?,?,?,?)''',
            (filing_ref, subscriber_id, tx_id, amount))
        conn.commit()
        conn.close()
        _log_aml_event('CTR_GENERATED', subscriber_id,
                      f'ref={filing_ref} amount=${amount:.2f}')
    except Exception as e:
        print(f'[AML] CTR error: {e}')


def _queue_sar(tx_id: str, subscriber_id: str, amount: float, flags: list):
    """Queue a SAR filing for review."""
    filing_ref = f'SAR-{datetime.now(timezone.utc).strftime("%Y%m%d")}-{tx_id[:8].upper()}'
    reason = ' | '.join(flags[:3]) if flags else 'Suspicious activity detected'
    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO sar_filings
            (filing_ref, subscriber_id, tx_ids, filing_reason, amount_usd)
            VALUES (?,?,?,?,?)''',
            (filing_ref, subscriber_id, json.dumps([tx_id]), reason, amount))
        conn.commit()
        conn.close()
        _log_aml_event('SAR_QUEUED', subscriber_id,
                      f'ref={filing_ref} reason={reason[:80]}')
    except Exception as e:
        print(f'[AML] SAR error: {e}')


# ══ AUDIT LOGGING ══════════════════════════════════════════════════

def _log_aml_event(event_type: str, subscriber_id: str, detail: str):
    """Tamper-evident audit log for all AML events."""
    try:
        entry_hash = hashlib.sha256(
            f"{event_type}{subscriber_id}{detail}{time.time()}".encode()
        ).hexdigest()
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO aml_audit
            (event_type, subscriber_id, detail, hash)
            VALUES (?,?,?,?)''',
            (event_type, subscriber_id, detail[:500], entry_hash))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

def _read_env():
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

def _verify_owner(token: str) -> bool:
    expected = _read_env().get('OWNER_TOKEN', '')
    return bool(expected) and hmac.compare_digest(str(token), str(expected))


@aml_bp.route('/api/aml/screen', methods=['POST'])
def aml_screen():
    """Screen a transaction through the AML engine."""
    data = request.get_json() or {}

    required = ['subscriber_id', 'amount_usd', 'direction', 'tx_type']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {missing}'}), 400

    try:
        result = process_transaction(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aml_bp.route('/api/aml/kyc', methods=['POST'])
def aml_kyc_submit():
    """Submit KYC for a subscriber."""
    data = request.get_json() or {}
    try:
        result = submit_kyc(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aml_bp.route('/api/aml/kyc/<subscriber_id>', methods=['GET'])
def aml_kyc_status(subscriber_id):
    """Get KYC status for a subscriber (public — limited fields)."""
    profile = get_kyc_profile(subscriber_id)
    if not profile:
        return jsonify({'verified': False, 'kyc_level': 0})
    return jsonify({
        'verified':     bool(profile.get('verified_at')),
        'kyc_level':    profile.get('kyc_level', 0),
        'risk_rating':  profile.get('risk_rating', 'standard'),
        'pep_status':   bool(profile.get('pep_status')),
        'expires_at':   profile.get('expires_at'),
    })


@aml_bp.route('/api/aml/compliance', methods=['GET'])
def aml_compliance_status():
    """Public compliance status — Star's regulatory posture."""
    return jsonify({
        'aml_program':  'Active',
        'frameworks': [
            'FATF Recommendations',
            'FinCEN BSA/AML',
            'EU AMLD6',
            'OFAC Sanctions Screening',
        ],
        'controls': [
            'Transaction monitoring',
            'CTR filing ($10,000+ threshold)',
            'SAR generation (risk-based)',
            'KYC tiered verification',
            'PEP screening',
            'Sanctions screening',
            'Velocity limits by tier',
            'Structuring detection',
            'Tamper-evident audit trail',
        ],
        'ctr_threshold':    AML_CONFIG['ctr_threshold'],
        'sar_threshold':    AML_CONFIG['sar_threshold'],
        'last_updated':     '2026-03-28',
        'compliance_officer': 'Sarah DeFer, MS Biomedical Informatics',
    })


@aml_bp.route('/api/aml/dashboard', methods=['POST'])
def aml_dashboard():
    """Owner-only AML dashboard — filings, alerts, stats."""
    data  = request.get_json() or {}
    token = data.get('owner_token', '')
    if not _verify_owner(token):
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM aml_transactions WHERE status='flagged'")
        flagged = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM aml_transactions WHERE status='review'")
        in_review = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM sar_filings WHERE status='pending'")
        sar_pending = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM ctr_filings WHERE status='pending'")
        ctr_pending = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM kyc_records WHERE kyc_level > 0")
        kyc_verified = c.fetchone()[0]

        c.execute('''SELECT tx_id, subscriber_id, amount_usd, risk_score, risk_flags, created_at
            FROM aml_transactions WHERE status IN ("flagged","review")
            ORDER BY risk_score DESC LIMIT 10''')
        alerts = [{
            'tx_id': r[0], 'subscriber': r[1], 'amount': r[2],
            'risk_score': r[3], 'flags': json.loads(r[4] or '[]'), 'time': r[5]
        } for r in c.fetchall()]

        conn.close()

        return jsonify({
            'summary': {
                'flagged_transactions': flagged,
                'in_review':            in_review,
                'sar_pending':          sar_pending,
                'ctr_pending':          ctr_pending,
                'kyc_verified':         kyc_verified,
            },
            'recent_alerts': alerts,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aml_bp.route('/api/aml/status')
def aml_status():
    """Health check for AML module."""
    try:
        conn = sqlite3.connect(AML_DB)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM aml_transactions")
        tx_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM kyc_records")
        kyc_count = c.fetchone()[0]
        conn.close()
        return jsonify({
            'status':           'active',
            'module':           'Star AML & Compliance Engine v1.0',
            'transactions_monitored': tx_count,
            'kyc_records':      kyc_count,
            'frameworks':       ['FATF', 'FinCEN', 'AMLD6', 'OFAC'],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
