#!/usr/bin/env python3
"""
환경 캠페인 크롤러 v4.0 (Native Python + Async)

- Playwright (Async) + Google GenAI 라이브러리 직접 사용
- 병렬 처리 지원
- 브라우저 충돌 해결
"""

import os
import sys
import asyncio
import yaml
import time
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.supabase_client import SupabaseService
from services.browser_service import BrowserService
from services.llm_service import LLMService
from models.campaign import CampaignData, MissionTemplateData


def load_env():
    """환경변수 로드"""
    env_path = PROJECT_ROOT / "config" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print("[WARN] config/.env 파일이 없습니다.")
        sys.exit(1)


def load_config() -> dict:
    """설정 파일 로드"""
    config_path = PROJECT_ROOT / "config" / "sites.yaml"
    if not config_path.exists():
        print(f"[ERROR] 설정 파일이 없습니다: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_default_missions(supabase: SupabaseService, campaign_id: int, campaign_title: str):
    """캠페인에 기본 미션 템플릿 생성"""
    default_mission = MissionTemplateData(
        campaign_id=campaign_id,
        title=f"{campaign_title} 참여 인증",
        description="캠페인 참여 후 인증샷을 업로드하세요.",
        order=1,
        verification_type="IMAGE",
        reward_points=0
    )
    supabase.insert_mission_template(default_mission)


def save_campaign_sync(result: dict, supabase: SupabaseService, existing_urls: set) -> int:
    """캠페인 저장 (동기 함수)"""
    saved_count = 0
    campaigns = result.get("campaigns", [])

    for camp in campaigns:
        campaign_url = camp.get("campaign_url")
        if not campaign_url or campaign_url in existing_urls:
            continue

        # CampaignData 생성
        campaign = CampaignData(
            title=camp.get("title") or "Unknown",
            campaign_url=campaign_url,
            host_organizer=camp.get("host_organizer"),
            description=camp.get("description"),
            image_url=camp.get("image_url"),
            start_date=camp.get("start_date"),
            end_date=camp.get("end_date"),
            region=camp.get("region"),
            category=camp.get("category"),
            campaign_type=camp.get("campaign_type") or "ONLINE"
        )

        # DB 저장
        campaign_id = supabase.insert_campaign(campaign)
        if campaign_id:
            existing_urls.add(campaign_url)
            saved_count += 1
            print(f"    [OK] 저장 완료: {campaign.title[:40]}")

            # 미션 템플릿 생성
            missions = camp.get("missions", [])
            if missions:
                for idx, mission in enumerate(missions, 1):
                    mission_data = MissionTemplateData(
                        campaign_id=campaign_id,
                        title=mission.get("title", f"{campaign.title} 미션 {idx}"),
                        description=mission.get("description"),
                        order=mission.get("order", idx),
                        verification_type=mission.get("verification_type", "TEXT_REVIEW"),
                        reward_points=10
                    )
                    supabase.insert_mission_template(mission_data)
            else:
                create_default_missions(supabase, campaign_id, campaign.title)
        else:
            print(f"    [FAIL] DB 저장 실패: {campaign.title[:40]}")

    return saved_count


async def process_detail_page(url: str, browser: BrowserService, llm: LLMService, supabase: SupabaseService, existing_urls: set):
    """상세 페이지 처리 (병렬 실행 단위)"""
    print(f"  [START] 상세 분석: {url}")
    
    # 1. HTML 추출
    html_content = await browser.get_page_content(url)
    if not html_content:
        print(f"  [FAIL] HTML 추출 실패: {url}")
        return 0

    # 2. LLM 분석
    result = await llm.extract_campaign_detail(html_content, url)
    if not result:
        print(f"  [FAIL] LLM 분석 실패: {url}")
        return 0

    if not result.get("is_environmental_campaign"):
        print(f"  [SKIP] 환경 캠페인 아님: {url}")
        return 0

    # 3. DB 저장 (동기 함수 호출)
    # Supabase 클라이언트는 Thread-safe하지 않을 수 있으므로 주의 필요하지만,
    # 간단한 insert 작업은 보통 문제 없음. 필요시 Lock 사용.
    return save_campaign_sync(result, supabase, existing_urls)


def ensure_https(url: str) -> str:
    """URL을 HTTPS로 강제 변환"""
    if not url:
        return url
    if url.startswith("http://"):
        return url.replace("http://", "https://", 1)
    if not url.startswith("http"):
        return "https://" + url
    return url


async def main():
    print("\n" + "=" * 60)
    print("       환경 캠페인 크롤러 v4.0 (Async)")
    print("       Native Playwright + Google GenAI")
    print("=" * 60)

    load_env()
    config = load_config()
    # 설정 파일에서 URL 로드 시 HTTPS 강제 적용
    urls = [ensure_https(u) for u in config.get("urls", [])]
    
    if not urls:
        print("[WARN] 크롤링할 URL이 없습니다.")
        return

    # 서비스 초기화
    try:
        supabase = SupabaseService()
        browser = BrowserService(headless=True) # 디버깅 시 False로 변경
        llm = LLMService()
    except Exception as e:
        print(f"[ERROR] 서비스 초기화 실패: {e}")
        return

    existing_urls = supabase.get_existing_urls()
    print(f"기존 캠페인 수: {len(existing_urls)}개")

    await browser.launch()
    
    total_new = 0
    
    try:
        # 1. 목록 페이지에서 URL 수집
        all_campaign_urls = set()
        
        print(f"\n[1단계] 목록 페이지 수집 ({len(urls)}개)")
        for list_url in urls:
            print(f"  접속 중: {list_url}")
            html = await browser.get_page_content(list_url)
            if html:
                print(f"  [DEBUG] HTML Length: {len(html)}")
                extracted = await llm.extract_campaign_urls(html, list_url)
                # 추출된 URL도 HTTPS 강제 적용
                extracted = [ensure_https(u) for u in extracted]
                print(f"  -> 발견된 URL: {len(extracted)}개")
                all_campaign_urls.update(extracted)
            else:
                print(f"  -> 접속 실패")

        # 중복 제거 및 필터링
        new_urls = [u for u in all_campaign_urls if u not in existing_urls]
        print(f"\n[2단계] 상세 분석 대상: {len(new_urls)}개 (기존 {len(all_campaign_urls) - len(new_urls)}개 제외)")

        if not new_urls:
            print("새로운 캠페인이 없습니다.")
            return

        # 2. 상세 페이지 병렬 처리
        # 한 번에 너무 많은 요청을 보내면 차단될 수 있으므로 세마포어 사용 권장
        # 여기서는 간단히 5개씩 끊어서 처리하거나 전체 병렬 처리
        
        BATCH_SIZE = 5
        for i in range(0, len(new_urls), BATCH_SIZE):
            batch_urls = new_urls[i:i+BATCH_SIZE]
            print(f"\n  Batch {i//BATCH_SIZE + 1} 처리 중 ({len(batch_urls)}개)...")
            
            tasks = [
                process_detail_page(url, browser, llm, supabase, existing_urls)
                for url in batch_urls
            ]
            
            results = await asyncio.gather(*tasks)
            total_new += sum(results)
            
            # 배치 간 딜레이
            if i + BATCH_SIZE < len(new_urls):
                await asyncio.sleep(2)

    finally:
        await browser.close()

    print("\n" + "=" * 60)
    print(f"       크롤링 완료!")
    print(f"       새로 추가된 캠페인: {total_new}개")
    print("=" * 60 + "\n")

    # GitHub Actions 연동: 결과 출력
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"new_campaigns_count={total_new}\n")
            if total_new > 0:
                f.write("has_new_campaigns=true\n")


if __name__ == "__main__":
    asyncio.run(main())
