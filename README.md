# 맛집 탐정 AI Agent

## 프로젝트 개요

이 프로젝트는 사용자의 자연어 요청을 분석해 조건에 맞는 맛집을 추천하는 Python + Streamlit 기반 AI Agent 앱입니다. 단순히 LLM에게 추천을 맡기는 방식이 아니라, Agent가 직접 도구를 선택하고 Kakao Local API 또는 샘플 데이터셋을 조회한 뒤 결과를 필터링하고 최종 추천을 생성합니다.

Streamlit 화면에서는 추천 결과뿐 아니라 Agent가 어떤 생각을 하고 어떤 도구를 호출했는지 ReAct Trace로 확인할 수 있습니다.

## 사용한 Agentic Design Pattern

### 1. ReAct Pattern

`agent.py`의 `RestaurantAgent.run()`은 Thought → Action → Observation → Final Answer 흐름으로 동작합니다.

- Thought: 사용자 요청을 분석하고 필요한 도구를 판단합니다.
- Action: OpenAI function calling의 `tools` 파라미터를 통해 `get_location_coords`, `search_restaurants`, `filter_restaurants` 중 필요한 도구를 호출합니다.
- Observation: 도구 실행 결과를 Agent에게 다시 전달합니다.
- Final Answer: 관찰 결과를 바탕으로 사용자 조건에 맞는 맛집 3곳을 추천합니다.

최대 반복 횟수는 5회이며, 각 단계는 `[THOUGHT]`, `[ACTION]`, `[OBSERVATION]`, `[FINAL ANSWER]` 형식으로 출력되고 Streamlit 사이드바의 Trace Log에 표시됩니다.

### 2. Reflection Pattern

ReAct 루프가 추천 결과를 만든 뒤, 원래 사용자 요청과 추천 결과를 다시 GPT에게 전달해 자기 평가를 수행합니다.

평가 질문은 다음 기준을 따릅니다.

> Does this recommendation satisfy the user's conditions? Rate 1-10 and explain gaps.

점수가 7점 미만이면 검색 반경을 넓히고 리뷰 수 기준으로 한 번 더 보완 검색을 수행합니다. Reflection 결과는 Streamlit 메인 화면 하단에 점수와 코멘트로 표시됩니다.

## 프로젝트 구조

```text
project/
├── app.py
├── agent.py
├── tools.py
├── kakao_api.py
├── requirements.txt
└── README.md
```

## 설치 및 실행 방법

Python 3.11 이상 환경에서 실행합니다.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## .env 설정 방법

프로젝트 루트에 `.env` 파일을 만들고 아래처럼 API 키를 입력합니다.

```env
OPENAI_API_KEY=your_key_here
KAKAO_REST_API_KEY=your_key_here
```

`.env` 파일은 API Key가 포함되므로 제출 파일이나 공개 GitHub 저장소에 포함하지 않아야 합니다.

## Kakao Local API 사용 방법

Kakao Developers에서 애플리케이션을 만든 뒤 REST API 키를 발급받아 `.env`의 `KAKAO_REST_API_KEY`에 넣습니다.

사용 API는 다음과 같습니다.

- Base URL: `https://dapi.kakao.com/v2/local`
- 키워드 검색: `/search/keyword.json`
- 주소 검색: `/search/address.json`
- 인증 헤더: `Authorization: KakaoAK {KAKAO_REST_API_KEY}`

API 호출이 실패하거나 키가 없으면 전주 지역 샘플 데이터셋 5개를 사용해 앱이 계속 동작합니다.

## 실행 테스트 시나리오

아래 문장을 입력창에 넣고 검색 버튼을 누릅니다.

```text
전주 객사 근처에서 친구랑 저녁 먹기 좋은 맛집을 찾아줘. 너무 비싸지 않고, 리뷰가 좋은 곳 위주로 3곳 추천해줘.
```

확인할 항목은 다음과 같습니다.

- 사이드바에 Agent의 `[THOUGHT]`, `[ACTION]`, `[OBSERVATION]`, `[FINAL ANSWER]` 로그가 표시되는지 확인합니다.
- 도구 이름과 입력값이 Trace Log에 표시되는지 확인합니다.
- 메인 화면에 추천 맛집 3곳의 이름, 카테고리, 평점, 주소, 거리, 가격대가 카드 형태로 표시되는지 확인합니다.
- Reflection 점수와 코멘트가 결과 아래에 표시되는지 확인합니다.

## 예외 처리

다음 상황에 대응하도록 구현했습니다.

- 검색 결과 없음: 검색어를 단순화하고 반경을 넓혀 재검색합니다.
- 존재하지 않는 지역: 전주 객사 같은 주요 장소를 대안으로 시도하거나 사용자에게 명확한 지역 입력을 요청합니다.
- API 호출 실패: 전주 지역 샘플 맛집 데이터셋으로 자동 대체합니다.
- 음식 종류가 모호함: 충분한 맥락이 없으면 Agent가 사용자에게 더 구체적인 조건을 요청하도록 시스템 프롬프트에 반영했습니다.
- 조건 부족: 최종 답변에서 지역, 음식 종류, 가격대 등 추가 조건 입력을 안내합니다.

## 제출 시 주의사항

제출할 때 `.venv`, `__pycache__`, `node_modules`, `.env` 파일은 포함하지 않습니다. 파일명은 과제 안내에 따라 `[이름]_[학번]_실습4.zip` 또는 GitHub 공개 저장소 주소가 담긴 텍스트 파일 형식으로 제출합니다.
