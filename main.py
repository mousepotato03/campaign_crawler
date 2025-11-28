#!/usr/bin/env python3
"""
환경 캠페인 크롤러 v3.0

2단계 분리 방식:
  1단계: Playwright MCP로 캠페인 URL 추출 → DB 중복 체크
  2단계: 새 URL마다 독립된 Gemini CLI 호출 (context 오염 방지) + browser_close

사용법:
    python main.py
"""

import os
import sys
import time
import yaml
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.supabase_client import SupabaseService
from services.gemini_rpa import GeminiRPAService
from models.campaign import CampaignData, MissionTemplateData


def load_env():
    """환경변수 로드"""
    env_path = PROJECT_ROOT / "config" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        example_path = PROJECT_ROOT / "config" / ".env.example"
        if example_path.exists():
            print("[WARN] config/.env 파일이 없습니다.")
            print("       config/.env.example을 참고하여 .env 파일을 생성하세요.")
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
    mission_id = supabase.insert_mission_template(default_mission)
    if mission_id:
        print(f"      [MISSION] 기본 미션 생성 (ID: {mission_id})")


def save_campaign(result: dict, supabase: SupabaseService, existing_urls: set) -> int:
    """
    캠페인 저장 (2단계에서 사용)

    Args:
        result: Gemini 분석 결과
        supabase: Supabase 서비스
        existing_urls: 기존 캠페인 URL 집합

    Returns:
        저장된 캠페인 수
    """
    saved_count = 0
    campaigns = result.get("campaigns", [])

    for camp in campaigns:
        campaign_url = camp.get("campaign_url")

        if not campaign_url:
            continue

        if campaign_url in existing_urls:
            print(f"    [SKIP] 이미 존재: {camp.get('title', 'Unknown')[:30]}")
            continue

        # CampaignData 생성
        campaign = CampaignData(
            title=camp.get("title") or "Unknown",
            campaign_url=campaign_url,
            host_organizer=camp.get("host_organizer") or "Unknown",
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
            print(f"    [OK] 저장 완료: {campaign.title[:40]} (ID: {campaign_id})")

            # 미션 템플릿 생성 (추출된 것 우선, 없으면 기본)
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
                    mission_id = supabase.insert_mission_template(mission_data)
                    if mission_id:
                        print(f"      [MISSION] 미션 생성: {mission_data.title[:30]} (ID: {mission_id})")
            else:
                create_default_missions(supabase, campaign_id, campaign.title)
        else:
            print(f"    [FAIL] DB 저장 실패: {campaign.title[:40]}")

    return saved_count


def main():
    """메인 실행 함수 - 2단계 분리 방식"""
    print("\n" + "=" * 60)
    print("       환경 캠페인 크롤러 v3.0")
    print("       2단계 분리: URL 수집 → 상세 추출")
    print("=" * 60)

    # 1. 환경변수 및 설정 로드
    load_env()
    config = load_config()

    settings = config.get("settings", {})
    delay = settings.get("request_delay_seconds", 3)
    timeout = settings.get("gemini_timeout", 180)
    debug_mode = settings.get("debug_mode", False)

    # 2. 서비스 초기화
    try:
        supabase = SupabaseService()
    except ValueError as e:
        print(f"\n[ERROR] Supabase 서비스 초기화 실패: {e}")
        sys.exit(1)

    # 3. 기존 캠페인 URL 조회
    existing_urls = supabase.get_existing_urls()
    print(f"\n기존 캠페인 수: {len(existing_urls)}개")

    # 4. URL 목록 로드
    urls = config.get("urls", [])
    if not urls:
        print("\n[WARN] 크롤링할 URL이 없습니다.")
        print("       config/sites.yaml에 URL을 추가하세요.")
        sys.exit(0)

    print(f"크롤링 대상 URL: {len(urls)}개")
    print(f"설정: delay={delay}초, timeout={timeout}초, debug={debug_mode}")

    # 5. 각 목록 URL 처리
    total_new = 0
    for idx, list_url in enumerate(urls, 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(urls)}] 목록 페이지: {list_url}")
        print("=" * 60)

        # ========== 1단계: URL 수집 ==========
        print("\n[1단계] 캠페인 URL 수집 중...")

        # Playwright MCP로 페이지 접근 및 URL 추출
        try:
            gemini = GeminiRPAService(timeout=timeout, debug=debug_mode)
            campaign_urls = gemini.extract_campaign_urls(list_url)
            gemini.close_browser()  # 1단계 브라우저 종료
        except Exception as e:
            print(f"  [ERROR] URL 추출 실패: {e}")
            continue

        print(f"  발견된 URL: {len(campaign_urls)}개")

        # DB 중복 체크 (top-down 순서 유지)
        new_urls = [u for u in campaign_urls if u not in existing_urls]
        skipped = len(campaign_urls) - len(new_urls)
        print(f"  새 URL: {len(new_urls)}개 (기존 {skipped}개 스킵)")

        if not new_urls:
            print("  [INFO] 새 캠페인 없음, 다음 URL로 이동")
            continue

        # ========== 2단계: 상세 정보 추출 ==========
        print(f"\n[2단계] 캠페인 상세 정보 추출...")

        for url_idx, campaign_url in enumerate(new_urls, 1):
            print(f"\n  [{url_idx}/{len(new_urls)}] {campaign_url}")

            try:
                # 매번 새 인스턴스 생성 (context 오염 방지)
                gemini = GeminiRPAService(timeout=timeout, debug=debug_mode)

                result = gemini.analyze_and_extract(campaign_url)

                # 반드시 브라우저 종료
                gemini.close_browser()

                if not result:
                    print(f"    [FAIL] 분석 실패")
                    continue

                if debug_mode:
                    print(f"    [DEBUG] is_env={result.get('is_environmental_campaign')}, "
                          f"campaigns={len(result.get('campaigns', []))}개")

                if result.get("is_environmental_campaign"):
                    saved = save_campaign(result, supabase, existing_urls)
                    total_new += saved
                else:
                    print(f"    [SKIP] 환경 캠페인이 아님")

            except Exception as e:
                print(f"    [ERROR] 처리 실패: {e}")

            time.sleep(delay)

        # 목록 URL 간 딜레이
        if idx < len(urls):
            time.sleep(delay)

    # 6. 결과 출력
    print("\n" + "=" * 60)
    print(f"       크롤링 완료!")
    print(f"       새로 추가된 캠페인: {total_new}개")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
