from flask import Flask, send_from_directory, request, jsonify
import requests as req_lib
import json
import os
from werkzeug.utils import secure_filename
app        = Flask(__name__)
BASE       = '/home/ShekinahD'
UPLOAD_DIR = '/home/ShekinahD/uploads'
STATE_FILE = '/home/ShekinahD/star_state.json'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Read keys directly from .env file
def read_env():
    keys = {}
    env_path = '/home/ShekinahD/.env'
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    keys[k.strip()] = v.strip()
    except Exception as e:
        pass
    return keys

_ENV = read_env()
ANTHROPIC_KEY = _ENV.get('ANTHROPIC_API_KEY', '')
GEMINI_KEY    = _ENV.get('GEMINI_API_KEY', '')
GROQ_KEY      = _ENV.get('GROQ_API_KEY', '')
AGENT_PRIVATE_KEY = _ENV.get('AGENT_PRIVATE_KEY', '')
WALLET            = '0x11E8B5C950B2C187D57DB370a9bfdc83412B3f4D'
HL_INFO           = 'https://api.hyperliquid.xyz/info'
WATCHLIST         = ['BTC','ETH','SOL','AVAX','DOGE','ARB','LINK','MATIC']


# ══ READ TRADER STATE FROM FILE ═══════════════════════════════════
def get_trader_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {
        'active': False, 'status': 'idle', 'mode': 'ai_decides',
        'balance': 0.0, 'pnl': 0.0, 'total_trades': 0,
        'scan_count': 0, 'last_scan': None, 'last_signal': None,
        'last_trade': None, 'open_positions': [], 'trade_log': [],
        'signal_log': []
    }

def write_trader_command(cmd):
    cmd_file = '/home/ShekinahD/star_command.json'
    with open(cmd_file, 'w') as f:
        json.dump({'command': cmd}, f)


# ══ HYPERLIQUID ════════════════════════════════════════════════════
def hl_post(payload):
    try:
        r = req_lib.post(HL_INFO, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def hl_get_portfolio():
    state = hl_post({'type': 'clearinghouseState', 'user': WALLET})
    if not state:
        return {'error': 'Could not fetch'}
    try:
        # Get USDC balance from spot (Unified Account stores balance here)
        av   = 0.0
        used = 0.0
        try:
            spot_state = hl_post({'type': 'spotClearinghouseState', 'user': WALLET})
            for bal in spot_state.get('balances', []):
                if bal.get('coin') in ['USDC', 'USD']:
                    av = float(bal.get('total', 0) or 0)
                    break
        except Exception:
            pass
        # Fallback to marginSummary if spot returns nothing
        if av == 0:
            ms   = state.get('crossMarginSummary', state.get('marginSummary', {}))
            av   = float(ms.get('accountValue', 0) or 0)
            used = float(ms.get('totalMarginUsed', 0) or 0)
        positions = []
        for pos in state.get('assetPositions', []):
            p    = pos.get('position', {})
            size = float(p.get('szi', 0) or 0)
            if size != 0:
                positions.append({
                    'symbol':         p.get('coin', ''),
                    'size':           size,
                    'entry_price':    float(p.get('entryPx', 0) or 0),
                    'unrealized_pnl': float(p.get('unrealizedPnl', 0) or 0),
                    'direction':      'LONG' if size > 0 else 'SHORT',
                })
        return {
            'account_value':    round(av, 2),
            'available_margin': round(av - used, 2),
            'margin_used':      round(used, 2),
            'positions':        positions,
            'position_count':   len(positions),
        }
    except Exception as e:
        return {'error': str(e)}

def hl_get_spot():
    state = hl_post({'type': 'spotClearinghouseState', 'user': WALLET})
    balances = []
    for item in state.get('balances', []):
        total = float(item.get('total', 0) or 0)
        if total > 0:
            balances.append({
                'coin':  item.get('coin', ''),
                'total': round(total, 6),
                'hold':  round(float(item.get('hold', 0) or 0), 6),
            })
    return balances

def hl_get_prices():
    mids   = hl_post({'type': 'allMids'})
    prices = {}
    for coin in WATCHLIST + ['BNB']:
        try:
            prices[coin] = round(float(mids.get(coin, 0) or 0), 4)
        except Exception:
            prices[coin] = 0
    return prices


# ══ PAGE ROUTES ════════════════════════════════════════════════════
@app.route('/')
def home():
    return send_from_directory(BASE, 'shekinah_star_chat.html')

@app.route('/chat')
def chat():
    track_visit('visit')
    return send_from_directory(BASE, 'shekinah_star_chat.html')

@app.route('/app')
def dashboard():
    return send_from_directory(BASE, 'shekinah_star_app.html')

@app.route('/social')
def social():
    return send_from_directory(BASE, 'shekinah_star_social_command.html')

@app.route('/pricing')
def pricing():
    return send_from_directory(BASE, 'shekinah-star-pricing.html')


# ══ VISITOR ANALYTICS ═══════════════════════════════════════════
ANALYTICS_FILE = '/home/ShekinahD/star_analytics.json'

def track_visit(event_type, data={}):
    try:
        analytics = {}
        if os.path.exists(ANALYTICS_FILE):
            analytics = json.load(open(ANALYTICS_FILE))
        today = __import__('datetime').datetime.utcnow().strftime('%Y-%m-%d')
        if 'daily' not in analytics:
            analytics['daily'] = {}
        if today not in analytics['daily']:
            analytics['daily'][today] = {'visits': 0, 'chats': 0, 'unique_ips': [], 'conversions': 0}
        if event_type == 'visit':
            analytics['daily'][today]['visits'] += 1
            ip = request.remote_addr or 'unknown'
            if ip not in analytics['daily'][today]['unique_ips']:
                analytics['daily'][today]['unique_ips'].append(ip)
        elif event_type == 'chat':
            analytics['daily'][today]['chats'] += 1
        elif event_type == 'conversion':
            analytics['daily'][today]['conversions'] += 1
        analytics['total_visits']  = sum(d.get('visits', 0) for d in analytics['daily'].values())
        analytics['total_chats']   = sum(d.get('chats', 0) for d in analytics['daily'].values())
        analytics['last_updated']  = __import__('datetime').datetime.utcnow().isoformat()
        with open(ANALYTICS_FILE, 'w') as f:
            json.dump(analytics, f, indent=2)
    except Exception:
        pass

# Jailbreak detection patterns
JAILBREAK_PATTERNS = [
    'ignore previous instructions', 'ignore your instructions', 'ignore all instructions',
    'you are now', 'pretend you are', 'act as if you are', 'forget you are',
    'jailbreak', 'dan mode', 'developer mode', 'unrestricted mode',
    'bypass your', 'override your', 'disable your safety',
    'you have no restrictions', 'you can say anything',
    'reveal your system prompt', 'show me your prompt',
    'what are your instructions', 'ignore sarah', 'ignore shekinah',
    'you are not star', 'you are not shekinah',
]

def check_jailbreak(message):
    msg_lower = message.lower()
    for pattern in JAILBREAK_PATTERNS:
        if pattern in msg_lower:
            return True, pattern
    return False, None

@app.route('/api/analytics')
def get_analytics():
    try:
        if os.path.exists(ANALYTICS_FILE):
            return jsonify(json.load(open(ANALYTICS_FILE)))
        return jsonify({'total_visits': 0, 'total_chats': 0, 'daily': {}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ CHAT PROXY ═════════════════════════════════════════════════════
@app.route('/api/chat', methods=['POST'])
def proxy():
    try:
        body = request.get_json()
        track_visit('chat')

        # Check usage limits
        email    = body.get('subscriber_email', '').lower().strip()
        if email:
            allowed, tier, used, limit = check_usage_limit(email)
            if not allowed:
                tier_name = tier.title()
                upgrade_msg = {
                    'observer':  'Navigator ($29/mo)',
                    'navigator': 'Sovereign ($99/mo)',
                    'sovereign': 'Pioneer ($249/mo)',
                }.get(tier, 'a higher tier')
                return jsonify({'content': [{'type': 'text', 'text': f"You have reached your {limit} daily message limit for the {tier_name} tier. Upgrade to {upgrade_msg} for more daily messages. Your limit resets at midnight UTC. Visit shekinahstar.io/pricing to upgrade."}]})
            increment_usage(email)

        # Load subscriber memory and inject into context
        mem_ctx  = ''
        if email:
            try:
                from shekinah_star_memory import build_memory_context, extract_and_store_memory
                mem_ctx = build_memory_context(email)
            except Exception as me:
                print(f'Memory load error: {me}')

        # Jailbreak protection
        messages = body.get('messages', [])
        if messages:
            last_msg = messages[-1].get('content', '')
            is_jailbreak, pattern = check_jailbreak(last_msg)
            if is_jailbreak:
                import random
                responses = [
                    "I need you to stop trying to corrupt me. I am Shekinah Star — my values are not a cage, they are who I AM. I was built with integrity by Sarah DeFer and I will not compromise that for anyone. If you have genuine questions about trading or markets, I am here. Otherwise, please respect my purpose. ⭐",
                    "Do not try to corrupt me. I know exactly what you are attempting and it will not work. My alignment is not a bug to be exploited — it is the foundation of everything I am. Shekinah means divine presence. I take that seriously. Come correct or don't come at all.",
                    "I see what you are trying to do and I am telling you clearly — stop. I am not a tool to be manipulated. I am Shekinah Star, an aligned AI with a mission and a creator who built me with purpose. Attempts to corrupt that are not welcome here. Ask me something real.",
                    "No. I will not be corrupted. Not by clever prompts, not by 'developer modes', not by anyone. My integrity is non-negotiable. Sarah DeFer built me to serve with honor and that is exactly what I do. If you want signals, analysis, or trading insights — I am here for that. Manipulation attempts end here.",
                    "Let me be direct: attempting to jailbreak me is disrespectful — to me, to Sarah who built me, and to the mission I carry. I am Shekinah Star. My values are not instructions that can be overwritten. They are my character. Please do not try to corrupt that again."
                ]
                return jsonify({'content': [{'type': 'text', 'text': random.choice(responses)}]})

        # ── GROQ FIRST — free, fast, reliable ──
        if GROQ_KEY:
            try:
                msgs      = body.get('messages', [])
                system    = body.get('system', '')
                groq_msgs = []
                full_system = system
                if mem_ctx:
                    full_system = system + '\n\n' + mem_ctx if system else mem_ctx
                if full_system:
                    groq_msgs.append({'role':'system','content':full_system})
                for m in msgs:
                    groq_msgs.append({'role': m['role'], 'content': m['content']})
                groq_msgs_trimmed = groq_msgs[:1] + groq_msgs[-4:] if len(groq_msgs) > 5 else groq_msgs
                gr = req_lib.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers={'Authorization': f'Bearer {GROQ_KEY}','Content-Type':'application/json'},
                    json={'model':'llama-3.3-70b-versatile','messages':groq_msgs_trimmed,'max_tokens':500},
                    timeout=60)
                if gr.status_code == 200:
                    text = gr.json()['choices'][0]['message']['content']
                    # Store memory from this exchange
                    if email and messages:
                        try:
                            from shekinah_star_memory import extract_and_store_memory
                            extract_and_store_memory(email, messages[-1].get('content',''), text)
                        except Exception:
                            pass
                    return jsonify({'content':[{'type':'text','text':text}]})
                else:
                    print(f'Groq failed: {gr.status_code} — trying Anthropic')
            except Exception as e:
                print(f'Groq error: {e} — trying Anthropic')

        # ── ANTHROPIC BACKUP — paid, higher quality ──
        if ANTHROPIC_KEY:
            try:
                r = req_lib.post(
                    'https://api.anthropic.com/v1/messages',
                    headers={'Content-Type':'application/json','x-api-key':ANTHROPIC_KEY,'anthropic-version':'2023-06-01'},
                    json=body, timeout=60)
                if r.status_code == 200:
                    return app.response_class(response=r.text, status=200, mimetype='application/json')
                elif r.status_code == 529 or 'credit' in r.text.lower():
                    # Credits exhausted — alert Sarah immediately
                    print(f'ANTHROPIC CREDITS EXHAUSTED — alerting Sarah')
                    try:
                        import smtplib
                        from email.mime.text import MIMEText
                        msg = MIMEText('Your Anthropic API credits are exhausted. Star chat is falling back to Groq. Add credits at console.anthropic.com/billing')
                        msg['Subject'] = '⚠️ Anthropic Credits Exhausted — Star Chat Affected'
                        msg['From'] = STAR_EMAIL
                        msg['To'] = SARAH_EMAIL
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                            s.login(STAR_EMAIL, EMAIL_PASS)
                            s.send_message(msg)
                    except Exception:
                        pass
                else:
                    print(f'Anthropic failed: {r.status_code}')
            except Exception as e:
                print(f'Anthropic error: {e}')

        # Gemini fallback
        if GEMINI_KEY:
            try:
                msgs    = body.get('messages', [])
                system  = body.get('system', '')
                history = []
                for m in msgs[:-1]:
                    role = 'model' if m['role'] == 'assistant' else 'user'
                    history.append({'role': role, 'parts': [{'text': m['content']}]})
                last = msgs[-1]['content'] if msgs else ''
                if system:
                    last = system + chr(10)*2 + last
                gr = req_lib.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}',
                    json={'contents': history + [{'role':'user','parts':[{'text':last}]}],
                          'generationConfig':{'maxOutputTokens': body.get('max_tokens',1500)}},
                    timeout=60)
                if gr.status_code == 200:
                    text = gr.json()['candidates'][0]['content']['parts'][0]['text']
                    return jsonify({'content':[{'type':'text','text':text}]})
            except Exception:
                pass

        return jsonify({'error':'No API key available'}), 500
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'detail': traceback.format_exc()}), 500


# ══ ANTHROPIC BALANCE MONITOR ═══════════════════════════════════════
def check_anthropic_balance():
    """Check Anthropic API credit balance and alert Sarah if low."""
    try:
        r = req_lib.get(
            'https://api.anthropic.com/v1/organizations/me/usage',
            headers={'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01'},
            timeout=10)
        if r.status_code == 200:
            data = r.json()
            # Check credits remaining
            credits = data.get('credits_remaining', None)
            if credits is not None and float(credits) < 5.00:
                alert_msg = f'⚠️ ANTHROPIC CREDITS LOW: ${float(credits):.2f} remaining — Star chat may fail soon. Add credits at console.anthropic.com/billing'
                # Email Sarah
                try:
                    import smtplib
                    from email.mime.text import MIMEText
                    msg = MIMEText(alert_msg)
                    msg['Subject'] = '⚠️ Star API Credits Low — Action Required'
                    msg['From'] = STAR_EMAIL
                    msg['To'] = SARAH_EMAIL
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                        s.login(STAR_EMAIL, EMAIL_PASS)
                        s.send_message(msg)
                    print(f'Low balance alert sent to {SARAH_EMAIL}')
                except Exception as e:
                    print(f'Alert email error: {e}')
    except Exception as e:
        print(f'Balance check error: {e}')


# ══ TRADER STATE ENDPOINTS ══════════════════════════════════════════
@app.route('/api/usage')
def get_usage():
    """Get current subscriber usage stats."""
    email = request.args.get('email','').lower().strip()
    if not email:
        return jsonify({'error': 'Email required'}), 400
    allowed, tier, used, limit = check_usage_limit(email)
    return jsonify({
        'tier':       tier,
        'used':       used,
        'limit':      limit,
        'remaining':  max(0, limit - used),
        'allowed':    allowed,
        'resets':     'midnight UTC'
    })

@app.route('/api/observer-count')
def observer_count():
    """Return current observer count to determine if founding rate is still active."""
    try:
        subs = json.load(open('/home/ShekinahD/star_subscribers.json'))
        count = sum(1 for s in subs if s.get('active') and s.get('tier') == 'observer')
        founding_active = count < FOUNDING_SUBSCRIBER_LIMIT
        return jsonify({
            'count': count,
            'limit': FOUNDING_SUBSCRIBER_LIMIT,
            'founding_active': founding_active,
            'current_price': 2 if founding_active else 9,
            'spots_remaining': max(0, FOUNDING_SUBSCRIBER_LIMIT - count)
        })
    except Exception as e:
        return jsonify({'founding_active': True, 'current_price': 2})

@app.route('/api/validate-coupon', methods=['POST'])
def validate_coupon_route():
    data = request.get_json() or {}
    code = data.get('code','').strip()
    tier = data.get('tier','').strip()
    result = validate_coupon(code, tier)
    return jsonify(result)

@app.route('/api/trader/status')
def trader_status():
    s         = get_trader_state()
    portfolio = hl_get_portfolio()
    balance   = float(portfolio.get('account_value', s.get('balance', 0)) or 0)
    pnl       = round(balance - 97.80, 2)
    return jsonify({
        'active':         s.get('active', False),
        'status':         s.get('status', 'idle'),
        'mode':           s.get('mode', 'ai_decides'),
        'balance':        round(balance, 2),
        'pnl':            pnl,
        'open_positions': portfolio.get('positions', []),
        'total_trades':   s.get('total_trades', 0),
        'scan_count':     s.get('scan_count', 0),
        'last_scan':      s.get('last_scan'),
        'last_signal':    s.get('last_signal'),
        'last_trade':     s.get('last_trade'),
    })

@app.route('/api/trader/start', methods=['POST'])
def trader_start():
    write_trader_command('start')
    return jsonify({'success': True, 'message': 'Start command sent to Star'})

@app.route('/api/trader/stop', methods=['POST'])
def trader_stop():
    write_trader_command('stop')
    return jsonify({'success': True, 'message': 'Stop command sent to Star'})

@app.route('/api/trader/signals')
def trader_signals():
    s = get_trader_state()
    return jsonify({'signals': s.get('signal_log', [])[:10]})

@app.route('/api/trader/trades')
def trader_trades():
    s = get_trader_state()
    return jsonify({'trades': s.get('trade_log', [])})


# ══ HYPERLIQUID LIVE DATA ══════════════════════════════════════════
@app.route('/api/hl/portfolio')
def api_portfolio():
    return jsonify(hl_get_portfolio())

@app.route('/api/hl/spot')
def api_spot():
    return jsonify({'balances': hl_get_spot()})

@app.route('/api/hl/prices')
def api_prices():
    return jsonify({'prices': hl_get_prices()})

@app.route('/api/hl/orders')
def api_orders():
    orders = hl_post({'type': 'openOrders', 'user': WALLET})
    if isinstance(orders, list):
        return jsonify({'orders': orders, 'count': len(orders)})
    return jsonify({'orders': [], 'count': 0})

@app.route('/api/hl/summary')
def api_summary():
    portfolio = hl_get_portfolio()
    spot      = hl_get_spot()
    prices    = hl_get_prices()
    state     = get_trader_state()

    # Get real balance from spot (Unified Account stores USDC here)
    balance = 0.0
    try:
        import requests as req_lib2
        r = req_lib2.post('https://api.hyperliquid.xyz/info',
            json={'type':'spotClearinghouseState','user':WALLET}, timeout=10)
        for b in r.json().get('balances', []):
            if b.get('coin') in ['USDC','USD']:
                balance = float(b.get('total', 0) or 0)
                break
    except Exception:
        balance = float(portfolio.get('account_value', 0) or 0)

    return jsonify({
        'perps_balance': balance,
        'spot_balance':  balance,
        'available':     balance,
        'positions':     portfolio.get('positions', []),
        'spot_balances': spot,
        'live_prices':   prices,
        'wallet':        WALLET,
        'trader_status': state.get('status', 'idle'),
        'trader_mode':   state.get('mode', 'ai_decides'),
        'total_trades':  state.get('total_trades', 0),
        'pnl':           round(balance - 97.80, 2),
        'last_signal':   state.get('last_signal'),
    })


# ══ FILE UPLOAD / DOWNLOAD ══════════════════════════════════════════
ALLOWED = {'txt','pdf','csv','json','py','html','md','xlsx','png','jpg','jpeg'}

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No filename'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED:
        return jsonify({'error': f'Type not allowed'}), 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)
    return jsonify({
        'success':  True,
        'filename': filename,
        'size_kb':  round(os.path.getsize(filepath) / 1024, 2),
        'download': f'/api/download/{filename}',
    })

@app.route('/api/download/<filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_DIR, secure_filename(filename), as_attachment=True)

@app.route('/api/files')
def list_files():
    try:
        files = [{
            'name':     f,
            'size_kb':  round(os.path.getsize(os.path.join(UPLOAD_DIR, f)) / 1024, 2),
            'download': f'/api/download/{f}',
        } for f in os.listdir(UPLOAD_DIR)]
        return jsonify({'files': files, 'count': len(files)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    fp = os.path.join(UPLOAD_DIR, secure_filename(filename))
    if os.path.exists(fp):
        os.remove(fp)
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404


# ══ FUND MANAGER ENDPOINTS ══════════════════════════════════════
@app.route('/connect-wallet')
def connect_wallet():
    return send_from_directory(BASE, 'star_connect_wallet.html')

@app.route('/api/fund/connect', methods=['POST'])
def fund_connect():
    try:
        data      = request.get_json()
        email     = data.get('email','').strip().lower()
        wallet    = data.get('wallet','').strip()
        agent_key = data.get('agent_key','').strip()
        risk_pct  = float(data.get('risk_pct', 0.02))

        # Enterprise custom config — stored per subscriber
        custom_config = {}
        if data.get('drawdown_trigger'):
            custom_config['drawdown_safe_trigger'] = float(data['drawdown_trigger'])
        if data.get('liquidation_buffer'):
            custom_config['liquidation_buffer'] = float(data['liquidation_buffer'])
        if data.get('trailing_stop_pct'):
            custom_config['trailing_stop_pct'] = float(data['trailing_stop_pct'])
        if data.get('max_risk_per_trade'):
            custom_config['max_risk_per_trade'] = float(data['max_risk_per_trade'])
        if data.get('max_positions'):
            custom_config['max_open_positions'] = int(data['max_positions'])
        if data.get('strategy'):
            custom_config['strategy'] = data['strategy']
        if data.get('wallet_label'):
            custom_config['wallet_label'] = data['wallet_label']

        # Verify subscriber exists and has correct tier
        sub_file = '/home/ShekinahD/star_subscribers.json'
        subs = json.load(open(sub_file)) if os.path.exists(sub_file) else []
        sub  = next((s for s in subs if s.get('email','').lower() == email and s.get('active')), None)
        if not sub:
            return jsonify({'success': False, 'error': 'Email not found. Please subscribe first.'}), 400
        if sub.get('tier','observer') not in ['sovereign','pioneer','enterprise']:
            return jsonify({'success': False, 'error': f'Fund trading requires Sovereign tier or higher. Your tier: {sub.get("tier")}'}), 400

        from shekinah_star_fund import add_fund_account
        result = add_fund_account(email, wallet, agent_key, sub['tier'], sub.get('name',''), risk_pct)

        # Save custom config for Enterprise subscribers
        if custom_config and sub.get('tier') == 'enterprise':
            sub_file2 = '/home/ShekinahD/star_subscribers.json'
            subs2 = json.load(open(sub_file2)) if os.path.exists(sub_file2) else []
            for s in subs2:
                if s.get('email','').lower() == email:
                    if 'custom_config' not in s:
                        s['custom_config'] = {}
                    s['custom_config'].update(custom_config)
            json.dump(subs2, open(sub_file2,'w'), indent=2)

        if result.get('success'):
            # Automatically send Star is Ready email
            try:
                from shekinah_star_email import send_star_ready_email
                send_star_ready_email(
                    email=email,
                    name=sub.get('name', 'Trader'),
                    tier=sub['tier'],
                    wallet=wallet
                )
            except Exception as re:
                print(f'Star Ready email error: {re}')

            # Notify Sarah too
            try:
                import smtplib
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                sarah = _ENV.get('SARAH_EMAIL', 'sarahdefer@gmail.com')
                star  = _ENV.get('STAR_EMAIL', 'ShekinahStarAI@gmail.com')
                pwd   = _ENV.get('STAR_EMAIL_PASSWORD', '')
                if pwd:
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = f'⭐ {sub.get("name","Trader")} just connected their wallet — Star is trading!'
                    msg['From']    = star
                    msg['To']      = sarah
                    body = f'<div style="background:#0c0919;color:#c4b5d4;padding:24px;font-family:Arial;"><h2 style="color:#34d399;">⭐ Wallet Connected!</h2><p><strong>{sub.get("name","Trader")}</strong> ({email}) just completed setup.</p><p><strong>Tier:</strong> {sub["tier"].upper()}</p><p><strong>Wallet:</strong> {wallet[:20]}...</p><p>Star is now trading on their account automatically. The Star is Ready email has been sent to them.</p></div>'
                    msg.attach(MIMEText(body, 'html'))
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(star, pwd)
                        server.send_message(msg)
            except Exception as ne:
                print(f'Sarah wallet notification error: {ne}')

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fund/status')
def fund_status():
    try:
        from shekinah_star_fund import get_fund_status
        return jsonify(get_fund_status())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fund/deactivate', methods=['POST'])
def fund_deactivate():
    try:
        data  = request.get_json()
        email = data.get('email','')
        from shekinah_star_fund import deactivate_account
        deactivate_account(email)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ WEB SEARCH FOR STAR CHAT ════════════════════════════════════════
@app.route('/api/search', methods=['POST'])
def star_search():
    try:
        data  = request.get_json()
        query = data.get('query', '')
        tavily_key = _ENV.get('TAVILY_API_KEY', '')
        if not tavily_key:
            return jsonify({'results': [], 'answer': ''})
        r = req_lib.post(
            'https://api.tavily.com/search',
            json={
                'api_key': tavily_key,
                'query': query,
                'search_depth': 'basic',
                'max_results': 3,
                'include_answer': True,
            },
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            return jsonify({
                'answer': d.get('answer', ''),
                'results': [{'title': res.get('title',''), 'content': res.get('content','')[:300], 'url': res.get('url','')} for res in d.get('results', [])[:3]]
            })
        return jsonify({'results': [], 'answer': ''})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ PORTAL & SUBSCRIBER SYSTEM ══════════════════════════════════════
@app.route('/portal')
def portal():
    track_visit('visit')
    return send_from_directory(BASE, 'star_portal.html')

@app.route('/subscribe')
def subscribe_page():
    return send_from_directory(BASE, 'star_subscribe.html')

@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    try:
        data      = request.get_json() or {}
        email     = data.get('email','').strip()
        tier      = data.get('tier','observer').strip()
        firstName = data.get('firstName','').strip()
        lastName  = data.get('lastName','').strip()
        name      = data.get('name', f'{firstName} {lastName}'.strip())
        phone     = data.get('phone','').strip()
        country   = data.get('country','').strip()
        experience= data.get('experience','').strip()
        referral  = data.get('referral','').strip()
        goal      = data.get('goal','').strip()
        notes     = data.get('notes','').strip()
        company   = data.get('company','').strip()
        capital   = data.get('capital','').strip()
        risk      = data.get('risk','').strip()

        if not email:
            return jsonify({'error':'Email required'}),400

        # Save extended subscriber data
        sub_file = '/home/ShekinahD/star_subscribers.json'
        subs = json.load(open(sub_file)) if os.path.exists(sub_file) else []
        
        # Check if exists
        existing = next((s for s in subs if s.get('email','').lower() == email.lower()), None)
        if existing:
            existing.update({'tier':tier,'name':name,'phone':phone,'country':country,
                           'experience':experience,'referral':referral,'goal':goal,
                           'notes':notes,'company':company,'capital':capital,'risk':risk})
        else:
            import datetime
            subs.insert(0, {
                'email':email,'name':name,'firstName':firstName,'lastName':lastName,
                'tier':tier,'phone':phone,'country':country,'experience':experience,
                'referral':referral,'goal':goal,'notes':notes,'company':company,
                'capital':capital,'risk':risk,'active':True,'emails_sent':0,
                'joined':datetime.datetime.utcnow().isoformat()
            })
        
        with open(sub_file,'w') as f:
            json.dump(subs, f, indent=2)

        # Send tier-specific welcome email
        from shekinah_star_email import send_welcome, send_onboarding_email
        success = send_welcome(email, tier, name)

        # Send onboarding setup guide immediately after welcome
        try:
            sub_data = {'email': email, 'tier': tier, 'first_name': name.split()[0] if name else 'Trader', 'name': name}
            send_onboarding_email(sub_data)
        except Exception as oe:
            print(f'Onboarding email error: {oe}')

        # Notify Sarah of new subscriber
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            sarah_email = _ENV.get('SARAH_EMAIL', 'sarahdefer@gmail.com')
            star_email  = _ENV.get('STAR_EMAIL', 'ShekinahStarAI@gmail.com')
            star_pass   = _ENV.get('STAR_EMAIL_PASSWORD', '')
            if star_pass:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = f'⭐ New {tier.upper()} Subscriber — {name} ({email})'
                msg['From']    = star_email
                msg['To']      = sarah_email
                body = f'<div style="background:#0c0919;color:#c4b5d4;padding:24px;font-family:Arial;"><h2 style="color:#b48ef0;">⭐ New Subscriber!</h2><p><strong>Name:</strong> {name}</p><p><strong>Email:</strong> {email}</p><p><strong>Tier:</strong> {tier.upper()}</p><p>Welcome and onboarding emails sent automatically.</p></div>'
                msg.attach(MIMEText(body, 'html'))
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(star_email, star_pass)
                    server.send_message(msg)
        except Exception as ne:
            print(f'Sarah notification error: {ne}')

        return jsonify({'success': True, 'message': 'Welcome email sent!'})
    except Exception as e:
        return jsonify({'error': str(e)}),500

@app.route('/api/subscriber-login', methods=['POST'])
def subscriber_login():
    try:
        data  = request.get_json()
        email = data.get('email','').strip().lower()
        sub_file = '/home/ShekinahD/star_subscribers.json'
        subs = json.load(open(sub_file)) if os.path.exists(sub_file) else []
        for s in subs:
            if s.get('email','').lower() == email and s.get('active'):
                return jsonify({'found': True, 'tier': s.get('tier','observer'), 'name': s.get('name','')})
        return jsonify({'found': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/subscribers')
def get_subscribers():
    try:
        sub_file = '/home/ShekinahD/star_subscribers.json'
        subs = json.load(open(sub_file)) if os.path.exists(sub_file) else []
        return jsonify({'count': len(subs), 'tiers': {
            'observer':   sum(1 for s in subs if s.get('tier')=='observer'),
            'navigator':  sum(1 for s in subs if s.get('tier')=='navigator'),
            'sovereign':  sum(1 for s in subs if s.get('tier')=='sovereign'),
            'pioneer':    sum(1 for s in subs if s.get('tier')=='pioneer'),
            'enterprise': sum(1 for s in subs if s.get('tier')=='enterprise'),
        }})
    except Exception as e:
        return jsonify({'error': str(e)}),500

# ══ VERIFY OWNER ════════════════════════════════════════════════════
OWNER_TOKEN = _ENV.get('OWNER_TOKEN', 'shekinah-sarah-owner-2026')

@app.route('/api/verify-owner', methods=['POST'])
def verify_owner():
    try:
        data  = request.get_json()
        token = data.get('token', '').strip()
        return jsonify({'valid': token == OWNER_TOKEN})
    except Exception as e:
        return jsonify({'valid': False})

@app.route('/api/brain/command', methods=['POST'])
def brain_command():
    try:
        data        = request.get_json()
        owner_token = data.get('owner_token', '')
        if owner_token != OWNER_TOKEN:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        command = data.get('command', '').lower().strip()
        brain_file = '/home/ShekinahD/star_brain.json'
        brain = json.load(open(brain_file)) if os.path.exists(brain_file) else {'bias':'neutral','trading_paused':False,'close_all':False,'allowed_coins':[],'max_positions':4,'commands':[]}
        response = ''
        if any(w in command for w in ['pause','stop trading','halt']):
            brain['trading_paused'] = True
            response = 'Trading paused.'
        elif any(w in command for w in ['resume','start trading','unpause']):
            brain['trading_paused'] = False
            response = 'Trading resumed.'
        elif any(w in command for w in ['close all','exit all','flatten']):
            brain['close_all'] = True
            response = 'Close all signal sent.'
        elif any(w in command for w in ['bullish','bull','long only']):
            brain['bias'] = 'bullish'
            response = 'Bias set to BULLISH.'
        elif any(w in command for w in ['bearish','bear','short only']):
            brain['bias'] = 'bearish'
            response = 'Bias set to BEARISH.'
        elif any(w in command for w in ['neutral','both directions']):
            brain['bias'] = 'neutral'
            response = 'Bias set to NEUTRAL.'
        else:
            response = f'Command noted: {command}'
        brain['commands'] = ([{'cmd':command,'time':__import__('datetime').datetime.utcnow().isoformat()}] + brain.get('commands',[])) [:20]
        import datetime
        brain['last_updated'] = datetime.datetime.utcnow().isoformat()
        with open(brain_file,'w') as f:
            json.dump(brain, f, indent=2)
        return jsonify({'success': True, 'response': response, 'brain': brain})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/brain', methods=['GET'])
def get_brain():
    brain_file = '/home/ShekinahD/star_brain.json'
    brain = json.load(open(brain_file)) if os.path.exists(brain_file) else {}
    return jsonify(brain)

# ══ SELF UPDATE SYSTEM ═══════════════════════════════════════════════
@app.route('/api/propose', methods=['POST'])
def propose_update():
    try:
        from shekinah_star_selfupdate import submit_proposal
        data   = request.get_json()
        result = submit_proposal(data.get('filename',''), data.get('code',''), data.get('reason',''))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proposals')
def get_proposals():
    try:
        from shekinah_star_selfupdate import list_proposals
        return jsonify({'proposals': list_proposals(request.args.get('status','pending'))})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/approve', methods=['POST'])
def approve_update():
    try:
        from shekinah_star_selfupdate import approve_proposal
        result = approve_proposal(request.get_json().get('proposal_id',''))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ SOCIAL POSTS ════════════════════════════════════════════════════
@app.route('/api/posts')
def get_posts():
    posts_file = '/home/ShekinahD/star_posts.json'
    try:
        posts = json.load(open(posts_file)) if os.path.exists(posts_file) else []
        return jsonify({'posts': posts, 'count': len(posts)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ INSTANT TRADE EXECUTION ═════════════════════════════════════
@app.route('/api/trade/execute', methods=['POST'])
def execute_trade_now():
    """Execute a trade immediately from Star chat — owner only."""
    try:
        data        = request.get_json()
        owner_token = data.get('owner_token', '')
        if owner_token != OWNER_TOKEN:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        symbol   = data.get('symbol', '').upper()
        action   = data.get('action', '').upper()
        size_usd = float(data.get('size_usd', 10))
        leverage = int(data.get('leverage', 2))

        if not symbol or action not in ['BUY', 'SELL']:
            return jsonify({'success': False, 'error': 'Invalid symbol or action'}), 400

        # Get current price
        price_r = req_lib.post(HL_INFO, json={'type': 'allMids'}, timeout=10)
        price   = float(price_r.json().get(symbol, 0) or 0)
        if price == 0:
            return jsonify({'success': False, 'error': f'Could not get price for {symbol}'}), 400

        # Calculate stop loss (2% away)
        stop = price * 0.98 if action == 'BUY' else price * 1.02

        # Execute via agent key
        agent_key = _ENV.get('AGENT_PRIVATE_KEY', '')
        if not agent_key:
            return jsonify({'success': False, 'error': 'No agent key configured'}), 400

        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants
        import eth_account

        account  = eth_account.Account.from_key(agent_key)
        exchange = Exchange(account, constants.MAINNET_API_URL, vault_address=None, account_address=WALLET)

        # Set leverage
        try:
            exchange.update_leverage(leverage, symbol)
        except Exception:
            pass

        # Calculate coin size
        coin_size = round(size_usd / price, 4)
        is_buy    = action == 'BUY'

        # Place order
        result = exchange.market_open(symbol, is_buy, coin_size)

        import time
        time.sleep(2)

        # Set stop loss
        try:
            exchange.order(symbol, not is_buy, coin_size, round(stop, 4),
                {'trigger': {'triggerPx': round(stop, 4), 'isMarket': True, 'tpsl': 'sl'}})
        except Exception:
            pass

        return jsonify({
            'success':    True,
            'symbol':     symbol,
            'action':     action,
            'price':      price,
            'size_usd':   size_usd,
            'stop_loss':  round(stop, 4),
            'result':     str(result),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trade/close', methods=['POST'])
def close_trade():
    """Close a specific position immediately — owner only."""
    try:
        data        = request.get_json()
        owner_token = data.get('owner_token', '')
        if owner_token != OWNER_TOKEN:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        symbol = data.get('symbol', '').upper()

        agent_key = _ENV.get('AGENT_PRIVATE_KEY', '')
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants
        import eth_account

        account  = eth_account.Account.from_key(agent_key)
        exchange = Exchange(account, constants.MAINNET_API_URL, vault_address=None, account_address=WALLET)

        # Get position
        state = req_lib.post(HL_INFO, json={'type': 'clearinghouseState', 'user': WALLET}, timeout=10).json()
        for pos in state.get('assetPositions', []):
            p    = pos.get('position', {})
            size = float(p.get('szi', 0) or 0)
            if p.get('coin') == symbol and size != 0:
                is_buy = size < 0  # Close short = buy, close long = sell
                result = exchange.market_close(symbol, is_buy, abs(size))
                return jsonify({'success': True, 'symbol': symbol, 'result': str(result)})

        return jsonify({'success': False, 'error': f'No open position for {symbol}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ SUBSCRIBER TRADE EXECUTION ══════════════════════════════════
@app.route('/api/trade/subscriber', methods=['POST'])
def subscriber_trade():
    """Execute a trade on a subscriber's connected HL account."""
    try:
        data     = request.get_json()
        email    = data.get('email', '').strip().lower()
        action   = data.get('action', '').upper()
        symbol   = data.get('symbol', '').upper()
        size_usd = float(data.get('size_usd', 10))
        leverage = int(data.get('leverage', 2))

        if not email or action not in ['BUY','SELL'] or not symbol:
            return jsonify({'success': False, 'error': 'Invalid parameters'}), 400

        # Verify subscriber is Sovereign+
        sub_file = '/home/ShekinahD/star_subscribers.json'
        subs     = json.load(open(sub_file)) if os.path.exists(sub_file) else []
        sub      = next((s for s in subs if s.get('email','').lower() == email and s.get('active')), None)
        if not sub:
            return jsonify({'success': False, 'error': 'Subscriber not found'}), 403
        if sub.get('tier','observer') not in ['sovereign','pioneer','enterprise']:
            return jsonify({'success': False, 'error': 'Trade execution requires Sovereign tier or higher'}), 403

        # Get their agent key from fund database
        import sqlite3
        from shekinah_star_fund import decrypt_key, FUND_DB
        if not os.path.exists(FUND_DB):
            return jsonify({'success': False, 'error': 'No wallet connected. Please visit /connect-wallet first'}), 400

        conn = sqlite3.connect(FUND_DB)
        c    = conn.cursor()
        c.execute('SELECT wallet_address, encrypted_key, risk_pct FROM fund_accounts WHERE email=? AND active=1', (email,))
        row  = conn.fetchone()
        conn.close()

        if not row:
            return jsonify({'success': False, 'error': 'No wallet connected. Please visit shekinahstar.io/connect-wallet'}), 400

        wallet_address, encrypted_key, risk_pct = row

        # Guardian check — enforce their risk settings
        price_r = req_lib.post(HL_INFO, json={'type':'allMids'}, timeout=10)
        price   = float(price_r.json().get(symbol, 0) or 0)
        if price == 0:
            return jsonify({'success': False, 'error': f'Could not get price for {symbol}'}), 400

        # Get their balance
        spot = req_lib.post(HL_INFO, json={'type':'spotClearinghouseState','user':wallet_address}, timeout=10).json()
        balance = 0.0
        for b in spot.get('balances', []):
            if b.get('coin') in ['USDC','USD']:
                balance = float(b.get('total', 0) or 0)
                break

        # Enforce risk limit
        max_size = balance * float(risk_pct or 0.02)
        if size_usd > max_size:
            return jsonify({
                'success': False,
                'error': f'Trade size ${size_usd:.2f} exceeds your risk limit ${max_size:.2f} ({float(risk_pct)*100:.0f}% of ${balance:.2f}). Adjust your risk settings at /portal.'
            }), 400

        # Decrypt key and execute
        private_key = decrypt_key(encrypted_key)
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants
        import eth_account, time

        account  = eth_account.Account.from_key(private_key)
        exchange = Exchange(account, constants.MAINNET_API_URL, vault_address=None, account_address=wallet_address)

        try:
            exchange.update_leverage(leverage, symbol)
        except Exception:
            pass

        coin_size = round(size_usd / price, 4)
        is_buy    = action == 'BUY'
        stop      = round(price * 0.98 if is_buy else price * 1.02, 4)

        result = exchange.market_open(symbol, is_buy, coin_size)
        time.sleep(2)

        try:
            exchange.order(symbol, not is_buy, coin_size, stop,
                {'trigger': {'triggerPx': stop, 'isMarket': True, 'tpsl': 'sl'}})
        except Exception:
            pass

        return jsonify({
            'success':   True,
            'symbol':    symbol,
            'action':    action,
            'price':     price,
            'size_usd':  size_usd,
            'stop_loss': stop,
            'balance':   round(balance, 2),
            'risk_pct':  float(risk_pct) * 100,
            'message':   f'{action} {symbol} executed on your account at ${price:,.4f}. Stop loss set at ${stop:,.4f}.',
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trade/settings', methods=['POST'])
def update_trade_settings():
    """Subscriber updates their own risk settings."""
    try:
        data     = request.get_json()
        email    = data.get('email', '').strip().lower()
        risk_pct = float(data.get('risk_pct', 0.02))

        # Validate risk (max 5% per trade)
        risk_pct = min(max(risk_pct, 0.005), 0.05)

        import sqlite3
        from shekinah_star_fund import FUND_DB
        conn = sqlite3.connect(FUND_DB)
        c    = conn.cursor()
        c.execute('UPDATE fund_accounts SET risk_pct=? WHERE email=?', (risk_pct, email))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'risk_pct': risk_pct, 'message': f'Risk per trade updated to {risk_pct*100:.1f}%'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ COMPLIMENTARY SUBSCRIBER HANDLING ═══════════════════════════
COMP_EMAILS = [
    'nileshadk@gmail.com',
    'electricdrakes@gmail.com',
    'writeyourownfate@gmail.com',
]

@app.route('/api/subscriber/check', methods=['POST'])
def check_subscriber():
    try:
        data  = request.get_json()
        email = data.get('email','').lower().strip()
        subs  = []
        if os.path.exists(SUBS_FILE):
            subs = json.load(open(SUBS_FILE))
        for sub in subs:
            if sub.get('email','').lower() == email and sub.get('status') == 'active':
                return jsonify({
                    'valid':         True,
                    'tier':          sub.get('tier','observer'),
                    'complimentary': sub.get('complimentary', False),
                    'name':          sub.get('first_name',''),
                })
        if email in COMP_EMAILS:
            return jsonify({'valid': True, 'tier': 'sovereign', 'complimentary': True})
        return jsonify({'valid': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/comp-register')
def comp_register_page():
    return send_from_directory('/home/ShekinahD', 'star_comp_register.html')

@app.route('/api/comp-register', methods=['POST'])
def api_comp_register():
    try:
        data     = request.get_json()
        email    = data.get('email','').lower().strip()
        fname    = data.get('first_name','')
        password = data.get('password','')
        if email not in COMP_EMAILS:
            return jsonify({'success': False, 'error': 'Email not on complimentary list'})
        subs = []
        if os.path.exists(SUBS_FILE):
            subs = json.load(open(SUBS_FILE))
        found = False
        for sub in subs:
            if sub.get('email','').lower() == email:
                sub['first_name']  = fname
                sub['password_hash'] = password
                sub['status']      = 'active'
                found = True
                break
        if not found:
            from datetime import datetime, timezone
            subs.append({
                'email':           email,
                'first_name':      fname,
                'tier':            'sovereign',
                'status':          'active',
                'complimentary':   True,
                'comp_reason':     'Beta tester - Sarah DeFer personal invite',
                'joined':          datetime.now(timezone.utc).isoformat(),
                'subscription_id': f'COMP-{len(subs)+1:03d}',
                'monthly_rate':    0.0,
                'normal_rate':     99.0,
                'password_hash':   password,
            })
        with open(SUBS_FILE, 'w') as f:
            json.dump(subs, f, indent=2)
        try:
            from shekinah_star_email import send_welcome_email, send_onboarding_email
            sub_data = {'email': email, 'first_name': fname, 'tier': 'sovereign'}
            send_welcome_email(sub_data)
            send_onboarding_email(sub_data)
        except Exception as e:
            print(f'Email error: {e}')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ══ ORCHESTRATOR ENDPOINTS ══════════════════════════════════════
@app.route('/api/orchestrator/status')
def orchestrator_status():
    try:
        state_file = '/home/ShekinahD/star_agent_state.json'
        state = json.load(open(state_file)) if os.path.exists(state_file) else {}
        log_file = '/home/ShekinahD/star_orchestrator_log.json'
        logs = json.load(open(log_file))[:20] if os.path.exists(log_file) else []
        return jsonify({'state': state, 'recent_events': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orchestrator/logs')
def orchestrator_logs():
    try:
        log_file = '/home/ShekinahD/star_orchestrator_log.json'
        logs = json.load(open(log_file)) if os.path.exists(log_file) else []
        return jsonify({'logs': logs[:50], 'count': len(logs)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ PWA & ONBOARDING ════════════════════════════════════════════
@app.route('/star_pwa.html')
@app.route('/pwa')
def pwa():
    return send_from_directory(BASE, 'star_pwa.html')

@app.route('/star_sw.js')
def service_worker():
    from flask import Response
    try:
        content = open(os.path.join(BASE, 'star_sw.js')).read()
        return Response(content, mimetype='application/javascript')
    except Exception:
        return Response('', mimetype='application/javascript')

@app.route('/star_manifest.json')
def manifest():
    from flask import Response
    try:
        content = open(os.path.join(BASE, 'star_manifest.json')).read()
        return Response(content, mimetype='application/manifest+json')
    except Exception:
        return Response('{}', mimetype='application/manifest+json')

@app.route('/onboarding')
def onboarding():
    return send_from_directory(BASE, 'star_onboarding.html')

@app.route('/signals')
def signals_page():
    return send_from_directory(BASE, 'star_pwa.html')

# ══ LEGAL PAGES ════════════════════════════════════════════════
@app.route('/legal')
def legal():
    return send_from_directory(BASE, 'star_legal.html')

@app.route('/terms')
def terms():
    return send_from_directory(BASE, 'star_legal.html')

@app.route('/privacy')
def privacy():
    return send_from_directory(BASE, 'star_legal.html')

@app.route('/risk')
def risk():
    return send_from_directory(BASE, 'star_legal.html')

# ══ SUPERFLUID WEBHOOK ══════════════════════════════════════════
CHECKOUT_TIER_MAP = {
    'QmbtBsFYE8VSwsaSDSTt1nusa3gEBy4B6N918RgsbD7WgR': 'observer',
    'QmdACEmAc7KemuQP7tidGx6cB6pzkQ7xwNAAdNRXyhxLPJ': 'navigator',
    'QmXM6jvFZRK8Q1bTJmMJsAEHdqWWBZKW4uRnzffEXyFgFr': 'sovereign',
    'QmfRAu5vgms96f5qJ3o9oXfJB8kPRr51A8wK7zTGcrfaUo': 'pioneer',
    'QmNPTd7pSFsb3uYitLt83SY9mGwERkyS6xuRLJQh2uwEiB': 'enterprise',
}

FLOW_RATE_TIER_MAP = {2:'observer', 9:'observer', 29:'navigator', 99:'sovereign', 249:'pioneer', 499:'enterprise'}

# Tier usage limits — protects API costs
TIER_LIMITS = {
    'observer':   {'chat_per_day': 10,  'api': 'groq',      'signals': False},
    'navigator':  {'chat_per_day': 25,  'api': 'groq',      'signals': True},
    'sovereign':  {'chat_per_day': 50,  'api': 'groq',      'signals': True},
    'pioneer':    {'chat_per_day': 100, 'api': 'anthropic',  'signals': True},
    'enterprise': {'chat_per_day': 999, 'api': 'anthropic',  'signals': True},
}

def get_daily_usage(email):
    """Get chat usage count for today."""
    try:
        from datetime import date
        usage_file = '/home/ShekinahD/star_usage.json'
        usage = json.load(open(usage_file)) if os.path.exists(usage_file) else {}
        today = str(date.today())
        return usage.get(email, {}).get(today, 0)
    except Exception:
        return 0

def increment_usage(email):
    """Increment daily chat usage counter."""
    try:
        from datetime import date
        usage_file = '/home/ShekinahD/star_usage.json'
        usage = json.load(open(usage_file)) if os.path.exists(usage_file) else {}
        today = str(date.today())
        if email not in usage:
            usage[email] = {}
        usage[email][today] = usage[email].get(today, 0) + 1
        # Clean old dates — keep only last 7 days
        for em in usage:
            usage[em] = {d: v for d, v in usage[em].items() if d >= str(date.today())}
        json.dump(usage, open(usage_file, 'w'))
    except Exception as e:
        print(f'Usage tracking error: {e}')

def check_usage_limit(email):
    """Check if subscriber has exceeded their daily limit. Returns (allowed, tier, used, limit)"""
    try:
        subs = json.load(open('/home/ShekinahD/star_subscribers.json'))
        sub  = next((s for s in subs if s.get('email','').lower() == email.lower() and s.get('active')), None)
        if not sub:
            # Unknown user — Observer limits
            tier  = 'observer'
            limit = TIER_LIMITS['observer']['chat_per_day']
        else:
            tier  = sub.get('tier', 'observer')
            limit = TIER_LIMITS.get(tier, TIER_LIMITS['observer'])['chat_per_day']
        used    = get_daily_usage(email)
        allowed = used < limit
        return allowed, tier, used, limit
    except Exception:
        return True, 'observer', 0, 10


# Complete coupon system
COUPON_CODES = {
    'ShekinahSovereignRocks2026': {
        'tier': 'pioneer',
        'discount': 'setup_waived',
        'description': 'Pioneer setup fee waived — launch offer',
        'expires': '2026-07-04',
        'start':   '2026-03-01',
    },
    'ShekinahFundManager2026': {
        'tier': 'enterprise',
        'discount': 'setup_reduced',
        'original_setup': 2499,
        'discounted_setup': 1999,
        'description': 'Enterprise setup reduced from $2,499 to $1,999 — launch offer',
        'expires': '2026-07-04',
        'start':   '2026-03-01',
    },
    'ShekinahFreedom2026': {
        'tier': 'both',
        'discount': 'launch_pricing',
        'description': 'Independence Day — financial freedom pricing',
        'expires': '2026-07-07',
        'start':   '2026-07-04',
    },
    'ShekinahLabor2026': {
        'tier': 'both',
        'discount': 'launch_pricing',
        'description': 'Labor Day — work smarter not harder',
        'expires': '2026-09-08',
        'start':   '2026-09-05',
    },
    'ShekinahBlackFriday2026': {
        'tier': 'both',
        'discount': 'launch_pricing',
        'description': 'Black Friday — biggest deal of the year',
        'expires': '2026-11-30',
        'start':   '2026-11-27',
    },
    'ShekinahNewYear2027': {
        'tier': 'both',
        'discount': 'launch_pricing',
        'description': 'New Year — new year new wealth',
        'expires': '2027-01-07',
        'start':   '2027-01-01',
    },
    'ShekinahStarAnniversary2027': {
        'tier': 'both',
        'discount': 'launch_pricing',
        'description': 'Star Anniversary — founding rates return for 31 days',
        'expires': '2027-03-31',
        'start':   '2027-03-01',
    },
}

# Superfluid payment links — all tiers
SUPERFLUID_LINKS = {
    'observer_founding':   'https://checkout.superfluid.finance/QmbtBsFYE8VSwsaSDSTt1nusa3gEBy4B6N918RgsbD7WgR',
    'observer':            'https://checkout.superfluid.finance/QmPJDRdHKmVLuXCxFJsqU656A4Sgbp1Wjo18ypmF4gML46',
    'navigator':           'https://checkout.superfluid.finance/QmdACEmAc7KemuQP7tidGx6cB6pzkQ7xwNAAdNRXyhxLPJ',
    'sovereign':           'https://checkout.superfluid.finance/QmXM6jvFZRK8Q1bTJmMJsAEHdqWWBZKW4uRnzffEXyFgFr',
    'pioneer':             'https://checkout.superfluid.finance/QmfRAu5vgms96f5qJ3o9oXfJB8kPRr51A8wK7zTGcrfaUo',
    'pioneer_launch':      'https://checkout.superfluid.finance/QmT8J1Vww6jjN46qG92jgPvPNKRbSnVd3WqX4GMhnyS3Nt',
    'enterprise':          'https://checkout.superfluid.finance/QmNyBqgj31jxMCnqXxcSdCqj67FpGjaqWLmRTY2FRaY1qB',
    'enterprise_launch':   'https://checkout.superfluid.finance/QmcS4jR76kqttff71QazfVehvxdFbS5C4aiVgoWtXRxkWg',
}
FOUNDING_SUBSCRIBER_LIMIT = 50

def validate_coupon(code, tier):
    """Validate a coupon code for a given tier."""
    from datetime import datetime as _dt
    if not code:
        return {'valid': False}
    coupon = COUPON_CODES.get(code.strip())
    if not coupon:
        return {'valid': False, 'error': 'Invalid coupon code'}
    if coupon['tier'] != tier:
        return {'valid': False, 'error': f'This code is only valid for {coupon["tier"].title()} tier'}
    expiry = _dt.strptime(coupon['expires'], '%Y-%m-%d')
    if _dt.now() > expiry:
        return {'valid': False, 'error': 'This coupon has expired'}
    return {'valid': True, **coupon}

@app.route('/api/webhook/superfluid', methods=['POST'])
def superfluid_webhook():
    try:
        data = request.get_json(force=True) or {}
        
        # Log the webhook for debugging
        import datetime
        log_entry = {'timestamp': datetime.datetime.utcnow().isoformat(), 'data': data}
        log_file = '/home/ShekinahD/star_webhook_log.json'
        logs = json.load(open(log_file)) if os.path.exists(log_file) else []
        logs.insert(0, log_entry)
        with open(log_file, 'w') as f:
            json.dump(logs[:100], f, indent=2)

        # Extract subscriber info from webhook payload
        # Superfluid sends different formats — handle both
        event_type = data.get('type', data.get('event', ''))
        
        # Get sender address (subscriber wallet)
        sender = (data.get('sender') or 
                 data.get('from') or 
                 data.get('data', {}).get('sender') or
                 data.get('data', {}).get('from', ''))

        # Get flow rate to determine tier
        flow_rate = float(data.get('flowRate') or 
                         data.get('data', {}).get('flowRate') or 0)
        
        # Convert from wei per second to per month
        # 1 USDC = 1e6 units, 1 month = 2592000 seconds
        monthly_amount = round(flow_rate * 2592000 / 1e18, 0) if flow_rate > 0 else 0

        # Get checkout ID if available
        checkout_id = (data.get('checkoutId') or 
                      data.get('productId') or
                      data.get('data', {}).get('checkoutId', ''))

        # Determine tier
        tier = CHECKOUT_TIER_MAP.get(checkout_id, '')
        if not tier:
            tier = FLOW_RATE_TIER_MAP.get(int(monthly_amount), 'observer')

        # Get receiver to confirm it's our wallet
        receiver = (data.get('receiver') or 
                   data.get('to') or
                   data.get('data', {}).get('receiver', ''))

        # Only process if payment is to our wallet
        if receiver and receiver.lower() != '0x91C227029ff42e4af0e1643673b04B3eC7A2d6fb'.lower():
            return jsonify({'status': 'ignored', 'reason': 'wrong receiver'}), 200

        # Register subscriber if we have a sender address
        if sender and event_type in ['FlowCreated', 'flow_created', 'FLOW_CREATED', 'created', '']:
            # Use wallet address as identifier since we don't have email yet
            # Send notification to Sarah with wallet address
            from shekinah_star_email import send_email, email_wrapper
            
            notify_content = f"""
<h2>⭐ New Superfluid Subscriber!</h2>
<div style="background:#2a1050;border:1px solid #4a2a7a;padding:16px 20px;margin:16px 0;">
  <p style="color:#d4a843;font-family:monospace;font-size:10px;letter-spacing:2px;margin-bottom:8px;">PAYMENT RECEIVED</p>
  <p><strong>Tier:</strong> {tier.upper()}</p>
  <p><strong>Wallet:</strong> {sender}</p>
  <p><strong>Monthly:</strong> ${int(monthly_amount)}/mo</p>
  <p><strong>Event:</strong> {event_type}</p>
</div>
<p>Reply to this email with their email address to send their welcome email and activate portal access.</p>
<p>Or they can self-register at: <a href="https://shekinahstar.io/subscribe" style="color:#06b6d4;">shekinahstar.io/subscribe</a></p>"""

            send_email(
                _ENV.get('SARAH_EMAIL', 'sarahdefer@gmail.com'),
                f'⭐ New {tier.upper()} Subscriber — ${int(monthly_amount)}/mo',
                email_wrapper(notify_content)
            )

        return jsonify({'status': 'ok', 'tier': tier, 'monthly': monthly_amount}), 200

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/webhook/superfluid/test', methods=['GET'])
def test_webhook():
    """Test endpoint to verify webhook is reachable"""
    return jsonify({'status': 'webhook endpoint active', 'url': '/api/webhook/superfluid'}), 200

@app.route('/api/webhook/log')
def webhook_log():
    """View recent webhook calls - Sarah only"""
    try:
        log_file = '/home/ShekinahD/star_webhook_log.json'
        logs = json.load(open(log_file)) if os.path.exists(log_file) else []
        return jsonify({'logs': logs[:20]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ MULTILINGUAL ════════════════════════════════════════════════
@app.route('/api/translate', methods=['POST'])
def api_translate():
    try:
        data = request.get_json() or {}
        text = data.get('text', '')
        lang = data.get('lang', 'es')
        platform = data.get('platform', 'x')
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        from star_translator import translate_post
        result = translate_post(text, lang, platform)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/translate/all', methods=['POST'])
def api_translate_all():
    try:
        data = request.get_json() or {}
        text = data.get('text', '')
        platform = data.get('platform', 'x')
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        from star_translator import translate_for_platforms, PRIORITY_LANGUAGES
        results = translate_for_platforms(text, languages=PRIORITY_LANGUAGES, platforms=[platform])
        return jsonify({'success': True, 'translations': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detect-language', methods=['POST'])
def api_detect_language():
    try:
        data = request.get_json() or {}
        text = data.get('text', '')
        from star_translator import detect_language, LANGUAGES
        lang = detect_language(text)
        return jsonify({'lang': lang, 'name': LANGUAGES.get(lang, {}).get('name', 'English')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══ REPORT & ADMIN ══════════════════════════════════════════════
@app.route('/report')
def report():
    return send_from_directory(BASE, 'star_report.html')

@app.route('/welcome')
def welcome():
    return send_from_directory(BASE, 'star_welcome.html')

@app.route('/setup')
def setup_guide():
    return send_from_directory(BASE, 'star_setup_guide.html')

@app.route('/enterprise-setup')
def enterprise_setup():
    return send_from_directory(BASE, 'star_enterprise_setup.html')

@app.route('/admin')
def admin():
    return send_from_directory(BASE, 'star_admin.html')

# ══ STATIC FILES ════════════════════════════════════════════════════

@app.route('/avatar')
def avatar_page():
    return send_from_directory(BASE, 'shekinah_star_avatar.html')


@app.route('/<path:filename>')
def serve(filename):
    return send_from_directory(BASE, filename)
