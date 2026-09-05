"""Search and resolve packaged foods from Open Food Facts."""
import math
import logging
import time
from urllib.parse import quote

import httpx

BASE_URL = "https://world.openfoodfacts.org"
SEARCH_URLS = (f"{BASE_URL}/cgi/search.pl", "https://br.openfoodfacts.org/cgi/search.pl")
HEADERS = {"User-Agent": "FORGE/1.0 (https://forge.aiexec.com.br)"}
logger = logging.getLogger(__name__)
_cache = {}
_TTL_SECONDS = 900


def _number(value, default=0.0):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _food(product):
    code = str(product.get("code") or "").strip()
    nutriments = product.get("nutriments") or {}
    name = (product.get("product_name_pt") or product.get("product_name") or "").strip()
    kcal = _number(nutriments.get("energy-kcal_100g"), -1)
    if kcal < 0:
        kj = _number(nutriments.get("energy_100g"), -1)
        kcal = kj / 4.184 if kj >= 0 else -1
    protein = _number(nutriments.get("proteins_100g"))
    carbs = _number(nutriments.get("carbohydrates_100g"))
    fat = _number(nutriments.get("fat_100g"))
    if not code or not name or kcal < 0 or kcal > 1000 or any(v < 0 or v > 100 for v in (protein, carbs, fat)):
        return None
    brands = str(product.get("brands") or "").strip()
    display_name = f"{name} — {brands}" if brands and brands.lower() not in name.lower() else name
    return {"id": f"off:{code}", "name": display_name[:180], "aliases": [], "grams": 100,
            "kcal": round(kcal, 1), "protein_g": round(protein, 1), "carbs_g": round(carbs, 1),
            "fat_g": round(fat, 1), "source": "Open Food Facts — confira o rótulo",
            "source_url": f"{BASE_URL}/product/{code}"}


async def search_external_foods(query, limit=12):
    key = "search:" + query.casefold().strip()
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < _TTL_SECONDS:
        return cached[1]
    params = {"search_terms": query, "search_simple": 1, "action": "process", "json": 1,
              "page_size": min(limit * 2, 24), "fields": "code,product_name,product_name_pt,brands,nutriments"}
    foods = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=5), headers=HEADERS, follow_redirects=True) as client:
        for url in SEARCH_URLS:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                foods = [food for product in response.json().get("products", []) if (food := _food(product))][:limit]
                if foods:
                    break
            except (httpx.HTTPError, ValueError, TypeError) as error:
                logger.warning("Open Food Facts search failed at %s: %s", url, error)
    # Falhas transitórias não devem bloquear a mesma busca por 15 minutos.
    if foods:
        _cache[key] = (time.monotonic(), foods)
    for food in foods:
        _cache[food["id"]] = (time.monotonic(), food)
    return foods


async def resolve_external_food(food_id):
    if not food_id.startswith("off:"):
        return None
    cached = _cache.get(food_id)
    if cached and time.monotonic() - cached[0] < _TTL_SECONDS:
        return cached[1]
    code = food_id[4:]
    if not code.isdigit() or len(code) > 20:
        return None
    try:
        fields = "code,product_name,product_name_pt,brands,nutriments"
        async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=5), headers=HEADERS, follow_redirects=True) as client:
            response = await client.get(f"{BASE_URL}/api/v2/product/{quote(code)}", params={"fields": fields})
            response.raise_for_status()
        food = _food(response.json().get("product") or {})
    except (httpx.HTTPError, ValueError, TypeError):
        food = None
    if food:
        _cache[food_id] = (time.monotonic(), food)
    return food
