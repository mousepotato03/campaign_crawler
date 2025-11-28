import os
import json
import google.generativeai as genai
from typing import List, Dict, Optional

class LLMService:
    """
    Google Gemini API 연동 서비스
    - google-generativeai 라이브러리 사용
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 환경변수가 필요합니다.")
        
        genai.configure(api_key=api_key)
        
        # 모델 설정
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        self.model = genai.GenerativeModel(self.model_name)
        
        # JSON 응답을 위한 설정
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.1,
            response_mime_type="application/json"
        )

    async def _generate_content(self, prompt: str) -> Optional[Dict]:
        """Gemini API 호출 및 JSON 파싱"""
        try:
            # 비동기 호출 (make_async=True가 지원되지 않는 버전일 수 있으므로 동기 호출을 비동기로 래핑하거나, 
            # 최신 라이브러리에서는 generate_content_async 사용)
            response = await self.model.generate_content_async(
                prompt,
                generation_config=self.generation_config
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            print(f"[LLM] Error generating content: {e}")
            return None

    async def extract_campaign_urls(self, html_content: str, base_url: str) -> List[str]:
        """HTML에서 캠페인 URL 추출"""
        from prompts.list_extraction import LIST_EXTRACTION_PROMPT
        
        # HTML이 너무 길 경우를 대비해 길이 제한 (필요시 조정)
        truncated_html = html_content[:1000000] 
        
        prompt = LIST_EXTRACTION_PROMPT.format(url=base_url, html=truncated_html)
        result = await self._generate_content(prompt)
        
        if result and "campaign_urls" in result:
            return result["campaign_urls"]
        
        print(f"[DEBUG] LLM Extraction Failed. Result: {result}")
        return []

    async def extract_campaign_detail(self, html_content: str, url: str) -> Optional[Dict]:
        """HTML에서 캠페인 상세 정보 추출"""
        from prompts.unified_extraction import UNIFIED_EXTRACTION_PROMPT
        
        truncated_html = html_content[:1000000]
        
        prompt = UNIFIED_EXTRACTION_PROMPT.format(url=url, html=truncated_html)
        result = await self._generate_content(prompt)
        
        return result
