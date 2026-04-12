from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
print("I called the get_token script")

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

response = supabase.auth.sign_in_with_oauth({
    "provider": "github",
    "options": {
        "redirect_to": "http://localhost:8000"
    }
})

print(response.url)