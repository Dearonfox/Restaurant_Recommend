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
Use ReAct style: think about the user's request, call tools, observe results, and produce a final answer.

Rules:
- Always call tools when restaurant data or location data is needed.
- Use Korean for user-facing answers.
- If the food type is ambiguous, ask a short clarifying question in the final answer unless there is enough context to recommend broad dinner places.
- If a location is invalid, try a nearby famous landmark or ask the user to clarify.
- If there are no results, broaden the search radius or simplify the query.
- Recommend exactly three restaurants when possible.
- Consider price, reviews, distance, and purpose.
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
        if self.client is None:
            restaurants = search_restaurants(query="맛집", location=self._guess_location(user_request), radius=1500)
            restaurants = filter_restaurants(restaurants, min_rating=4.0, max_price_level="중간", sort_by="review_count")[:3]
            final_answer = self._build_fallback_answer(user_request, restaurants)
            reflection = {
                "score": 8 if restaurants else 5,
                "comment": "OPENAI_API_KEY가 없어 GPT 호출 대신 샘플 데이터와 규칙 기반 로직으로 평가했습니다.",
            }
            self._log("OBSERVATION", "OPENAI_API_KEY가 없어 샘플 데이터 fallback으로 추천을 생성합니다.")
            self._log("FINAL ANSWER", final_answer)
            self._log("OBSERVATION", f"Reflection 결과: {json.dumps(reflection, ensure_ascii=False)}")
            return {
                "final_answer": final_answer,
                "restaurants": restaurants,
                "reflection": reflection,
                "trace": self.trace,
            }

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ]

        final_answer = ""
        restaurants: List[Dict[str, Any]] = []

        for iteration in range(1, self.max_iterations + 1):
            self._log("THOUGHT", f"{iteration}번째 반복: 사용자 조건을 분석하고 필요한 도구 호출을 결정합니다.")

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_definitions(),
                    tool_choice="auto",
                )
            except Exception as exc:
                self._log("OBSERVATION", f"OpenAI 호출 실패: {exc}. 샘플 데이터 기반으로 추천을 생성합니다.")
                restaurants = search_restaurants(query="맛집", location="전주 객사", radius=1500)
                restaurants = filter_restaurants(restaurants, min_rating=4.0, max_price_level="중간", sort_by="review_count")[:3]
                final_answer = self._build_fallback_answer(user_request, restaurants)
                self._log("FINAL ANSWER", final_answer)
                break

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
                    self._log("ACTION", f"{tool_name} 호출\n입력값: {json.dumps(arguments, ensure_ascii=False)}")

                    observation = self._execute_tool(tool_name, arguments)
                    if isinstance(observation, list):
                        restaurants = observation
                    elif isinstance(observation, dict) and "restaurants" in observation:
                        restaurants = observation["restaurants"]

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

        if not final_answer:
            restaurants = restaurants or search_restaurants(query="맛집", location="전주 객사", radius=1500)
            restaurants = filter_restaurants(restaurants, min_rating=4.0, max_price_level="중간", sort_by="review_count")[:3]
            final_answer = self._build_fallback_answer(user_request, restaurants)
            self._log("FINAL ANSWER", final_answer)

        recommended = self._extract_recommended_restaurants(restaurants)
        reflection = self._reflect(user_request, recommended, final_answer)

        if reflection.get("score", 10) < 7:
            self._log("THOUGHT", "Reflection 점수가 낮아 검색 반경을 넓히고 리뷰 수 기준으로 한 번 더 보완 검색합니다.")
            improved = search_restaurants(query="맛집", location=self._guess_location(user_request), radius=3000)
            improved = filter_restaurants(improved, min_rating=4.0, max_price_level="중간", sort_by="review_count")[:3]
            if improved:
                recommended = improved
                final_answer = self._build_fallback_answer(user_request, recommended)
                self._log("ACTION", "Reflection 보완 검색 실행: query=맛집, radius=3000, sort_by=review_count")
                self._log("OBSERVATION", json.dumps(recommended, ensure_ascii=False, indent=2))
                self._log("FINAL ANSWER", final_answer)
                reflection = self._reflect(user_request, recommended, final_answer)

        return {
            "final_answer": final_answer,
            "restaurants": recommended,
            "reflection": reflection,
            "trace": self.trace,
        }

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        try:
            if tool_name == "search_restaurants":
                result = search_restaurants(
                    query=arguments.get("query", "맛집"),
                    location=arguments.get("location", "전주 객사"),
                    radius=int(arguments.get("radius", 1000)),
                )
                if not result:
                    broader = search_restaurants(
                        query=self._simplify_query(arguments.get("query", "맛집")),
                        location=arguments.get("location", "전주 객사"),
                        radius=max(int(arguments.get("radius", 1000)) * 2, 2000),
                    )
                    return {
                        "message": "검색 결과가 없어 검색어를 단순화하고 반경을 넓혔습니다.",
                        "restaurants": broader,
                    }
                return result

            if tool_name == "filter_restaurants":
                return filter_restaurants(
                    restaurants=arguments.get("restaurants", []),
                    min_rating=float(arguments.get("min_rating", 0.0)),
                    max_price_level=arguments.get("max_price_level", "중간"),
                    sort_by=arguments.get("sort_by", "rating"),
                )

            if tool_name == "get_location_coords":
                result = get_location_coords(arguments.get("location_name", ""))
                if not result:
                    fallback_location = "전주 객사"
                    fallback = get_location_coords(fallback_location)
                    return {
                        "message": f"입력 지역을 찾지 못해 가까운 주요 장소인 '{fallback_location}'를 시도했습니다.",
                        "location": fallback,
                    }
                return result

            return {"error": f"알 수 없는 도구입니다: {tool_name}"}
        except Exception as exc:
            self._log("OBSERVATION", f"도구 실행 실패: {exc}. 샘플 데이터로 대체합니다.")
            return search_restaurants(query="맛집", location="전주 객사", radius=1500)

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
                "score": 8 if restaurants else 5,
                "comment": f"Reflection API 호출이 실패해 규칙 기반으로 평가했습니다. 오류: {exc}",
            }
        reflection["score"] = int(reflection.get("score", 0))
        reflection["comment"] = str(reflection.get("comment", "평가 의견이 없습니다."))
        self._log("OBSERVATION", f"Reflection 결과: {json.dumps(reflection, ensure_ascii=False)}")
        return reflection

    def _extract_recommended_restaurants(self, restaurants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not restaurants:
            restaurants = search_restaurants(query="맛집", location="전주 객사", radius=1500)
        return restaurants[:3]

    def _build_fallback_answer(self, user_request: str, restaurants: List[Dict[str, Any]]) -> str:
        if not restaurants:
            return (
                "조건에 맞는 맛집을 찾지 못했습니다. 지역명이나 음식 종류를 조금 더 구체적으로 알려주시면 "
                "검색 반경과 키워드를 조정해 다시 추천할 수 있습니다."
            )

        lines = [f"요청하신 조건을 바탕으로 추천할 만한 맛집 3곳입니다: {user_request}"]
        for index, restaurant in enumerate(restaurants[:3], start=1):
            lines.append(
                f"{index}. {restaurant.get('name')} - {restaurant.get('category')} / "
                f"평점 {restaurant.get('rating')} / 리뷰 {restaurant.get('review_count')}개 / "
                f"{restaurant.get('distance')}m / 가격대 {restaurant.get('price_level', '중간')}"
            )
        lines.append("너무 비싸지 않고 리뷰가 좋은 곳을 우선으로 골랐습니다.")
        return "\n".join(lines)

    def _parse_arguments(self, raw_arguments: str) -> Dict[str, Any]:
        try:
            return json.loads(raw_arguments or "{}")
        except json.JSONDecodeError:
            return {}

    def _simplify_query(self, query: str) -> str:
        for keyword in ["맛집", "한식", "일식", "양식", "카페", "디저트", "파스타", "비빔밥", "국밥"]:
            if keyword in query:
                return keyword
        return "맛집"

    def _guess_location(self, user_request: str) -> str:
        if "객사" in user_request:
            return "전주 객사"
        if "전주" in user_request:
            return "전주"
        match = re.search(r"([가-힣A-Za-z0-9]+)\s*(근처|주변|에서)", user_request)
        if match:
            return match.group(1)
        return "전주 객사"

    def _log(self, step_type: str, message: str) -> None:
        entry = {"type": f"[{step_type}]", "message": message}
        self.trace.append(entry)
        print(f"[{step_type}] {message}")
