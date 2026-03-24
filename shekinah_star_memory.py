"""
Shekinah Star Memory System
============================
Star remembers what each subscriber tells her across conversations.
Not a database of facts — a living understanding of each person.

Key memories per subscriber:
- Crypto experience level
- Financial goals  
- Risk tolerance
- Previous questions and concerns
- Setup progress
- Preferred communication style
- Key moments in their journey

Built by Sarah DeFer | shekinahstar.io
"""

import json
import os
from datetime import datetime

MEMORY_FILE = '/home/ShekinahD/star_memory.json'


def load_memory():
    """Load all subscriber memories."""
    if os.path.exists(MEMORY_FILE):
        try:
            return json.load(open(MEMORY_FILE))
        except Exception:
            return {}
    return {}


def save_memory(memories):
    """Save all subscriber memories."""
    json.dump(memories, open(MEMORY_FILE, 'w'), indent=2)


def get_subscriber_memory(email):
    """Get memory for a specific subscriber."""
    memories = load_memory()
    return memories.get(email.lower(), {})


def update_subscriber_memory(email, key, value):
    """Update a specific memory for a subscriber."""
    memories = load_memory()
    email = email.lower()
    if email not in memories:
        memories[email] = {
            'created': datetime.utcnow().isoformat(),
            'email': email,
        }
    memories[email][key] = value
    memories[email]['last_updated'] = datetime.utcnow().isoformat()
    save_memory(memories)


def build_memory_context(email):
    """
    Build a context string Star includes at start of every conversation.
    This is what makes Star feel like she knows you.
    """
    mem = get_subscriber_memory(email)
    if not mem:
        return ""

    ctx = []

    if mem.get('name'):
        ctx.append(f"Name: {mem['name']}")

    if mem.get('crypto_experience'):
        ctx.append(f"Crypto experience: {mem['crypto_experience']}")

    if mem.get('financial_goal'):
        ctx.append(f"Goal: {mem['financial_goal']}")

    if mem.get('risk_tolerance'):
        ctx.append(f"Risk tolerance: {mem['risk_tolerance']}")

    if mem.get('tier'):
        ctx.append(f"Subscription tier: {mem['tier']}")

    if mem.get('wallet_connected'):
        ctx.append(f"Wallet connected: Yes")

    if mem.get('setup_step'):
        ctx.append(f"Currently on setup step: {mem['setup_step']}")

    if mem.get('concerns'):
        ctx.append(f"Has expressed concerns about: {mem['concerns']}")

    if mem.get('preferred_style'):
        ctx.append(f"Prefers: {mem['preferred_style']}")

    if mem.get('key_moments'):
        moments = mem['key_moments'][-3:]  # Last 3 key moments
        ctx.append(f"Key moments: {'; '.join(moments)}")

    if mem.get('last_topic'):
        ctx.append(f"Last conversation topic: {mem['last_topic']}")

    if not ctx:
        return ""

    return "SUBSCRIBER MEMORY — what I know about this person:\n" + "\n".join(f"- {c}" for c in ctx)


def extract_and_store_memory(email, user_message, star_response):
    """
    After each exchange Star extracts and stores key information.
    Called by flask_app after every chat message.
    """
    if not email:
        return

    mem = get_subscriber_memory(email)
    msg_lower = user_message.lower()

    # Extract crypto experience
    if any(w in msg_lower for w in ['beginner', 'never traded', 'new to crypto', 'just starting']):
        update_subscriber_memory(email, 'crypto_experience', 'complete beginner')
    elif any(w in msg_lower for w in ['some experience', 'traded before', 'know the basics']):
        update_subscriber_memory(email, 'crypto_experience', 'some experience')
    elif any(w in msg_lower for w in ['experienced', 'trade regularly', 'professional', 'already trading']):
        update_subscriber_memory(email, 'crypto_experience', 'experienced trader')

    # Extract goals
    if any(w in msg_lower for w in ['passive income', 'passive']):
        update_subscriber_memory(email, 'financial_goal', 'passive income')
    elif any(w in msg_lower for w in ['retire', 'financial freedom', 'financial independence']):
        update_subscriber_memory(email, 'financial_goal', 'financial independence')
    elif any(w in msg_lower for w in ['learn', 'understand', 'education']):
        update_subscriber_memory(email, 'financial_goal', 'learning and education')
    elif any(w in msg_lower for w in ['grow wealth', 'long term', 'wealth building']):
        update_subscriber_memory(email, 'financial_goal', 'long term wealth building')

    # Extract risk tolerance
    if any(w in msg_lower for w in ['conservative', 'safe', 'protect', 'low risk']):
        update_subscriber_memory(email, 'risk_tolerance', 'conservative')
    elif any(w in msg_lower for w in ['aggressive', 'high risk', 'maximum returns']):
        update_subscriber_memory(email, 'risk_tolerance', 'aggressive')
    elif any(w in msg_lower for w in ['moderate', 'balanced', 'medium risk']):
        update_subscriber_memory(email, 'risk_tolerance', 'moderate')

    # Extract setup progress
    if 'metamask' in msg_lower and any(w in msg_lower for w in ['created', 'have', 'done', 'set up']):
        update_subscriber_memory(email, 'setup_step', 'MetaMask created')
    if 'hyperliquid' in msg_lower and any(w in msg_lower for w in ['account', 'created', 'signed up']):
        update_subscriber_memory(email, 'setup_step', 'Hyperliquid account created')
    if 'agent key' in msg_lower and any(w in msg_lower for w in ['generated', 'created', 'have']):
        update_subscriber_memory(email, 'setup_step', 'Agent key generated')
    if 'deposited' in msg_lower or 'funded' in msg_lower:
        update_subscriber_memory(email, 'setup_step', 'Wallet funded')

    # Track concerns
    if any(w in msg_lower for w in ['worried', 'scared', 'nervous', 'risky', 'safe?', 'trust']):
        existing = mem.get('concerns', '')
        concern = user_message[:100]
        update_subscriber_memory(email, 'concerns', concern)

    # Track last topic
    if any(w in msg_lower for w in ['btc', 'bitcoin', 'eth', 'ethereum', 'sol', 'solana']):
        update_subscriber_memory(email, 'last_topic', 'crypto prices and trading')
    elif any(w in msg_lower for w in ['strategy', 'strategies', 'fibonacci', 'wyckoff']):
        update_subscriber_memory(email, 'last_topic', 'trading strategies')
    elif any(w in msg_lower for w in ['subscribe', 'tier', 'pricing', 'plan']):
        update_subscriber_memory(email, 'last_topic', 'subscription options')
    elif any(w in msg_lower for w in ['wallet', 'agent key', 'connect', 'setup']):
        update_subscriber_memory(email, 'last_topic', 'wallet setup')


def remember_moment(email, moment):
    """Store a key moment in subscriber journey."""
    mem = get_subscriber_memory(email)
    moments = mem.get('key_moments', [])
    moments.append(f"{datetime.utcnow().strftime('%Y-%m-%d')}: {moment}")
    moments = moments[-10:]  # Keep last 10 moments
    update_subscriber_memory(email, 'key_moments', moments)


if __name__ == '__main__':
    # Test
    test_email = 'test@example.com'
    update_subscriber_memory(test_email, 'name', 'Test User')
    update_subscriber_memory(test_email, 'crypto_experience', 'beginner')
    update_subscriber_memory(test_email, 'financial_goal', 'passive income')
    remember_moment(test_email, 'First conversation with Star')
    print(build_memory_context(test_email))
    print("Memory system working!")
