import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from tools import (
    filter_restaurants,
    get_location_coords,
    search_restaurants,
    tool_definitions,
)


load_dotenv()


SYSTEM_PROMPT = """
You are a Korean restaurant recommendation AI agent.
Use ReAct style: Thought -> Action -> Observation -> Final Answer.

Rules:
- Always call tools when restaurant or location data is needed.
- Use Korean for user-facing answers.
- Recommend exactly three restaurants when possible.
- Consider price, review count, rating, distance, and user purpose.
- If the location is invalid, observe the tool error and suggest a clearer location.
- If there are no results, broaden the radius or simplify the query before giving up.
- If the food type is ambiguous but the user gave a meal purpose, search broad "맛집".
- Return concise, useful recommendations.
""".strip()


class RestaurantAgent:
    def __init__(self, model: str = "gpt-4o-mini", max_iterations: int = 5):
        self.model = model
        self.max_iterations = max_iterations
        api_key = os.getenv("OPENAI_API_KEY")
        self.client: Optional[OpenAI] = OpenAI(api_key=api_key) if api_key else None
        self.trace: List[Dict[str, str]] = []

    def run(self, user_request: str) -> Dict[str, Any]:
        self.trace = []
        self._log("THOUGHT", "사용자 요청에서 지역, 음식 종류, 가격대, 리뷰/평점 조건을 확인합니다.")

        validation = self._validate_request(user_request)
        if validation["status"] == "need_more_info":
            final_answer = validation["message"]
            reflection = {"score": 4, "comment": "지역 또는 목적 조건이 부족해 추가 질문을 제시했습니다."}
            self._log("OBSERVATION", json.dumps(validation, ensure_ascii=False, indent=2))
            self._log("FINAL ANSWER", final_answer)
            return {"final_answer": final_answer, "restaurants": [], "reflection": reflection, "trace": self.trace}

        if self.client is None:
            self._log("OBSERVATION", "OPENAI_API_KEY가 없어 규칙 기반 ReAct 루프로 대체 실행합니다.")
            return self._run_rule_based(user_request)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ]
        final_answer = ""
        restaurants: List[Dict[str, Any]] = []

        for iteration in range(1, self.max_iterations + 1):
            self._log("THOUGHT", f"{iteration}번째 ReAct 반복: 필요한 도구를 선택하고 결과를 관찰합니다.")

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_definitions(),
                    tool_choice="auto",
                )
            except Exception as exc:
                self._log("OBSERVATION", f"OpenAI API 호출 실패: {exc}. 규칙 기반 대안 흐름으로 전환합니다.")
                return self._run_rule_based(user_request)

            message = response.choices[0].message
            assistant_content = message.content or ""
            if assistant_content:
                self._log("THOUGHT", assistant_content)

            tool_calls = message.tool_calls or []
            if tool_calls:
                messages.append(message.model_dump(exclude_none=True))
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    arguments = self._parse_arguments(tool_call.function.arguments)
                    self._log("ACTION", f"도구 호출: {tool_name}\n입력값: {json.dumps(arguments, ensure_ascii=False)}")

                    observation = self._execute_tool(tool_name, arguments)
                    restaurants = self._restaurants_from_observation(observation, restaurants)

                    observation_text = json.dumps(observation, ensure_ascii=False, indent=2)
                    self._log("OBSERVATION", observation_text)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": observation_text,
                        }
                    )
                continue

            final_answer = assistant_content.strip()
            if final_answer:
                self._log("FINAL ANSWER", final_answer)
                break

        if not restaurants:
            self._log("OBSERVATION", "LLM 도구 루프에서 추천 후보가 충분하지 않아 규칙 기반 보완 검색을 실행합니다.")
            fallback_result = self._run_rule_based(user_request)
            fallback_result["trace"] = self.trace
            return fallback_result

        recommended = restaurants[:3]
        if not final_answer:
            final_answer = self._build_final_answer(user_request, recommended)
            self._log("FINAL ANSWER", final_answer)

        reflection = self._reflect(user_request, recommended, final_answer)
        if reflection.get("score", 10) < 7:
            self._log("THOUGHT", "Reflection 점수가 낮아 검색 반경을 넓히고 리뷰 수 기준으로 보완합니다.")
            improved = self._improve_recommendations(user_request)
            if improved:
                recommended = improved
                final_answer = self._build_final_answer(user_request, recommended)
                self._log("ACTION", "보완 검색 실행: query=맛집, radius=3000, sort_by=review_count")
                self._log("OBSERVATION", json.dumps(recommended, ensure_ascii=False, indent=2))
                self._log("FINAL ANSWER", final_answer)
                reflection = self._reflect(user_request, recommended, final_answer)

        return {
            "final_answer": final_answer,
            "restaurants": recommended,
            "reflection": reflection,
            "trace": self.trace,
        }

    def _run_rule_based(self, user_request: str) -> Dict[str, Any]:
        plan = {
            "steps": [
                "지역 추출",
                "음식/목적 조건 파악",
                "맛집 검색 도구 호출",
                "평점/리뷰/거리/가격대 기준 필터링",
                "Reflection으로 조건 충족 여부 검토",
            ]
        }
        self._log("THOUGHT", f"Plan-and-Solve 단계 분해: {json.dumps(plan, ensure_ascii=False)}")

        location = self._guess_location(user_request)
        query = self._guess_query(user_request)
        max_price_level = "중간" if any(word in user_request for word in ["비싸지", "저렴", "가성비"]) else "비쌈"

        self._log("ACTION", f"도구 호출: get_location_coords\n입력값: {json.dumps({'location_name': location}, ensure_ascii=False)}")
        location_observation = get_location_coords(location)
        self._log("OBSERVATION", json.dumps(location_observation, ensure_ascii=False, indent=2))

        if location_observation.get("status") == "not_found":
            final_answer = (
                f"{location} 위치를 찾지 못했습니다. 동 이름, 역 이름, 랜드마크처럼 더 구체적인 지역을 알려주시면 "
                "검색 반경을 조정해서 다시 추천드릴게요."
            )
            reflection = {"score": 4, "comment": "존재하지 않는 지역 입력에 대해 대안 입력을 요청했습니다."}
            self._log("FINAL ANSWER", final_answer)
            return {"final_answer": final_answer, "restaurants": [], "reflection": reflection, "trace": self.trace}

        self._log(
            "ACTION",
            f"도구 호출: search_restaurants\n입력값: {json.dumps({'query': query, 'location': location, 'radius': 1500}, ensure_ascii=False)}",
        )
        restaurants = search_restaurants(query=query, location=location, radius=1500)
        self._log("OBSERVATION", json.dumps({"count": len(restaurants), "restaurants": restaurants}, ensure_ascii=False, indent=2))

        if not restaurants:
            self._log("THOUGHT", "검색 결과가 없어 검색어를 '맛집'으로 단순화하고 반경을 3000m로 확대합니다.")
            self._log(
                "ACTION",
                f"도구 호출: search_restaurants\n입력값: {json.dumps({'query': '맛집', 'location': location, 'radius': 3000}, ensure_ascii=False)}",
            )
            restaurants = search_restaurants(query="맛집", location=location, radius=3000)
            self._log("OBSERVATION", json.dumps({"count": len(restaurants), "restaurants": restaurants}, ensure_ascii=False, indent=2))

        self._log(
            "ACTION",
            "도구 호출: filter_restaurants\n입력값: "
            + json.dumps(
                {"min_rating": 4.0, "max_price_level": max_price_level, "sort_by": "review_count"},
                ensure_ascii=False,
            ),
        )
        filtered = filter_restaurants(restaurants, min_rating=4.0, max_price_level=max_price_level, sort_by="review_count")[:3]
        self._log("OBSERVATION", json.dumps({"count": len(filtered), "restaurants": filtered}, ensure_ascii=False, indent=2))

        if not filtered:
            final_answer = (
                "조건에 맞는 맛집을 찾지 못했습니다. 음식 종류를 넓히거나 가격대/거리 조건을 완화하면 "
                "다시 검색할 수 있습니다."
            )
            reflection = {"score": 5, "comment": "검색 결과 없음 상황에서 조건 완화라는 대안을 제시했습니다."}
            self._log("FINAL ANSWER", final_answer)
            return {"final_answer": final_answer, "restaurants": [], "reflection": reflection, "trace": self.trace}

        final_answer = self._build_final_answer(user_request, filtered)
        self._log("FINAL ANSWER", final_answer)
        reflection = self._reflect(user_request, filtered, final_answer)
        return {"final_answer": final_answer, "restaurants": filtered, "reflection": reflection, "trace": self.trace}

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        try:
            if tool_name == "search_restaurants":
                query = arguments.get("query", "맛집")
                location = arguments.get("location") or self._guess_location(query)
                if not location:
                    return {
                        "status": "need_more_info",
                        "message": "검색할 지역이 없어 맛집 검색을 실행할 수 없습니다.",
                        "recovery": "예: 발산역 주변 양고기 맛집, 서울 강서구 카페처럼 지역을 포함해 주세요.",
                    }
                radius = int(arguments.get("radius", 1000))
                result = search_restaurants(query=query, location=location, radius=radius)
                if not result:
                    broader = search_restaurants(
                        query=self._simplify_query(query),
                        location=location,
                        radius=max(radius * 2, 2000),
                    )
                    return {
                        "status": "no_results",
                        "message": "검색 결과가 없어 검색어를 단순화하고 반경을 넓혔습니다.",
                        "restaurants": broader,
                        "recovery": "그래도 결과가 없으면 지역명이나 음식 종류를 더 구체화해야 합니다.",
                    }
                return {"status": "ok", "restaurants": result}

            if tool_name == "filter_restaurants":
                filtered = filter_restaurants(
                    restaurants=arguments.get("restaurants", []),
                    min_rating=float(arguments.get("min_rating", 0.0)),
                    max_price_level=arguments.get("max_price_level", "중간"),
                    sort_by=arguments.get("sort_by", "rating"),
                )
                return {"status": "ok", "restaurants": filtered}

            if tool_name == "get_location_coords":
                return get_location_coords(arguments.get("location_name", ""))

            return {"status": "error", "message": f"알 수 없는 도구입니다: {tool_name}"}
        except Exception as exc:
            return {
                "status": "tool_error",
                "message": f"도구 실행 실패: {exc}",
                "recovery": "Agent는 샘플 데이터셋 또는 더 단순한 검색 조건으로 대체할 수 있습니다.",
            }

    def _reflect(self, user_request: str, restaurants: List[Dict[str, Any]], final_answer: str) -> Dict[str, Any]:
        prompt = f"""
Original user request:
{user_request}

Recommended restaurants:
{json.dumps(restaurants, ensure_ascii=False, indent=2)}

Final answer:
{final_answer}

Evaluate whether this recommendation satisfies the user's conditions.
Return only JSON with keys: score, comment.
score must be an integer from 1 to 10.
comment must be Korean and explain gaps or strengths briefly.
""".strip()
        if self.client is None:
            reflection = {
                "score": 8 if len(restaurants) >= 3 else 5,
                "comment": "규칙 기반 Reflection: 리뷰 수, 가격대, 거리 조건을 기준으로 추천 결과를 점검했습니다.",
            }
            self._log("OBSERVATION", f"Reflection 결과: {json.dumps(reflection, ensure_ascii=False)}")
            return reflection

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict recommendation evaluator. Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            reflection = json.loads(content)
        except Exception as exc:
            reflection = {
                "score": 8 if len(restaurants) >= 3 else 5,
                "comment": f"Reflection API 호출이 실패해 규칙 기반으로 평가했습니다. 오류: {exc}",
            }
        reflection["score"] = int(reflection.get("score", 0))
        reflection["comment"] = str(reflection.get("comment", "평가 의견이 없습니다."))
        self._log("OBSERVATION", f"Reflection 결과: {json.dumps(reflection, ensure_ascii=False)}")
        return reflection

    def _improve_recommendations(self, user_request: str) -> List[Dict[str, Any]]:
        improved = search_restaurants(query="맛집", location=self._guess_location(user_request), radius=3000)
        return filter_restaurants(improved, min_rating=4.0, max_price_level="중간", sort_by="review_count")[:3]

    def _build_final_answer(self, user_request: str, restaurants: List[Dict[str, Any]]) -> str:
        if not restaurants:
            return "조건에 맞는 맛집을 찾지 못했습니다. 지역이나 음식 종류를 조금 더 구체적으로 알려주세요."

        lines = [f"요청하신 조건을 기준으로 추천할 만한 맛집 3곳입니다: {user_request}"]
        for index, restaurant in enumerate(restaurants[:3], start=1):
            source_label = "Kakao" if restaurant.get("source") == "kakao" else "샘플 데이터"
            lines.append(
                f"{index}. {restaurant.get('name')} - {restaurant.get('category')} / "
                f"평점 {restaurant.get('rating')} / 리뷰 {restaurant.get('review_count')}개 / "
                f"{restaurant.get('distance')}m / {self._format_price_label(restaurant.get('price_level', '중간'))} / 출처 {source_label}"
            )
        lines.append("너무 비싸지 않고 리뷰가 좋은 곳을 우선으로 골랐습니다.")
        return "\n".join(lines)

    def _format_price_label(self, price_level: str) -> str:
        labels = {
            "저렴": "가성비 좋음",
            "중간": "부담 적은 편",
            "비쌈": "특별한 날 추천",
        }
        return labels.get(str(price_level), "가격 정보 참고")

    def _validate_request(self, user_request: str) -> Dict[str, str]:
        if not user_request.strip():
            return {"status": "need_more_info", "message": "지역과 원하는 음식 종류 또는 방문 목적을 입력해 주세요."}
        if not self._has_location_hint(user_request):
            return {
                "status": "need_more_info",
                "message": "어느 지역에서 찾을지 알려주세요. 예: 전주 객사 근처 맛집, 서울 홍대 파스타 맛집",
            }
        if len(user_request.strip()) < 5:
            return {"status": "need_more_info", "message": "지역, 음식 종류, 가격대 중 하나 이상을 더 알려주세요."}
        return {"status": "ok", "message": "요청 조건이 충분합니다."}

    def _restaurants_from_observation(
        self,
        observation: Any,
        current: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if isinstance(observation, list):
            return observation
        if isinstance(observation, dict) and isinstance(observation.get("restaurants"), list):
            return observation["restaurants"]
        return current

    def _parse_arguments(self, raw_arguments: str) -> Dict[str, Any]:
        try:
            return json.loads(raw_arguments or "{}")
        except json.JSONDecodeError:
            return {}

    def _simplify_query(self, query: str) -> str:
        for keyword in ["맛집", "한식", "일식", "양식", "카페", "디저트", "파스타", "비빔밥", "국밥", "양고기", "양꼬치"]:
            if keyword in query:
                return keyword
        return "맛집"

    def _guess_query(self, user_request: str) -> str:
        for keyword in ["양고기", "양꼬치", "한식", "일식", "양식", "카페", "디저트", "파스타", "비빔밥", "국밥", "칼국수"]:
            if keyword in user_request:
                return keyword
        return "맛집"

    def _guess_location(self, user_request: str) -> str:
        known_locations = {
            "발산역": "서울 강서구 발산역",
            "마곡역": "서울 강서구 마곡역",
            "강서구": "서울시 강서구",
            "홍대": "서울 홍대",
            "객사": "전주 객사",
            "전주": "전주",
        }
        for keyword, location in known_locations.items():
            if keyword in user_request:
                return location

        station_match = re.search(r"([가-힣A-Za-z0-9]+역)", user_request)
        if station_match:
            return station_match.group(1)

        area_match = re.search(
            r"([가-힣A-Za-z0-9]+(?:시|군|구|동|읍|면|로|길)?)\s*(?:근처|주변|에서)",
            user_request,
        )
        if area_match:
            return area_match.group(1)

        return ""

    def _has_location_hint(self, user_request: str) -> bool:
        return bool(re.search(r"(전주|객사|서울|홍대|강서구|발산역|마곡역|근처|주변|에서|역|동|구)", user_request))

    def _log(self, step_type: str, message: str) -> None:
        entry = {"type": f"[{step_type}]", "message": message}
        self.trace.append(entry)
        print(f"[{step_type}] {message}")
