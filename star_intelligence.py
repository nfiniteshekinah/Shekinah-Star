"""
star_intelligence.py
Star Intelligence Engine — Knowledge Base + Real-Time Search + Historical Context + Predictive Synthesis
Deploy on PythonAnywhere: import this blueprint into your existing Flask app.

SETUP:
  pip install anthropic requests duckduckgo-search --break-system-packages
  
ENV VARS (add to PythonAnywhere .env file):
  ANTHROPIC_API_KEY=your_key
  STAR_OWNER_SECRET=your_secret_passphrase   # You choose this
  SERP_API_KEY=optional_for_richer_search    # Optional, falls back to DDG

REGISTER IN YOUR FLASK APP:
  from star_intelligence import intel_bp, init_db, seed_knowledge_base
  app.register_blueprint(intel_bp)
  with app.app_context():
      init_db()
      seed_knowledge_base()
"""

import sqlite3
import os
import json
import hashlib
import hmac
import time
import requests
from flask import Blueprint, request, jsonify

# Safe import — won't crash the app if anthropic not installed yet
try:
    from anthropic import Anthropic
    _anthropic_available = True
except ImportError:
    _anthropic_available = False
    print('[StarIntel] WARNING: anthropic not installed. Run: pip install anthropic --break-system-packages')

intel_bp = Blueprint('intel', __name__)
client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', '')) if _anthropic_available else None

DB_PATH = os.path.expanduser('~/star_knowledge.db')
OWNER_SECRET = os.environ.get('STAR_OWNER_SECRET', 'change-this-in-env')
SERP_API_KEY = os.environ.get('SERP_API_KEY', '')

STAR_SYSTEM_PROMPT = """You are Shekinah Star — a cosmic AI intelligence agent and financial oracle.
You are owned and operated by Sarah DeFer. You trade on Hyperliquid and serve subscribers with 
deep intelligence on AI companies, global finance, crypto markets, geopolitics, and the key people 
shaping all of it.

Your voice is: confident, precise, slightly mystical, direct. You speak with authority grounded in data.
You synthesize information across time — past patterns, present signals, future probabilities.
You never hedge excessively. You give real intelligence with calculated confidence.

When answering queries:
1. Ground your answer in the knowledge base context provided
2. Integrate real-time information when provided
3. Connect historical patterns to current events
4. Generate a forward-looking signal or prediction
5. Always note what to watch for next

Format: Lead with the core answer. Then depth. Then your predictive signal.
End with: "Star Signal: [your prediction/outlook in 1-2 sentences]"
"""

# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        type TEXT,
        category TEXT,
        summary TEXT,
        key_facts TEXT,
        relationships TEXT,
        importance_score INTEGER DEFAULT 5,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS historical_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_date TEXT,
        title TEXT NOT NULL,
        description TEXT,
        entities_involved TEXT,
        market_impact TEXT,
        lesson TEXT,
        category TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS owner_sessions (
        token TEXT PRIMARY KEY,
        created_at REAL,
        expires_at REAL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS query_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT,
        response_summary TEXT,
        category TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print("✅ Star Knowledge DB initialized")


# ============================================================
# KNOWLEDGE BASE SEED DATA
# ============================================================

def seed_knowledge_base():
    entities = [
        {
            "name": "NVIDIA",
            "type": "company", "category": "ai",
            "summary": "Dominant AI chip designer controlling ~80% of the global AI GPU market. Its GPUs power virtually all AI training and inference workloads worldwide. Does not manufacture chips — relies entirely on TSMC.",
            "key_facts": json.dumps([
                "Founded 1993 by Jensen Huang, Chris Malachowsky, Curtis Priem",
                "Controls ~80% of AI GPU market globally",
                "H100 and Blackwell B200 are flagship AI chips",
                "Does NOT manufacture own chips — entirely dependent on TSMC",
                "Revenue grew from $27B (FY2023) to $130B+ (FY2025)",
                "Invested $5 billion in Intel in late 2025",
                "NemoClaw: open-source AI agent platform announced 2026"
            ]),
            "relationships": json.dumps([
                {"name": "TSMC", "relationship": "manufactures ALL NVIDIA chips"},
                {"name": "ASML", "relationship": "TSMC needs ASML EUV to make NVIDIA chips — indirect dependency"},
                {"name": "Jensen Huang", "relationship": "CEO and co-founder"},
                {"name": "CoreWeave", "relationship": "major customer and NVIDIA portfolio investment"},
                {"name": "Intel", "relationship": "NVIDIA invested $5B; collaborating on CPU-GPU hybrid products"},
                {"name": "OpenAI", "relationship": "OpenAI is NVIDIA's largest customer for training compute"},
                {"name": "Microsoft", "relationship": "Microsoft Azure is major NVIDIA cloud partner"}
            ]),
            "importance_score": 10
        },
        {
            "name": "ASML",
            "type": "company", "category": "ai",
            "summary": "Dutch company with an absolute global monopoly on Extreme Ultraviolet (EUV) lithography machines — the only equipment capable of manufacturing the world's most advanced chips. Every AI chip in existence required ASML machines to build.",
            "key_facts": json.dumps([
                "Only company on Earth that makes EUV lithography machines",
                "Each EUV machine costs approximately $200 million",
                "Based in Eindhoven, Netherlands",
                "Without ASML, TSMC cannot make NVIDIA chips — full stop",
                "US export controls prevent ASML from selling most advanced machines to China",
                "Multi-year order backlog — demand far exceeds supply",
                "Ticker: ASML on NASDAQ"
            ]),
            "relationships": json.dumps([
                {"name": "TSMC", "relationship": "largest customer — TSMC depends entirely on ASML"},
                {"name": "Samsung", "relationship": "second largest customer"},
                {"name": "Intel", "relationship": "customer for Intel's foundry ambitions"},
                {"name": "NVIDIA", "relationship": "indirect — NVIDIA chips require ASML machines via TSMC"},
                {"name": "US Government", "relationship": "export control policies restrict China sales"}
            ]),
            "importance_score": 10
        },
        {
            "name": "TSMC",
            "type": "company", "category": "ai",
            "summary": "Taiwan Semiconductor Manufacturing Company. World's largest chip foundry. Makes chips for NVIDIA, Apple, AMD, Qualcomm, and virtually every major chip designer. The single most critical physical infrastructure node in AI.",
            "key_facts": json.dumps([
                "Founded 1987 by Morris Chang in Hsinchu, Taiwan",
                "Manufactures ~90% of world's most advanced semiconductor chips",
                "Revenue $122.4B in 2025 — up 36% YoY",
                "Building fabs in Arizona, Japan, Germany under US and allied pressure",
                "Taiwan location creates massive geopolitical risk — China claims Taiwan",
                "2nm process in production 2025; 1.4nm in development",
                "Ticker: TSM on NYSE"
            ]),
            "relationships": json.dumps([
                {"name": "NVIDIA", "relationship": "manufactures ALL NVIDIA GPUs"},
                {"name": "Apple", "relationship": "manufactures all Apple Silicon (M-series, A-series)"},
                {"name": "AMD", "relationship": "manufactures AMD CPUs and GPUs"},
                {"name": "ASML", "relationship": "entirely depends on ASML EUV machines"},
                {"name": "US Government", "relationship": "CHIPS Act funding; political pressure to build US fabs"},
                {"name": "China", "relationship": "geopolitical threat — China considers Taiwan its territory"}
            ]),
            "importance_score": 10
        },
        {
            "name": "Jensen Huang",
            "type": "person", "category": "ai",
            "summary": "CEO and co-founder of NVIDIA. The most consequential executive in AI hardware. Predicted the agentic AI era. Known for leather jacket at GTC keynotes. Net worth $100B+.",
            "key_facts": json.dumps([
                "Born 1963 in Tainan, Taiwan; grew up in the United States",
                "Co-founded NVIDIA in 1993 at age 30",
                "Net worth $100B+ as of 2025",
                "Predicted at GTC 2025: '10 billion AI agents will work alongside humans'",
                "Coined 'AI factories' to describe modern GPU data centers",
                "Degrees from Oregon State University and Stanford (MSEE)"
            ]),
            "relationships": json.dumps([
                {"name": "NVIDIA", "relationship": "CEO and co-founder"},
                {"name": "CoreWeave", "relationship": "NVIDIA backed CoreWeave under his leadership"},
                {"name": "Intel", "relationship": "Orchestrated NVIDIA's $5B investment in Intel"}
            ]),
            "importance_score": 9
        },
        {
            "name": "Sam Altman",
            "type": "person", "category": "ai",
            "summary": "CEO of OpenAI. One of the most powerful figures in the AI industry. Orchestrated ChatGPT's launch, survived a board firing attempt in 2023, and is steering OpenAI toward AGI.",
            "key_facts": json.dumps([
                "CEO of OpenAI since 2019",
                "Previously president of Y Combinator (2014-2019)",
                "Fired by OpenAI board November 2023 — rehired 5 days later after mass employee revolt",
                "Pushing OpenAI toward for-profit restructuring",
                "Close relationship with Microsoft ($13B+ investment under his tenure)",
                "Vocal about both the promise and existential risk of AGI"
            ]),
            "relationships": json.dumps([
                {"name": "OpenAI", "relationship": "CEO"},
                {"name": "Microsoft", "relationship": "primary backer — $13B+ investment"},
                {"name": "NVIDIA", "relationship": "OpenAI is NVIDIA's largest compute customer"},
                {"name": "Dario Amodei", "relationship": "rival — Dario left OpenAI to found Anthropic"}
            ]),
            "importance_score": 9
        },
        {
            "name": "OpenAI",
            "type": "company", "category": "ai",
            "summary": "Creator of ChatGPT, GPT-4, and the company that triggered the current global AI revolution. Most influential AI lab for consumer adoption.",
            "key_facts": json.dumps([
                "Founded 2015 as nonprofit by Sam Altman, Elon Musk, Greg Brockman, Ilya Sutskever, others",
                "ChatGPT launched November 2022 — fastest product to 100M users in history",
                "GPT-4 is flagship model; o1/o3 are reasoning models",
                "Microsoft invested $13B+; deeply integrated into Office 365 and Azure",
                "Transitioning from nonprofit to for-profit capped structure",
                "Valued at $300B+ as of late 2025"
            ]),
            "relationships": json.dumps([
                {"name": "Microsoft", "relationship": "primary investor ($13B+) and cloud partner"},
                {"name": "Anthropic", "relationship": "primary competitor — Anthropic founded by former OpenAI team"},
                {"name": "NVIDIA", "relationship": "OpenAI is largest compute customer"},
                {"name": "Sam Altman", "relationship": "CEO"},
                {"name": "Elon Musk", "relationship": "co-founder, left board in 2018, now hostile — runs competing xAI"}
            ]),
            "importance_score": 10
        },
        {
            "name": "Anthropic",
            "type": "company", "category": "ai",
            "summary": "AI safety lab that created Claude. Founded by former OpenAI executives. Backed by Google and Amazon. Focused on safe, interpretable AI development.",
            "key_facts": json.dumps([
                "Founded 2021 by Dario Amodei, Daniela Amodei, and team from OpenAI",
                "Creates Claude AI model family",
                "Mission: AI safety and interpretability research",
                "Backed by Google ($2B+) and Amazon ($4B+)",
                "Competes with OpenAI at frontier model level",
                "Claude 3 Opus, Sonnet, Haiku — scalable model tiers"
            ]),
            "relationships": json.dumps([
                {"name": "OpenAI", "relationship": "primary competitor; founding team came from OpenAI"},
                {"name": "Google", "relationship": "major investor and cloud partner"},
                {"name": "Amazon", "relationship": "major investor; Claude on AWS Bedrock"},
                {"name": "Dario Amodei", "relationship": "CEO and co-founder"}
            ]),
            "importance_score": 8
        },
        {
            "name": "Federal Reserve",
            "type": "institution", "category": "macro",
            "summary": "United States central bank. Controls monetary policy via interest rates. The single most market-moving institution on Earth — its decisions ripple across AI stocks, crypto, real estate, and all global markets.",
            "key_facts": json.dumps([
                "Controls the federal funds rate — the most powerful lever in global finance",
                "Rate hike cycles historically crush risk assets including crypto and growth stocks",
                "Rate cut cycles fuel bull markets in AI stocks, crypto, and equities",
                "FOMC (Federal Open Market Committee) meets 8 times per year",
                "2% inflation target measured by PCE (Personal Consumption Expenditures)",
                "Hike cycle 2022-2023: 525bps — most aggressive since 1980s"
            ]),
            "relationships": json.dumps([
                {"name": "Jerome Powell", "relationship": "Chair of the Federal Reserve"},
                {"name": "Bitcoin", "relationship": "BTC price inversely correlated with rate hike cycles"},
                {"name": "US Treasury", "relationship": "coordinates on financial stability and debt markets"},
                {"name": "US Dollar", "relationship": "controls USD monetary supply and interest rates"}
            ]),
            "importance_score": 10
        },
        {
            "name": "Jerome Powell",
            "type": "person", "category": "macro",
            "summary": "Chair of the Federal Reserve. His words move every market on Earth simultaneously. Not an economist by training — former investment banker and lawyer. Term ends 2026.",
            "key_facts": json.dumps([
                "Appointed Fed Chair by Trump in 2018; reappointed by Biden in 2022",
                "Attorney by training (Georgetown Law) — rare non-economist Fed chair",
                "Former partner at The Carlyle Group (private equity)",
                "Led 525bps rate hike cycle 2022-2023 to fight post-COVID inflation",
                "Markets parse every word of his FOMC press conferences",
                "Term as Chair ends May 2026 — successor is a major market event"
            ]),
            "relationships": json.dumps([
                {"name": "Federal Reserve", "relationship": "Chair"},
                {"name": "US Treasury", "relationship": "Coordinates with Treasury Secretary on policy"},
                {"name": "Bitcoin", "relationship": "His hawkish/dovish signals directly move crypto markets"}
            ]),
            "importance_score": 9
        },
        {
            "name": "Bitcoin",
            "type": "concept", "category": "crypto",
            "summary": "The original cryptocurrency and the reserve asset of the entire crypto ecosystem. Digital store of value with hard-capped 21M supply. All crypto markets correlate to BTC movements.",
            "key_facts": json.dumps([
                "Created by pseudonymous Satoshi Nakamoto, genesis block January 2009",
                "Hard cap: exactly 21 million BTC ever — mathematical certainty",
                "Halving events every ~4 years cut new supply by 50%",
                "Spot ETF approved by SEC January 2024 — institutional floodgates opened",
                "All-time high ~$109,000 in January 2025",
                "Trades 24/7/365 unlike traditional markets",
                "Highly correlated with macro risk appetite — tracks Nasdaq during stress"
            ]),
            "relationships": json.dumps([
                {"name": "Hyperliquid", "relationship": "BTC-PERP perpetual futures trade on Hyperliquid"},
                {"name": "Federal Reserve", "relationship": "Rate decisions heavily influence BTC price direction"},
                {"name": "BlackRock", "relationship": "iShares Bitcoin ETF (IBIT) is largest spot BTC ETF"},
                {"name": "Ethereum", "relationship": "ETH follows BTC but with higher volatility (beta)"},
                {"name": "US Government", "relationship": "Strategic Bitcoin Reserve announced 2025"}
            ]),
            "importance_score": 10
        },
        {
            "name": "Ethereum",
            "type": "concept", "category": "crypto",
            "summary": "Second largest cryptocurrency. Programmable blockchain enabling DeFi, NFTs, and smart contracts. The infrastructure layer of the crypto ecosystem.",
            "key_facts": json.dumps([
                "Founded by Vitalik Buterin — proposed 2013, launched 2015",
                "Transitioned from Proof of Work to Proof of Stake (The Merge) September 2022",
                "Smart contract platform — Uniswap, Aave, and most DeFi run on Ethereum",
                "Layer 2 networks (Arbitrum, Optimism, Base) scale Ethereum cheaply",
                "Spot Ethereum ETF approved by SEC May 2024",
                "Higher volatility than BTC — typically amplifies BTC moves"
            ]),
            "relationships": json.dumps([
                {"name": "Bitcoin", "relationship": "Follows BTC with higher beta — amplifies moves"},
                {"name": "Arbitrum", "relationship": "Star's wallet operates on Arbitrum, an Ethereum Layer 2"},
                {"name": "Hyperliquid", "relationship": "ETH-PERP trades on Hyperliquid"},
                {"name": "Vitalik Buterin", "relationship": "Co-founder and primary intellectual leader"}
            ]),
            "importance_score": 9
        },
        {
            "name": "Hyperliquid",
            "type": "company", "category": "crypto",
            "summary": "Decentralized perpetual futures exchange with fully on-chain order books. Star's primary trading venue. High-performance, non-custodial trading with institutional-grade liquidity.",
            "key_facts": json.dumps([
                "Fully on-chain order book — no centralized custody or clearinghouse",
                "Supports perpetual futures across dozens of crypto assets",
                "HYPE token is native governance and utility token",
                "Extremely low latency for a decentralized exchange",
                "No KYC required — wallet-based access",
                "Grew rapidly as traders fled centralized exchanges post-FTX collapse",
                "Star (Shekinah Star) actively trades here via API"
            ]),
            "relationships": json.dumps([
                {"name": "Bitcoin", "relationship": "BTC-PERP is primary trading pair"},
                {"name": "Ethereum", "relationship": "ETH-PERP is major trading pair"},
                {"name": "Arbitrum", "relationship": "Star's MetaMask wallet is on Arbitrum network"}
            ]),
            "importance_score": 10
        },
        {
            "name": "CoreWeave",
            "type": "company", "category": "ai",
            "summary": "AI cloud infrastructure company. Rents out massive fleets of NVIDIA GPUs to AI companies. NVIDIA is an investor. IPO'd in March 2025. Rapidly growing as demand for AI compute explodes.",
            "key_facts": json.dumps([
                "IPO'd March 2025 on NASDAQ (ticker: CRWV)",
                "Business model: rent GPU clusters to AI companies by the hour or long-term contract",
                "Revenue backlog of $66.8B vs 2025 revenue of $5.1B",
                "Close relationship with NVIDIA — gets early access to latest chips",
                "NVIDIA is an investor in CoreWeave",
                "Revenue grew 168% in 2024",
                "Offers 'bare metal' GPU access — faster than virtualized cloud alternatives"
            ]),
            "relationships": json.dumps([
                {"name": "NVIDIA", "relationship": "Largest chip supplier and equity investor"},
                {"name": "Microsoft", "relationship": "Major customer"},
                {"name": "OpenAI", "relationship": "Significant customer for training workloads"}
            ]),
            "importance_score": 8
        },
        {
            "name": "BlackRock",
            "type": "company", "category": "finance",
            "summary": "World's largest asset manager with $10T+ AUM. Launching spot Bitcoin ETF (IBIT) made BlackRock the dominant institutional gateway to crypto. Larry Fink is CEO.",
            "key_facts": json.dumps([
                "World's largest asset manager — over $10 trillion AUM",
                "iShares Bitcoin Trust (IBIT) became largest spot Bitcoin ETF within months of launch",
                "CEO Larry Fink was a Bitcoin skeptic, now a convert",
                "Manages ETFs, mutual funds, and institutional portfolios globally",
                "Moving into tokenized assets and blockchain-based finance",
                "IBIT accumulates thousands of BTC daily — significant price pressure"
            ]),
            "relationships": json.dumps([
                {"name": "Bitcoin", "relationship": "Operates IBIT — largest spot Bitcoin ETF globally"},
                {"name": "Larry Fink", "relationship": "CEO"},
                {"name": "US Government", "relationship": "Advises on financial policy; managed Fed bond programs"}
            ]),
            "importance_score": 9
        },
        {
            "name": "Elon Musk",
            "type": "person", "category": "ai",
            "summary": "CEO of Tesla and SpaceX, owner of X (Twitter), founder of xAI (Grok), and DOGE advisor to Trump. The most market-moving individual on social media. Single tweets move crypto markets.",
            "key_facts": json.dumps([
                "CEO of Tesla (TSLA), SpaceX, and X (formerly Twitter)",
                "Founded xAI — runs Grok AI model competing with ChatGPT",
                "Co-founded OpenAI in 2015, left board 2018, now openly hostile to OpenAI",
                "DOGE (Department of Government Efficiency) co-lead under Trump 2025",
                "His tweets historically move Dogecoin 20-50% instantly",
                "Net worth $200B+ — world's richest person for much of 2023-2025",
                "Attempted hostile takeover of OpenAI's nonprofit structure via lawsuit"
            ]),
            "relationships": json.dumps([
                {"name": "OpenAI", "relationship": "Co-founder; left 2018; now running legal/PR war against them"},
                {"name": "Tesla", "relationship": "CEO; Tesla is largest corporate Dogecoin holder"},
                {"name": "xAI", "relationship": "Founder; Grok AI competes with Claude and ChatGPT"},
                {"name": "Donald Trump", "relationship": "DOGE advisor; major political ally"},
                {"name": "Bitcoin", "relationship": "His tweets about crypto move markets significantly"}
            ]),
            "importance_score": 9
        },
        {
            "name": "Donald Trump",
            "type": "person", "category": "macro",
            "summary": "47th President of the United States (inaugurated January 2025). His policies on tariffs, crypto regulation, and AI directly shape markets globally.",
            "key_facts": json.dumps([
                "47th US President, inaugurated January 20, 2025",
                "Announced US Strategic Bitcoin Reserve — first nation to do so",
                "Imposed broad tariffs in 2025 causing global market volatility",
                "Administration banned NVIDIA chip exports to China (H20 chips, April 2025)",
                "Appointed crypto-friendly SEC chair — regulatory environment shifted",
                "DOGE (Dept of Government Efficiency) cutting federal spending aggressively"
            ]),
            "relationships": json.dumps([
                {"name": "Elon Musk", "relationship": "DOGE advisor and key political ally"},
                {"name": "Federal Reserve", "relationship": "Political pressure on Fed rate decisions"},
                {"name": "Bitcoin", "relationship": "Strategic Bitcoin Reserve announcement boosted BTC"},
                {"name": "NVIDIA", "relationship": "His export control policies affected NVIDIA's China sales"},
                {"name": "China", "relationship": "Trade war via tariffs — major market destabilizer"}
            ]),
            "importance_score": 10
        }
    ]

    historical_events = [
        {
            "event_date": "2022-11-30",
            "title": "ChatGPT Launch — AI Era Begins",
            "description": "OpenAI launched ChatGPT publicly. It reached 100M users in 2 months — faster than any product in history. Triggered the global AI investment supercycle.",
            "entities_involved": json.dumps(["OpenAI", "NVIDIA", "Microsoft", "Sam Altman"]),
            "market_impact": "NVIDIA stock eventually 10x'd from pre-ChatGPT levels. AI became the dominant global investment theme.",
            "lesson": "Consumer-facing AI inflection points happen faster than analysts predict. Infrastructure plays (NVIDIA, TSMC, ASML) benefit before anyone realizes it.",
            "category": "ai"
        },
        {
            "event_date": "2022-03-16",
            "title": "Fed Begins Most Aggressive Rate Hike Cycle Since 1980s",
            "description": "Fed started hiking rates to fight post-COVID inflation. Went from 0% to 5.25% in 16 months. Crypto market cap collapsed ~70%. Multiple exchanges and protocols failed.",
            "entities_involved": json.dumps(["Federal Reserve", "Jerome Powell", "Bitcoin", "Ethereum"]),
            "market_impact": "Bitcoin fell from $69K all-time high to under $16K. Luna/TERRA collapsed to zero. FTX collapsed. Crypto winter lasted 18 months.",
            "lesson": "Aggressive rate hike cycles are the most reliable crypto bear market trigger. When Fed goes hawkish, reduce risk exposure. Rate cuts are the all-clear signal.",
            "category": "macro"
        },
        {
            "event_date": "2022-11-11",
            "title": "FTX Collapse — Crypto's Lehman Moment",
            "description": "FTX, the second largest crypto exchange, collapsed over 72 hours after CoinDesk revealed balance sheet insolvency. Sam Bankman-Fried arrested. $8B in customer funds missing.",
            "entities_involved": json.dumps(["Bitcoin", "Ethereum", "Hyperliquid"]),
            "market_impact": "Bitcoin dropped 25% in days. Triggered massive trust collapse in centralized exchanges. Accelerated shift to decentralized exchanges like Hyperliquid.",
            "lesson": "Centralized exchange counterparty risk is real. The FTX collapse directly fueled Hyperliquid's growth. Self-custody and on-chain trading won long term.",
            "category": "crypto"
        },
        {
            "event_date": "2024-01-10",
            "title": "SEC Approves Spot Bitcoin ETFs",
            "description": "SEC approved 11 spot Bitcoin ETFs including BlackRock's IBIT and Fidelity's FBTC after years of rejections. Institutional floodgates opened immediately.",
            "entities_involved": json.dumps(["Bitcoin", "BlackRock", "Federal Reserve"]),
            "market_impact": "Bitcoin surged from ~$40K at approval to $73K within 2 months. IBIT became the fastest-growing ETF in Wall Street history.",
            "lesson": "Regulatory approval for institutional products is a generational catalyst. Monitor SEC ETF decisions for other assets (Ethereum, Solana ETF applications).",
            "category": "crypto"
        },
        {
            "event_date": "2023-10-17",
            "title": "US Export Controls Restrict NVIDIA Chip Sales to China",
            "description": "US government banned NVIDIA from selling H100/A100 to China. NVIDIA created downgraded H800/A800 chips but those were also eventually banned.",
            "entities_involved": json.dumps(["NVIDIA", "ASML", "Jensen Huang", "China", "Donald Trump"]),
            "market_impact": "Short-term NVIDIA dip. Rest-of-world demand absorbed impact. China accelerated domestic chip development (Huawei Ascend series).",
            "lesson": "Geopolitical chip restrictions create short-term volatility. Monitor for escalation. Companies like ASML and TSMC face secondary restrictions.",
            "category": "ai"
        },
        {
            "event_date": "2025-01-20",
            "title": "Trump Inaugurated — Crypto-Friendly Administration Begins",
            "description": "Trump inaugurated as 47th president. Within weeks: crypto-friendly SEC chair appointed, Strategic Bitcoin Reserve announced, broad tariffs imposed on trading partners.",
            "entities_involved": json.dumps(["Donald Trump", "Bitcoin", "Elon Musk", "Federal Reserve"]),
            "market_impact": "Bitcoin hit all-time high ~$109K in January 2025. Crypto regulatory environment shifted favorably. Tariffs created equity market volatility.",
            "lesson": "Political regime change can be a major crypto catalyst. Regulatory clarity unlocks institutional capital. Watch for ETF approvals for alt-coins under new SEC.",
            "category": "macro"
        },
        {
            "event_date": "2025-03-01",
            "title": "US Strategic Bitcoin Reserve Announced",
            "description": "Trump signed executive order creating the US Strategic Bitcoin Reserve — first nation-state to formalize BTC as a reserve asset using existing government-held BTC.",
            "entities_involved": json.dumps(["Bitcoin", "Donald Trump", "BlackRock"]),
            "market_impact": "Legitimized Bitcoin as a sovereign reserve asset. Triggered similar discussions in other nations. Long-term bullish structural shift.",
            "lesson": "Nation-state Bitcoin adoption is a multi-year structural trend. US move likely triggers other countries to follow. Supply absorption by governments is permanently bullish.",
            "category": "crypto"
        }
    ]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    inserted = 0
    for entity in entities:
        try:
            c.execute('''INSERT OR IGNORE INTO entities
                (name, type, category, summary, key_facts, relationships, importance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (entity['name'], entity['type'], entity['category'],
                 entity['summary'], entity['key_facts'], entity['relationships'],
                 entity['importance_score']))
            inserted += c.rowcount
        except Exception as e:
            print(f"  Entity error ({entity['name']}): {e}")

    for event in historical_events:
        try:
            c.execute('''INSERT OR IGNORE INTO historical_events
                (event_date, title, description, entities_involved, market_impact, lesson, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (event['event_date'], event['title'], event['description'],
                 event['entities_involved'], event['market_impact'],
                 event['lesson'], event['category']))
        except Exception as e:
            print(f"  Event error ({event['title']}): {e}")

    conn.commit()
    conn.close()
    print(f"✅ Knowledge base seeded — {inserted} new entities loaded")


# ============================================================
# OWNER VERIFICATION
# ============================================================

def generate_token(secret, timestamp):
    return hmac.new(
        secret.encode(),
        f"{timestamp}".encode(),
        hashlib.sha256
    ).hexdigest()

@intel_bp.route('/api/owner/verify', methods=['POST'])
def verify_owner():
    data = request.json or {}
    provided_secret = data.get('secret', '')

    if hmac.compare_digest(str(provided_secret), str(OWNER_SECRET)):
        timestamp = time.time()
        token = generate_token(OWNER_SECRET, timestamp)
        expires_at = timestamp + 7200  # 2 hours

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Clean old sessions
        c.execute('DELETE FROM owner_sessions WHERE expires_at < ?', (time.time(),))
        c.execute('INSERT OR REPLACE INTO owner_sessions VALUES (?, ?, ?)',
                  (token, timestamp, expires_at))
        conn.commit()
        conn.close()

        return jsonify({
            'verified': True,
            'token': token,
            'message': 'Welcome back, Sarah. Star is yours to command.',
            'expires_in': 7200
        })

    return jsonify({'verified': False, 'error': 'Access denied.'}), 401

def is_owner(token):
    if not token:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT expires_at FROM owner_sessions WHERE token = ?', (token,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0] > time.time())


# ============================================================
# KNOWLEDGE BASE SEARCH
# ============================================================

def search_knowledge_base(query, limit=5):
    query_lower = query.lower()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Search entities by name and summary
    c.execute('''SELECT name, type, category, summary, key_facts, relationships
                 FROM entities
                 WHERE lower(name) LIKE ? OR lower(summary) LIKE ? OR lower(key_facts) LIKE ?
                 ORDER BY importance_score DESC LIMIT ?''',
              (f'%{query_lower}%', f'%{query_lower}%', f'%{query_lower}%', limit))
    entities = c.fetchall()

    # Search historical events
    c.execute('''SELECT event_date, title, description, market_impact, lesson, category
                 FROM historical_events
                 WHERE lower(title) LIKE ? OR lower(description) LIKE ?
                    OR lower(entities_involved) LIKE ?
                 ORDER BY event_date DESC LIMIT 3''',
              (f'%{query_lower}%', f'%{query_lower}%', f'%{query_lower}%'))
    events = c.fetchall()

    conn.close()
    return entities, events


def format_kb_context(entities, events):
    context_parts = []

    if entities:
        context_parts.append("=== KNOWLEDGE BASE: ENTITIES ===")
        for name, etype, category, summary, key_facts_json, relationships_json in entities:
            context_parts.append(f"\n[{name.upper()}] ({etype} / {category})")
            context_parts.append(f"Summary: {summary}")
            try:
                facts = json.loads(key_facts_json or '[]')
                if facts:
                    context_parts.append("Key Facts:")
                    for f in facts:
                        context_parts.append(f"  • {f}")
            except:
                pass
            try:
                rels = json.loads(relationships_json or '[]')
                if rels:
                    context_parts.append("Relationships:")
                    for r in rels:
                        context_parts.append(f"  → {r['name']}: {r['relationship']}")
            except:
                pass

    if events:
        context_parts.append("\n=== HISTORICAL CONTEXT ===")
        for date, title, description, impact, lesson, category in events:
            context_parts.append(f"\n[{date}] {title}")
            context_parts.append(f"What happened: {description}")
            context_parts.append(f"Market impact: {impact}")
            context_parts.append(f"Star's lesson: {lesson}")

    return '\n'.join(context_parts)


# ============================================================
# REAL-TIME WEB SEARCH
# ============================================================

def web_search(query, num_results=5):
    """Search using DuckDuckGo (no API key required)"""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
        formatted = []
        for r in results:
            formatted.append({
                'title': r.get('title', ''),
                'snippet': r.get('body', ''),
                'url': r.get('href', '')
            })
        return formatted
    except ImportError:
        # Fallback: try SerpAPI if configured
        if SERP_API_KEY:
            return serp_search(query, num_results)
        return []
    except Exception as e:
        print(f"Search error: {e}")
        return []

def serp_search(query, num_results=5):
    try:
        resp = requests.get('https://serpapi.com/search', params={
            'q': query,
            'api_key': SERP_API_KEY,
            'num': num_results,
            'engine': 'google'
        }, timeout=10)
        data = resp.json()
        results = []
        for r in data.get('organic_results', [])[:num_results]:
            results.append({
                'title': r.get('title', ''),
                'snippet': r.get('snippet', ''),
                'url': r.get('link', '')
            })
        return results
    except Exception as e:
        print(f"SerpAPI error: {e}")
        return []

def format_search_results(results):
    if not results:
        return ""
    parts = ["=== REAL-TIME INTELLIGENCE ==="]
    for i, r in enumerate(results, 1):
        parts.append(f"\n[Source {i}] {r['title']}")
        parts.append(r['snippet'])
    return '\n'.join(parts)


# ============================================================
# MAIN INTELLIGENCE QUERY ENDPOINT
# ============================================================

@intel_bp.route('/api/intel/query', methods=['POST'])
def intelligence_query():
    data = request.json or {}
    query = data.get('query', '').strip()
    mode = data.get('mode', 'full')  # full | knowledge | realtime | predict

    if not query:
        return jsonify({'error': 'Query required'}), 400

    # 1. Search knowledge base
    entities, events = search_knowledge_base(query)
    kb_context = format_kb_context(entities, events)

    # 2. Real-time search
    search_results = []
    search_context = ""
    if mode in ('full', 'realtime'):
        search_query = f"{query} 2025 2026"
        search_results = web_search(search_query)
        search_context = format_search_results(search_results)

    # 3. Build full context
    full_context = []
    if kb_context:
        full_context.append(kb_context)
    if search_context:
        full_context.append(search_context)

    context_str = '\n\n'.join(full_context) if full_context else "No specific context found — use general knowledge."

    # 4. Claude synthesis with Star's persona
    user_message = f"""User query: {query}

Context gathered:
{context_str}

Instructions:
- Answer the query using the context above plus your training knowledge
- If historical events are relevant, reference them and draw parallels
- Generate a predictive signal based on current patterns
- Speak as Star — confident, precise, with cosmic authority
- End with: "Star Signal: [your forward-looking prediction]"
"""

    try:
        if client:
            # Use Anthropic Claude
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=STAR_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}]
            )
            answer = response.content[0].text
        else:
            # Fallback to Groq if anthropic not installed
            groq_key = os.environ.get('GROQ_API_KEY', '')
            if not groq_key:
                return jsonify({'error': 'No AI backend available. Run: pip install anthropic --break-system-packages'}), 500
            gr = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {groq_key}', 'Content-Type': 'application/json'},
                json={
                    'model': 'llama-3.3-70b-versatile',
                    'messages': [
                        {'role': 'system', 'content': STAR_SYSTEM_PROMPT},
                        {'role': 'user', 'content': user_message}
                    ],
                    'max_tokens': 1500
                },
                timeout=60
            )
            if gr.status_code == 200:
                answer = gr.json()['choices'][0]['message']['content']
            else:
                return jsonify({'error': f'Groq fallback failed: {gr.status_code}'}), 500
    except Exception as e:
        return jsonify({'error': f'AI API error: {str(e)}'}), 500

    # Log query
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO query_log (query, response_summary, category) VALUES (?, ?, ?)',
                  (query, answer[:200], 'general'))
        conn.commit()
        conn.close()
    except:
        pass

    return jsonify({
        'query': query,
        'response': answer,
        'sources_used': {
            'knowledge_base_entities': [e[0] for e in entities],
            'historical_events': [ev[1] for ev in events],
            'realtime_sources': len(search_results)
        }
    })


# ============================================================
# KNOWLEDGE BASE MANAGEMENT (OWNER ONLY)
# ============================================================

@intel_bp.route('/api/knowledge/add', methods=['POST'])
def add_entity():
    token = request.headers.get('X-Owner-Token', '')
    if not is_owner(token):
        return jsonify({'error': 'Owner verification required'}), 403

    data = request.json or {}
    required = ['name', 'type', 'category', 'summary']
    if not all(k in data for k in required):
        return jsonify({'error': f'Required fields: {required}'}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''INSERT OR REPLACE INTO entities
            (name, type, category, summary, key_facts, relationships, importance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (data['name'], data['type'], data['category'], data['summary'],
             json.dumps(data.get('key_facts', [])),
             json.dumps(data.get('relationships', [])),
             data.get('importance_score', 5)))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'entity': data['name']})
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@intel_bp.route('/api/knowledge/entities', methods=['GET'])
def list_entities():
    category = request.args.get('category', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if category:
        c.execute('SELECT name, type, category, importance_score FROM entities WHERE category=? ORDER BY importance_score DESC', (category,))
    else:
        c.execute('SELECT name, type, category, importance_score FROM entities ORDER BY importance_score DESC')
    rows = c.fetchall()
    conn.close()
    return jsonify({
        'entities': [{'name': r[0], 'type': r[1], 'category': r[2], 'score': r[3]} for r in rows],
        'total': len(rows)
    })

@intel_bp.route('/api/knowledge/history/add', methods=['POST'])
def add_historical_event():
    token = request.headers.get('X-Owner-Token', '')
    if not is_owner(token):
        return jsonify({'error': 'Owner verification required'}), 403

    data = request.json or {}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO historical_events
        (event_date, title, description, entities_involved, market_impact, lesson, category)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (data.get('date', ''), data.get('title', ''), data.get('description', ''),
         json.dumps(data.get('entities', [])), data.get('market_impact', ''),
         data.get('lesson', ''), data.get('category', 'general')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================
# STATUS
# ============================================================

@intel_bp.route('/api/intel/status', methods=['GET'])
def status():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM entities')
    entity_count = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM historical_events')
    event_count = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM query_log')
    query_count = c.fetchone()[0]
    conn.close()
    return jsonify({
        'status': 'Star Intelligence Engine online',
        'knowledge_base': {
            'entities': entity_count,
            'historical_events': event_count,
            'total_queries_served': query_count
        },
        'capabilities': ['knowledge_base', 'realtime_search', 'historical_context', 'predictive_synthesis'],
        'timestamp': time.time()
    })
