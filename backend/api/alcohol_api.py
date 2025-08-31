from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()

# Define the request body model
class SearchRequest(BaseModel):
    query: str
    serpapi_key: str

@app.post("/search")
def google_search(request: SearchRequest):
    url = "https://serpapi.com/search"
    params = {
        "q": request.query,
        "api_key": request.serpapi_key,
        "engine": "google"
    }
    response = requests.get(url, params=params)
    return response.json()
