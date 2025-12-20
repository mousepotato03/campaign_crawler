"""캠페인 상세 페이지 추출 프롬프트 - 상세 정보 추출 전용"""

UNIFIED_EXTRACTION_PROMPT = """
제공된 HTML 콘텐츠를 분석하여 환경 캠페인 상세 정보를 수집하세요.

## URL
{url}

## HTML Context
{html}

## 작업 순서
1. HTML 내용을 바탕으로 환경/에코/친환경/탄소중립/제로웨이스트 관련 캠페인인지 판단
2. 캠페인 상세 정보 추출

## 추출할 캠페인 정보
- title: 캠페인 제목 (필수)
- description: 간단 소개 (필수,200자 이내)
- host_organizer: 주최 기관명 (필수)
- image_url: 썸네일 이미지 URL (절대 경로, jpg, png, svg 형식)
- start_date: 캠페인 시작일 (YYYY-MM-DD 형식)
- end_date: 캠페인 종료일 (YYYY-MM-DD 형식)
- region: 지역 (주최 지역, 없다면 "전국"으로 기입)
- category: 카테고리 (재활용/대중교통/에너지절약/제로웨이스트/자연보호/교육/기타 중 선택)
- campaign_type: ONLINE 또는 OFFLINE

## 추출할 미션 정보
이 캠페인을 '완료'하거나 '수료'하기 위해 사용자가 수행해야 하는 **구체적인 행동(Action)**을 순서대로 추출하세요.
단순한 정보 확인이 아닌, 사용자가 직접 실행해야 하는 '참여 방법', '활동 내용', '미션', '인증 방법' 섹션의 내용을 중점적으로 분석하세요.

**추출 대상 예시:**
- "모임 등록하기", "신청서 작성"
- "가이드북 읽고 단체 논의 시작하기"
- "실천 방법 정하기"
- "인증서 발급 신청", "결과 보고"
- "SNS에 필수 해시태그와 함께 업로드"

**추출 제외 대상:**
- 개인정보 수집 동의
- 단순한 캠페인 소개 문구
- "많은 참여 부탁드립니다" 같은 인사말

**각 미션 항목:**
- title: 미션 제목 (웹페이지에 적힌 텍스트 **그대로** 추출, 절대 요약하거나 말을 바꾸지 말 것)
- description: 미션 설명 (웹페이지에 적힌 상세 내용을 **그대로** 복사, 500자 이내)
- verification_type: 미션 수행을 확인/인증하는 방식
  - "IMAGE": 사진/이미지/스크린샷/인증샷 업로드가 필요한 경우
  - "TEXT_REVIEW": 텍스트 작성/소감문/댓글/설문조사/링크제출이 필요한 경우
  - "QUIZ": 퀴즈/문제풀이가 필요한 경우
- order: 수행 순서 (1부터 시작)

## 출력 형식 (반드시 JSON만 출력)
```json
{{
    "page_type": "detail",
    "is_environmental_campaign": true 또는 false,
    "campaigns": [
        {{
            "title": "캠페인 제목",
            "campaign_url": "{url}",
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
2. 해당 캠페인의 모든 정보를 campaigns[0]에 담기
3. URL은 반드시 절대 경로로 변환 (https://로 시작)
4. 날짜는 반드시 시작일과 종료일을 기입해야함. YYYY-MM-DD 형식
5. 정보가 없는 필드는 null로 설정
6. JSON 외의 다른 텍스트 출력 금지
7. 미션이 명시되어 있지 않으면 missions는 빈 배열 []로 설정
8. verification_type 판단: 사진/이미지→IMAGE, 텍스트/소감→TEXT_REVIEW, 퀴즈→QUIZ
"""
