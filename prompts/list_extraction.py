"""캠페인 목록 페이지에서 URL 추출 프롬프트 (Playwright MCP 사용)"""

LIST_EXTRACTION_PROMPT = """
@playwright MCP를 사용하여 캠페인 목록 페이지에서 캠페인 URL들을 수집하세요.

## URL
{url}

## 작업 순서
1. browser_navigate로 페이지 접속
2. browser_snapshot으로 페이지 구조 파악
3. 캠페인 목록에서 각 캠페인의 상세 페이지 링크 추출
4. 모든 작업 완료 후 반드시 browser_close 도구를 호출하여 브라우저 종료

## 추출 규칙
1. 캠페인 목록에서 각 캠페인의 상세 페이지 링크를 찾으세요
2. URL은 반드시 절대 경로로 변환 (https://로 시작)
3. top-down 순서대로 (위에서 아래로) 정렬하세요
4. 중복 URL은 제거하세요
5. 환경/에코/친환경/탄소중립/제로웨이스트/재활용 관련 캠페인 링크만 추출하세요

## 출력 형식 (JSON만 출력)
```json
{{
    "campaign_urls": [
        "https://example.com/campaign/1",
        "https://example.com/campaign/2"
    ]
}}
```

## 중요
- JSON 외의 다른 텍스트 출력 금지
- 중복이나 관련 없는 URL은 제외하세요
"""
