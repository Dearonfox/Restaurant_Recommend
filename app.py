import html
from urllib.parse import quote_plus

import streamlit as st
from dotenv import load_dotenv

from agent import RestaurantAgent
from naver_api import enrich_restaurants_with_naver


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
.restaurant-card .thumb {
    aspect-ratio: 16 / 10;
    background: #eef2f7;
    border-radius: 7px;
    margin-bottom: 16px;
    object-fit: cover;
    width: 100%;
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
.restaurant-card .menu-list {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 6px;
}
.restaurant-card .menu-chip {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 999px;
    color: #9a3412;
    display: inline-block;
    font-size: 0.86rem;
    font-weight: 800;
    padding: 4px 9px;
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


def format_price_label(price_level: str) -> str:
    labels = {
        "저렴": "가성비 좋음",
        "중간": "부담 적은 편",
        "비쌈": "특별한 날 추천",
    }
    return labels.get(price_level, "가격 정보 참고")


def run_search(user_request: str) -> None:
    if not user_request.strip():
        st.warning("찾고 싶은 지역, 음식 종류, 목적 등을 입력해 주세요.")
        return

    agent = RestaurantAgent()
    with st.spinner("조건을 분석하고 맛집을 찾는 중입니다..."):
        result = agent.run(user_request)
        result["restaurants"] = enrich_restaurants_with_naver(result.get("restaurants", []))
    st.session_state.trace_log = result["trace"]
    st.session_state.last_result = result


def submit_search() -> None:
    run_search(st.session_state.get("user_request", ""))


def render_restaurant_card(restaurant: dict) -> str:
    raw_name = str(restaurant.get("name", "이름 없음"))
    raw_address = str(restaurant.get("address", "정보 없음"))
    naver_map_url = restaurant.get("naver_map_url") or build_naver_map_url(raw_name, raw_address)
    image_url = str(restaurant.get("naver_image_url", ""))
    menus = restaurant.get("naver_menus", [])[:3]

    name = html.escape(raw_name)
    category = html.escape(str(restaurant.get("category", "정보 없음")))
    rating = html.escape(str(restaurant.get("rating", 0)))
    review_count = html.escape(str(restaurant.get("review_count", 0)))
    address = html.escape(raw_address)
    distance = html.escape(str(restaurant.get("distance", "정보 없음")))
    price_level = html.escape(format_price_label(str(restaurant.get("price_level", "중간"))))
    naver_map_url = html.escape(str(naver_map_url), quote=True)
    image_url = html.escape(image_url, quote=True)

    parts = ['<div class="restaurant-card">']
    if image_url:
        parts.append(f'<img class="thumb" src="{image_url}" alt="{name} 대표 이미지">')
    parts.extend(
        [
            f"<h3>{name}</h3>",
            '<div class="meta-row">',
            '<div class="label">분류</div>',
            f'<div class="value">{category}</div>',
            "</div>",
        ]
    )
    if menus:
        menu_chips = "".join(
            f'<span class="menu-chip">{html.escape(str(menu))}</span>'
            for menu in menus
        )
        parts.extend(
            [
                '<div class="meta-row">',
                '<div class="label">대표 메뉴 후보</div>',
                f'<div class="menu-list">{menu_chips}</div>',
                "</div>",
            ]
        )
    parts.extend(
        [
            '<div class="meta-row">',
            '<div class="label">평점 / 리뷰</div>',
            f'<div class="rating"><span>⭐</span><span>{rating} · 리뷰 {review_count}개</span></div>',
            "</div>",
            '<div class="meta-row">',
            '<div class="label">주소</div>',
            f'<div class="value">{address}</div>',
            f'<a class="map-link" href="{naver_map_url}" target="_blank" rel="noopener noreferrer">네이버 지도에서 보기</a>',
            "</div>",
            '<div class="meta-row compact-grid">',
            "<div>",
            '<div class="label">거리</div>',
            f'<div class="value">{distance}m</div>',
            "</div>",
            "<div>",
            '<div class="label">가격</div>',
            f'<div class="value"><span class="price-pill">{price_level}</span></div>',
            "</div>",
            "</div>",
            "</div>",
        ]
    )
    return "".join(parts)


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
            with column:
                st.markdown(render_restaurant_card(restaurant), unsafe_allow_html=True)
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
