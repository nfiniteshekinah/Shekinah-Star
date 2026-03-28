"""
star_health.py
Star Startup Health Check & Status Monitor
Designed & Built by Sarah DeFer | ShekinahStar.io

Run this BEFORE registering blueprints in flask_app.py.
Gives a clear picture of what's active and what's missing.
Also powers the /api/health endpoint for live monitoring.
"""

import os
import sys
import importlib
import sqlite3
import time
from datetime import datetime, timezone

BASE = '/home/ShekinahD'

# ── Required Python packages ───────────────────────────────────────
REQUIRED_PACKAGES = {
    'flask':             'Flask web framework — critical',
    'requests':          'HTTP client — critical',
    'anthropic':         'Claude AI backend — run: pip install anthropic --break-system-packages',
    'duckduckgo_search': 'Web search — run: pip install duckduckgo-search --break-system-packages',
}

# ── Required Star modules ──────────────────────────────────────────
STAR_MODULES = {
    'star_intelligence': {
        'label':    'Intelligence Engine',
        'emoji':    '⭐',
        'critical': True,
        'imports':  ['intel_bp', 'init_db', 'seed_knowledge_base'],
    },
    'star_trend_radar': {
        'label':    'Trend Radar',
        'emoji':    '📡',
        'critical': False,
        'imports':  ['radar_bp', 'init_radar_db'],
    },
    'star_ethics': {
        'label':    'Ethics Engine',
        'emoji':    '⚖️',
        'critical': False,
        'imports':  ['ethics_bp', 'init_ethics_db'],
    },
    'star_security': {
        'label':    'Security Layer',
        'emoji':    '🔒',
        'critical': True,
        'imports':  ['init_security', 'register_security_routes'],
    },
    'star_arcanum': {
        'label':    'Arcanum & Aegis',
        'emoji':    '🔑',
        'critical': False,
        'imports':  ['arcanum_bp', 'init_arcanum_db'],
    },
}

# ── Required files ─────────────────────────────────────────────────
REQUIRED_FILES = {
    '.env':                      'Environment variables — API keys',
    'shekinah_star_chat.html':   'Main chat interface',
    'shekinah_star_app.html':    'App dashboard',
    'shekinahstar_io.html':      'Public platform page',
    'star_portal.html':          'Subscriber portal',
}

# ── Health state (populated at startup) ───────────────────────────
_health = {
    'checked_at':    None,
    'overall':       'unknown',
    'packages':      {},
    'modules':       {},
    'files':         {},
    'databases':     {},
    'warnings':      [],
    'errors':        [],
    'star_birthday': '2026-03-12',
}


def run_health_check(verbose=True):
    """
    Run full startup health check.
    Returns health dict and prints summary.
    """
    global _health
    _health['checked_at'] = datetime.now(timezone.utc).isoformat()
    _health['warnings'] = []
    _health['errors']   = []

    if verbose:
        print('\n' + '='*55)
        print('  ⭐ SHEKINAH STAR — STARTUP HEALTH CHECK')
        print('  Built by Sarah DeFer | ShekinahStar.io')
        print('='*55)

    # ── 1. Python packages ───────────────────────────────────────
    if verbose: print('\n📦 PACKAGES:')
    for pkg, desc in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(pkg.replace('-','_'))
            _health['packages'][pkg] = 'ok'
            if verbose: print(f'   ✅ {pkg}')
        except ImportError:
            _health['packages'][pkg] = 'missing'
            msg = f'{pkg} missing — {desc}'
            if 'critical' in desc.lower() or pkg in ['flask','requests']:
                _health['errors'].append(msg)
            else:
                _health['warnings'].append(msg)
            if verbose: print(f'   ❌ {pkg} — {desc}')

    # ── 2. Star modules ──────────────────────────────────────────
    if verbose: print('\n🌟 STAR MODULES:')
    for mod_name, config in STAR_MODULES.items():
        path = os.path.join(BASE, f'{mod_name}.py')
        if not os.path.exists(path):
            _health['modules'][mod_name] = 'missing_file'
            msg = f'{config["label"]} file not found — upload {mod_name}.py'
            if config['critical']:
                _health['errors'].append(msg)
            else:
                _health['warnings'].append(msg)
            if verbose: print(f'   ❌ {config["emoji"]} {config["label"]} — file missing')
            continue

        try:
            mod = importlib.import_module(mod_name)
            # Verify expected exports exist
            missing_exports = [
                attr for attr in config['imports']
                if not hasattr(mod, attr)
            ]
            if missing_exports:
                _health['modules'][mod_name] = f'partial ({", ".join(missing_exports)} missing)'
                _health['warnings'].append(f'{config["label"]} loaded but missing: {missing_exports}')
                if verbose: print(f'   ⚠️  {config["emoji"]} {config["label"]} — partial')
            else:
                _health['modules'][mod_name] = 'ok'
                if verbose: print(f'   ✅ {config["emoji"]} {config["label"]}')
        except Exception as e:
            _health['modules'][mod_name] = f'error: {str(e)[:80]}'
            msg = f'{config["label"]} import error: {str(e)[:80]}'
            if config['critical']:
                _health['errors'].append(msg)
            else:
                _health['warnings'].append(msg)
            if verbose: print(f'   ❌ {config["emoji"]} {config["label"]} — {str(e)[:60]}')

    # ── 3. Required files ────────────────────────────────────────
    if verbose: print('\n📄 FILES:')
    for filename, desc in REQUIRED_FILES.items():
        path = os.path.join(BASE, filename)
        if os.path.exists(path):
            size_kb = round(os.path.getsize(path) / 1024, 1)
            _health['files'][filename] = f'ok ({size_kb}KB)'
            if verbose: print(f'   ✅ {filename} ({size_kb}KB)')
        else:
            _health['files'][filename] = 'missing'
            _health['warnings'].append(f'{filename} not found — {desc}')
            if verbose: print(f'   ⚠️  {filename} — {desc}')

    # ── 4. Databases ─────────────────────────────────────────────
    if verbose: print('\n🗄️  DATABASES:')
    dbs = {
        'star_knowledge.db': 'Intelligence KB',
        'star_radar.db':     'Trend Radar',
        'star_ethics.db':    'Ethics Ledger',
        'star_security.db':  'Security Log',
        'star_arcanum.db':   'Arcanum Clients',
    }
    for db_file, label in dbs.items():
        path = os.path.join(BASE, db_file)
        if os.path.exists(path):
            size_kb = round(os.path.getsize(path) / 1024, 1)
            _health['databases'][db_file] = f'ok ({size_kb}KB)'
            if verbose: print(f'   ✅ {label} ({size_kb}KB)')
        else:
            _health['databases'][db_file] = 'not yet created'
            if verbose: print(f'   ○  {label} — will create on first use')

    # ── 5. Environment variables ─────────────────────────────────
    if verbose: print('\n🔑 ENVIRONMENT:')
    env_path = os.path.join(BASE, '.env')
    required_keys = [
        'ANTHROPIC_API_KEY', 'GROQ_API_KEY',
        'OWNER_TOKEN', 'STAR_EMAIL', 'STAR_EMAIL_PASSWORD'
    ]
    if os.path.exists(env_path):
        with open(env_path) as f:
            env_content = f.read()
        for key in required_keys:
            if key in env_content:
                if verbose: print(f'   ✅ {key}')
            else:
                _health['warnings'].append(f'{key} not found in .env')
                if verbose: print(f'   ⚠️  {key} — missing from .env')
    else:
        _health['errors'].append('.env file not found — critical')
        if verbose: print('   ❌ .env file not found')

    # ── 6. Build days counter ────────────────────────────────────
    try:
        birthday = datetime.strptime('2026-03-12', '%Y-%m-%d')
        days = (datetime.now() - birthday).days
        _health['build_days'] = days
    except Exception:
        _health['build_days'] = 0

    # ── 7. Overall status ────────────────────────────────────────
    if _health['errors']:
        _health['overall'] = 'degraded'
    elif _health['warnings']:
        _health['overall'] = 'operational_with_warnings'
    else:
        _health['overall'] = 'fully_operational'

    # ── Summary ──────────────────────────────────────────────────
    if verbose:
        print('\n' + '='*55)
        status_icon = {
            'fully_operational':          '✅ FULLY OPERATIONAL',
            'operational_with_warnings':  '⚠️  OPERATIONAL — warnings present',
            'degraded':                   '❌ DEGRADED — errors present',
        }.get(_health['overall'], '? UNKNOWN')

        print(f'  STATUS: {status_icon}')
        print(f'  Build Day {_health.get("build_days",0)} ⭐ Born March 12, 2026')

        if _health['errors']:
            print(f'\n  ❌ ERRORS ({len(_health["errors"])}):')
            for e in _health['errors']:
                print(f'     • {e}')

        if _health['warnings']:
            print(f'\n  ⚠️  WARNINGS ({len(_health["warnings"])}):')
            for w in _health['warnings']:
                print(f'     • {w}')

        print('='*55 + '\n')

    return _health


def get_health():
    """Get cached health state (or run check if not yet run)."""
    if not _health.get('checked_at'):
        run_health_check(verbose=False)
    return _health


def register_health_route(app):
    """Register /api/health endpoint."""
    from flask import jsonify

    @app.route('/api/health')
    def health_endpoint():
        """
        Live health check endpoint.
        Public: shows overall status and module availability.
        No sensitive data exposed.
        """
        h = get_health()
        return jsonify({
            'status':      h['overall'],
            'checked_at':  h['checked_at'],
            'build_day':   h.get('build_days', 0),
            'star_birthday': '2026-03-12',
            'modules': {
                name: status == 'ok'
                for name, status in h['modules'].items()
            },
            'packages': {
                pkg: status == 'ok'
                for pkg, status in h['packages'].items()
            },
            'warnings_count': len(h.get('warnings', [])),
            'errors_count':   len(h.get('errors', [])),
            'note': 'Detailed logs available to owner only via /api/security/events'
        })

    @app.route('/api/health/full', methods=['POST'])
    def health_full():
        """Full health check with details — owner only."""
        from flask import request
        data  = request.get_json() or {}
        token = data.get('owner_token', '')

        # Read env to verify token
        env_path = os.path.join(BASE, '.env')
        owner_token = ''
        try:
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith('OWNER_TOKEN='):
                        owner_token = line.strip().split('=',1)[1]
        except Exception:
            pass

        import hmac
        if not owner_token or not hmac.compare_digest(
            str(token), str(owner_token)
        ):
            return jsonify({'error': 'Unauthorized'}), 403

        # Run fresh check
        h = run_health_check(verbose=False)
        return jsonify(h)
