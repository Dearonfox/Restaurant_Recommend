# Restaurant Recommend Agent

자연어로 입력한 조건을 바탕으로 맛집을 검색하고, 리뷰 수·평점·거리·가격대를 고려해 3곳을 추천하는 Streamlit 기반 AI Agent입니다.

단순히 LLM에게 “맛집 추천해줘”라고 묻는 구조가 아니라, Agent가 직접 검색 도구를 호출하고 결과를 관찰한 뒤 최종 답변을 만듭니다. 실행 과정은 ReAct 형식의 Trace로 남기기 때문에 어떤 도구가 어떤 입력값으로 호출됐는지 확인할 수 있습니다.

## Features

- 지역 기반 맛집 검색
- 음식 종류 기반 검색
- 평점, 리뷰 수, 거리, 가격대 기준 필터링
- Kakao Local API 연동
- API 실패 시 샘플 데이터셋 fallback
- ReAct Trace 시각화
- 추천 결과에 대한 Reflection 평가
- 과제 테스트 시나리오 실행 로그 생성

## Tech Stack

- Python 3.11+
- Streamlit
- OpenAI API
- Kakao Local API
- python-dotenv
- requests

## Project Structure

```text
restaurant_recommend/
├── app.py
├── agent.py
├── tools.py
├── kakao_api.py
├── run_assignment_scenario.py
├── assignment_trace.md
├── requirements.txt
└── README.md
```

주요 파일 역할:

- `app.py`: Streamlit 화면 구성
- `agent.py`: ReAct Agent 실행 루프와 Reflection 로직
- `tools.py`: 위치 조회, 맛집 검색, 후보 필터링 도구
- `kakao_api.py`: Kakao Local API 요청 처리
- `run_assignment_scenario.py`: 테스트 프롬프트 실행 및 Trace 파일 생성
- `assignment_trace.md`: 실행 로그 예시

## Getting Started

### 1. 가상환경 생성

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. 패키지 설치

```powershell
pip install -r requirements.txt
```

### 3. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 만들고 API 키를 입력합니다.

```env
OPENAI_API_KEY=your_openai_api_key
KAKAO_REST_API_KEY=your_kakao_rest_api_key
```

`.env`는 `.gitignore`에 포함되어 있어 저장소에 업로드하지 않습니다.

### 4. 앱 실행

```powershell
streamlit run app.py
```

## Kakao Local API 설정

Kakao Local API를 사용하려면 REST API 키가 필요합니다.

1. [Kakao Developers](https://developers.kakao.com/)에 로그인합니다.
2. 내 애플리케이션에서 앱을 생성합니다.
3. 앱 키 메뉴에서 `REST API 키`를 복사합니다.
4. 제품 설정에서 카카오맵/로컬 API 사용을 활성화합니다.
5. `.env`에 `KAKAO_REST_API_KEY`로 등록합니다.

사용하는 API:

- 주소 검색: `/v2/local/search/address.json`
- 키워드 검색: `/v2/local/search/keyword.json`

요청 헤더는 다음 형식을 사용합니다.

```text
Authorization: KakaoAK {KAKAO_REST_API_KEY}
```

## Agent Design

### ReAct

Agent는 다음 흐름으로 동작합니다.

```text
Thought -> Action -> Observation -> Final Answer
```

예를 들어 사용자가 “전주 객사 근처에서 친구랑 저녁 먹기 좋은 맛집”을 요청하면 Agent는 먼저 조건을 분석하고, 필요한 도구를 선택해 호출합니다. 도구 결과는 Observation으로 다시 Agent에게 전달되며, 이 관찰 결과를 바탕으로 최종 추천 문장을 만듭니다.

Trace에는 다음 정보가 남습니다.

- Agent의 판단 과정
- 호출한 도구 이름
- 도구 입력값
- 도구 실행 결과
- 최종 답변

### Tool Use

Agent가 사용하는 도구는 `tools.py`에 정의되어 있습니다.

- `get_location_coords(location_name)`: 지역명 또는 장소명을 좌표 정보로 변환
- `search_restaurants(query, location, radius)`: 지역과 키워드 기반으로 맛집 후보 검색
- `filter_restaurants(restaurants, min_rating, max_price_level, sort_by)`: 조건에 맞는 후보 필터링

### Reflection

추천이 끝난 뒤 `_reflect()` 단계에서 결과가 사용자 조건에 맞는지 평가합니다. 평가 결과는 점수와 코멘트로 반환되며, 앱 화면과 Trace 로그에서 확인할 수 있습니다.

### Plan-and-Solve Fallback

OpenAI API 호출이 실패하거나 네트워크가 막혀 있는 환경에서는 규칙 기반 fallback 루프가 실행됩니다. 이때도 단순히 샘플 결과를 바로 반환하지 않고 다음 단계로 문제를 나눠 처리합니다.

```text
지역 추출 -> 조건 분석 -> 검색 도구 호출 -> 필터링 -> Reflection
```

## Error Handling

다음 상황을 처리합니다.

- 지역을 찾을 수 없는 경우: 더 구체적인 지역명이나 랜드마크 입력 요청
- 검색 결과가 없는 경우: 검색어를 단순화하고 반경 확대
- 음식 종류가 모호한 경우: 식사 목적이 있으면 넓은 키워드인 `맛집`으로 검색
- Kakao API 호출 실패: 오류를 Trace에 남기고 샘플 데이터셋 사용
- OpenAI API 호출 실패: 규칙 기반 ReAct 루프로 대체 실행
- 입력 조건이 부족한 경우: 필요한 조건을 사용자에게 다시 요청

## Trace Scenario

아래 명령을 실행하면 테스트 프롬프트로 Agent를 실행하고 `assignment_trace.md`를 생성합니다.

```powershell
.\.venv\Scripts\python.exe run_assignment_scenario.py
```

사용한 테스트 프롬프트:

```text
전주 객사 근처에서 친구랑 저녁 먹기 좋은 맛집을 찾아줘. 너무 비싸지 않고, 리뷰가 좋은 곳 위주로 3곳 추천해줘.
```

생성되는 `assignment_trace.md`에는 ReAct 단계별 로그, 도구 호출 입력값, Observation, 최종 추천 결과, Reflection 결과가 포함됩니다.

## Sample Output

추천 결과는 다음과 같은 형태로 생성됩니다.

```text
1. PNB풍년제과 - 카페/베이커리 / 평점 4.6 / 리뷰 2100개 / 120m / 가격대 저렴
2. 하숙영가족회관 - 한식 / 평점 4.5 / 리뷰 1240개 / 150m / 가격대 중간
3. 고궁 - 한식/비빔밥 / 평점 4.3 / 리뷰 980개 / 300m / 가격대 중간
```

## Notes

- API 키가 들어 있는 `.env`는 커밋하지 않습니다.
- 외부 API 사용이 불가능한 환경에서도 테스트할 수 있도록 전주 객사 기준 샘플 데이터셋을 포함했습니다.
- Streamlit 사이드바에서 Agent Trace를 직접 확인할 수 있습니다.
