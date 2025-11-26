"""통합 캠페인 추출 프롬프트 - LLM이 페이지를 직접 분석하고 판단"""

UNIFIED_EXTRACTION_PROMPT = """
@playwright MCP를 사용하여 환경 캠페인 정보를 수집하세요.

## URL
{url}

## 작업 순서
1. browser_navigate로 페이지 접속
2. browser_snapshot으로 페이지 구조 파악
3. 페이지 타입 판단:
   - 캠페인 목록 페이지인가? (여러 캠페인이 나열된 페이지)
   - 캠페인 상세 페이지인가? (단일 캠페인의 상세 정보)
   - 환경/에코/친환경/탄소중립/제로웨이스트 관련 캠페인인가?

4. 타입에 따라 정보 추출:
   - 목록 페이지: 각 캠페인의 상세 페이지 URL 수집
   - 상세 페이지: 캠페인 상세 정보 추출

## 추출할 캠페인 정보 (상세 페이지인 경우)
- title: 캠페인 제목 (필수)
- description: 상세 설명 (500자 이내, HTML 태그 제거)
- host_organizer: 주최/주관 기관명
- image_url: 섬네일 이미지 URL (절대 경로, jpg, png, svg 형식)
- start_date: 캠페인 시작일 (YYYY-MM-DD 형식)
- end_date: 캠페인 종료일 (YYYY-MM-DD 형식)
- region: 지역 (주최 지역, 없다면 "전체"로 기입)
- category: 카테고리 (재활용/대중교통/에너지절약/제로웨이스트/자연보호/교육/기타 중 선택)
- campaign_type: ONLINE 또는 OFFLINE

## 추출할 미션 정보 (상세 페이지인 경우)
캠페인 참여를 위해 요구하는 활동/미션이 있다면 추출하세요:
- title: 미션 제목 (예: "기후위기 문장 완성하기", "인증 사진 업로드")
- description: 미션 설명 (구체적인 안내 내용, 500자 이내)
- verification_type: 미션 제출 방식 판단
  - "IMAGE": 사진/이미지/인증샷 업로드를 요구하는 경우
  - "TEXT_REVIEW": 텍스트/소감문/문장완성/글 작성을 요구하는 경우
  - "QUIZ": 퀴즈/문제풀이/OX 문제를 요구하는 경우
- order: 미션 순서 (1부터 시작)

## 출력 형식 (반드시 JSON만 출력)
```json
{{
    "page_type": "list" 또는 "detail",
    "is_environmental_campaign": true 또는 false,
    "campaigns": [
        {{
            "title": "캠페인 제목",
            "campaign_url": "상세 페이지 절대 URL",
            "description": "캠페인 설명...",
            "host_organizer": "주최 기관",
            "image_url": "https://example.com/image.jpg",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "region": "서울",
            "category": "제로웨이스트",
            "campaign_type": "ONLINE",
            "missions": [
                {{
                    "title": "미션 제목",
                    "description": "미션 설명",
                    "verification_type": "IMAGE 또는 TEXT_REVIEW 또는 QUIZ",
                    "order": 1
                }}
            ]
        }}
    ]
}}
```

## 중요 규칙
1. 환경 캠페인이 아니면 is_environmental_campaign: false로 설정하고 campaigns는 빈 배열
2. 목록 페이지면 각 캠페인의 title과 campaign_url만 수집 (missions 불필요)
3. 상세 페이지면 해당 캠페인의 모든 정보를 campaigns[0]에 담기
4. URL은 반드시 절대 경로로 변환 (https://로 시작)
5. 날짜는 반드시 YYYY-MM-DD 형식
6. 정보가 없는 필드는 null로 설정
7. JSON 외의 다른 텍스트 출력 금지
8. 미션이 명시되어 있지 않으면 missions는 빈 배열 []로 설정
9. verification_type 판단: 사진/이미지→IMAGE, 텍스트/소감→TEXT_REVIEW, 퀴즈→QUIZ
"""
