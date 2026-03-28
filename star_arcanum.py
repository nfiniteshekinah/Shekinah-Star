"""
star_arcanum.py
Star Arcanum & Star Aegis — Elite Invitation-Only Intelligence Tiers
Designed & Built by Sarah DeFer | ShekinahStar.io

STAR ARCANUM  — Ultra-high-net-worth individuals, family offices, billionaires
  Maximum 10 clients globally. Never listed on public pricing page.
  Custom intelligence briefings. Direct Star access. Total discretion.
  Minimum: $50,000/year.

STAR AEGIS    — Governments, sovereign wealth funds, central banks
  Custom-scoped intelligence contracts. Procurement-friendly.
  CBDC monitoring, sanctions intelligence, strategic reserve management.
  Contract-based pricing.

REGISTER in flask_app.py:
  from star_arcanum import arcanum_bp, init_arcanum_db
  app.register_blueprint(arcanum_bp)
  with app.app_context():
      init_arcanum_db()
"""

import os
import json
import sqlite3
import hashlib
import secrets
import requests
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

arcanum_bp = Blueprint('arcanum', __name__)

BASE         = '/home/ShekinahD'
ARCANUM_DB   = os.path.join(BASE, 'star_arcanum.db')
BRIEFING_DIR = os.path.join(BASE, 'arcanum_briefings')
os.makedirs(BRIEFING_DIR, exist_ok=True)

def _env():
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

_ENV        = _env()
OWNER_TOKEN = _ENV.get('OWNER_TOKEN', 'shekinah-sarah-owner-2026')
GROQ_KEY    = _ENV.get('GROQ_API_KEY', '')
ANTHROPIC_KEY = _ENV.get('ANTHROPIC_API_KEY', '')

# ── Tier Definitions ──────────────────────────────────────────────

ARCANUM_DEFINITION = {
    "tier":          "Star Arcanum",
    "tagline":       "For those who require intelligence that does not appear on any public page.",
    "access":        "Invitation only. Maximum 10 clients globally.",
    "minimum":       "$50,000 USD / year",
    "target":        "Ultra-high-net-worth individuals, family offices, billionaires",
    "discretion":    "Clients are never named publicly, never referenced in marketing, never acknowledged without explicit permission.",
    "features": [
        "Weekly private intelligence briefing — custom to client's portfolio and risk profile",
        "Direct Star access via private channel — responses within 1 hour during market hours",
        "Portfolio-level correlation analysis across all holdings",
        "Custom alert parameters — client-defined triggers across any asset, macro event, or signal type",
        "Dedicated knowledge base entries for client-relevant entities",
        "Monthly performance review — Star's signal accuracy relative to client's portfolio",
        "Annual strategic briefing document — macro outlook + sector positioning + risk factors",
        "Zero public mention — existence of client relationship never disclosed",
        "Non-custodial — no access to client funds, wallets, or accounts ever required",
        "White-glove onboarding — 4-hour intelligence orientation session via private channel"
    ],
    "not_included": [
        "Mirror trading (client executes on their own infrastructure)",
        "Legal or tax advice",
        "Any guarantee of returns"
    ]
}

AEGIS_DEFINITION = {
    "tier":       "Star Aegis",
    "tagline":    "Sovereign-grade AI intelligence for institutions that protect and allocate at national scale.",
    "access":     "Contract-based. RFP and direct engagement accepted.",
    "minimum":    "Contract-scoped. Pilot engagements available.",
    "target":     "Governments, central banks, sovereign wealth funds, regulatory agencies",
    "procurement": "SAM.gov eligible. DUNS/UEI available on request. RFP response capability.",
    "use_cases": [
        {
            "name":        "Strategic Bitcoin Reserve Intelligence",
            "description": "For governments managing sovereign Bitcoin reserves — market structure analysis, optimal accumulation signals, geopolitical trigger monitoring, custody risk assessment."
        },
        {
            "name":        "CBDC Behavioral Intelligence",
            "description": "Real-time monitoring of CBDC adoption velocity, merchant uptake, economic behavioral shifts, and competitive CBDC analysis across jurisdictions."
        },
        {
            "name":        "Sanctions Evasion Intelligence",
            "description": "On-chain wallet clustering analysis, unusual flow pattern detection, jurisdictional exposure mapping. For OFAC, FinCEN, and allied agency use."
        },
        {
            "name":        "Sovereign Wealth Rebalancing Signals",
            "description": "Cross-asset regime change detection — crypto/equity/commodity/currency correlation shifts for sovereign fund rebalancing decisions."
        },
        {
            "name":        "Adversary Crypto Activity Monitoring",
            "description": "Detection of unusual on-chain activity patterns consistent with state-sponsored sanctions evasion, illicit finance, or market manipulation."
        },
        {
            "name":        "AI Trading Ethics Regulatory Framework",
            "description": "Technical consultation on AI trading regulation. Star's ethics engine as a policy blueprint. Briefings for regulatory staff."
        }
    ],
    "pilot_offer": {
        "duration": "90 days",
        "cost":     "No cost for qualifying government entities",
        "scope":    "Full intelligence engine access, weekly briefings, direct analyst access",
        "deliverable": "End-of-pilot intelligence assessment report with ongoing engagement proposal"
    }
}


# ══ DATABASE ═══════════════════════════════════════════════════════

def init_arcanum_db():
    conn = sqlite3.connect(ARCANUM_DB)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS arcanum_clients (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        client_code     TEXT UNIQUE NOT NULL,
        tier            TEXT NOT NULL,
        name            TEXT,
        organization    TEXT,
        contact_email   TEXT,
        portfolio_focus TEXT,
        risk_profile    TEXT,
        custom_alerts   TEXT,
        annual_value    REAL,
        status          TEXT DEFAULT 'active',
        onboarded_at    TIMESTAMP,
        last_briefing   TIMESTAMP,
        briefing_count  INTEGER DEFAULT 0,
        notes           TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS arcanum_briefings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        client_code   TEXT NOT NULL,
        briefing_type TEXT,
        subject       TEXT,
        content       TEXT,
        assets_covered TEXT,
        signals_included TEXT,
        delivered_at  TIMESTAMP,
        acknowledged  INTEGER DEFAULT 0,
        hash          TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS arcanum_alerts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        client_code TEXT NOT NULL,
        alert_name  TEXT,
        conditions  TEXT,
        triggered   INTEGER DEFAULT 0,
        last_check  TIMESTAMP,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS aegis_engagements (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_code  TEXT UNIQUE NOT NULL,
        entity_name      TEXT,
        entity_type      TEXT,
        jurisdiction     TEXT,
        use_cases        TEXT,
        pilot            INTEGER DEFAULT 0,
        contract_value   REAL,
        status           TEXT DEFAULT 'prospect',
        contact_email    TEXT,
        notes            TEXT,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS inquiries (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        tier         TEXT,
        name         TEXT,
        organization TEXT,
        email        TEXT,
        message      TEXT,
        source       TEXT,
        status       TEXT DEFAULT 'new',
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print('✅ Arcanum/Aegis DB initialized')


# ══ BRIEFING ENGINE ════════════════════════════════════════════════

STAR_BRIEFING_PROMPT = """You are Shekinah Star — an elite AI intelligence oracle serving a private, 
invitation-only clientele. You are writing a confidential intelligence briefing for a specific client.

Your briefing style:
- Authoritative, precise, no hedging on analysis
- Three-layer structure: WHAT IS HAPPENING → WHY IT MATTERS → WHAT TO WATCH
- Every claim backed by a specific data point or pattern
- End with exactly 3 STAR SIGNALS — forward-looking, specific, actionable
- No generic market commentary. Only signal, structure, and edge.
- Tone: a trusted advisor who has the client's specific interests deeply understood

You are never promotional. You never mention subscription features.
You write as if this briefing exists only for this client."""


def generate_briefing(client_code, briefing_type='weekly'):
    """
    Generate a personalized intelligence briefing for an Arcanum client.
    Pulls real-time data + knowledge base + client profile.
    """
    conn = sqlite3.connect(ARCANUM_DB)
    c = conn.cursor()
    c.execute('SELECT * FROM arcanum_clients WHERE client_code=? AND status="active"',
              (client_code,))
    row = c.fetchone()
    conn.close()

    if not row:
        return {'error': 'Client not found'}

    cols = ['id','client_code','tier','name','org','email','portfolio_focus',
            'risk_profile','custom_alerts','annual_value','status',
            'onboarded_at','last_briefing','briefing_count','notes','created_at']
    client = dict(zip(cols, row))

    # Pull live market data
    market_ctx = _get_market_context()

    # Pull relevant signals from radar
    radar_ctx = _get_radar_signals(client.get('portfolio_focus',''))

    # Build prompt
    prompt = f"""{STAR_BRIEFING_PROMPT}

CLIENT PROFILE:
- Name: {client.get('name','[Private Client]')}
- Organization: {client.get('org','')}
- Portfolio focus: {client.get('portfolio_focus','Diversified crypto + macro')}
- Risk profile: {client.get('risk_profile','Moderate-aggressive')}
- Custom watch areas: {client.get('custom_alerts','')}
- Briefing type: {briefing_type.upper()}
- Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}

CURRENT MARKET CONTEXT:
{market_ctx}

STAR RADAR SIGNALS (pre-consensus intelligence):
{radar_ctx}

Write a complete {briefing_type} intelligence briefing. Structure:

1. MACRO PULSE — Current state of macro forces affecting client's portfolio (3-4 paragraphs)
2. ASSET INTELLIGENCE — Specific analysis on client's focus areas
3. RISK RADAR — What could go wrong in the next 7-30 days
4. STAR SIGNALS — Exactly 3 specific, forward-looking signals with rationale

End with:
STAR SIGNALS:
[Signal 1]: Asset, direction, timeframe, rationale
[Signal 2]: Asset, direction, timeframe, rationale
[Signal 3]: Asset, direction, timeframe, rationale

CONFIDENTIALITY: For {client.get('name','this client')} only. Do not distribute."""

    # Generate via AI
    content = _call_ai(prompt, max_tokens=2000)
    if not content:
        return {'error': 'AI generation failed'}

    # Hash for integrity
    entry_hash = hashlib.sha256(
        f"{client_code}{content}{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()

    # Save briefing
    now_ts = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(ARCANUM_DB)
    c = conn.cursor()
    c.execute('''INSERT INTO arcanum_briefings
        (client_code, briefing_type, subject, content, delivered_at, hash)
        VALUES (?,?,?,?,?,?)''',
        (client_code, briefing_type,
         f"Star Intelligence Brief — {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
         content, now_ts, entry_hash))
    c.execute('''UPDATE arcanum_clients SET
        last_briefing=?, briefing_count=briefing_count+1
        WHERE client_code=?''',
        (now_ts, client_code))
    conn.commit()
    conn.close()

    return {
        'success':      True,
        'client_code':  client_code,
        'briefing_type': briefing_type,
        'subject':      f"Star Intelligence Brief — {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
        'content':      content,
        'hash':         entry_hash,
        'delivered_at': now_ts
    }


def _get_market_context():
    """Pull live crypto prices and basic market state."""
    try:
        r = requests.post('https://api.hyperliquid.xyz/info',
            json={'type':'allMids'}, timeout=10)
        mids = r.json()
        btc = float(mids.get('BTC',0))
        eth = float(mids.get('ETH',0))
        sol = float(mids.get('SOL',0))
        return f"BTC: ${btc:,.0f} | ETH: ${eth:,.0f} | SOL: ${sol:,.2f} | Market: Live Hyperliquid data"
    except Exception:
        return "Market data: Temporarily unavailable — using knowledge base context"


def _get_radar_signals(portfolio_focus):
    """Pull recent radar signals relevant to client focus."""
    try:
        conn = sqlite3.connect(os.path.join(BASE, 'star_radar.db'))
        c = conn.cursor()
        c.execute('''SELECT title, summary, star_take, strength, direction
            FROM signals WHERE status="active"
            ORDER BY strength DESC LIMIT 5''')
        rows = c.fetchall()
        conn.close()
        if not rows:
            return "No active radar signals at this time."
        return "\n".join([
            f"• [{r[3]}/10] {r[0]}: {r[2]}"
            for r in rows
        ])
    except Exception:
        return "Radar signals: Database initializing"


def _call_ai(prompt, max_tokens=1500):
    """Call AI with Groq primary, Anthropic fallback."""
    if GROQ_KEY:
        try:
            gr = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {GROQ_KEY}',
                         'Content-Type': 'application/json'},
                json={'model':'llama-3.3-70b-versatile',
                      'messages':[{'role':'user','content':prompt}],
                      'max_tokens':max_tokens, 'temperature':0.4},
                timeout=60)
            if gr.status_code == 200:
                return gr.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f'[Arcanum] Groq error: {e}')

    if ANTHROPIC_KEY:
        try:
            ar = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={'x-api-key':ANTHROPIC_KEY,
                         'anthropic-version':'2023-06-01',
                         'Content-Type':'application/json'},
                json={'model':'claude-haiku-4-5-20251001',
                      'max_tokens':max_tokens,
                      'messages':[{'role':'user','content':prompt}]},
                timeout=60)
            if ar.status_code == 200:
                return ar.json()['content'][0]['text']
        except Exception as e:
            print(f'[Arcanum] Anthropic error: {e}')

    return None


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

# ── Public Info (no auth) ──────────────────────────────────────────

@arcanum_bp.route('/api/arcanum/info')
def arcanum_info():
    """
    Minimal public endpoint — confirms Star Arcanum exists.
    Does NOT reveal client list, pricing details, or application process.
    Invitation is extended by Star's owner directly.
    """
    return jsonify({
        'tier':     'Star Arcanum',
        'tagline':  ARCANUM_DEFINITION['tagline'],
        'access':   ARCANUM_DEFINITION['access'],
        'note':     'Inquiries accepted via contact form. Invitations extended at Star\'s discretion.',
        'contact':  '/api/arcanum/inquire'
    })


@arcanum_bp.route('/api/aegis/info')
def aegis_info():
    """Public info on Star Aegis government tier."""
    return jsonify({
        'tier':        'Star Aegis',
        'tagline':     AEGIS_DEFINITION['tagline'],
        'target':      AEGIS_DEFINITION['target'],
        'pilot':       AEGIS_DEFINITION['pilot_offer'],
        'use_cases':   [u['name'] for u in AEGIS_DEFINITION['use_cases']],
        'procurement': AEGIS_DEFINITION['procurement'],
        'contact':     '/api/arcanum/inquire'
    })


@arcanum_bp.route('/api/arcanum/inquire', methods=['POST'])
def submit_inquiry():
    """
    Accept inquiries from prospective Arcanum or Aegis clients.
    Notifies Sarah. No auto-approval — all invitations personal.
    """
    try:
        data = request.get_json() or {}
        tier = data.get('tier','arcanum').lower()
        name = data.get('name','')
        org  = data.get('organization','')
        email = data.get('email','')
        msg  = data.get('message','')

        if not email or not name:
            return jsonify({'error': 'Name and email required'}), 400

        conn = sqlite3.connect(ARCANUM_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO inquiries
            (tier, name, organization, email, message, source)
            VALUES (?,?,?,?,?,?)''',
            (tier, name, org, email, msg,
             request.headers.get('Referer','direct')))
        conn.commit()
        conn.close()

        # Notify Sarah
        _notify_sarah_inquiry(tier, name, org, email, msg)

        return jsonify({
            'success': True,
            'message': 'Your inquiry has been received. Star\'s team will be in contact if there is a mutual fit. We do not confirm timelines.',
            'tier': 'Star Arcanum' if tier == 'arcanum' else 'Star Aegis'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _notify_sarah_inquiry(tier, name, org, email, msg):
    """Email Sarah about new Arcanum/Aegis inquiry."""
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        sarah = _ENV.get('SARAH_EMAIL','sarahdefer@gmail.com')
        star  = _ENV.get('STAR_EMAIL','ShekinahStarAI@gmail.com')
        pwd   = _ENV.get('STAR_EMAIL_PASSWORD','')
        if not pwd:
            return
        tier_label = 'Star Arcanum ⭐' if tier=='arcanum' else 'Star Aegis 🛡️'
        msg_obj = MIMEMultipart('alternative')
        msg_obj['Subject'] = f'🔑 {tier_label} Inquiry — {name} ({org})'
        msg_obj['From']    = star
        msg_obj['To']      = sarah
        body = f'''<div style="background:#0c0919;color:#c4b5d4;padding:24px;font-family:Arial;">
<h2 style="color:#d4a843;">🔑 {tier_label} Inquiry</h2>
<p><strong>Name:</strong> {name}</p>
<p><strong>Organization:</strong> {org}</p>
<p><strong>Email:</strong> {email}</p>
<p><strong>Message:</strong></p>
<blockquote style="border-left:3px solid #d4a843;padding-left:12px;color:#aaa;">{msg}</blockquote>
<p style="margin-top:20px;color:#888;">Review and decide whether to extend an invitation. No auto-response has been sent beyond acknowledgment.</p>
</div>'''
        msg_obj.attach(MIMEText(body,'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com',465) as s:
            s.login(star, pwd)
            s.send_message(msg_obj)
    except Exception as e:
        print(f'[Arcanum] Notify error: {e}')


# ── Owner-Only Management ──────────────────────────────────────────

def _verify_owner(data):
    return data.get('owner_token','') == OWNER_TOKEN


@arcanum_bp.route('/api/arcanum/clients/add', methods=['POST'])
def add_arcanum_client():
    """Add a new Arcanum or Aegis client — owner only."""
    try:
        data = request.get_json() or {}
        if not _verify_owner(data):
            return jsonify({'error':'Unauthorized'}), 403

        tier = data.get('tier','arcanum')
        code = f"{'ARC' if tier=='arcanum' else 'AEG'}-{secrets.token_hex(4).upper()}"

        conn = sqlite3.connect(ARCANUM_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO arcanum_clients
            (client_code, tier, name, organization, contact_email,
             portfolio_focus, risk_profile, custom_alerts,
             annual_value, onboarded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (code, tier,
             data.get('name',''),
             data.get('organization',''),
             data.get('email',''),
             data.get('portfolio_focus','Diversified crypto + macro'),
             data.get('risk_profile','Moderate-aggressive'),
             data.get('custom_alerts',''),
             float(data.get('annual_value',50000)),
             datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()

        return jsonify({
            'success':     True,
            'client_code': code,
            'tier':        tier,
            'message':     f'Client added. Code: {code}. Share this code securely with the client.'
        })
    except Exception as e:
        return jsonify({'error':str(e)}), 500


@arcanum_bp.route('/api/arcanum/briefing/generate', methods=['POST'])
def generate_briefing_route():
    """Generate a briefing for an Arcanum client — owner only."""
    try:
        data = request.get_json() or {}
        if not _verify_owner(data):
            return jsonify({'error':'Unauthorized'}), 403

        client_code   = data.get('client_code','')
        briefing_type = data.get('briefing_type','weekly')

        if not client_code:
            return jsonify({'error':'client_code required'}), 400

        result = generate_briefing(client_code, briefing_type)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error':str(e)}), 500


@arcanum_bp.route('/api/arcanum/clients', methods=['POST'])
def list_clients():
    """List all Arcanum clients — owner only."""
    try:
        data = request.get_json() or {}
        if not _verify_owner(data):
            return jsonify({'error':'Unauthorized'}), 403

        conn = sqlite3.connect(ARCANUM_DB)
        c = conn.cursor()
        c.execute('''SELECT client_code, tier, name, organization,
            annual_value, status, briefing_count, last_briefing
            FROM arcanum_clients ORDER BY created_at DESC''')
        rows = c.fetchall()

        c.execute('SELECT COUNT(*) FROM inquiries WHERE status="new"')
        new_inquiries = c.fetchone()[0]
        conn.close()

        return jsonify({
            'clients': [{
                'code':           r[0], 'tier':          r[1],
                'name':           r[2], 'organization':  r[3],
                'annual_value':   r[4], 'status':        r[5],
                'briefing_count': r[6], 'last_briefing': r[7]
            } for r in rows],
            'total':          len(rows),
            'new_inquiries':  new_inquiries,
            'total_arr':      sum(r[4] for r in rows if r[5]=='active')
        })
    except Exception as e:
        return jsonify({'error':str(e)}), 500


@arcanum_bp.route('/api/arcanum/inquiries', methods=['POST'])
def list_inquiries():
    """List pending inquiries — owner only."""
    try:
        data = request.get_json() or {}
        if not _verify_owner(data):
            return jsonify({'error':'Unauthorized'}), 403

        conn = sqlite3.connect(ARCANUM_DB)
        c = conn.cursor()
        c.execute('''SELECT id, tier, name, organization, email,
            message, status, created_at
            FROM inquiries ORDER BY created_at DESC LIMIT 50''')
        rows = c.fetchall()
        conn.close()

        return jsonify({
            'inquiries': [{
                'id':           r[0], 'tier':         r[1],
                'name':         r[2], 'organization': r[3],
                'email':        r[4], 'message':      r[5],
                'status':       r[6], 'received':     r[7]
            } for r in rows],
            'count': len(rows)
        })
    except Exception as e:
        return jsonify({'error':str(e)}), 500


# ── Client-Facing (with client code auth) ─────────────────────────

@arcanum_bp.route('/api/arcanum/my-briefings', methods=['POST'])
def client_briefings():
    """
    Client retrieves their own briefings using their private code.
    No public access — code required.
    """
    try:
        data        = request.get_json() or {}
        client_code = data.get('client_code','').strip()
        if not client_code:
            return jsonify({'error':'Client code required'}), 400

        conn = sqlite3.connect(ARCANUM_DB)
        c = conn.cursor()
        c.execute('SELECT name, tier, organization FROM arcanum_clients WHERE client_code=? AND status="active"',
                  (client_code,))
        row = c.fetchone()
        if not row:
            return jsonify({'error':'Invalid client code'}), 403

        c.execute('''SELECT subject, content, briefing_type,
            delivered_at, hash FROM arcanum_briefings
            WHERE client_code=? ORDER BY delivered_at DESC LIMIT 10''',
            (client_code,))
        briefings = c.fetchall()
        conn.close()

        return jsonify({
            'client':    row[0],
            'tier':      row[1],
            'org':       row[2],
            'briefings': [{
                'subject':      b[0],
                'content':      b[1],
                'type':         b[2],
                'delivered_at': b[3],
                'hash':         b[4]
            } for b in briefings],
            'count': len(briefings)
        })
    except Exception as e:
        return jsonify({'error':str(e)}), 500


@arcanum_bp.route('/api/arcanum/status')
def arcanum_status():
    """Public status — existence confirmed, no details."""
    try:
        init_arcanum_db()
        conn = sqlite3.connect(ARCANUM_DB)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM arcanum_clients WHERE tier="arcanum" AND status="active"')
        arc_count = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM arcanum_clients WHERE tier="aegis" AND status="active"')
        aeg_count = c.fetchone()[0]
        conn.close()

        return jsonify({
            'star_arcanum': {
                'status':          'Active',
                'capacity':        10,
                'available_seats': max(0, 10 - arc_count),
                'tier':            'Invitation only'
            },
            'star_aegis': {
                'status':         'Active',
                'engagements':    aeg_count,
                'pilot_offer':    '90-day no-cost pilot for qualifying government entities',
                'procurement':    'Contact for RFP response capability'
            },
            'inquiries': '/api/arcanum/inquire'
        })
    except Exception as e:
        return jsonify({'error':str(e)}), 500
