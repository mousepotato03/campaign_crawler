"""캠페인 및 미션 템플릿 데이터 모델"""

from dataclasses import dataclass, asdict
from typing import Optional
from datetime import date


@dataclass
class CampaignData:
    """캠페인 데이터 모델 - Supabase campaigns 테이블과 매핑"""
    title: str
    campaign_url: str
    host_organizer: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM-DD 형식 문자열
    end_date: Optional[str] = None    # YYYY-MM-DD 형식 문자열
    region: Optional[str] = None
    status: str = "ACTIVE"
    submission_type: str = "MANUAL_GUIDE"
    category: Optional[str] = None
    campaign_type: str = "ONLINE"
    rpa_site_config_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Supabase INSERT용 딕셔너리 변환"""
        data = asdict(self)
        # None 값 제거
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class MissionTemplateData:
    """미션 템플릿 데이터 모델 - Supabase mission_templates 테이블과 매핑"""
    campaign_id: int
    title: str
    description: Optional[str] = None
    order: int = 0
    verification_type: str = "IMAGE"  # IMAGE, QUIZ, TEXT_REVIEW, RPA_ACTION
    reward_points: int = 10

    def to_dict(self) -> dict:
        """Supabase INSERT용 딕셔너리 변환"""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}
