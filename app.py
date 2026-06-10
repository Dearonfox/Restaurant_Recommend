import html

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
        min-height: 320px;
        padding: 22px;
    }
    .restaurant-card h3 {
        color: #111827;
        font-size: 1.45rem;
        font-weight: 800;
        line-height: 1.25;
        margin: 0 0 18px;
    }
    .restaurant-card .meta-row {
        border-top: 1px solid #eef2f7;
        margin-top: 14px;
        padding-top: 14px;
    }
    .restaurant-card .label {
        color: #526173;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0;
        margin-bottom: 4px;
    }
    .restaurant-card .value {
        color: #172033;
        font-size: 1rem;
        font-weight: 600;
        line-height: 1.45;
        word-break: keep-all;
        overflow-wrap: anywhere;
    }
    .restaurant-card .rating {
        align-items: center;
        color: #172033;
        display: flex;
        font-size: 1.05rem;
        font-weight: 800;
        gap: 8px;
    }
    .restaurant-card .price-pill {
        background: #e8f3ff;
        border: 1px solid #bfdbfe;
        border-radius: 999px;
        color: #0f4c81;
        display: inline-block;
        font-weight: 800;
        padding: 4px 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🍽️ 맛집 추천 AI Agent")

if "trace_log" not in st.session_state:
    st.session_state.trace_log = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None

with st.sidebar:
    st.header("Agent Trace")
    if st.session_state.trace_log:
        for index, step in enumerate(st.session_state.trace_log, start=1):
            label = f"{index}. {step.get('type', 'STEP')}"
            with st.expander(label, expanded=index == len(st.session_state.trace_log)):
                st.write(step.get("message", ""))
    else:
        st.info("검색을 실행하면 ReAct 단계별 로그가 표시됩니다.")

user_request = st.text_input(
    "어떤 맛집을 찾으시나요?",
    placeholder="예: 전주 객사 근처에서 친구와 먹기 좋은 맛집 3곳 추천해줘",
)

search_clicked = st.button("검색", type="primary", use_container_width=True)

if search_clicked:
    if not user_request.strip():
        st.warning("찾고 싶은 지역, 음식 종류, 목적 등을 입력해 주세요.")
    else:
        agent = RestaurantAgent()
        with st.spinner("조건을 분석하고 맛집을 찾는 중입니다..."):
            result = agent.run(user_request)
        st.session_state.trace_log = result["trace"]
        st.session_state.last_result = result
        st.rerun()

result = st.session_state.last_result

if result:
    st.subheader("추천 맛집 TOP 3")
    restaurants = result.get("restaurants", [])[:3]

    if restaurants:
        columns = st.columns(len(restaurants))
        for column, restaurant in zip(columns, restaurants):
            name = html.escape(str(restaurant.get("name", "이름 없음")))
            category = html.escape(str(restaurant.get("category", "정보 없음")))
            rating = html.escape(str(restaurant.get("rating", 0)))
            review_count = html.escape(str(restaurant.get("review_count", 0)))
            address = html.escape(str(restaurant.get("address", "정보 없음")))
            distance = html.escape(str(restaurant.get("distance", "정보 없음")))
            price_level = html.escape(str(restaurant.get("price_level", "중간")))

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
                        </div>
                        <div class="meta-row">
                            <div class="label">거리</div>
                            <div class="value">{distance}m</div>
                        </div>
                        <div class="meta-row">
                            <div class="label">가격대</div>
                            <div class="value"><span class="price-pill">{price_level}</span></div>
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
    st.info("원하는 맛집 조건을 입력하고 검색 버튼을 눌러 주세요.")
