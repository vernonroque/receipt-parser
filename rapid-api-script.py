import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(".env")

# RapidAPI credentials
X_RAPIDAPI_KEY = os.getenv("X_RAPIDAPI_KEY")

url = "https://receipt-parser2.p.rapidapi.com/api/parse"

headers = {
    "Accept": "application/json",
    "X-RapidAPI-Key": X_RAPIDAPI_KEY,
    "X-RapidAPI-Host": "receipt-parser2.p.rapidapi.com"
}

with open("Carulla.pdf", "rb") as f:
    files = {"file": ("Carulla.pdf", f, "application/pdf")}
    response = requests.post(url, files=files, headers=headers)

print(response.json())