import datetime
import re
import time
import statistics
import ollama
from scraper import scrape_livcheers_via_typing  # new scraper

# Simple in-memory TTL cache (replace with Redis in prod)
_CACHE = {}
CACHE_TTL_SECS = 60 * 10  # 10 minutes

# Location + State aliases → city slug
LOCATION_ALIASES = {
    "blr": "bangalore",
    "bengaluru": "bangalore",
    "banglore": "bangalore",
    "delhi ncr": "delhi",
    "new delhi": "delhi",
    "mum": "mumbai",
    "bombay": "mumbai",
    "madras": "chennai",
    "hyd": "hyderabad",
    "pune city": "pune",
    # states mapped to main cities
    "tamilnadu": "chennai",
    "tamil nadu": "chennai",
    "karnataka": "bangalore",
    "kerala": "kochi",
    "goa": "goa",
    "maharashtra": "mumbai",
    "telangana": "hyderabad",
    "andhra": "vizag",
    "west bengal": "kolkata",
    "kolkata": "kolkata",
}

REAL_TIME_KEYWORDS = [
    "today", "latest", "current", "price", "availability",
    "now", "update", "cost", "how much", "howmuch"
]

def _now_ts():
    return int(time.time())

def _cache_get(key):
    val = _CACHE.get(key)
    if not val:
        return None
    ts, data = val
    if _now_ts() - ts > CACHE_TTL_SECS:
        del _CACHE[key]
        return None
    return data

def _cache_set(key, data):
    _CACHE[key] = (_now_ts(), data)

def is_real_time_query(prompt: str) -> bool:
    low = prompt.lower()
    return any(k in low for k in REAL_TIME_KEYWORDS)

def extract_brand_location(prompt: str):
    """
    Extract brand and location from query.
    """
    loc_match = re.search(
        r"\bin\s+([a-zA-Z\s]+?)(?:\?|$|\b(today|now|current|price|prices|latest|how much|cost)\b)",
        prompt,
        flags=re.I,
    )
    location = loc_match.group(1).strip() if loc_match else ""
    brand = prompt
    if loc_match:
        brand = brand.replace(loc_match.group(0), "")

    # Clean brand
    brand = re.sub(
        r"\b(what|is|the|price|prices|cost|of|today|current|latest|now|tell me|give me|how much)\b",
        "", brand, flags=re.I)
    brand = re.sub(r"[^a-zA-Z0-9\s]", "", brand)
    brand = re.sub(r"\s+", " ", brand).strip()

    # Normalize location
    loc_clean = location.lower().strip()
    if loc_clean in LOCATION_ALIASES:
        location = LOCATION_ALIASES[loc_clean]
    else:
        location = loc_clean if loc_clean else ""

    return brand or "alcohol", location or "delhi"  # default city = delhi

def _parse_numeric_price(p_str):
    if not p_str:
        return None
    m = re.search(r"(\d[\d,]*(?:\.\d{1,2})?)", str(p_str))
    if not m:
        return None
    num = m.group(1).replace(",", "")
    try:
        return float(num)
    except Exception:
        return None

def _format_inr(n):
    try:
        i = int(round(n))
        s = f"{i:,}"
        return "₹" + s
    except Exception:
        return f"₹{n}"

def _aggregate_prices(price_list):
    if not price_list:
        return None
    cleaned = sorted([p for p in price_list if p is not None])
    if not cleaned:
        return None
    return {
        "count": len(cleaned),
        "median": statistics.median(cleaned),
        "mean": statistics.mean(cleaned),
        "min": min(cleaned),
        "max": max(cleaned),
    }

def query_mistral(prompt):
    try:
        response = ollama.chat(
            model="mistral",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant specialized in alcoholic drinks. "
                        "Answer only alcohol-related queries in short, complete sentences. "
                        "If the query is unrelated to alcohol, reply: "
                        "'Sorry, I can only answer questions related to alcoholic drinks.'"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.get("message", {}).get("content", "").strip()
    except Exception:
        return None

def handle_query(prompt, limit=6, debug=False):
    # Non-real-time → Mistral only
    if not is_real_time_query(prompt):
        ans = query_mistral(prompt)
        return ans or "Sorry, I can only answer questions related to alcoholic drinks."

    # Extract
    brand_raw, location = extract_brand_location(prompt)
    brand = brand_raw.strip()
    if debug:
        print(f"DEBUG: Extracted brand='{brand}', location='{location}'")

    # Cache
    cache_key = f"scrape::{brand.lower()}::{location.lower()}"
    scraped = _cache_get(cache_key)
    if not scraped:
        try:
            scraped = scrape_livcheers_via_typing(brand, location, limit=limit)
        except Exception as e:
            if debug:
                print(f"DEBUG: Scraper exception: {e}")
            scraped = []
        _cache_set(cache_key, scraped)

    # Filter
    qterm = brand.lower().strip()
    relevant = [item for item in scraped if qterm in (item.get("name") or "").lower()]
    used = relevant if relevant else scraped

    # Parse
    numeric_prices, examples = [], []
    for it in used:
        price_str = it.get("price") or ""
        num = _parse_numeric_price(price_str)
        if num is not None:
            numeric_prices.append(num)
        examples.append({"name": it.get("name"), "price": it.get("price")})

    agg = _aggregate_prices(numeric_prices)
    year = datetime.datetime.now().year

    # Case 1: We got numeric prices
    if agg:
        avg_price = _format_inr(agg["median"])
        mn_fmt = _format_inr(agg["min"])
        mx_fmt = _format_inr(agg["max"])
        subject = brand if brand else (prompt.split()[0] if prompt.split() else "This item")
        examples_text = ", ".join([f"{e['name']} {e['price']}" for e in examples[:3]])
        return (
            f"As of {year}, the average price of {subject}"
            + (f" in {location.title()}" if location else "")
            + f" is about {avg_price}. "
            + f"Depending on the bottle size, prices usually range between {mn_fmt} and {mx_fmt}. "
            + (f"Some examples: {examples_text}." if examples_text else "")
        )

    # Case 2: No usable data → fall back to Mistral
    if not used:
        mistral_ans = query_mistral(prompt)
        return f"As of {year}, {mistral_ans}" if mistral_ans else f"As of {year}, no data could be found."

    # Case 3: Listings exist but prices not numeric
    example_text = ", ".join([f"{e['name']} {e['price']}" for e in examples[:4]])
    return (
        f"As of {year}, I found these listings for {brand or 'the requested item'}"
        + (f" in {location.title()}" if location else "")
        + f": {example_text}. Exact prices could not be parsed."
    )

if __name__ == "__main__":
    print(handle_query("Give me Kingfisher prices in Tamilnadu today", limit=6, debug=True))
    print(handle_query("What is the price of Old Monk in Goa?", limit=6, debug=True))
    print(handle_query("Suggest cocktails with vodka"))
