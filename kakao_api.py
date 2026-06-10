import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


load_dotenv()

BASE_URL = "https://dapi.kakao.com/v2/local"


class KakaoLocalAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KAKAO_REST_API_KEY", "")
        self.last_error = ""

    def keyword_search(
        self,
        query: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        radius: int = 1000,
        size: int = 15,
    ) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []

        params: Dict[str, Any] = {
            "query": query,
            "radius": radius,
            "size": size,
            "category_group_code": "FD6",
        }
        if x is not None and y is not None:
            params["x"] = x
            params["y"] = y

        return self._get("/search/keyword.json", params).get("documents", [])

    def address_search(self, location_name: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []

        params = {"query": location_name, "size": 5}
        return self._get("/search/address.json", params).get("documents", [])

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Authorization": f"KakaoAK {self.api_key}"}
        try:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                headers=headers,
                params=params,
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                self.last_error = f"Kakao API error {response.status_code}: {response.text[:300]}"
            else:
                self.last_error = f"Kakao API request failed: {exc}"
            print(self.last_error)
            return {"documents": []}
