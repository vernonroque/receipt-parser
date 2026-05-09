"""CLI script to generate a new API key and store it in Supabase.

Usage:
    python scripts/create_key.py --name "Production"
"""

import argparse
import asyncio
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a new API key in Supabase.")
    parser.add_argument("--name", required=True, help="Human-readable label for the key.")
    args = parser.parse_args()

    # Load .env before importing project modules so settings resolve correctly.
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Error: python-dotenv is not installed. Run: pip install python-dotenv")
        sys.exit(1)

    load_dotenv()

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url:
        print("Error: SUPABASE_URL is not set in the environment or .env file.")
        sys.exit(1)
    if not supabase_service_key:
        print("Error: SUPABASE_SERVICE_KEY is not set in the environment or .env file.")
        sys.exit(1)

    asyncio.run(_create(args.name, supabase_url, supabase_service_key))


async def _create(name: str, supabase_url: str, supabase_service_key: str) -> None:
    from supabase import acreate_client

    from app.services.api_key_service import generate_api_key

    supabase = await acreate_client(supabase_url, supabase_service_key)
    raw_key = await generate_api_key(name, supabase)

    print()
    print(f"API key created for: {name}")
    print(f"Key: {raw_key}")
    print()
    print("Save this key now — it will NOT be shown again.")
    print()


if __name__ == "__main__":
    main()
