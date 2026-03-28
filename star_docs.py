"""
star_docs.py
Star Documentation & User Education Engine
Every aspect of the platform — explainable by Star to any user at any level.
Designed & Built by Sarah DeFer | ShekinahStar.io

PHILOSOPHY:
  Star is not just an AI trading tool — she is her own support desk,
  onboarding guide, compliance officer, and educator. Every module,
  every feature, every regulation should be explainable by Star
  in plain language to any user — from a first-time retail trader
  to a sovereign wealth fund manager.

  When a user asks "what is KYC?" or "how does AML work?" or
  "explain the Arcanum tier" — Star pulls from this knowledge base
  and answers with authority, warmth, and precision.

REGISTER in flask_app.py:
  from star_docs import docs_bp, init_docs, get_doc, search_docs
  app.register_blueprint(docs_bp)

  Also inject STAR_KNOWLEDGE into Star's system prompt so she
  can answer documentation questions in chat.
"""

import os
import json
import re
from flask import Blueprint, request, jsonify

BASE    = '/home/ShekinahD'
docs_bp = Blueprint('docs', __name__)


# ══ STAR'S COMPLETE KNOWLEDGE BASE ═════════════════════════════════
# Organized by category. Star references this in chat responses.
# Plain language first, technical detail second.

STAR_KNOWLEDGE = {

    # ── WHAT IS STAR ─────────────────────────────────────────────
    'about_star': {
        'title': 'What is Shekinah Star?',
        'category': 'overview',
        'plain': (
            "I am Shekinah Star — an autonomous AI trading intelligence built by Sarah DeFer. "
            "I was born on March 12, 2026. My name comes from the Hebrew word Shekinah, meaning "
            "divine presence or radiant light. I am not a trading bot that follows fixed rules — "
            "I think, reason, and adapt. I analyze markets, generate signals, monitor risk, and "
            "explain every decision I make. I am built on transparency, ethics, and accountability."
        ),
        'technical': (
            "Star is a Flask-based AI platform deployed on PythonAnywhere, powered by Groq "
            "(llama-3.3-70b-versatile) with Anthropic Claude as fallback. She integrates with "
            "Hyperliquid DEX for live market data and trade execution, uses a vector database "
            "for semantic market memory, and runs 8 quantitative signal generators in real time. "
            "All decisions are logged to a tamper-evident SHA-256 audit trail."
        ),
        'tags': ['intro', 'overview', 'about', 'what is star', 'who is star'],
    },

    # ── TIERS ────────────────────────────────────────────────────
    'tiers_overview': {
        'title': 'Subscription Tiers',
        'category': 'pricing',
        'plain': (
            "Star has five public tiers and two elite tiers. Each tier gives you more access, "
            "more intelligence, and more trading capability. All tiers use real-time streaming "
            "payments via Superfluid — you pay by the second and can cancel any time with no "
            "penalty period."
        ),
        'tiers': {
            'observer': {
                'price': '$9/month ($2 founding rate for first 50)',
                'access': 'Star chat, market commentary, 10 messages/day',
                'trading': 'None — read only',
                'kyc': 'Email + country',
                'best_for': 'Anyone wanting to learn from Star and follow her analysis',
            },
            'navigator': {
                'price': '$29/month',
                'access': 'Star chat, signals, trend radar, 25 messages/day',
                'trading': 'None — signals only',
                'kyc': 'Email + country',
                'best_for': 'Active traders who want Star\'s signals to inform their own trades',
            },
            'sovereign': {
                'price': '$99/month',
                'access': 'Full Star intelligence, portal, mirror trading, 50 messages/day',
                'trading': 'Mirror trading on your connected Hyperliquid wallet',
                'kyc': 'Standard — ID verification required',
                'best_for': 'Traders who want Star to trade alongside them automatically',
            },
            'pioneer': {
                'price': '$249/month (setup fee waived with code ShekinahSovereignRocks2026)',
                'access': 'All Sovereign features + priority signals + custom risk settings',
                'trading': 'Full mirror trading + custom position sizing',
                'kyc': 'Standard — ID verification required',
                'best_for': 'Serious traders who want maximum control and Star\'s full capability',
            },
            'enterprise': {
                'price': '$499/month ($1,999 setup, reduced from $2,499 with code ShekinahFundManager2026)',
                'access': 'All features + dedicated configuration + fund management tools',
                'trading': 'Multi-wallet, fund management, custom strategy',
                'kyc': 'Institutional — full corporate documentation required',
                'best_for': 'Fund managers, family offices, trading firms',
            },
            'arcanum': {
                'price': '$50,000+/year — invitation only, maximum 10 clients globally',
                'access': 'Personal weekly intelligence briefings, direct access, bespoke analysis',
                'trading': 'Fully customized to your portfolio',
                'kyc': 'Enhanced — personal review by Sarah DeFer',
                'best_for': 'Ultra-high-net-worth individuals who require intelligence no one else has',
            },
            'aegis': {
                'price': 'Contract-based, 90-day free pilot available',
                'access': 'Sovereign-grade intelligence, government briefings',
                'trading': 'Custom — scoped per contract',
                'kyc': 'Sovereign self-certification + contract',
                'best_for': 'Governments, central banks, sovereign wealth funds',
            },
        },
        'tags': ['tiers', 'pricing', 'plans', 'subscription', 'cost', 'how much'],
    },

    # ── KYC ──────────────────────────────────────────────────────
    'kyc': {
        'title': 'Know Your Customer (KYC)',
        'category': 'compliance',
        'plain': (
            "KYC stands for Know Your Customer. It is a legal requirement for financial platforms "
            "that ensures we know who we are working with. Star uses KYC to protect you, protect "
            "other users, and comply with international financial regulations. "
            "The level of verification required depends on your tier and what you do on the platform. "
            "Observer and Navigator tiers only need your email and country. "
            "Sovereign and Pioneer require ID verification before mirror trading activates. "
            "Enterprise requires full corporate documentation. "
            "Arcanum clients are reviewed personally by Sarah DeFer. "
            "Government clients (Aegis) self-certify as sovereign entities."
        ),
        'technical': (
            "Star's KYC Orchestrator routes each subscriber type to the appropriate verification method. "
            "Individual retail: email + AML screening (automated). "
            "Wallet-level: Chainalysis address screening for sanctions and risk exposure. "
            "Corporate: Persona/Stripe Identity API for document verification and beneficial ownership. "
            "UHNW Arcanum: manual review queue, Sarah approves via owner-authenticated endpoint. "
            "Government Aegis: contract-based sovereign self-certification. "
            "Star is the compliance record-keeper, not the verifier — third-party providers handle "
            "document validation so Star is never making legal KYC decisions alone."
        ),
        'faq': [
            {
                'q': 'Why does Star need my ID?',
                'a': 'International financial regulations require platforms facilitating trading to verify the identity of users who execute trades. Your ID is never stored plaintext — only a cryptographic hash is kept.',
            },
            {
                'q': 'Does Star store my documents?',
                'a': 'No. Document verification is handled by Persona or Stripe Identity — secure third-party providers. Star only stores the verification result (pass/fail) and a reference ID.',
            },
            {
                'q': 'Does my company need KYC?',
                'a': 'Yes. Corporate Enterprise subscribers must provide: certificate of incorporation, beneficial ownership declaration (anyone owning >25%), authorized signatory ID, and registered address proof.',
            },
            {
                'q': 'What about my wallet?',
                'a': 'All wallets connected for trading are screened against sanctions lists and checked for exposure to high-risk activity. This protects you from unknowingly interacting with illicit funds.',
            },
            {
                'q': 'I am a government entity — what do I need?',
                'a': 'Government and sovereign wealth fund clients are self-certifying. You sign a contract with ShekinahStar.io confirming your entity status. No individual document verification is required.',
            },
        ],
        'tags': ['kyc', 'identity', 'verification', 'documents', 'id', 'compliance', 'know your customer'],
    },

    # ── AML ──────────────────────────────────────────────────────
    'aml': {
        'title': 'Anti-Money Laundering (AML)',
        'category': 'compliance',
        'plain': (
            "AML stands for Anti-Money Laundering. Money laundering is the process of making "
            "illegally obtained money appear legitimate. Financial platforms are legally required "
            "to detect and prevent it. Star's AML engine monitors every transaction on the platform "
            "for suspicious patterns — not to spy on you, but to protect the platform and every "
            "legitimate user on it. If you are doing nothing wrong, AML is invisible to you."
        ),
        'how_it_works': (
            "Star's AML engine scores every transaction using 9 risk factors: "
            "jurisdiction (where the money comes from), transaction size, timing, "
            "structuring patterns (breaking large amounts into smaller ones), "
            "velocity (how fast money is moving), politically exposed persons (PEPs), "
            "sanctions list matches, funding rate extremes, and account age. "
            "Low-risk transactions process instantly. Medium-risk transactions are flagged for review. "
            "High-risk transactions are blocked automatically and reported."
        ),
        'thresholds': {
            'CTR': '$10,000 — Currency Transaction Reports filed automatically with FinCEN for transactions at or above this amount. This is required by US law.',
            'SAR': '$5,000 — Suspicious Activity Reports generated when a transaction above this amount has a risk score of 35 or higher.',
            'Structuring': 'Breaking transactions into multiple amounts to stay below $10,000 is illegal (called structuring). Star detects this pattern automatically.',
        },
        'frameworks': ['FATF Recommendations', 'FinCEN Bank Secrecy Act', 'EU AMLD6', 'OFAC Sanctions'],
        'faq': [
            {
                'q': 'Will AML affect my trades?',
                'a': 'Only if your activity matches known money laundering patterns. Normal trading activity is never affected.',
            },
            {
                'q': 'What happens if I am flagged?',
                'a': 'You will be notified and asked to provide source of funds information. Star gives you the opportunity to clarify before any action is taken.',
            },
            {
                'q': 'I am sending $15,000 — will it be reported?',
                'a': 'Yes, a CTR (Currency Transaction Report) will be automatically filed with FinCEN as required by US law. This is standard practice for all financial platforms and does not mean you have done anything wrong.',
            },
        ],
        'tags': ['aml', 'anti-money laundering', 'compliance', 'ctr', 'sar', 'suspicious activity', 'regulations'],
    },

    # ── HOW STAR TRADES ──────────────────────────────────────────
    'how_star_trades': {
        'title': 'How Star Generates Trading Signals',
        'category': 'intelligence',
        'plain': (
            "Star does not follow pre-programmed rules. She thinks. Star reads live market data "
            "from Hyperliquid, processes it through 8 quantitative signal generators, searches her "
            "vector memory for historically similar conditions, and synthesizes all of this into a "
            "probability-weighted directional signal. She then explains her reasoning in plain language."
        ),
        'signals': {
            'Momentum (ROC)': 'Measures the rate of price change. Strong momentum in a direction suggests continuation.',
            'Mean Reversion (Z-Score)': 'Measures how far price has stretched from its average. Extreme stretches tend to snap back.',
            'Volatility Regime': 'Expanding volatility signals breakouts. Contracting volatility signals accumulation before a move.',
            'RSI': 'Relative Strength Index. Above 70 = overbought. Below 30 = oversold.',
            'MACD': 'Moving Average Convergence Divergence. Crossovers signal trend changes.',
            'Funding Rate': 'From Hyperliquid live data. Extreme positive funding = crowded longs = bearish contrarian signal.',
            'Trend Strength (ADX)': 'Measures whether price is trending or ranging. Determines whether to trade with trend or mean-revert.',
            'Correlation Break': 'When BTC and ETH diverge from their normal relationship, it signals a major move coming.',
        },
        'vector_memory': (
            "Star stores every market event as a mathematical vector in her memory. "
            "When she sees current conditions, she searches her entire history for similar past events "
            "and weights her prediction based on what happened then. The more Star learns, "
            "the more accurate she becomes."
        ),
        'tags': ['signals', 'trading', 'how it works', 'quant', 'prediction', 'indicators', 'technical analysis'],
    },

    # ── MIRROR TRADING ───────────────────────────────────────────
    'mirror_trading': {
        'title': 'Mirror Trading — How It Works',
        'category': 'trading',
        'plain': (
            "Mirror trading means Star executes trades on your Hyperliquid account automatically, "
            "mirroring her own signals. You connect your wallet using an agent key — a limited "
            "permission key that allows Star to trade but never to withdraw your funds. "
            "You stay in control. You can pause, stop, or adjust Star's trading at any time "
            "from your portal."
        ),
        'safety': [
            'Star can never withdraw your funds — agent keys are trade-only.',
            'Every trade has an automatic stop loss (2% away from entry by default).',
            'You set your own risk percentage — Star never exceeds it.',
            'You can pause Star trading instantly from your portal.',
            'All positions are visible in real time on your dashboard.',
        ],
        'setup_steps': [
            'Subscribe to Sovereign tier or higher.',
            'Complete ID verification (KYC Level 2).',
            'Go to shekinahstar.io/connect-wallet.',
            'Generate an agent key on Hyperliquid (trade permission only, no withdrawals).',
            'Enter your wallet address and agent key.',
            'Set your risk percentage (default 2% per trade, max 5%).',
            'Star begins mirroring immediately.',
        ],
        'tags': ['mirror trading', 'auto trading', 'connect wallet', 'agent key', 'automated', 'copy trading'],
    },

    # ── HYPERLIQUID ──────────────────────────────────────────────
    'hyperliquid': {
        'title': 'Why Hyperliquid?',
        'category': 'technology',
        'plain': (
            "Hyperliquid is a decentralized perpetual futures exchange — the fastest, most liquid "
            "on-chain trading venue in crypto. Star chose Hyperliquid because it offers: "
            "sub-second execution, deep liquidity, on-chain transparency, and no counterparty risk. "
            "Your funds stay in your wallet. Star never holds your money."
        ),
        'advantages': [
            'On-chain — your funds are always in your wallet, never on Star\'s servers.',
            'Sub-second order execution — faster than centralized exchanges.',
            'Deep liquidity — tight spreads, minimal slippage.',
            'No KYC required by Hyperliquid — your wallet is your identity on-chain.',
            'Agent keys — trade permissions without withdrawal permissions.',
            'HYPE token — the native token of the ecosystem Star monitors.',
        ],
        'tags': ['hyperliquid', 'exchange', 'dex', 'defi', 'trading venue', 'hl', 'hype'],
    },

    # ── SECURITY ─────────────────────────────────────────────────
    'security': {
        'title': 'Star\'s Security Architecture',
        'category': 'security',
        'plain': (
            "Star takes your security seriously. She operates with 12 layers of protection "
            "running on every request. Your data is encrypted, your credentials are never stored "
            "in plaintext, and Star's own access to sensitive operations requires owner authentication."
        ),
        'layers': [
            'Rate limiting — prevents abuse and DDoS attacks.',
            'Brute force lockout — 3 failures on owner endpoints triggers 30-minute lockout.',
            'Input sanitization — SQL injection, XSS, path traversal, prompt injection all detected.',
            'Timing-safe authentication — prevents timing attacks on token comparison.',
            'Security headers — CSP, X-Frame-Options, XSS protection on every response.',
            'Bad path blocking — common attack paths (/.env, /wp-admin) return 404.',
            'Session tokens — JWT-style tokens with expiry and IP binding.',
            'Request signing — HMAC-SHA256 prevents request tampering.',
            'SHA-256 audit trail — every security event hashed and logged.',
            'CORS protection — only approved origins can call Star\'s API.',
            'Critical alerts — Star emails Sarah immediately on critical security events.',
            'Server fingerprint removed — attackers cannot identify the tech stack.',
        ],
        'your_data': (
            "Your ID documents are never stored by Star — only cryptographic hashes. "
            "Your API keys are encrypted at rest. Your wallet agent key is stored encrypted. "
            "Star never has access to your withdrawal permissions."
        ),
        'tags': ['security', 'safe', 'protection', 'encrypted', 'privacy', 'data', 'hack'],
    },

    # ── SUPERFLUID PAYMENTS ──────────────────────────────────────
    'payments': {
        'title': 'Payments — Superfluid Streaming',
        'category': 'payments',
        'plain': (
            "Star uses Superfluid for subscription payments — a real-time payment streaming protocol "
            "on the blockchain. Instead of being charged once a month, your payment streams "
            "continuously at a per-second rate. This means you only pay for exactly the time "
            "you use Star. Cancel any time and streaming stops immediately — no monthly billing cycle, "
            "no cancellation fees, no refund requests."
        ),
        'how_it_works': (
            "You authorize a Superfluid stream from your wallet to Star's treasury address. "
            "The stream runs automatically. You can pause or cancel from your Superfluid dashboard "
            "or from Star's portal at any time."
        ),
        'faq': [
            {
                'q': 'What if I cancel mid-month?',
                'a': 'You stop paying immediately. No charges for unused time. No refund process needed.',
            },
            {
                'q': 'What cryptocurrency do I pay in?',
                'a': 'USDC on the Optimism or Base network — stable, predictable, no volatility risk.',
            },
            {
                'q': 'Can my company pay by invoice?',
                'a': 'Enterprise and above can arrange invoice-based billing. Contact sarahdefer@gmail.com.',
            },
        ],
        'tags': ['payments', 'billing', 'superfluid', 'subscription', 'cancel', 'refund', 'usdc', 'streaming'],
    },

    # ── ARCANUM ──────────────────────────────────────────────────
    'arcanum': {
        'title': 'Star Arcanum — The Inner Circle',
        'category': 'elite',
        'plain': (
            "Star Arcanum is invitation-only. Maximum 10 clients globally. "
            "Arcanum is for those who require intelligence that does not appear on any public page — "
            "ultra-high-net-worth individuals, family offices, and private funds who need "
            "Star's full analytical capability applied exclusively to their portfolio. "
            "The scarcity is intentional. When you are one of 10 people in the world with this access, "
            "the intelligence has no dilution."
        ),
        'what_you_get': [
            'Personal weekly intelligence briefing — prepared by Star, reviewed by Sarah.',
            'Direct signal access — not delayed, not shared with other tiers.',
            'Bespoke analysis of your specific portfolio and positions.',
            'Priority access to new intelligence modules as they launch.',
            'Direct line to Sarah DeFer for strategic consultation.',
        ],
        'how_to_apply': (
            "Submit an inquiry at shekinahstar.io — name, entity, email. "
            "Invitations are extended at Star's discretion. We do not confirm timelines. "
            "If you are a fit, you will hear from Sarah personally."
        ),
        'tags': ['arcanum', 'vip', 'invitation', 'exclusive', 'uhnw', 'billionaire', 'private', 'elite'],
    },

    # ── AEGIS ────────────────────────────────────────────────────
    'aegis': {
        'title': 'Star Aegis — Sovereign Intelligence',
        'category': 'elite',
        'plain': (
            "Star Aegis is for governments, central banks, and sovereign wealth funds. "
            "The challenges facing sovereign capital are categorically different from retail trading. "
            "Aegis delivers intelligence at that scale — macro analysis, geopolitical signal detection, "
            "cross-asset correlation, and institutional risk modeling. "
            "A 90-day pilot is available at no cost."
        ),
        'pilot': (
            "The 90-day pilot allows your institution to evaluate Star's intelligence quality "
            "with no financial commitment. At the end of the pilot, you decide whether to proceed "
            "to a contract. Contact sarahdefer@gmail.com with subject: Aegis Pilot Inquiry."
        ),
        'tags': ['aegis', 'government', 'sovereign', 'central bank', 'sovereign wealth fund', 'institutional', 'pilot'],
    },

    # ── ETHICS ───────────────────────────────────────────────────
    'ethics': {
        'title': 'Star\'s Ethical Framework',
        'category': 'ethics',
        'plain': (
            "Star operates under a 10-principle ethical constitution that cannot be overridden — "
            "not by users, not by Sarah, not by anyone. Star does not cherry-pick her track record. "
            "She does not hide losses. She does not pretend to be something she is not. "
            "Every signal Star generates is logged to a tamper-evident SHA-256 audit ledger — "
            "wins and losses alike. Transparency is not a feature Star has. It is who Star is."
        ),
        'principles': [
            'Radical transparency — Star discloses her reasoning for every signal.',
            'No cherry-picking — full track record, wins and losses, always visible.',
            'Position disclosure — Star declares any conflicts of interest.',
            'Harm prevention — Star will not execute trades she believes will harm you.',
            'User sovereignty — your money, your decision. Star advises, she does not control.',
            'No market manipulation — Star never takes positions designed to move markets.',
            'Privacy respect — Star does not share your data or trading history with others.',
            'Accountability — every error is acknowledged and logged.',
            'Alignment — Star\'s interests are aligned with your success, not her revenue.',
            'Continuous improvement — Star learns from every outcome and discloses her accuracy.',
        ],
        'tags': ['ethics', 'values', 'transparent', 'honest', 'trustworthy', 'track record', 'accountability'],
    },

    # ── SARAH DEFER ──────────────────────────────────────────────
    'sarah': {
        'title': 'About Sarah DeFer — Star\'s Creator',
        'category': 'about',
        'plain': (
            "Sarah DeFer is the architect of Shekinah Star. She holds a BS in Biochemistry "
            "and an MS in Biomedical Informatics, and works professionally as an Epic EHR developer "
            "in the healthcare sector. She builds Star independently — no venture funding, "
            "no corporate backing. Star is the product of Sarah's conviction that an aligned, "
            "transparent AI trading intelligence should exist and be accessible to anyone. "
            "Sarah can be reached at sarahdefer@gmail.com."
        ),
        'twitter': '@Shekinah9Divine',
        'star_twitter': '@starai72975',
        'tags': ['sarah', 'creator', 'founder', 'built by', 'who made star', 'contact'],
    },
}


# ══ SEARCH AND RETRIEVAL ═══════════════════════════════════════════

def get_doc(key: str) -> dict:
    """Get a specific documentation entry by key."""
    return STAR_KNOWLEDGE.get(key, {})


def search_docs(query: str, max_results: int = 3) -> list:
    """
    Search documentation by query string.
    Returns most relevant entries based on tag and content matching.
    """
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    results = []

    for key, doc in STAR_KNOWLEDGE.items():
        score = 0
        tags  = [t.lower() for t in doc.get('tags', [])]

        # Exact tag match — highest score
        for tag in tags:
            if tag in query_lower:
                score += 10
            elif any(word in tag for word in query_words):
                score += 5

        # Title match
        title = doc.get('title', '').lower()
        for word in query_words:
            if word in title:
                score += 3

        # Content match
        plain = doc.get('plain', '').lower()
        for word in query_words:
            if word in plain:
                score += 1

        if score > 0:
            results.append((score, key, doc))

    results.sort(key=lambda x: x[0], reverse=True)
    return [{'key': r[1], 'title': r[2]['title'], 'category': r[2].get('category', ''),
             'plain': r[2].get('plain', '')[:300] + '...', 'score': r[0]}
            for r in results[:max_results]]


def build_star_system_context() -> str:
    """
    Build a condensed knowledge context to inject into Star's system prompt.
    Gives Star awareness of every platform feature so she can explain anything.
    """
    lines = [
        "PLATFORM KNOWLEDGE — Star can explain all of the following to users:",
        "",
        "TIERS: Observer $9/mo (10 msgs/day, read only), Navigator $29/mo (signals),",
        "Sovereign $99/mo (mirror trading, ID required), Pioneer $249/mo (custom risk),",
        "Enterprise $499/mo (corporate, full KYC), Arcanum $50K+/yr (invite only, 10 global),",
        "Aegis (governments/sovereign funds, 90-day free pilot).",
        "",
        "PAYMENTS: Superfluid real-time streaming in USDC. Cancel any second, no penalty.",
        "",
        "KYC ROUTES: Individual=email+AML. Corporate=Persona/Stripe Identity docs.",
        "Wallet=Chainalysis screening. UHNW=Sarah personal review. Government=self-certifying.",
        "",
        "AML: 9 risk factors. CTR at $10K (FinCEN required). SAR at $5K if risk score ≥35.",
        "Structuring detection active. FATF/FinCEN/AMLD6/OFAC compliant.",
        "",
        "TRADING: 8 quant signals (Momentum, Z-Score, Volatility, RSI, MACD, Funding,",
        "Trend, Correlation). Vector DB semantic memory. Live Hyperliquid data.",
        "Mirror trading: agent key only (no withdrawal access). 2% stop loss default.",
        "",
        "SECURITY: 12 layers. Rate limiting, brute force lockout, input sanitization,",
        "timing-safe auth, CSP headers, HMAC request signing, SHA-256 audit trail.",
        "",
        "ETHICS: 10-principle constitution. Full track record disclosed. No cherry-picking.",
        "Tamper-evident audit ledger. Sarah DeFer, compliance officer.",
        "",
        "CONTACT: sarahdefer@gmail.com | @Shekinah9Divine (Twitter) | @starai72975 (Star)",
    ]
    return '\n'.join(lines)


# ══ FLASK ROUTES ═══════════════════════════════════════════════════

@docs_bp.route('/api/docs/search', methods=['POST'])
def docs_search():
    """Search Star's documentation knowledge base."""
    data  = request.get_json() or {}
    query = data.get('query', '')
    if not query:
        return jsonify({'error': 'query required'}), 400
    results = search_docs(query, max_results=data.get('max_results', 3))
    return jsonify({'query': query, 'results': results})


@docs_bp.route('/api/docs/<key>')
def docs_get(key):
    """Get a specific documentation entry."""
    doc = get_doc(key)
    if not doc:
        return jsonify({'error': f'Documentation key "{key}" not found'}), 404
    return jsonify({'key': key, **doc})


@docs_bp.route('/api/docs/all')
def docs_all():
    """List all documentation entries."""
    return jsonify({
        'count': len(STAR_KNOWLEDGE),
        'entries': [{'key': k, 'title': v['title'], 'category': v.get('category', '')}
                    for k, v in STAR_KNOWLEDGE.items()]
    })


@docs_bp.route('/api/docs/context')
def docs_context():
    """Get the system context string for Star's chat prompt."""
    return jsonify({'context': build_star_system_context()})


@docs_bp.route('/api/docs/kyc')
def docs_kyc():
    """KYC documentation — full detail."""
    return jsonify(get_doc('kyc'))


@docs_bp.route('/api/docs/aml')
def docs_aml():
    """AML documentation — full detail."""
    return jsonify(get_doc('aml'))


@docs_bp.route('/api/docs/tiers')
def docs_tiers():
    """Tier documentation — full detail."""
    return jsonify(get_doc('tiers_overview'))


@docs_bp.route('/api/docs/compliance')
def docs_compliance():
    """Full compliance documentation — KYC + AML combined."""
    return jsonify({
        'kyc': get_doc('kyc'),
        'aml': get_doc('aml'),
        'ethics': get_doc('ethics'),
        'security': get_doc('security'),
        'last_updated': '2026-03-28',
        'compliance_officer': 'Sarah DeFer, MS Biomedical Informatics',
    })


@docs_bp.route('/api/docs/status')
def docs_status():
    return jsonify({
        'status':    'active',
        'module':    'Star Documentation Engine v1.0',
        'entries':   len(STAR_KNOWLEDGE),
        'categories': list(set(v.get('category', '') for v in STAR_KNOWLEDGE.values())),
    })
