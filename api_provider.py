# -*- coding: utf-8 -*-
import logging
import os
import aiohttp
from datetime import datetime


API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("API_BASE_URL", "")


accounts_cache = {}

def _make_api_session() -> aiohttp.ClientSession:
    connector = aiohttp.TCPConnector(ssl=False)
   
    headers = {"x-om-auth-token": API_KEY, "Accept": "application/json"}
    return aiohttp.ClientSession(connector=connector, headers=headers)

async def api_get_accounts() -> list[dict]:
    try:
        async with _make_api_session() as session:
            async with session.get(f"{BASE_URL}/api/v0/accounts") as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                if isinstance(data, list): return data
                if isinstance(data, dict): return data.get("accounts", data.get("data", []))
                return []
    except Exception as e:
        logging.error(f"api_get_accounts error: {e}")
        return []

async def load_accounts():
    data = await api_get_accounts()
    if data:
        for acc in data:
            if acc.get("name") and acc.get("platform_account_id"):
                accounts_cache[acc["name"]] = str(acc["platform_account_id"])
        logging.info(f"Loaded {len(accounts_cache)} accounts from API.")

async def api_get_transactions(platform_account_id: str, start_utc: datetime, end_utc: datetime) -> list[dict]:
    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_str   = end_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    url = f"{BASE_URL}/api/v0/platforms/onlyfans/accounts/{platform_account_id}/transactions"
    params = {"start": start_str, "end": end_str, "limit": 1000}
    try:
        async with _make_api_session() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200: return []
                data = await resp.json()
                if isinstance(data, list): return data
                if isinstance(data, dict): return data.get("transactions", data.get("data", []))
                return []
    except Exception as e:
        logging.error(f"api_get_transactions error for {platform_account_id}: {e}")
        return []

async def get_account_profit(acc_name, start_time_utc, end_time_utc):
    platform_id = accounts_cache.get(acc_name)
    if not platform_id: return 0.0
    transactions = await api_get_transactions(platform_id, start_time_utc, end_time_utc)
    total_profit = 0.0
    for tx in transactions:
        if tx.get("status") in ["done", "loading", "success", "completed"]:
            total_profit += float(tx.get("amount", 0.0))
    return total_profit
