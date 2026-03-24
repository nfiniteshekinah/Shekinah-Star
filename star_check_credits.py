"""
Daily credit balance checker.
Add to PythonAnywhere scheduled tasks — daily at 09:00
python /home/ShekinahD/star_check_credits.py
"""
import os, smtplib, requests
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv('/home/ShekinahD/.env')

ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY','')
GROQ_KEY      = os.getenv('GROQ_API_KEY','')
STAR_EMAIL    = os.getenv('STAR_EMAIL','ShekinahStarAI@gmail.com')
EMAIL_PASS    = os.getenv('STAR_EMAIL_PASSWORD','')
SARAH_EMAIL   = os.getenv('SARAH_EMAIL','sarahdefer@gmail.com')

def send_alert(subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From']    = STAR_EMAIL
        msg['To']      = SARAH_EMAIL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(STAR_EMAIL, EMAIL_PASS)
            s.send_message(msg)
        print(f'Alert sent: {subject}')
    except Exception as e:
        print(f'Alert failed: {e}')

def check_anthropic():
    if not ANTHROPIC_KEY:
        return
    try:
        # Test with minimal request to check if credits work
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'Content-Type':'application/json','x-api-key':ANTHROPIC_KEY,'anthropic-version':'2023-06-01'},
            json={'model':'claude-haiku-4-5-20251001','max_tokens':10,'messages':[{'role':'user','content':'hi'}]},
            timeout=15)
        
        if r.status_code == 200:
            print('Anthropic: OK')
        elif r.status_code in [402, 529]:
            send_alert(
                '⚠️ URGENT: Anthropic Credits Exhausted — Star Chat Down',
                'Your Anthropic API credits are exhausted. Star chat is failing.\n\nAdd credits immediately at:\nhttps://console.anthropic.com/billing\n\nGroq free backup is active but Star quality is reduced.'
            )
        elif r.status_code == 200:
            # Check remaining if header available
            remaining = r.headers.get('anthropic-ratelimit-tokens-remaining')
            print(f'Anthropic: OK — tokens remaining: {remaining}')
        else:
            print(f'Anthropic: Status {r.status_code}')
    except Exception as e:
        print(f'Anthropic check error: {e}')

def check_groq():
    if not GROQ_KEY:
        print('Groq: No key')
        return
    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization':f'Bearer {GROQ_KEY}','Content-Type':'application/json'},
            json={'model':'llama-3.1-8b-instant','messages':[{'role':'user','content':'hi'}],'max_tokens':5},
            timeout=15)
        if r.status_code == 200:
            print('Groq: OK')
        elif r.status_code == 429:
            send_alert(
                '⚠️ Groq Rate Limited — Star Backup Unavailable',
                'Groq free tier is rate limited. If Anthropic credits are also low, Star chat may fail.\n\nCheck usage at https://console.groq.com'
            )
        else:
            print(f'Groq: Status {r.status_code}')
    except Exception as e:
        print(f'Groq check error: {e}')

if __name__ == '__main__':
    print('Checking API credits...')
    check_anthropic()
    check_groq()
    print('Done')
