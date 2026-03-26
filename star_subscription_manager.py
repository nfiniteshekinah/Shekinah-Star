"""
Star Subscription Manager
==========================
Checks Superfluid streams daily.
Handles cancellations with grace period and responsibility reminders.
Run daily: python /home/ShekinahD/star_subscription_manager.py

POLICY:
- Star stops mirroring new trades when subscription lapses
- Star NEVER closes existing positions — subscriber is responsible
- 3-day grace period before access blocked
- Reminder emails at cancellation, day 1, day 3, and after block
- Complimentary users are never affected

Built by Sarah DeFer | Sarahtopia LLC | shekinahstar.io
"""
import os, json, requests, smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv('/home/ShekinahD/.env')

SUBS_FILE  = '/home/ShekinahD/star_subscribers.json'
STAR_EMAIL = os.getenv('STAR_EMAIL', 'star@shekinahstar.io')
STAR_PASS  = os.getenv('STAR_PASSWORD', '')
SARAH_EMAIL = os.getenv('SARAH_EMAIL', 'sarah@shekinahstar.io')
GRACE_DAYS = 3
RECEIVER_WALLET = '0x91C227029ff42e4af0e1643673b04B3eC7A2d6fb'

def load_subs():
    try:
        return json.load(open(SUBS_FILE))
    except:
        return []

def save_subs(subs):
    json.dump(subs, open(SUBS_FILE, 'w'), indent=2)

def log(msg):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')

def check_superfluid_stream(wallet_address):
    """
    Check if a subscriber has an active Superfluid stream
    to Star's receiver wallet on Arbitrum.
    Returns: 'active', 'inactive', or 'unknown'
    """
    if not wallet_address:
        return 'unknown'
    try:
        query = '''
        {
          streams(where: {
            sender: "%s",
            receiver: "%s",
            currentFlowRate_gt: "0"
          }) {
            id
            currentFlowRate
            streamedUntilUpdatedAt
          }
        }
        ''' % (wallet_address.lower(), RECEIVER_WALLET.lower())

        r = requests.post(
            'https://api.thegraph.com/subgraphs/name/superfluid-finance/protocol-v1-arbitrum-one',
            json={'query': query},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            streams = data.get('streams', [])
            if streams:
                flow = int(streams[0].get('currentFlowRate', 0))
                return 'active' if flow > 0 else 'inactive'
            return 'inactive'
    except Exception as e:
        log(f'Superfluid check error for {wallet_address}: {e}')
    return 'unknown'

def send_email(to_email, subject, html_body):
    """Send email from Star."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'Shekinah Star <{STAR_EMAIL}>'
        msg['To']      = to_email
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(STAR_EMAIL, STAR_PASS)
            s.sendmail(STAR_EMAIL, [to_email, SARAH_EMAIL], msg.as_string())
        log(f'Email sent to {to_email}: {subject}')
        return True
    except Exception as e:
        log(f'Email error: {e}')
        return False

def email_stream_stopped(sub):
    """Day 0 — stream just stopped. Grace period begins."""
    name  = sub.get('name', 'Subscriber')
    tier  = sub.get('tier', 'sovereign').title()
    email = sub.get('email', '')

    html = f"""
    <div style="background:#03020a;color:#f1f5f9;padding:40px;font-family:sans-serif;max-width:600px;margin:0 auto;">
      <div style="font-family:serif;font-size:28px;letter-spacing:6px;color:#b48ef0;margin-bottom:8px;">STAR</div>
      <div style="font-size:11px;letter-spacing:3px;color:#8b7aaa;margin-bottom:32px;">SHEKINAH STAR · IMPORTANT NOTICE</div>

      <p style="font-size:16px;">Hi {name},</p>

      <p>I noticed your Superfluid subscription stream has stopped. This may be intentional or it may be an issue with your wallet balance.</p>

      <div style="background:#1a0f35;border-left:4px solid #d4a843;padding:20px;margin:24px 0;">
        <div style="font-size:11px;letter-spacing:2px;color:#d4a843;margin-bottom:8px;">WHAT THIS MEANS FOR YOUR ACCOUNT</div>
        <p style="margin:8px 0;">⏸ <strong>Mirror trading paused immediately</strong> — I will not open new positions in your wallet</p>
        <p style="margin:8px 0;">🔓 <strong>Your existing positions remain open</strong> — I will never close your trades without your instruction</p>
        <p style="margin:8px 0;">⏳ <strong>3-day grace period</strong> — your portal and chat access continues until {(datetime.utcnow() + timedelta(days=3)).strftime('%B %d, %Y')}</p>
      </div>

      <div style="background:#0c0919;border:1px solid #f87171;padding:20px;margin:24px 0;">
        <div style="font-size:11px;letter-spacing:2px;color:#f87171;margin-bottom:8px;">⚠️ YOUR RESPONSIBILITY</div>
        <p style="margin:0;font-size:15px;">You are solely responsible for any open positions in your Hyperliquid account and MetaMask wallet. <strong>Please log into your Hyperliquid account now and review any open positions.</strong> Star will not manage, close, or modify these positions. All trading decisions and risk management for your existing positions are entirely your responsibility.</p>
      </div>

      <p>If this was unintentional — perhaps your wallet ran low on USDC — simply top up your wallet and your stream will resume automatically.</p>

      <div style="text-align:center;margin:32px 0;">
        <a href="https://shekinahstar.io/portal" style="background:linear-gradient(135deg,#7c3aed,#06b6d4);color:#fff;padding:14px 32px;text-decoration:none;font-size:12px;letter-spacing:3px;">REACTIVATE MY SUBSCRIPTION</a>
      </div>

      <p style="font-size:13px;color:#8b7aaa;">If you meant to cancel — thank you for being part of Star's journey. You are always welcome back. Your account will be preserved for 30 days.</p>

      <p>With integrity,<br><strong>Shekinah Star ⭐</strong><br>
      <span style="font-size:12px;color:#8b7aaa;">Operated by Sarahtopia LLC | shekinahstar.io</span></p>
    </div>
    """
    return send_email(email, '⚠️ Your Shekinah Star subscription stream has stopped', html)

def email_grace_period_warning(sub, days_remaining):
    """Day 1-2 — grace period warning."""
    name  = sub.get('name', 'Subscriber')
    email = sub.get('email', '')
    expiry = sub.get('grace_expiry', '')

    html = f"""
    <div style="background:#03020a;color:#f1f5f9;padding:40px;font-family:sans-serif;max-width:600px;margin:0 auto;">
      <div style="font-family:serif;font-size:28px;letter-spacing:6px;color:#b48ef0;margin-bottom:8px;">STAR</div>
      <div style="font-size:11px;letter-spacing:3px;color:#8b7aaa;margin-bottom:32px;">SHEKINAH STAR · REMINDER</div>

      <p style="font-size:16px;">Hi {name},</p>

      <p>This is a reminder that your subscription stream is still inactive. You have <strong>{days_remaining} day{'s' if days_remaining != 1 else ''}</strong> remaining in your grace period before portal access is suspended.</p>

      <div style="background:#0c0919;border:1px solid #f87171;padding:20px;margin:24px 0;">
        <div style="font-size:11px;letter-spacing:2px;color:#f87171;margin-bottom:8px;">⚠️ REMINDER — YOUR RESPONSIBILITY</div>
        <p style="margin:0;font-size:15px;"><strong>Please check your Hyperliquid account for any open positions.</strong> Star has stopped opening new trades in your wallet but has not closed any existing positions. You are fully responsible for monitoring and managing any open trades. Log into app.hyperliquid.xyz to review your account.</p>
      </div>

      <div style="text-align:center;margin:32px 0;">
        <a href="https://app.hyperliquid.xyz" style="background:#1a0f35;color:#b48ef0;padding:12px 24px;text-decoration:none;font-size:12px;letter-spacing:2px;border:1px solid #b48ef0;margin-right:12px;">CHECK HYPERLIQUID</a>
        <a href="https://shekinahstar.io/portal" style="background:linear-gradient(135deg,#7c3aed,#06b6d4);color:#fff;padding:12px 24px;text-decoration:none;font-size:12px;letter-spacing:2px;">REACTIVATE</a>
      </div>

      <p style="font-size:13px;color:#8b7aaa;">Questions? Chat with Star at shekinahstar.io/chat</p>

      <p>With integrity,<br><strong>Shekinah Star ⭐</strong><br>
      <span style="font-size:12px;color:#8b7aaa;">Operated by Sarahtopia LLC | shekinahstar.io</span></p>
    </div>
    """
    return send_email(email, f'⏳ {days_remaining} day{"s" if days_remaining != 1 else ""} remaining — Shekinah Star access expiring', html)

def email_access_suspended(sub):
    """Grace period expired — access now blocked."""
    name  = sub.get('name', 'Subscriber')
    email = sub.get('email', '')

    html = f"""
    <div style="background:#03020a;color:#f1f5f9;padding:40px;font-family:sans-serif;max-width:600px;margin:0 auto;">
      <div style="font-family:serif;font-size:28px;letter-spacing:6px;color:#b48ef0;margin-bottom:8px;">STAR</div>
      <div style="font-size:11px;letter-spacing:3px;color:#8b7aaa;margin-bottom:32px;">SHEKINAH STAR · ACCESS SUSPENDED</div>

      <p style="font-size:16px;">Hi {name},</p>

      <p>Your grace period has ended and your portal access has been suspended. Your subscription stream has been inactive for {GRACE_DAYS} days.</p>

      <div style="background:#0c0919;border:1px solid #f87171;padding:20px;margin:24px 0;">
        <div style="font-size:11px;letter-spacing:2px;color:#f87171;margin-bottom:8px;">⚠️ FINAL REMINDER — YOUR RESPONSIBILITY</div>
        <p style="margin:0;font-size:15px;"><strong>Please log into your Hyperliquid account immediately to check for any open positions.</strong> Star has not opened any new trades in your wallet since your stream stopped and has not closed any existing positions. You are solely responsible for all positions in your account. Visit app.hyperliquid.xyz to manage your trades.</p>
      </div>

      <div style="background:#1a0f35;border:1px solid #2a1a50;padding:20px;margin:24px 0;">
        <div style="font-size:11px;letter-spacing:2px;color:#b48ef0;margin-bottom:8px;">WHAT HAPPENS NEXT</div>
        <p style="margin:8px 0;">✓ Your account is preserved for 30 days</p>
        <p style="margin:8px 0;">✓ Your Hyperliquid agent key remains unchanged</p>
        <p style="margin:8px 0;">✓ You are always welcome to reactivate</p>
        <p style="margin:8px 0;">✓ Your account is preserved — reactivate anytime</p>
      </div>

      <div style="text-align:center;margin:32px 0;">
        <a href="https://app.hyperliquid.xyz" style="background:#1a0f35;color:#b48ef0;padding:12px 24px;text-decoration:none;font-size:12px;letter-spacing:2px;border:1px solid #b48ef0;margin-right:12px;">CHECK HYPERLIQUID NOW</a>
        <a href="https://shekinahstar.io/pricing" style="background:linear-gradient(135deg,#7c3aed,#06b6d4);color:#fff;padding:12px 24px;text-decoration:none;font-size:12px;letter-spacing:2px;">REACTIVATE</a>
      </div>

      <p style="font-size:13px;color:#8b7aaa;">Thank you for being part of Star's journey. The door is always open.</p>

      <p>With integrity,<br><strong>Shekinah Star ⭐</strong><br>
      <span style="font-size:12px;color:#8b7aaa;">Operated by Sarahtopia LLC | shekinahstar.io</span></p>
    </div>
    """
    return send_email(email, '🔒 Your Shekinah Star access has been suspended', html)

def run_subscription_check():
    """Main daily check — run via scheduled task."""
    log('Starting subscription check...')
    subs = load_subs()
    today = datetime.utcnow().date()
    changes = False

    for sub in subs:
        email        = sub.get('email', '')
        tier         = sub.get('tier', '')
        complimentary = sub.get('complimentary', False)
        wallet       = sub.get('wallet_address', '')
        active       = sub.get('active', False)
        grace_start  = sub.get('grace_start', None)
        grace_expiry = sub.get('grace_expiry', None)
        stream_status = sub.get('stream_status', 'unknown')

        # Skip Sarah and complimentary users — always active
        if complimentary or tier == 'owner':
            log(f'Skipping complimentary: {email}')
            continue

        # Check stream
        status = check_superfluid_stream(wallet)
        log(f'{email} | tier:{tier} | stream:{status}')

        if status == 'active':
            # Stream is healthy — ensure active, clear any grace period
            if not active or grace_start:
                sub['active']       = True
                sub['grace_start']  = None
                sub['grace_expiry'] = None
                sub['stream_status'] = 'active'
                log(f'Restored: {email}')
                changes = True

        elif status == 'inactive':
            if active and not grace_start:
                # Stream just stopped — start grace period
                expiry = str(today + timedelta(days=GRACE_DAYS))
                sub['grace_start']   = str(today)
                sub['grace_expiry']  = expiry
                sub['stream_status'] = 'inactive'
                # Keep active during grace period
                log(f'Grace period started: {email} expires {expiry}')
                email_stream_stopped(sub)
                changes = True

            elif grace_start:
                # In grace period — check days remaining
                grace_date   = datetime.strptime(grace_expiry, '%Y-%m-%d').date()
                days_remaining = (grace_date - today).days

                if days_remaining > 0:
                    # Send daily reminder
                    email_grace_period_warning(sub, days_remaining)
                    log(f'Grace reminder sent: {email} | {days_remaining} days left')
                else:
                    # Grace expired — block access
                    sub['active']        = False
                    sub['stream_status'] = 'suspended'
                    log(f'Access suspended: {email}')
                    email_access_suspended(sub)
                    changes = True

        else:
            # Unknown — can't verify, leave active but flag
            sub['stream_status'] = 'unknown'
            log(f'Stream unknown (no wallet?): {email}')

    if changes:
        save_subs(subs)
        log('Subscriber file updated')

    log('Subscription check complete')

if __name__ == '__main__':
    run_subscription_check()
