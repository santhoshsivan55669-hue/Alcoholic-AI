import requests
import json
from bs4 import BeautifulSoup

# ---- CONFIG ----
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"

# ---- GOOGLE SEARCH SCRAPER ----
def google_search(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    url = "https://www.google.com/search"
    params = {"q": query}
    res = requests.get(url, params=params, headers=headers)

    soup = BeautifulSoup(res.text, "html.parser")
    results = []

    for g in soup.select(".tF2Cxc")[:5]:  # top 5 results
        title = g.select_one("h3")
        link = g.select_one("a")["href"]
        snippet = g.select_one(".VwiC3b")
        if title and link:
            results.append(f"{title.text} - {link}\n{snippet.text if snippet else ''}")

    return "\n\n".join(results)

# ---- ASK MISTRAL ----
def ask_mistral(prompt):
    payload = {
        "model": MODEL,
        "prompt": f"""You are an alcohol keyword extractor. 
Rules:
- Only return keywords related to alcoholic drinks. 
- Always ignore non-alcohol meanings (e.g., "Corona" → "Corona Beer").
- Give realtime and upto date information about the alcohol including the price.
- Output as a comma-separated list.
- If you cannot answer confidently or if you cannot answer from year 2025, return ONLY JSON in this format:
{{"tool": "google_search", "query": "<search term>"}}

User: {prompt}
Answer:""",
        "stream": False,
    }
    res = requests.post(OLLAMA_URL, json=payload)
    return res.json()["response"]

# ---- ROUTER ----
def router(user_input):
    response = ask_mistral(user_input)

    # try:
    data = json.loads(response)
    if data.get("tool") == "google_search":
        print(f" Mistral requested Google Search: {data['query']}")
        search_results = google_search(data["query"])
        
        # Re-inject search results into Mistral for final precise answer
        final_prompt = f"""User asked: {user_input}
I searched Google and found these results:

{search_results}

Give the most precise, fact-based answer using these results only.
If multiple answers exist, summarize clearly in one concise response."""
        
        return ask_mistral(final_prompt)
    # except Exception:
    #     return response

# ---- MAIN LOOP ----
if __name__ == "__main__":
    print("💡 Chat with Mistral + Google Search (free, no API key)")
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        answer = router(user_input)
        print(f"Bot: {answer}")