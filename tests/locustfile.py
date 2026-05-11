"""
ScamRadar+ load test — find the performance cliff before users do.

Run against local backend:
    locust -f tests/locustfile.py --host http://localhost:8000

Run against Render (careful — external API calls count against rate limits):
    locust -f tests/locustfile.py --host https://scamradar-api-l2vv.onrender.com

Open http://localhost:8089 to control the swarm.

Recommended ramp-up sequence to find the cliff:
  1. Start with 5 users, spawn rate 1/s  — baseline
  2. Ramp to 20 users, spawn rate 2/s    — normal load
  3. Ramp to 50 users, spawn rate 5/s    — stress test
  4. Ramp to 100 users, spawn rate 10/s  — watch p95 / error rate

Expected healthy numbers:
  /predict (no URL)         p50 < 200ms   p95 < 600ms
  /predict (with URL)       p50 < 800ms   p95 < 2000ms
  /analyze-conversation     p50 < 1500ms  p95 < 4000ms
  /health                   p50 < 10ms    p95 < 50ms
"""

import random
from locust import HttpUser, task, between, constant_pacing

# ── Message corpus ─────────────────────────────────────────────────────────────

SCAM_MESSAGES = [
    "URGENT: Your PayPal account has been suspended! Verify now at http://paypal-secure-verify.tk/login",
    "Congratulations! You've been selected to claim your $1,000 Amazon gift card. Click here to claim your prize before it expires!",
    "Your bank account will be locked in 24 hours unless you verify your credentials at http://secure-bank-login.ml",
    "I turned $500 into $12,000 in 6 weeks with this crypto strategy. DM me for the link to join my group.",
    "FINAL NOTICE from IRS: You owe back taxes. Failure to respond will result in arrest. Call 1-800-555-0199 immediately.",
    "Your package is held at customs. Pay the $3.99 release fee at http://dhl-customs-clearance.tk to receive it.",
    "Hi I think we matched on Tinder? I've been using this amazing investment platform and made $8,000 this month alone.",
    "Send $500 in Bitcoin to this address: 1A2b3C4d5E6f and receive $5,000 back within 24 hours guaranteed.",
    "Your Apple ID has been compromised. Go to http://apple-secure-id.ml and verify immediately or your account will be deleted.",
    "We are offering you a job from home earning $5,000 per week. No experience needed. Limited spots available. Register now!",
]

LEGIT_MESSAGES = [
    "Your Amazon order #123-4567890-1234567 has shipped. Estimated delivery is Thursday. Track your package at amazon.com/orders",
    "Your WhatsApp verification code is 847-291. Do not share this code with anyone.",
    "Hi, I wanted to confirm our meeting tomorrow at 2pm. Let me know if the time still works for you.",
    "Your Netflix subscription has been renewed. $15.99 has been charged to your card ending in 4242.",
    "Reminder: Your dentist appointment is on Friday May 15 at 10:30am. Reply CONFIRM to confirm or CANCEL to cancel.",
    "Your Uber ride has been completed. Total: $12.50. Rate your driver: uber.com/rate",
    "Thank you for your purchase at Starbucks. Your receipt is attached. Have a great day!",
    "Hi, this is Sarah from HR. Just checking in about the team meeting notes from yesterday.",
    "Your flight AA1234 from New York to Los Angeles departs at 8:30am tomorrow. Check in now at aa.com",
    "Package delivered to your front door at 2:15pm. Photo proof available in the FedEx app.",
]

CONVERSATIONS = [
    # Pig butchering / investment scam
    """Hey I found your profile online
I'm a forex trader and I made $45,000 last month
I can teach you my strategy
Just start with $200 and I'll guide you personally
I use this special platform that guarantees returns
Many of my students already withdrew profits
Let me show you my portfolio screenshots""",

    # Romance + advance fee
    """Hi beautiful
I am US Army officer currently deployed in Syria
I would like to know you better
I have $2.5 million in gold bars I need to transfer out of the country
I need a trusted person to help me
I will give you 30 percent commission
Please send me your bank account details""",

    # Legit customer support
    """Hello I need help with my recent order
I ordered a blue jacket but received a red one
Order number is 78234891
I want to return it and get the correct item
Can you help me please
I can send photos of what I received""",
]

# ── User behaviour classes ─────────────────────────────────────────────────────

class StandardUser(HttpUser):
    """
    Typical user: mostly single-message predictions, occasional health checks.
    Wait 1-3s between requests — models realistic human pacing.
    """
    wait_time = between(1, 3)
    weight    = 60          # 60% of the swarm

    @task(8)
    def predict_scam(self):
        self.client.post(
            '/predict',
            json={'text': random.choice(SCAM_MESSAGES)},
            name='/predict [scam]',
        )

    @task(5)
    def predict_legit(self):
        self.client.post(
            '/predict',
            json={'text': random.choice(LEGIT_MESSAGES)},
            name='/predict [legit]',
        )

    @task(1)
    def health(self):
        self.client.get('/health', name='/health')

    @task(1)
    def stats(self):
        self.client.get('/stats', name='/stats')


class PowerUser(HttpUser):
    """
    API integrator firing requests quickly with minimal wait.
    Stress-tests concurrency and cache effectiveness.
    """
    wait_time = between(0.1, 0.5)
    weight    = 25          # 25% of the swarm

    # Intentionally repeat the same message — proves cache hit path
    REPEATED_MSG = SCAM_MESSAGES[0]

    @task(5)
    def predict_repeated(self):
        """Same message repeatedly — should be served from cache after first hit."""
        self.client.post(
            '/predict',
            json={'text': self.REPEATED_MSG},
            name='/predict [cache-hit]',
        )

    @task(3)
    def predict_varied(self):
        self.client.post(
            '/predict',
            json={'text': random.choice(SCAM_MESSAGES + LEGIT_MESSAGES)},
            name='/predict [varied]',
        )

    @task(2)
    def analyze_conversation(self):
        self.client.post(
            '/analyze-conversation',
            json={'text': random.choice(CONVERSATIONS)},
            name='/analyze-conversation',
        )


class SlowPoller(HttpUser):
    """
    Simulates users who paste a message, wait for the result, then paste another.
    5-15s between requests — stress-tests long-tail response times.
    """
    wait_time = between(5, 15)
    weight    = 15          # 15% of the swarm

    @task(3)
    def predict_url(self):
        """Message with a URL — exercises the GSB/VT path."""
        self.client.post(
            '/predict',
            json={'text': 'URGENT: Your PayPal account suspended. Verify now at http://paypal-secure-verify.tk/login or account closed.'},
            name='/predict [url-check]',
        )

    @task(2)
    def analyze_conversation(self):
        self.client.post(
            '/analyze-conversation',
            json={'text': random.choice(CONVERSATIONS)},
            name='/analyze-conversation',
        )

    @task(1)
    def health(self):
        self.client.get('/health', name='/health')
