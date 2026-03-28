"""
star_kyc.py
Star KYC Orchestrator
Know Your Customer — Tiered Verification Routing
Designed & Built by Sarah DeFer | ShekinahStar.io

PHILOSOPHY:
  Star is the compliance record-keeper, not the verifier.
  Each subscriber type is routed to the appropriate verification
  method. Star stores results, never makes KYC decisions alone.

VERIFICATION ROUTES:
  Retail (Observer → Pioneer) → Email + country + AML screening
  Corporate (Enterprise)      → Persona/Stripe Identity API (docs)
  Wallet (all trading tiers)  → Chainalysis address screening
  Arcanum UHNW                → Manual — Sarah reviews personally
  Aegis Government            → Contract-based, self-certifying

REGISTER in flask_app.py:
  from star_kyc import kyc_bp, init_kyc_db
  app.register_blueprint(kyc_bp)
  with app.app_context():
      init_kyc_db()
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

BASE   = '/home/ShekinahD'
KYC_DB = os.path.join(BASE, 'star_kyc.db')
kyc_bp = Blueprint('kyc', __name__)

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

# ── KYC levels ──────────────────────────────────────────────────
KYC_LEVELS = {
    0: 'none',
    1: 'basic',        # email + country + AML
    2: 'standard',     # + ID document
    3: 'enhanced',     # + proof of address + source of funds
    4: 'institutional' # + corporate docs + beneficial ownership
}

# ── Required KYC level per tier ─────────────────────────────────
TIER_KYC_REQUIREMENTS = {
    'observer':   1,  # basic — email + country
    'navigator':  1,  # basic
    'sovereign':  2,  # standard — ID required for trading
    'pioneer':    2,  # standard
    'enterprise': 4,  # institutional — full corporate docs
    'arcanum':    3,  # enhanced — manual review by Sarah
    'aegis':      4,  # institutional — contract-based
}

# ── Verification routes per entity type ─────────────────────────
VERIFICATION_ROUTES = {
    'individual': {
        'provider':     'internal',
        'method':       'email_aml_screening',
        'description':  'Email verification + AML screening',
        'auto':         True,
    },
    'corporate': {
        'provider':     'persona',  # swap for stripe_identity or jumio
        'method':       'document_verification',
        'description':  'Corporate docs + beneficial ownership',
        'auto':         False,  # requires document upload
    },
    'wallet': {
        'provider':     'chainalysis',
        'method':       'address_screening',
        'description':  'Wallet address sanctions + risk screening',
        'auto':         True,
    },
    'uhnw': {
        'provider':     'manual',
        'method':       'sarah_review',
        'description':  'Personal review by Sarah DeFer',
        'auto':         False,
    },
    'government': {
        'provider':     'contract',
        'method':       'self_certifying',
        'description':  'Sovereign entity self-certification',
        'auto':         False,
    },
}


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_kyc_db():
    conn = sqlite3.connect(KYC_DB)
    c = conn.cursor()

    # Master KYC records
    c.execute('''CREATE TABLE IF NOT EXISTS kyc_records (
        subscriber_id   TEXT PRIMARY KEY,
        email           TEXT,
        tier            TEXT,
        entity_type     TEXT,  -- individual, corporate, uhnw, government
        kyc_level       INTEGER DEFAULT 0,
        kyc_required    INTEGER DEFAULT 1,
        status          TEXT DEFAULT 'pending',
        -- pending, in_progress, approved, rejected, expired, manual_review
        full_name       TEXT,
        date_of_birth   TEXT,
        nationality     TEXT,
        country         TEXT,
        pep_status      INTEGER DEFAULT 0,
        sanctions_clear INTEGER DEFAULT 0,
        wallet_screened INTEGER DEFAULT 0,
        wallet_risk     TEXT DEFAULT 'unknown',
        id_verified     INTEGER DEFAULT 0,
        corporate_verified INTEGER DEFAULT 0,
        provider_ref    TEXT,  -- external provider reference ID
        reviewer        TEXT,  -- for manual reviews
        notes           TEXT,
        approved_at     TIMESTAMP,
        expires_at      TIMESTAMP,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Corporate entity records
    c.execute('''CREATE TABLE IF NOT EXISTS corporate_kyc (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        subscriber_id   TEXT,
        company_name    TEXT,
        company_type    TEXT,  -- llc, corp, fund, trust, etc
        jurisdiction    TEXT,
        reg_number      TEXT,
        reg_number_hash TEXT,  -- SHA-256, never plaintext
        beneficial_owners TEXT,  -- JSON array
        authorized_signer TEXT,
        doc_status      TEXT DEFAULT 'pending',
        provider_ref    TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Wallet screening results
    c.execute('''CREATE TABLE IF NOT EXISTS wallet_screenings (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        subscriber_id   TEXT,
        wallet_address  TEXT,
        chain           TEXT DEFAULT 'ethereum',
        risk_score      REAL DEFAULT 0,
        risk_level      TEXT DEFAULT 'unknown',
        sanctions_hit   INTEGER DEFAULT 0,
        darknet_exposure REAL DEFAULT 0,
        mixer_exposure  REAL DEFAULT 0,
        provider        TEXT DEFAULT 'internal',
        raw_response    TEXT,
        screened_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # KYC audit trail
    c.execute('''CREATE TABLE IF NOT EXISTS kyc_audit (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        subscriber_id   TEXT,
        event           TEXT,
        detail          TEXT,
        officer         TEXT DEFAULT 'Star_KYC_Engine',
        hash            TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Manual review queue (Arcanum + exceptions)
    c.execute('''CREATE TABLE IF NOT EXISTS review_queue (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        subscriber_id   TEXT,
        tier            TEXT,
        priority        TEXT DEFAULT 'standard',  -- urgent, standard, low
        reason          TEXT,
        status          TEXT DEFAULT 'pending',
        assigned_to     TEXT DEFAULT 'Sarah DeFer',
        notes           TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at     TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print('✅ Star KYC Orchestrator initialized')


# ══ ROUTING ENGINE ══════════════════════════════════════════════════

def route_kyc(subscriber_id: str, tier: str, entity_type: str = 'individual',
              wallet_address: str = None) -> dict:
    """
    Main KYC router. Determines what verification is needed and initiates it.
    Returns a routing plan with steps required.
    """
    required_level = TIER_KYC_REQUIREMENTS.get(tier, 1)
    current_level  = _get_current_kyc_level(subscriber_id)
    route          = VERIFICATION_ROUTES.get(entity_type, VERIFICATION_ROUTES['individual'])

    steps_required = []
    steps_completed = []

    # ── Step 1: Basic email + AML (everyone) ────────────────────
    aml_clear = _check_aml_status(subscriber_id)
    if aml_clear:
        steps_completed.append('aml_screening')
    else:
        steps_required.append({
            'step':        'aml_screening',
            'description': 'Anti-money laundering screening',
            'provider':    'internal',
            'auto':        True,
            'required_for': 'all tiers',
        })

    # ── Step 2: Wallet screening (trading tiers) ─────────────────
    if tier in ('sovereign', 'pioneer', 'enterprise', 'arcanum', 'aegis'):
        if wallet_address:
            wallet_result = screen_wallet(subscriber_id, wallet_address)
            if wallet_result.get('risk_level') in ('low', 'medium'):
                steps_completed.append('wallet_screening')
            else:
                steps_required.append({
                    'step':        'wallet_screening',
                    'description': 'Wallet address risk screening',
                    'provider':    'internal + Chainalysis (production)',
                    'auto':        True,
                    'wallet':      wallet_address,
                })
        else:
            steps_required.append({
                'step':        'wallet_screening',
                'description': 'Connect your Hyperliquid wallet for screening',
                'provider':    'internal',
                'auto':        True,
                'action':      'provide_wallet_address',
            })

    # ── Step 3: Document verification (corporate/enterprise) ─────
    if entity_type == 'corporate' or tier == 'enterprise':
        corp_status = _get_corporate_status(subscriber_id)
        if corp_status == 'approved':
            steps_completed.append('corporate_verification')
        else:
            steps_required.append({
                'step':        'corporate_verification',
                'description': 'Corporate documents + beneficial ownership',
                'provider':    'Persona / Stripe Identity',
                'auto':        False,
                'documents_needed': [
                    'Certificate of incorporation',
                    'Beneficial ownership declaration (>25% owners)',
                    'Authorized signatory ID',
                    'Registered address proof',
                    'Source of funds declaration',
                ],
                'action':      'upload_corporate_docs',
            })

    # ── Step 4: Manual review (Arcanum UHNW) ─────────────────────
    if tier == 'arcanum':
        review_status = _get_review_status(subscriber_id)
        if review_status == 'approved':
            steps_completed.append('manual_review')
        else:
            steps_required.append({
                'step':        'manual_review',
                'description': 'Personal review by Sarah DeFer — Arcanum standard',
                'provider':    'manual',
                'auto':        False,
                'timeline':    '48-72 hours',
                'action':      'await_invitation',
            })

    # ── Step 5: Government self-certification (Aegis) ────────────
    if tier == 'aegis':
        steps_required.append({
            'step':        'government_certification',
            'description': 'Sovereign entity self-certification + contract',
            'provider':    'contract',
            'auto':        False,
            'action':      'contact_sarah',
            'email':       'sarahdefer@gmail.com',
        })

    # Overall status
    if not steps_required:
        overall = 'approved'
    elif not steps_completed and steps_required:
        overall = 'not_started'
    else:
        overall = 'in_progress'

    _log_kyc_event(subscriber_id, 'ROUTE_DETERMINED',
                   f'tier={tier} entity={entity_type} steps_required={len(steps_required)}')

    return {
        'subscriber_id':    subscriber_id,
        'tier':             tier,
        'entity_type':      entity_type,
        'kyc_required_level': required_level,
        'kyc_current_level':  current_level,
        'overall_status':   overall,
        'steps_completed':  steps_completed,
        'steps_required':   steps_required,
        'can_proceed':      overall in ('approved', 'in_progress') and aml_clear,
        'route':            route,
    }


# ══ WALLET SCREENING ═══════════════════════════════════════════════

def screen_wallet(subscriber_id: str, wallet_address: str, chain: str = 'ethereum') -> dict:
    """
    Screen a wallet address for sanctions and risk.
    Uses internal heuristics now — plug in Chainalysis API key for production.
    """
    chainalysis_key = _ENV.get('CHAINALYSIS_API_KEY', '')

    result = {
        'wallet':      wallet_address,
        'chain':       chain,
        'risk_score':  0.0,
        'risk_level':  'low',
        'sanctions_hit': False,
        'darknet_exposure': 0.0,
        'mixer_exposure': 0.0,
        'provider':    'internal',
        'screened_at': datetime.now(timezone.utc).isoformat(),
    }

    # Production: Chainalysis KYT API
    if chainalysis_key:
        try:
            r = requests.post(
                'https://api.chainalysis.com/api/kyt/v2/users',
                headers={
                    'Token': chainalysis_key,
                    'Content-Type': 'application/json',
                },
                json={'userId': subscriber_id},
                timeout=10
            )
            if r.status_code in (200, 201):
                # Register address
                r2 = requests.post(
                    f'https://api.chainalysis.com/api/kyt/v2/users/{subscriber_id}/transfers',
                    headers={'Token': chainalysis_key, 'Content-Type': 'application/json'},
                    json={
                        'network':    chain.upper(),
                        'asset':      'ETH',
                        'transferReference': wallet_address,
                        'direction':  'received',
                    },
                    timeout=10
                )
                if r2.status_code == 200:
                    data = r2.json()
                    result['risk_score']       = float(data.get('riskScore', 0))
                    result['risk_level']       = data.get('riskLevel', 'low').lower()
                    result['sanctions_hit']    = data.get('sanctionsExposure', 0) > 0
                    result['darknet_exposure'] = float(data.get('darkwebExposure', 0))
                    result['mixer_exposure']   = float(data.get('mixerExposure', 0))
                    result['provider']         = 'chainalysis'
        except Exception as e:
            print(f'[KYC] Chainalysis error: {e}')

    # Internal heuristics fallback
    if result['provider'] == 'internal':
        addr = wallet_address.lower()
        # Known high-risk patterns (simplified)
        if addr.startswith('0x000') or len(wallet_address) != 42:
            result['risk_level'] = 'high'
            result['risk_score'] = 0.9
        else:
            result['risk_level'] = 'low'
            result['risk_score'] = 0.05

    # Determine if blocked
    result['blocked'] = (
        result['sanctions_hit'] or
        result['risk_level'] == 'severe' or
        result['risk_score'] > 0.8
    )

    # Store result
    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO wallet_screenings
            (subscriber_id, wallet_address, chain, risk_score, risk_level,
             sanctions_hit, darknet_exposure, mixer_exposure, provider, raw_response)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (subscriber_id, wallet_address, chain,
             result['risk_score'], result['risk_level'],
             int(result['sanctions_hit']),
             result['darknet_exposure'], result['mixer_exposure'],
             result['provider'], json.dumps(result)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[KYC] Wallet store error: {e}')

    _log_kyc_event(subscriber_id, 'WALLET_SCREENED',
                   f'wallet={wallet_address[:10]}... risk={result["risk_level"]}')

    return result


# ══ CORPORATE KYC ══════════════════════════════════════════════════

def submit_corporate_kyc(subscriber_id: str, data: dict) -> dict:
    """
    Submit corporate KYC. Initiates verification via Persona or Stripe Identity.
    In production: generate an inquiry link and send to the authorized signatory.
    """
    company_name   = data.get('company_name', '')
    company_type   = data.get('company_type', '')
    jurisdiction   = data.get('jurisdiction', '').upper()
    reg_number     = data.get('registration_number', '')
    beneficial_owners = data.get('beneficial_owners', [])
    authorized_signer = data.get('authorized_signer', '')

    if not all([company_name, company_type, jurisdiction, authorized_signer]):
        return {'success': False, 'error': 'Missing required corporate fields'}

    # Hash reg number — never store plaintext
    reg_hash = hashlib.sha256(f"{reg_number}{subscriber_id}".encode()).hexdigest()

    # Check sanctioned jurisdictions
    sanctioned = ['CU', 'IR', 'KP', 'RU', 'SY', 'BY']
    if jurisdiction in sanctioned:
        _log_kyc_event(subscriber_id, 'CORP_KYC_BLOCKED',
                      f'Sanctioned jurisdiction: {jurisdiction}')
        return {'success': False, 'error': 'Corporate entity jurisdiction not supported.'}

    # Generate Persona inquiry (production)
    persona_key = _ENV.get('PERSONA_API_KEY', '')
    provider_ref = ''
    inquiry_url  = ''

    if persona_key:
        try:
            r = requests.post(
                'https://withpersona.com/api/v1/inquiries',
                headers={
                    'Authorization': f'Bearer {persona_key}',
                    'Persona-Version': '2023-01-05',
                    'Content-Type':  'application/json',
                },
                json={
                    'data': {
                        'attributes': {
                            'inquiry-template-id': _ENV.get('PERSONA_TEMPLATE_ID', ''),
                            'reference-id':        subscriber_id,
                            'fields': {
                                'company-name': company_name,
                                'jurisdiction': jurisdiction,
                            }
                        }
                    }
                },
                timeout=10
            )
            if r.status_code in (200, 201):
                resp = r.json()
                provider_ref = resp['data']['id']
                inquiry_url  = resp['data']['attributes'].get('inquiry-url', '')
        except Exception as e:
            print(f'[KYC] Persona error: {e}')

    # Store corporate record
    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO corporate_kyc
            (subscriber_id, company_name, company_type, jurisdiction,
             reg_number_hash, beneficial_owners, authorized_signer,
             doc_status, provider_ref)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (subscriber_id, company_name, company_type, jurisdiction,
             reg_hash, json.dumps(beneficial_owners), authorized_signer,
             'pending', provider_ref))
        conn.commit()
        conn.close()
    except Exception as e:
        return {'success': False, 'error': str(e)}

    _log_kyc_event(subscriber_id, 'CORP_KYC_SUBMITTED',
                  f'company={company_name} jurisdiction={jurisdiction}')

    response = {
        'success':     True,
        'status':      'pending',
        'company':     company_name,
        'message':     'Corporate KYC submitted. Document verification initiated.',
        'next_steps':  [],
    }

    if inquiry_url:
        response['verification_url'] = inquiry_url
        response['message'] = f'Complete verification at the provided link. Authorized signatory ({authorized_signer}) must complete the process.'
    else:
        response['next_steps'] = [
            f'Email certificate of incorporation to sarahdefer@gmail.com',
            f'Subject: Corporate KYC — {company_name} — {subscriber_id}',
            'Include: incorporation docs, beneficial ownership declaration, signatory ID',
            'Timeline: 2-5 business days',
        ]
        response['message'] = 'Corporate KYC submitted. Manual document review required.'

    return response


# ══ MANUAL REVIEW QUEUE ════════════════════════════════════════════

def queue_manual_review(subscriber_id: str, tier: str, reason: str,
                        priority: str = 'standard') -> dict:
    """Queue subscriber for manual review by Sarah (Arcanum + exceptions)."""
    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO review_queue
            (subscriber_id, tier, priority, reason)
            VALUES (?,?,?,?)''',
            (subscriber_id, tier, priority, reason))
        conn.commit()
        conn.close()
    except Exception as e:
        return {'success': False, 'error': str(e)}

    # Alert Sarah
    _alert_sarah_kyc(subscriber_id, tier, reason, priority)
    _log_kyc_event(subscriber_id, 'MANUAL_REVIEW_QUEUED',
                  f'tier={tier} priority={priority}')

    return {
        'success':  True,
        'status':   'queued_for_review',
        'message':  'Your application has been queued for personal review by Sarah DeFer.',
        'timeline': '24-48 hours for Arcanum, 48-72 hours for exceptions',
        'priority': priority,
    }


def approve_manual_review(subscriber_id: str, reviewer: str,
                          owner_token: str, notes: str = '') -> dict:
    """Sarah approves a manual review."""
    expected = _ENV.get('OWNER_TOKEN', '')
    if not hmac.compare_digest(str(owner_token), str(expected)):
        return {'success': False, 'error': 'Unauthorized'}

    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('''UPDATE review_queue SET status=?, reviewed_at=?, notes=?
            WHERE subscriber_id=? AND status="pending"''',
            ('approved', datetime.now(timezone.utc).isoformat(), notes, subscriber_id))
        c.execute('''UPDATE kyc_records SET status=?, kyc_level=3,
            approved_at=?, reviewer=?, updated_at=?
            WHERE subscriber_id=?''',
            ('approved', datetime.now(timezone.utc).isoformat(), reviewer,
             datetime.now(timezone.utc).isoformat(), subscriber_id))
        conn.commit()
        conn.close()
    except Exception as e:
        return {'success': False, 'error': str(e)}

    _log_kyc_event(subscriber_id, 'MANUAL_REVIEW_APPROVED',
                  f'reviewer={reviewer}')
    return {'success': True, 'status': 'approved', 'subscriber_id': subscriber_id}


# ══ HELPER FUNCTIONS ═══════════════════════════════════════════════

def _get_current_kyc_level(subscriber_id: str) -> int:
    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('SELECT kyc_level FROM kyc_records WHERE subscriber_id=?',
                  (subscriber_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0


def _check_aml_status(subscriber_id: str) -> bool:
    """Check if AML screening passed in star_aml.db."""
    try:
        aml_db = os.path.join(BASE, 'star_aml.db')
        if not os.path.exists(aml_db):
            return True  # AML not yet active — allow
        conn = sqlite3.connect(aml_db)
        c = conn.cursor()
        c.execute('''SELECT sanctions_clear FROM kyc_records
            WHERE subscriber_id=?''', (subscriber_id,))
        row = c.fetchone()
        conn.close()
        return bool(row[0]) if row else True
    except Exception:
        return True


def _get_corporate_status(subscriber_id: str) -> str:
    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('SELECT doc_status FROM corporate_kyc WHERE subscriber_id=?',
                  (subscriber_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 'not_submitted'
    except Exception:
        return 'not_submitted'


def _get_review_status(subscriber_id: str) -> str:
    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('SELECT status FROM review_queue WHERE subscriber_id=? ORDER BY id DESC LIMIT 1',
                  (subscriber_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 'not_submitted'
    except Exception:
        return 'not_submitted'


def _alert_sarah_kyc(subscriber_id: str, tier: str, reason: str, priority: str):
    """Email Sarah when manual review is needed."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        star  = _ENV.get('STAR_EMAIL', 'ShekinahStarAI@gmail.com')
        sarah = _ENV.get('SARAH_EMAIL', 'sarahdefer@gmail.com')
        pwd   = _ENV.get('STAR_EMAIL_PASSWORD', '')
        if not pwd:
            return
        msg = MIMEText(
            f'KYC MANUAL REVIEW REQUIRED\n\n'
            f'Subscriber: {subscriber_id}\n'
            f'Tier: {tier.upper()}\n'
            f'Priority: {priority.upper()}\n'
            f'Reason: {reason}\n\n'
            f'Review at: POST /api/kyc/review/approve with owner_token\n'
            f'Time: {datetime.now(timezone.utc).isoformat()}'
        )
        msg['Subject'] = f'⭐ KYC Review Required — {tier.upper()} — {priority.upper()} Priority'
        msg['From']    = star
        msg['To']      = sarah
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(star, pwd)
            s.send_message(msg)
    except Exception:
        pass


def _log_kyc_event(subscriber_id: str, event: str, detail: str):
    try:
        entry_hash = hashlib.sha256(
            f"{event}{subscriber_id}{detail}{time.time()}".encode()
        ).hexdigest()
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('INSERT INTO kyc_audit (subscriber_id, event, detail, hash) VALUES (?,?,?,?)',
                  (subscriber_id, event, detail[:500], entry_hash))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

@kyc_bp.route('/api/kyc/route', methods=['POST'])
def kyc_route():
    """Get KYC routing plan for a subscriber."""
    data = request.get_json() or {}
    subscriber_id = data.get('subscriber_id', '')
    tier          = data.get('tier', 'observer')
    entity_type   = data.get('entity_type', 'individual')
    wallet        = data.get('wallet_address', '')

    if not subscriber_id:
        return jsonify({'error': 'subscriber_id required'}), 400

    result = route_kyc(subscriber_id, tier, entity_type, wallet)
    return jsonify(result)


@kyc_bp.route('/api/kyc/wallet', methods=['POST'])
def kyc_wallet_screen():
    """Screen a wallet address."""
    data          = request.get_json() or {}
    subscriber_id = data.get('subscriber_id', '')
    wallet        = data.get('wallet_address', '')
    chain         = data.get('chain', 'ethereum')

    if not subscriber_id or not wallet:
        return jsonify({'error': 'subscriber_id and wallet_address required'}), 400

    result = screen_wallet(subscriber_id, wallet, chain)
    return jsonify(result)


@kyc_bp.route('/api/kyc/corporate', methods=['POST'])
def kyc_corporate():
    """Submit corporate KYC."""
    data          = request.get_json() or {}
    subscriber_id = data.get('subscriber_id', '')
    if not subscriber_id:
        return jsonify({'error': 'subscriber_id required'}), 400

    result = submit_corporate_kyc(subscriber_id, data)
    return jsonify(result)


@kyc_bp.route('/api/kyc/review/request', methods=['POST'])
def kyc_request_review():
    """Request manual review (Arcanum applicants)."""
    data          = request.get_json() or {}
    subscriber_id = data.get('subscriber_id', '')
    tier          = data.get('tier', 'arcanum')
    reason        = data.get('reason', 'Arcanum tier application')

    if not subscriber_id:
        return jsonify({'error': 'subscriber_id required'}), 400

    priority = 'urgent' if tier == 'arcanum' else 'standard'
    result = queue_manual_review(subscriber_id, tier, reason, priority)
    return jsonify(result)


@kyc_bp.route('/api/kyc/review/approve', methods=['POST'])
def kyc_approve():
    """Sarah approves a manual KYC review."""
    data          = request.get_json() or {}
    subscriber_id = data.get('subscriber_id', '')
    owner_token   = data.get('owner_token', '')
    notes         = data.get('notes', '')

    if not subscriber_id or not owner_token:
        return jsonify({'error': 'subscriber_id and owner_token required'}), 400

    result = approve_manual_review(subscriber_id, 'Sarah DeFer', owner_token, notes)
    return jsonify(result)


@kyc_bp.route('/api/kyc/status/<subscriber_id>')
def kyc_status(subscriber_id):
    """Get KYC status for a subscriber."""
    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('''SELECT tier, entity_type, kyc_level, status,
            wallet_screened, wallet_risk, id_verified, corporate_verified,
            approved_at, expires_at
            FROM kyc_records WHERE subscriber_id=?''', (subscriber_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({
                'subscriber_id': subscriber_id,
                'status':        'not_started',
                'kyc_level':     0,
            })

        return jsonify({
            'subscriber_id':    subscriber_id,
            'tier':             row[0],
            'entity_type':      row[1],
            'kyc_level':        row[2],
            'status':           row[3],
            'wallet_screened':  bool(row[4]),
            'wallet_risk':      row[5],
            'id_verified':      bool(row[6]),
            'corporate_verified': bool(row[7]),
            'approved_at':      row[8],
            'expires_at':       row[9],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kyc_bp.route('/api/kyc/queue', methods=['POST'])
def kyc_queue():
    """Owner: view manual review queue."""
    data  = request.get_json() or {}
    token = data.get('owner_token', '')
    expected = _ENV.get('OWNER_TOKEN', '')
    if not hmac.compare_digest(str(token), str(expected)):
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute('''SELECT subscriber_id, tier, priority, reason, status, created_at
            FROM review_queue WHERE status="pending"
            ORDER BY
              CASE priority WHEN "urgent" THEN 1 WHEN "standard" THEN 2 ELSE 3 END,
              created_at ASC''')
        rows = c.fetchall()
        conn.close()
        return jsonify({
            'pending_reviews': len(rows),
            'queue': [{'subscriber_id': r[0], 'tier': r[1], 'priority': r[2],
                      'reason': r[3], 'status': r[4], 'submitted': r[5]} for r in rows]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kyc_bp.route('/api/kyc/compliance')
def kyc_compliance():
    """Public KYC compliance statement."""
    return jsonify({
        'kyc_program':  'Active',
        'approach':     'Risk-based, tiered KYC routing',
        'entity_types': {
            'individual':   'Email + AML screening + ID verification',
            'corporate':    'Full corporate docs + beneficial ownership + authorized signatory',
            'wallet':       'On-chain address screening (sanctions + risk)',
            'uhnw':         'Personal review by compliance officer',
            'government':   'Sovereign self-certification + contract',
        },
        'providers': [
            'Internal AML engine (star_aml)',
            'Chainalysis KYT (wallet screening)',
            'Persona (corporate docs)',
            'Manual review (UHNW/Arcanum)',
        ],
        'standards':    ['FATF', 'FinCEN BSA', 'EU AMLD6', 'OFAC'],
        'officer':      'Sarah DeFer, MS Biomedical Informatics',
        'updated':      '2026-03-28',
    })


@kyc_bp.route('/api/kyc/status')
def kyc_module_status():
    try:
        conn = sqlite3.connect(KYC_DB)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM kyc_records")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM kyc_records WHERE status='approved'")
        approved = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM review_queue WHERE status='pending'")
        pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM wallet_screenings")
        wallets = c.fetchone()[0]
        conn.close()
        return jsonify({
            'status':             'active',
            'module':             'Star KYC Orchestrator v1.0',
            'total_records':      total,
            'approved':           approved,
            'pending_review':     pending,
            'wallets_screened':   wallets,
            'chainalysis_active': bool(_ENV.get('CHAINALYSIS_API_KEY')),
            'persona_active':     bool(_ENV.get('PERSONA_API_KEY')),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
