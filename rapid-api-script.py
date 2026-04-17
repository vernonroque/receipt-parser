import requests

url = "https://receipt-parser2.p.rapidapi.com/api/parse"

headers = {
    "Accept": "application/json",
    "Authorization": "Bearer {your_api_key_or_rapidapi_tokenX_RapidAPI-Proxy-Secret}",
    "X-RapidAPI-Key": "8406a41e53mshea021ef3347fc42p18d471jsn5e08e24374f5",
    "X-RapidAPI-Host": "receipt-parser2.p.rapidapi.com"
}

with open("Carulla.pdf", "rb") as f:
    files = {"file": ("Carulla.pdf", f, "application/pdf")}
    response = requests.post(url, files=files, headers=headers)

print(response.json())