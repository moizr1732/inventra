"""Deterministic language understanding for the Inventra assistant.

This layer turns a user message into a structured `Understanding`. It never
reads business data and never calls an external service, so it works when
Groq is disabled or unavailable.

Output describes what the user *asked for* (social act, intents, references,
numbers). Deciding which items those references point to, and fetching the
facts, happens in the engine using live database data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

INTENT_ORDER = ["risk", "forecast", "planning", "purchase_orders", "inventory", "valuation", "scenario"]

# Words that never identify an inventory item on their own.
STOPWORDS = {
    "the", "and", "for", "of", "with", "item", "items", "stock", "inventory", "quantity",
    "level", "levels", "order", "orders", "purchase", "forecast", "risk", "planning",
    "demand", "our", "what", "about", "how", "much", "many", "need", "buy", "current",
    "show", "tell", "me", "is", "are", "do", "we", "have", "high", "low", "product",
    "products", "material", "materials", "new", "old", "one", "ones", "this", "that",
    "please", "can", "you", "its", "it", "reorder", "supplier", "cost", "value",
}

_GREETING = re.compile(
    r"^(hi+|hello|hey+|hiya|howdy|greetings|good (morning|afternoon|evening|day)|"
    r"assalam(?:u)?\s*(?:o)?\s*alaikum|salam)\b[\s,!.]*"
)

_PATTERNS = {
    "thanks": re.compile(r"\b(thanks|thank you|thx|ty|cheers|appreciate it|much appreciated)\b"),
    "farewell": re.compile(r"\b(bye|goodbye|good ?bye|see you|see ya|cya|that's all|thats all|that is all|no more questions)\b"),
    "acknowledgement": re.compile(
        r"^(ok|okay|k|great|cool|nice|perfect|got it|understood|makes sense|alright|sounds good|awesome|sure|yes|yep|yeah)[.!]?$"
    ),
    "how_are_you": re.compile(r"\bhow (are|r) (you|u)\b|\bhow'?s it going\b|\bhow do you do\b"),
    "capabilities": re.compile(
        r"\bwhat can you do\b|\bwhat do you do\b|\bcapabilit\w*\b|\bwhat (are|can) (your|you) (features|abilities)\b"
        r"|\bhow (can|do|should) (you|i|we) (help|use)\b|^help\b|\bhelp me\b$|\bhow do i use\b"
    ),
    "identity": re.compile(r"\bwho are you\b|\bwhat are you\b|\bwhat is inventra\b"),
    "write": re.compile(
        r"\b(create|place|approve|cancel|delete|remove|update|change|modify|edit|raise|issue|receive|"
        r"record|book|submit|add|set)\b"
    ),
    "write_question_prefix": re.compile(r"^(what|which|how|why|when|who|where|should|is|are|do|does)\b"),
    "risk": re.compile(
        r"\b(risks?|risky|at risk|shortages?|short|running out|run out|runs out|out of stock|stock ?out|"
        r"reorder|re-order|replenish\w*|restock\w*|low stock|critical|overstock\w*|enough|sufficient\w*|"
        r"buy more|purchase more|order more|need to (buy|purchase|order)|do we need|should we (buy|order|purchase)|"
        r"how much (to )?(buy|order|purchase)|reorder quantity|order quantity|suggested order|quantity to order|"
        r"cover|coverage|days of cover|running low)\b"
    ),
    "forecast": re.compile(
        r"\b(forecasts?|forecasting|predict\w*|projections?|future demand|expected demand|"
        r"next (three |3 )?(months?|periods?)|demand (trend|outlook)|how much will (we|i) (use|need|consume))\b"
    ),
    "planning": re.compile(r"\b(planning|planned|overrides?|overridden|adjusted demand|final demand|adjustments?)\b"),
    "purchase_orders": re.compile(
        r"\b(purchase orders?|pos|po|outstanding orders?|open orders?|on order|incoming|deliver\w*|delivery|"
        r"suppliers?|supplied by|received|ordered quantity|order status)\b"
    ),
    "inventory": re.compile(
        r"\b(stock|on hand|on-hand|available|availability|reserved|quantity|how many|how much|inventory|details?|"
        r"lead time|safety stock|reorder level|category|unit cost|price|position|levels?|balance|do we have|have we got)\b"
    ),
    "summary": re.compile(
        r"\b(all items|all inventory|all products|every item|overview|summary|full inventory|inventory position|"
        r"stock position|current inventory|our inventory|everything|list (all|the)? ?(items|products|inventory)|"
        r"show (me )?(the )?inventory|what do we have|stock levels?)\b"
    ),
    "valuation": re.compile(r"\b(value|valuation|worth|total cost|stock value|inventory value)\b"),
    "scenario": re.compile(
        r"\b(what if|what happens if|scenario|simulat\w*|sensitivity|increase\w*|decrease\w*|drop\w*|"
        r"reduc\w*|grow\w*|rise\w*|spike\w*|surge\w*|go up|go down)\b|\d+(?:\.\d+)?\s*(?:%|percent)\b"
    ),
    "explain": re.compile(
        r"\b(why|explain|explanation|how (is|was|did) (that|it|this) (calculated|computed)|how do you calculate|"
        r"breakdown|reasoning|based on what|how calculated)\b"
    ),
    "forecast_accuracy": re.compile(
        r"\b(forecast|prediction)s? (accuracy|vs\.?|versus|against) (actual|actuals|real)|"
        r"\b(compare|comparison)\b.*\b(forecast|predicted)\b.*\b(actual|consumption)\b|"
        r"\bactual\b.*\bcompar\w*\b.*\b(forecast|predicted)\b"
    ),
    "supplier_performance": re.compile(
        r"\bsupplier (performance|rating|score|reliability|scorecard)\b|\bon[- ]time delivery\b"
    ),
    "pronoun": re.compile(
        r"\b(it|its|it's|that one|this one|that item|this item|that product|this product|that material|"
        r"this material|the same one|the same item|the same product|the previous one|the last one|"
        r"the previous item|that|this)\b"
    ),
    "ambiguous_reference": re.compile(r"\b(the other (one|item|product)|another one|the second one|the first one)\b"),
    "percent": re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)"),
}


@dataclass
class Understanding:
    social: str | None = None            # greeting | thanks | farewell | acknowledgement | how_are_you | capabilities | identity
    greeting_with_request: bool = False  # e.g. "Hi, what is the risk on fabric?"
    write_request: bool = False
    unsupported: str | None = None       # forecast_accuracy | supplier_performance
    intents: list[str] = field(default_factory=list)
    explain: bool = False
    uses_pronoun: bool = False
    ambiguous_reference: bool = False
    percent_change: float | None = None
    text: str = ""
    cleaned: str = ""


def normalise(message: str) -> str:
    text = message.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", text).strip()


def _has(name: str, text: str) -> bool:
    return bool(_PATTERNS[name].search(text))


def understand(message: str) -> Understanding:
    raw = normalise(message)
    text = raw.lower()
    result = Understanding(text=raw)

    greeting_match = _GREETING.match(text)
    remainder = text[greeting_match.end():].strip() if greeting_match else text
    remainder = re.sub(r"^(there|team|again|inventra)[\s,!.]*", "", remainder).strip()

    if greeting_match and not remainder:
        result.social = "greeting"
        return result

    if greeting_match:
        result.greeting_with_request = True
    result.cleaned = remainder or text

    # Social acts apply only when the whole message is social.
    if _has("acknowledgement", remainder):
        result.social = "acknowledgement"
        return result
    if _has("farewell", remainder) and not _has("risk", remainder) and not _has("inventory", remainder):
        result.social = "farewell"
        return result
    if _has("thanks", remainder) and not any(_has(k, remainder) for k in ("risk", "forecast", "planning", "purchase_orders", "inventory", "summary")):
        result.social = "thanks"
        return result
    if _has("how_are_you", remainder) and len(remainder.split()) <= 6:
        result.social = "how_are_you"
        return result
    if _has("capabilities", remainder):
        result.social = "capabilities"
        return result
    if _has("identity", remainder) and len(remainder.split()) <= 6:
        result.social = "identity"
        return result

    if _has("forecast_accuracy", remainder):
        result.unsupported = "forecast_accuracy"
    elif _has("supplier_performance", remainder):
        result.unsupported = "supplier_performance"

    if _has("write", remainder) and not _PATTERNS["write_question_prefix"].match(remainder) and "what if" not in remainder:
        result.write_request = True

    intents = [name for name in INTENT_ORDER if _has(name, remainder)]
    # "inventory" is a generic word; drop it when a more specific intent exists.
    if "inventory" in intents and len(intents) > 1:
        intents.remove("inventory")
    if _has("summary", remainder) and "inventory" not in intents:
        intents.append("inventory")
    if "purchase_orders" in intents and "risk" in intents and "outstanding" not in remainder:
        pass  # both may be asked together; keep both.

    result.intents = intents
    result.explain = _has("explain", remainder)
    result.uses_pronoun = _has("pronoun", remainder)
    result.ambiguous_reference = _has("ambiguous_reference", remainder)

    pct = _PATTERNS["percent"].search(remainder)
    if pct:
        result.percent_change = float(pct.group(1))
        if re.search(r"\b(decrease|drop|reduc|fall|decline|go down|lower)\w*", remainder):
            result.percent_change = -result.percent_change

    return result


def find_item_tokens(text: str, codes_and_names: list[tuple[int, str, str]]):
    """Return (full_match_ids, partial_scores) for item codes and names in text.

    `codes_and_names` is a list of (item_id, item_code, item_name).
    """
    lowered = text.lower()
    full: list[int] = []
    partial: dict[int, int] = {}

    def boundary(term: str) -> re.Pattern:
        return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")

    for item_id, code, name in codes_and_names:
        if boundary(code).search(lowered) or boundary(name).search(lowered):
            full.append(item_id)
            continue
        words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) >= 3 and w not in STOPWORDS]
        hits = sum(1 for w in set(words) if boundary(w).search(lowered))
        if hits:
            partial[item_id] = hits

    return full, partial
