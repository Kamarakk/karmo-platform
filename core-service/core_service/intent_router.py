"""Model-chosen routing (2026-10-07, Kamara's "rebuild" decision).

Keyword lists kept sending ordinary questions to the wrong place (a plant-care
question answered from BloomBoss sales, "how do I kill weeds" refused as a
change request). When the iMac brain is up, qwen3:8b reads the message and
picks one route from a fixed list instead; the operator then runs that route's
existing handler. The model only chooses a label: anything it says that is not
exactly one known route is ignored and the keyword rules decide, as before.
"""

from __future__ import annotations

import re

ROUTER_MODEL = "qwen3:8b"
ROUTER_TIMEOUT_SECONDS = 10.0

ROUTES = ("memory", "bloomboss", "price", "web", "status", "change", "tasks", "run_code", "code_help", "heavy", "chat")

ROUTER_PROMPT = """You decide where Kamara's message to KARMO goes. Kamara is a network supervisor who also runs \
BloomBoss, a small rare-plant business (Alocasia, Anthurium, Philodendron, Monstera) that buys from suppliers \
like Emgarden and sells on Palmstreet. KARMO is his private assistant running on his own servers.

Reply with exactly one route name and nothing else.

memory: what Kamara told KARMO before or asked it to remember: "what do you know about...", "did I tell you...", "when did I say...", a shipment, order or date he mentioned, or anything about his own past conversations with KARMO.
bloomboss: his own BloomBoss business records: his sales, orders, inventory, stock, suppliers, invoices, \
profit, best sellers, or how a plant he sells is doing in sales.
price: what price he should charge or list one of his plants at.
web: needs current information from the internet: news, today's prices or rates, weather, scores, \
recent releases or events, opening hours, or he asks to search, look up online or google something.
status: the health of KARMO or KarmoLab itself: servers, workers, containers, services, CPU, memory, disk, uptime.
change: asks KARMO to change its own systems: restart, stop, deploy, upgrade, delete or reconfigure KARMO's \
servers, services, models, files or settings.
tasks: his KARMO task list or to-dos.
run_code: asks KARMO to run or execute code, or to use Python to calculate or process something.
code_help: write, explain, review or fix code or a script, without running it.
heavy: long writing or deep reasoning: draft an email, letter, post, listing, plan or report; compare options \
or anything asked for "in detail"; a detailed step-by-step guide; summarize, translate or rewrite a long text.
chat: everything else: general knowledge, plant care and growing advice, how-to questions, IT and networking \
concepts, advice, small talk, and questions about Kamara, his family or what KARMO remembers.

Examples:
What humidity does a variegated Alocasia need? -> chat
How are my Ninja Albos selling? -> bloomboss
What did I buy from Emgarden last time? -> bloomboss
How is the stock market doing today? -> web
What should I list my Thai Constellation at? -> price
How do I kill weeds without hurting my dog? -> chat
Restart the ollama service on AI01 -> change
Is Worker02 online? -> status
Is Palmstreet down right now? -> web
Use python to add up 17.5, 22 and 9.99 -> run_code
Write a bash script that pings every host in a list -> code_help
Draft an email to my vendor about a late shipment -> heavy
What are my kids' names? -> chat
What do you know about Arisa's Aug 30 shipment? -> memory
Did I tell you when my dog's vet visit is? -> memory
How does a VLAN work? -> chat"""

_ROUTE_WORD = re.compile(r"[a-z_]+")


def parse_route(reply: str) -> str | None:
    """The route the model named, or None unless its reply is exactly one
    known route (an arrow, quotes or a trailing period are tolerated)."""
    words = _ROUTE_WORD.findall((reply or "").lower())
    words = [w for w in words if w != "route"]
    if len(words) == 1 and words[0] in ROUTES:
        return words[0]
    return None


def router_messages(text: str, previous_question: str | None = None, plant_names=()) -> list[dict]:
    prompt = ROUTER_PROMPT
    if plant_names:
        # A plant he sells, named on its own ("tell me about the Ninja Albos"),
        # is a question about his business.
        prompt += "\n\nPlants BloomBoss sells (a message about one of these, with no care question, is bloomboss): " \
            + ", ".join(sorted(plant_names)[:60])
    content = text.strip()
    if previous_question:
        content = f"(His previous message was: {previous_question.strip()[:300]})\n{content}"
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content[:2000]},
    ]


def classify(model_client, text: str, previous_question: str | None = None, *, plant_names=(),
             model: str = ROUTER_MODEL, timeout: float = ROUTER_TIMEOUT_SECONDS) -> str | None:
    """One short model call. None on any failure or an unusable reply."""
    try:
        reply = model_client.chat(model=model, messages=router_messages(text, previous_question, plant_names),
                                  temperature=0.0, timeout=timeout)
    except Exception:  # noqa: BLE001 -- the keyword rules take over
        return None
    return parse_route(reply)


def fast_client(model_client):
    """The iMac's own client while it answers, else None. Model routing never
    runs on AI01's CPU (the extra call would cost 10-15 seconds per question)
    and never falls back there mid-call."""
    check = getattr(model_client, "primary_available", None)
    if not callable(check):
        return None
    try:
        return model_client.primary if check() else None
    except Exception:  # noqa: BLE001
        return None
