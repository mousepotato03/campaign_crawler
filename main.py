#!/usr/bin/env python3
"""
환경 캠페인 크롤러 v2.0

URL만 추가하면 LLM(Gemini)이 Playwright MCP를 사용해
직접 페이지를 탐색하고 환경 캠페인인지 판단하여 데이터를 수집합니다.

사용법:
    python main.py
"""

import os
import sys
import time
import yaml
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
        reward_points=10
    )
    mission_id = supabase.insert_mission_template(default_mission)
    if mission_id:
        print(f"      [MISSION] 기본 미션 생성 (ID: {mission_id})")


def process_url(url: str, gemini: GeminiRPAService, supabase: SupabaseService,
                existing_urls: set, delay: int, depth: int = 0, max_depth: int = 2,
                debug: bool = False) -> int:
    """
    단일 URL 처리 - LLM이 페이지를 분석하고 캠페인 정보 추출

    Args:
        url: 분석할 URL
        gemini: Gemini RPA 서비스
        supabase: Supabase 서비스
        existing_urls: 이미 존재하는 캠페인 URL 집합
        delay: 요청 간 딜레이 (초)
        depth: 현재 탐색 깊이
        max_depth: 최대 탐색 깊이
        debug: 디버그 모드 활성화 여부

    Returns:
        새로 추가된 캠페인 수
    """
    indent = "  " * depth
    print(f"\n{indent}[분석 중] {url}")

    # 깊이 제한 확인
    if depth >= max_depth:
        print(f"{indent}  [SKIP] 최대 깊이 도달 (depth={depth})")
        return 0

    # 이미 처리된 URL 스킵
    if url in existing_urls:
        print(f"{indent}  [SKIP] 이미 존재하는 캠페인")
        return 0

    # 1. LLM이 페이지 분석 및 캠페인 추출
    result = gemini.analyze_and_extract(url)

    if not result:
        print(f"{indent}  [FAIL] 페이지 분석 실패")
        return 0

    # 디버그: 분석 결과 요약 출력
    if debug:
        print(f"{indent}  [DEBUG-RESULT] page_type={result.get('page_type')}, "
              f"is_env={result.get('is_environmental_campaign')}, "
              f"campaigns={len(result.get('campaigns', []))}개")

    # 2. 환경 캠페인 여부 확인
    if not result.get("is_environmental_campaign", False):
        print(f"{indent}  [SKIP] 환경 캠페인이 아님")
        return 0

    # 3. 페이지 타입에 따라 처리
    page_type = result.get("page_type", "unknown")
    campaigns = result.get("campaigns", [])

    print(f"{indent}  [INFO] 페이지 타입: {page_type}, 발견: {len(campaigns)}개")

    new_count = 0

    if page_type == "list":
        # 목록 페이지: 각 캠페인 URL로 재귀 처리
        for idx, camp in enumerate(campaigns, 1):
            campaign_url = camp.get("campaign_url")
            if not campaign_url:
                continue

            print(f"{indent}  [{idx}/{len(campaigns)}] {camp.get('title', 'Unknown')[:40]}...")
            time.sleep(delay)

            new_count += process_url(
                campaign_url, gemini, supabase, existing_urls,
                delay, depth + 1, max_depth, debug
            )

    elif page_type == "detail":
        # 상세 페이지: DB 저장
        for camp in campaigns:
            campaign_url = camp.get("campaign_url") or url

            if campaign_url in existing_urls:
                print(f"{indent}  [SKIP] 이미 존재: {camp.get('title', 'Unknown')[:30]}")
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
                new_count += 1
                print(f"{indent}  [OK] 저장 완료: {campaign.title[:40]} (ID: {campaign_id})")

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
                print(f"{indent}  [FAIL] DB 저장 실패: {campaign.title[:40]}")

    else:
        print(f"{indent}  [WARN] 알 수 없는 페이지 타입: {page_type}")

    return new_count


def main():
    """메인 실행 함수"""
    print("\n" + "=" * 60)
    print("       환경 캠페인 크롤러 v2.0")
    print("       LLM 자율 판단 + Playwright MCP")
    print("=" * 60)

    # 1. 환경변수 및 설정 로드
    load_env()
    config = load_config()

    settings = config.get("settings", {})
    delay = settings.get("request_delay_seconds", 3)
    timeout = settings.get("gemini_timeout", 180)
    max_depth = settings.get("max_depth", 2)

    debug_mode = settings.get("debug_mode", False)

    # 2. 서비스 초기화
    try:
        supabase = SupabaseService()
        gemini = GeminiRPAService(timeout=timeout, debug=debug_mode)
    except ValueError as e:
        print(f"\n[ERROR] 서비스 초기화 실패: {e}")
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
    print(f"설정: delay={delay}초, timeout={timeout}초, max_depth={max_depth}, debug={debug_mode}")

    # 5. 각 URL 처리
    total_new = 0
    for idx, url in enumerate(urls, 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(urls)}] 시작: {url}")
        print("=" * 60)

        try:
            new_count = process_url(
                url, gemini, supabase, existing_urls,
                delay, depth=0, max_depth=max_depth, debug=debug_mode
            )
            total_new += new_count
        except Exception as e:
            print(f"\n[ERROR] 처리 중 오류: {e}")
            continue

        # URL 간 딜레이
        if idx < len(urls):
            time.sleep(delay)

    # 6. 결과 출력
    print("\n" + "=" * 60)
    print(f"       크롤링 완료!")
    print(f"       새로 추가된 캠페인: {total_new}개")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
