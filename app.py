import html
from urllib.parse import quote_plus

import streamlit as st
from dotenv import load_dotenv

from agent import RestaurantAgent


load_dotenv()

st.set_page_config(page_title="맛집 추천 AI Agent", page_icon="🍽️", layout="wide")

st.markdown(
    """
    <style>
    .restaurant-card {
        background: #ffffff;
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
        color: #172033;
        padding: 22px;
    }
    .restaurant-card h3 {
        color: #111827;
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.25;
        margin: 0 0 16px;
        min-height: 3.3rem;
    }
    .restaurant-card .meta-row {
        border-top: 1px solid #eef2f7;
        margin-top: 12px;
        padding-top: 12px;
    }
    .restaurant-card .label {
        color: #526173;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0;
        margin-bottom: 4px;
    }
    .restaurant-card .value {
        color: #172033;
        font-size: 0.96rem;
        font-weight: 650;
        line-height: 1.4;
        word-break: keep-all;
        overflow-wrap: anywhere;
    }
    .restaurant-card .rating {
        align-items: center;
        color: #172033;
        display: flex;
        font-size: 1rem;
        font-weight: 800;
        gap: 8px;
    }
    .restaurant-card .compact-grid {
        display: grid;
        gap: 12px;
        grid-template-columns: 1fr 1fr;
    }
    .restaurant-card .price-pill {
        background: #e8f3ff;
        border: 1px solid #bfdbfe;
        border-radius: 999px;
        color: #0f4c81;
        display: inline-block;
        font-weight: 800;
        padding: 3px 9px;
    }
    .restaurant-card .map-link {
        align-items: center;
        background: #03c75a;
        border-radius: 7px;
        color: #ffffff !important;
        display: inline-flex;
        font-weight: 800;
        justify-content: center;
        margin-top: 10px;
        padding: 9px 12px;
        text-decoration: none !important;
        width: 100%;
    }
    .restaurant-card .map-link:hover {
        background: #02b351;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def build_naver_map_url(name: str, address: str) -> str:
    query = quote_plus(f"{name} {address}".strip())
    return f"https://map.naver.com/p/search/{query}"


def run_search(user_request: str) -> None:
    if not user_request.strip():
        st.warning("찾고 싶은 지역, 음식 종류, 목적 등을 입력해 주세요.")
        return

    agent = RestaurantAgent()
    with st.spinner("조건을 분석하고 맛집을 찾는 중입니다..."):
        result = agent.run(user_request)
    st.session_state.trace_log = result["trace"]
    st.session_state.last_result = result
    st.rerun()


def submit_search() -> None:
    run_search(st.session_state.get("user_request", ""))


st.title("🍽️ 맛집 추천 AI Agent")

if "trace_log" not in st.session_state:
    st.session_state.trace_log = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "user_request" not in st.session_state:
    st.session_state.user_request = ""

with st.sidebar:
    st.header("Agent Trace")
    if st.session_state.trace_log:
        for index, step in enumerate(st.session_state.trace_log, start=1):
            label = f"{index}. {step.get('type', 'STEP')}"
            with st.expander(label, expanded=index == len(st.session_state.trace_log)):
                st.write(step.get("message", ""))
    else:
        st.info("검색을 실행하면 ReAct 단계별 로그가 표시됩니다.")

st.text_input(
    "어떤 맛집을 찾으시나요?",
    key="user_request",
    placeholder="예: 전주 객사 근처에서 친구랑 저녁 먹기 좋은 맛집 3곳 추천해줘",
    on_change=submit_search,
)

if st.button("검색", type="primary", use_container_width=True):
    submit_search()

result = st.session_state.last_result

if result:
    st.subheader("추천 맛집 TOP 3")
    restaurants = result.get("restaurants", [])[:3]

    if restaurants:
        columns = st.columns(len(restaurants))
        for column, restaurant in zip(columns, restaurants):
            raw_name = str(restaurant.get("name", "이름 없음"))
            raw_address = str(restaurant.get("address", "정보 없음"))
            naver_map_url = restaurant.get("naver_map_url") or build_naver_map_url(raw_name, raw_address)

            name = html.escape(raw_name)
            category = html.escape(str(restaurant.get("category", "정보 없음")))
            rating = html.escape(str(restaurant.get("rating", 0)))
            review_count = html.escape(str(restaurant.get("review_count", 0)))
            address = html.escape(raw_address)
            distance = html.escape(str(restaurant.get("distance", "정보 없음")))
            price_level = html.escape(str(restaurant.get("price_level", "중간")))
            naver_map_url = html.escape(str(naver_map_url), quote=True)

            with column:
                st.markdown(
                    f"""
                    <div class="restaurant-card">
                        <h3>{name}</h3>
                        <div class="meta-row">
                            <div class="label">분류</div>
                            <div class="value">{category}</div>
                        </div>
                        <div class="meta-row">
                            <div class="label">평점 / 리뷰</div>
                            <div class="rating"><span>⭐</span><span>{rating} · 리뷰 {review_count}개</span></div>
                        </div>
                        <div class="meta-row">
                            <div class="label">주소</div>
                            <div class="value">{address}</div>
                            <a class="map-link" href="{naver_map_url}" target="_blank" rel="noopener noreferrer">네이버 지도에서 보기</a>
                        </div>
                        <div class="meta-row compact-grid">
                            <div>
                                <div class="label">거리</div>
                                <div class="value">{distance}m</div>
                            </div>
                            <div>
                                <div class="label">가격대</div>
                                <div class="value"><span class="price-pill">{price_level}</span></div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.warning("추천 결과가 없습니다. 요청 조건을 조금 더 구체적으로 입력해 주세요.")

    st.subheader("최종 답변")
    st.write(result.get("final_answer", "최종 답변을 생성하지 못했습니다."))

    reflection = result.get("reflection", {})
    if reflection:
        st.subheader("Reflection 결과")
        score = reflection.get("score", 0)
        st.metric("만족도 점수", f"{score}/10")
        st.write(reflection.get("comment", "검토 의견이 없습니다."))

else:
    st.info("원하는 맛집 조건을 입력하고 엔터 또는 검색 버튼을 눌러 주세요.")
