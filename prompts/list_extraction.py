"""캠페인 목록 페이지에서 URL 추출 프롬프트 (HTML 분석)"""

LIST_EXTRACTION_PROMPT = """
제공된 HTML 콘텐츠를 분석하여 캠페인 목록 페이지에서 캠페인 URL들을 수집하세요.

## URL
{url}

## HTML Context
{html}

## 추출 규칙
1. HTML 내에서 각 캠페인의 상세 페이지로 이동하는 링크를 찾으세요. (href 속성뿐만 아니라 onclick, data-url, window.open 등 자바스크립트나 데이터 속성에 포함된 링크도 확인)
2. URL은 반드시 절대 경로로 변환 (https://로 시작)
   - href가 상대 경로인 경우, 위 URL을 기준으로 절대 경로로 만드세요.
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
