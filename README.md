# 맛집 추천 AI Agent

사용자의 자연어 요청을 분석해 지역, 음식 종류, 가격대, 리뷰 수, 거리 조건을 고려하고 맛집 3곳을 추천하는 Python + Streamlit 기반 ReAct Agent 프로젝트입니다.

Agent는 Kakao Local API를 우선 사용해 실제 장소를 검색하고, 외부 API 호출이 실패하거나 과제 실행 환경에서 네트워크 사용이 어려운 경우 전주 객사 샘플 데이터셋으로 대체합니다. 실행 과정은 `Thought -> Action -> Observation -> Final Answer` Trace로 확인할 수 있습니다.

## 제출 항목 체크

- 소스 코드: `app.py`, `agent.py`, `tools.py`, `kakao_api.py`, `run_assignment_scenario.py`
- 실행 환경 정리 파일: `requirements.txt`
- README: `README.md`
- 실행 로그: `assignment_trace.md`
- Agentic Design Pattern 설명: 이 README의 "사용한 Agentic Design Pattern" 섹션
- ReAct Agent 도구 호출 Trace: `assignment_trace.md` 또는 Streamlit 사이드바 `Agent Trace`
- 외부 API 사용 방법: 이 README의 "Kakao Local API 사용 방법" 섹션

## 프로젝트 구조

```text
restaurant_recommend/
├── app.py                    # Streamlit UI
├── agent.py                  # ReAct Agent 실행 루프
├── tools.py                  # 맛집 검색/좌표 조회/필터링 도구
├── kakao_api.py              # Kakao Local API 클라이언트
├── run_assignment_scenario.py# 과제 지정 프롬프트 실행 및 Trace 저장
├── assignment_trace.md       # 과제 실행 로그
├── requirements.txt          # 실행 환경 패키지
├── README.md
└── .gitignore
```

## 설치 및 실행 방법

Python 3.11 이상 환경을 권장합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## 환경 변수 설정

프로젝트 루트에 `.env` 파일을 만들고 다음 값을 입력합니다.

```env
OPENAI_API_KEY=your_openai_api_key
KAKAO_REST_API_KEY=your_kakao_rest_api_key
```

`.env` 파일은 `.gitignore`에 포함되어 있으므로 GitHub에 업로드하지 않습니다.

## Kakao Local API 사용 방법

이 프로젝트는 Kakao Local API를 사용합니다.

1. [Kakao Developers](https://developers.kakao.com/) 접속
2. 내 애플리케이션 생성
3. 생성한 앱의 "앱 키" 메뉴에서 REST API 키 복사
4. 제품 설정에서 카카오맵/로컬 API 사용 설정 활성화
5. `.env` 파일에 `KAKAO_REST_API_KEY` 값으로 입력

사용 API:

- 주소 검색: `https://dapi.kakao.com/v2/local/search/address.json`
- 키워드 검색: `https://dapi.kakao.com/v2/local/search/keyword.json`
- 인증 헤더: `Authorization: KakaoAK {KAKAO_REST_API_KEY}`

외부 API가 실패하면 Agent는 해당 오류를 Observation으로 기록하고, 전주 객사 샘플 데이터셋으로 대체하여 과제 테스트 시나리오가 계속 실행되도록 처리합니다.

## 사용한 Agentic Design Pattern

### 1. ReAct Pattern

필수 조건인 ReAct 패턴을 `agent.py`의 `RestaurantAgent.run()`과 `_run_rule_based()`에 구현했습니다.

실행 흐름:

```text
Thought -> Action -> Observation -> Final Answer
```

- Thought: 사용자 요청에서 지역, 음식 종류, 가격대, 리뷰 조건을 분석합니다.
- Action: 필요한 도구를 선택해 호출합니다.
- Observation: 도구 실행 결과 또는 오류를 Agent가 다시 관찰합니다.
- Final Answer: 관찰 결과를 바탕으로 최종 맛집 3곳을 추천합니다.

Trace 예시는 `assignment_trace.md`에서 확인할 수 있습니다.

### 2. Tool Use Pattern

Agent가 직접 도구를 선택하고 호출합니다.

- `get_location_coords`: 지역명 또는 장소명을 좌표로 변환
- `search_restaurants`: Kakao Local API 또는 샘플 데이터셋에서 맛집 후보 검색
- `filter_restaurants`: 평점, 리뷰 수, 거리, 가격대 기준으로 후보 필터링

도구 이름과 입력값은 Trace의 `[ACTION]` 단계에 기록됩니다.

### 3. Reflection Pattern

추천 후 `agent.py`의 `_reflect()`에서 결과가 사용자 조건에 맞는지 평가합니다.

평가 기준:

- 요청한 지역과 맞는가
- 가격대가 너무 비싸지 않은가
- 리뷰 수와 평점이 충분한가
- 최종 추천이 3곳으로 정리되었는가

Reflection 결과는 점수와 코멘트로 출력되며, Streamlit 화면과 `assignment_trace.md`에서 확인할 수 있습니다.

### 4. Plan-and-Solve Pattern

규칙 기반 대체 흐름에서는 다음 단계로 문제를 분해합니다.

1. 지역 추출
2. 음식/목적 조건 파악
3. 맛집 검색 도구 호출
4. 평점/리뷰/거리/가격대 기준 필터링
5. Reflection으로 조건 충족 여부 검토

이 계획은 Trace의 `[THOUGHT]` 단계에 기록됩니다.

## 예외 처리

다음 상황을 단순 오류 출력이 아니라 Agent의 Observation으로 기록하고 대안을 제시하도록 구현했습니다.

- 존재하지 않는 지역: 더 구체적인 지역명, 역명, 랜드마크 입력 요청
- 검색 결과 없음: 검색어 단순화 및 검색 반경 확대
- 음식 종류가 모호함: 식사 목적이 있으면 넓은 키워드인 `맛집`으로 검색
- API 호출 실패: 오류를 Observation에 기록하고 샘플 데이터셋 사용
- 사용자 조건 부족: 지역 또는 음식 종류/목적 입력 요청
- OpenAI API 호출 실패: 규칙 기반 ReAct 루프로 대체 실행

## 실행 테스트 시나리오

과제 지정 프롬프트:

```text
전주 객사 근처에서 친구랑 저녁 먹기 좋은 맛집을 찾아줘. 너무 비싸지 않고, 리뷰가 좋은 곳 위주로 3곳 추천해줘.
```

Trace 파일 생성:

```powershell
.\.venv\Scripts\python.exe run_assignment_scenario.py
```

실행하면 `assignment_trace.md`가 생성됩니다. 이 파일에는 다음 내용이 포함됩니다.

- Agent의 판단 과정
- 호출한 도구 이름
- 도구 입력값
- 도구 실행 결과
- 최종 추천 결과
- Reflection 결과

## Streamlit 화면에서 확인하는 방법

```powershell
streamlit run app.py
```

브라우저에서 프롬프트를 입력하고 검색하면 다음을 확인할 수 있습니다.

- 메인 화면: 추천 맛집 TOP 3 카드
- 하단: 최종 답변 및 Reflection 결과
- 사이드바: ReAct Agent Trace

## 제출 시 포함하면 좋은 파일

GitHub 저장소 제출 시 다음 파일이 포함되어 있으면 요구 항목을 모두 확인할 수 있습니다.

```text
app.py
agent.py
tools.py
kakao_api.py
run_assignment_scenario.py
requirements.txt
README.md
assignment_trace.md
```

API 키가 들어 있는 `.env`는 제출하지 않습니다.
