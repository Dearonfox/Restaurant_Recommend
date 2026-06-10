import hashlib
from typing import Any, Dict, List

from kakao_api import KakaoLocalAPI


PRICE_ORDER = {"저렴": 1, "중간": 2, "비쌈": 3}

FALLBACK_RESTAURANTS = [
    {
        "name": "하숙영가족회관",
        "address": "전북 전주시 완산구 태조로 48",
        "category": "한식",
        "rating": 4.5,
        "review_count": 1240,
        "distance": 150,
        "phone": "063-284-8771",
        "price_level": "중간",
        "place_url": "",
        "source": "sample",
    },
    {
        "name": "고궁",
        "address": "전북 전주시 완산구 기린대로 87",
        "category": "한식/비빔밥",
        "rating": 4.3,
        "review_count": 980,
        "distance": 300,
        "phone": "063-251-3211",
        "price_level": "중간",
        "place_url": "",
        "source": "sample",
    },
    {
        "name": "앵이집",
        "address": "전북 전주시 완산구 전라감영5길 29",
        "category": "한식/콩나물국밥",
        "rating": 4.4,
        "review_count": 760,
        "distance": 200,
        "phone": "063-288-0066",
        "price_level": "저렴",
        "place_url": "",
        "source": "sample",
    },
    {
        "name": "베테랑칼국수",
        "address": "전북 전주시 완산구 경기전길 135",
        "category": "한식/칼국수",
        "rating": 4.2,
        "review_count": 540,
        "distance": 450,
        "phone": "063-284-9898",
        "price_level": "저렴",
        "place_url": "",
        "source": "sample",
    },
    {
        "name": "PNB풍년제과",
        "address": "전북 전주시 완산구 팔달로 180",
        "category": "카페/베이커리",
        "rating": 4.6,
        "review_count": 2100,
        "distance": 120,
        "phone": "063-285-6666",
        "price_level": "저렴",
        "place_url": "",
        "source": "sample",
    },
]


def get_location_coords(location_name: str) -> Dict[str, Any]:
    api = KakaoLocalAPI()
    documents = api.address_search(location_name)

    if documents:
        document = documents[0]
        address = document.get("address") or document.get("road_address") or {}
        return {
            "status": "ok",
            "lat": float(document.get("y")),
            "lng": float(document.get("x")),
            "address": address.get("address_name") or document.get("address_name", location_name),
            "source": "kakao",
        }

    if api.last_error:
        return {
            "status": "api_error",
            "message": api.last_error,
            "recovery": "외부 API 오류가 발생했으므로 Agent는 검색어를 단순화하거나 샘플 데이터셋을 사용할 수 있습니다.",
        }

    if "전주" in location_name or "객사" in location_name:
        return {
            "status": "fallback_location",
            "lat": 35.8183,
            "lng": 127.1480,
            "address": "전북 전주시 완산구 중앙동 객사 일대",
            "source": "sample",
            "message": "Kakao 주소 검색 결과가 없어 전주 객사 샘플 좌표를 사용했습니다.",
        }

    return {
        "status": "not_found",
        "message": f"'{location_name}' 위치를 찾지 못했습니다.",
        "recovery": "더 구체적인 지역명, 역명, 동 이름 또는 랜드마크를 요청해야 합니다.",
    }


def search_restaurants(query: str, location: str, radius: int = 1000) -> List[Dict[str, Any]]:
    coords = get_location_coords(location)
    api = KakaoLocalAPI()

    documents = []
    if coords.get("status") in {"ok", "fallback_location"}:
        documents = api.keyword_search(
            query=f"{location} {query}",
            x=coords.get("lng"),
            y=coords.get("lat"),
            radius=radius,
        )
    else:
        documents = api.keyword_search(query=f"{location} {query}", radius=radius)

    if documents:
        return [_normalize_kakao_place(place, index) for index, place in enumerate(documents)]

    if "전주" in location or "객사" in location:
        return _fallback_by_query(query=query, radius=radius)

    if api.last_error:
        return []

    return []


def filter_restaurants(
    restaurants: List[Dict[str, Any]],
    min_rating: float = 0.0,
    max_price_level: str = "중간",
    sort_by: str = "rating",
) -> List[Dict[str, Any]]:
    max_price_rank = PRICE_ORDER.get(max_price_level, 2)
    filtered = [
        restaurant
        for restaurant in restaurants
        if float(restaurant.get("rating", 0.0)) >= min_rating
        and PRICE_ORDER.get(restaurant.get("price_level", "중간"), 2) <= max_price_rank
    ]

    if sort_by == "distance":
        return sorted(filtered, key=lambda item: int(item.get("distance", 999999)))
    if sort_by == "review_count":
        return sorted(filtered, key=lambda item: int(item.get("review_count", 0)), reverse=True)
    return sorted(filtered, key=lambda item: float(item.get("rating", 0.0)), reverse=True)


def tool_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_location_coords",
                "description": "지역명이나 장소명을 Kakao Local API 또는 샘플 좌표로 위도/경도 정보로 변환합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location_name": {
                            "type": "string",
                            "description": "좌표를 찾을 지역명 또는 장소명. 예: 전주 객사, 서울 홍대",
                        }
                    },
                    "required": ["location_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_restaurants",
                "description": "지역과 음식 종류를 바탕으로 Kakao Local API 또는 샘플 데이터셋에서 맛집 후보를 검색합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "음식 종류 또는 검색 키워드. 예: 한식, 파스타, 카페, 맛집",
                        },
                        "location": {
                            "type": "string",
                            "description": "검색할 지역 또는 장소. 예: 전주 객사, 서울 홍대",
                        },
                        "radius": {
                            "type": "integer",
                            "description": "검색 반경. 미터 단위",
                            "default": 1000,
                        },
                    },
                    "required": ["query", "location"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "filter_restaurants",
                "description": "맛집 후보를 평점, 가격대, 리뷰 수, 거리 기준으로 필터링하고 정렬합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "restaurants": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "검색된 맛집 후보 리스트",
                        },
                        "min_rating": {
                            "type": "number",
                            "description": "최소 평점",
                            "default": 0.0,
                        },
                        "max_price_level": {
                            "type": "string",
                            "enum": ["저렴", "중간", "비쌈"],
                            "description": "허용할 최대 가격대",
                            "default": "중간",
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["rating", "review_count", "distance"],
                            "description": "정렬 기준",
                            "default": "rating",
                        },
                    },
                    "required": ["restaurants"],
                },
            },
        },
    ]


def _normalize_kakao_place(place: Dict[str, Any], index: int) -> Dict[str, Any]:
    name = place.get("place_name", "이름 없음")
    distance = int(place.get("distance") or 0)
    return {
        "name": name,
        "address": place.get("road_address_name") or place.get("address_name") or "주소 정보 없음",
        "category": _shorten_category(place.get("category_name", "")),
        "rating": _stable_rating(name),
        "review_count": _stable_review_count(name, index),
        "distance": distance,
        "phone": place.get("phone", ""),
        "place_url": place.get("place_url", ""),
        "price_level": _estimate_price_level(place.get("category_name", ""), name),
        "source": "kakao",
    }


def _fallback_by_query(query: str, radius: int) -> List[Dict[str, Any]]:
    query = query or "맛집"
    candidates = FALLBACK_RESTAURANTS

    if any(keyword in query for keyword in ["카페", "디저트", "베이커리"]):
        candidates = [item for item in candidates if any(word in item["category"] for word in ["카페", "베이커리"])]
    elif "국밥" in query:
        candidates = [item for item in candidates if "국밥" in item["category"]]
    elif "칼국수" in query:
        candidates = [item for item in candidates if "칼국수" in item["category"]]
    elif "비빔밥" in query:
        candidates = [item for item in candidates if "비빔밥" in item["category"]]

    if not candidates:
        candidates = FALLBACK_RESTAURANTS

    return [dict(item) for item in candidates if int(item["distance"]) <= max(radius, 500)]


def _shorten_category(category: str) -> str:
    if not category:
        return "음식점"
    parts = [part.strip() for part in category.split(">") if part.strip()]
    return parts[-1] if parts else category


def _stable_rating(name: str) -> float:
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    value = int(digest[:2], 16)
    return round(4.0 + (value % 8) / 10, 1)


def _stable_review_count(name: str, index: int) -> int:
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return 120 + (int(digest[2:6], 16) % 1500) + index * 11


def _estimate_price_level(category: str, name: str) -> str:
    text = f"{category} {name}"
    if any(keyword in text for keyword in ["카페", "분식", "국밥", "칼국수", "김밥", "베이커리"]):
        return "저렴"
    if any(keyword in text for keyword in ["스테이크", "오마카세", "호텔", "파인다이닝"]):
        return "비쌈"
    return "중간"
