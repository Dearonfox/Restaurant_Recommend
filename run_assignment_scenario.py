import json
from pathlib import Path

from agent import RestaurantAgent


SCENARIO_PROMPT = "전주 객사 근처에서 친구랑 저녁 먹기 좋은 맛집을 찾아줘. 너무 비싸지 않고, 리뷰가 좋은 곳 위주로 3곳 추천해줘."
OUTPUT_PATH = Path("assignment_trace.md")


def main() -> None:
    agent = RestaurantAgent()
    result = agent.run(SCENARIO_PROMPT)

    lines = [
        "# 맛집 추천 Agent 실행 Trace",
        "",
        "## 실행 프롬프트",
        "",
        SCENARIO_PROMPT,
        "",
        "## 단계별 Trace",
        "",
    ]

    for index, step in enumerate(result["trace"], start=1):
        lines.append(f"### {index}. {step['type']}")
        lines.append("")
        lines.append("```text")
        lines.append(step["message"])
        lines.append("```")
        lines.append("")

    lines.extend(
        [
            "## 최종 추천 결과",
            "",
            result["final_answer"],
            "",
            "## Reflection 결과",
            "",
            "```json",
            json.dumps(result["reflection"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Trace saved to {OUTPUT_PATH}")
    print(result["final_answer"])


if __name__ == "__main__":
    main()
