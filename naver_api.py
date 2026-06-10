import os
import re
from html import unescape
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


load_dotenv()

BASE_URL = "https://openapi.naver.com/v1/search"

MENU_KEYWORDS = [
    "양꼬치",
    "양갈비",
    "꿔바로우",
    "마라탕",
    "비빔밥",
    "콩나물국밥",
    "칼국수",
    "초코파이",
    "파스타",
    "스테이크",
    "라멘",
    "초밥",
    "돈카츠",
    "커피",
    "케이크",
    "디저트",
    "삼겹살",
    "갈비",
    "냉면",
    "김치찌개",
    "된장찌개",
    "국밥",
    "치킨",
    "피자",
]

CATEGORY_MENU_FALLBACKS = {
    "양고기": ["양꼬치", "양갈비", "꿔바로우"],
    "양꼬치": ["양꼬치", "양갈비", "꿔바로우"],
    "카페": ["커피", "케이크", "디저트"],
    "베이커리": ["커피", "초코파이", "베이커리"],
    "비빔밥": ["비빔밥", "육회비빔밥", "전주비빔밥"],
    "국밥": ["콩나물국밥", "국밥", "모주"],
    "칼국수": ["칼국수", "만두", "쫄면"],
    "파스타": ["파스타", "스테이크", "리조또"],
}


class NaverSearchAPI:
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id or os.getenv("NAVER_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("NAVER_CLIENT_SECRET", "")
        self.last_error = ""

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def image_search(self, query: str, display: int = 3) -> List[Dict[str, Any]]:
        return self._get("image", {"query": query, "display": display, "sort": "sim"}).get("items", [])

    def blog_search(self, query: str, display: int = 10) -> List[Dict[str, Any]]:
        return self._get("blog", {"query": query, "display": display, "sort": "sim"}).get("items", [])

    def local_search(self, query: str, display: int = 5) -> List[Dict[str, Any]]:
        return self._get("local", {"query": query, "display": display, "sort": "random"}).get("items", [])

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {"items": []}

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        try:
            response = requests.get(
                f"{BASE_URL}/{endpoint}.json",
                headers=headers,
                params=params,
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                self.last_error = f"Naver API error {response.status_code}: {response.text[:300]}"
            else:
                self.last_error = f"Naver API request failed: {exc}"
            print(self.last_error)
            return {"items": []}


def enrich_restaurants_with_naver(restaurants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    api = NaverSearchAPI()
    return [enrich_restaurant_with_naver(restaurant, api) for restaurant in restaurants]


def enrich_restaurant_with_naver(restaurant: Dict[str, Any], api: Optional[NaverSearchAPI] = None) -> Dict[str, Any]:
    api = api or NaverSearchAPI()
    enriched = dict(restaurant)
    name = str(enriched.get("name", ""))
    address = str(enriched.get("address", ""))
    category = str(enriched.get("category", ""))
    query = f"{name} {address}".strip()

    enriched["naver_menus"] = []
    enriched["naver_image_url"] = ""
    enriched["naver_place_url"] = ""

    if api.enabled:
        local_items = api.local_search(query)
        if local_items:
            enriched["naver_place_url"] = local_items[0].get("link", "")

        image_items = api.image_search(f"{query} 대표메뉴")
        enriched["naver_image_url"] = _pick_image_url(image_items)

        blog_items = api.blog_search(f"{query} 메뉴")
        enriched["naver_menus"] = _extract_menu_candidates(blog_items, category=category, name=name)

    if not enriched["naver_menus"]:
        enriched["naver_menus"] = _fallback_menus(category=category, name=name)

    return enriched


def _pick_image_url(items: List[Dict[str, Any]]) -> str:
    for item in items:
        thumbnail = item.get("thumbnail") or item.get("link")
        if thumbnail:
            return str(thumbnail)
    return ""


def _extract_menu_candidates(items: List[Dict[str, Any]], category: str, name: str) -> List[str]:
    text = " ".join(
        _clean_html(f"{item.get('title', '')} {item.get('description', '')}")
        for item in items
    )
    scores: Dict[str, int] = {}
    for keyword in MENU_KEYWORDS:
        count = text.count(keyword)
        if count:
            scores[keyword] = count

    ordered = sorted(scores, key=lambda keyword: (-scores[keyword], keyword))
    menus = ordered[:3]
    if len(menus) < 3:
        for menu in _fallback_menus(category=category, name=name):
            if menu not in menus:
                menus.append(menu)
            if len(menus) == 3:
                break
    return menus[:3]


def _fallback_menus(category: str, name: str) -> List[str]:
    text = f"{category} {name}"
    for keyword, menus in CATEGORY_MENU_FALLBACKS.items():
        if keyword in text:
            return menus[:3]
    return []


def _clean_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", text)
    return unescape(cleaned)
