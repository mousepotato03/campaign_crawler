"""Supabase 클라이언트 - 캠페인 및 미션 템플릿 CRUD"""

import os
from typing import Optional, Set
from supabase import create_client, Client

from models.campaign import CampaignData, MissionTemplateData


class SupabaseService:
    """Supabase 데이터베이스 연동 서비스"""

    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL과 SUPABASE_SERVICE_KEY 환경변수가 필요합니다.")

        self.client: Client = create_client(url, key)

    def get_existing_urls(self) -> Set[str]:
        """기존 캠페인 URL 목록 조회 (중복 체크용)"""
        result = self.client.table("campaigns").select("campaign_url").execute()
        return {row["campaign_url"] for row in result.data}

    def campaign_exists(self, url: str) -> bool:
        """특정 URL의 캠페인이 이미 존재하는지 확인"""
        result = self.client.table("campaigns") \
            .select("id") \
            .eq("campaign_url", url) \
            .execute()
        return len(result.data) > 0

    def insert_campaign(self, campaign: CampaignData) -> Optional[int]:
        """
        캠페인 데이터 저장

        Returns:
            저장된 캠페인 ID, 이미 존재하면 None
        """
        if self.campaign_exists(campaign.campaign_url):
            print(f"  [SKIP] 이미 존재: {campaign.title}")
            return None

        try:
            result = self.client.table("campaigns") \
                .insert(campaign.to_dict()) \
                .execute()

            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            print(f"  [ERROR] 캠페인 저장 실패: {e}")
            return None

    def insert_mission_template(self, mission: MissionTemplateData) -> Optional[int]:
        """
        미션 템플릿 저장

        Returns:
            저장된 미션 템플릿 ID
        """
        try:
            result = self.client.table("mission_templates") \
                .insert(mission.to_dict()) \
                .execute()

            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            print(f"  [ERROR] 미션 템플릿 저장 실패: {e}")
            return None
