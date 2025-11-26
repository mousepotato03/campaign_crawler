"""Gemini CLI + MCP를 통한 RPA 서비스"""

import subprocess
import json
import re
import os
from typing import Optional, Dict, List
from pathlib import Path


class GeminiRPAService:
    """Gemini CLI를 subprocess로 호출하여 Playwright MCP 작업 수행"""

    def __init__(self, timeout: int = 120, debug: bool = False):
        self.timeout = timeout
        self.debug = debug
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.project_root = Path(__file__).parent.parent

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY 환경변수가 필요합니다.")

    def execute_prompt(self, prompt: str) -> Optional[Dict]:
        """
        Gemini CLI를 subprocess로 호출하여 MCP 작업 수행

        Args:
            prompt: Gemini에게 전달할 프롬프트

        Returns:
            파싱된 JSON 응답 또는 None
        """
        env = os.environ.copy()
        env["GOOGLE_API_KEY"] = self.api_key
        env["CI"] = "true"        # CI 환경으로 인식시켜 인터랙티브 UI 비활성화
        env["NO_COLOR"] = "1"     # 색상 출력 비활성화
        env["TERM"] = "dumb"      # 단순 터미널로 인식

        # Windows에서 gemini CLI 호출 (shell=True로 .cmd 파일 인식)
        # -o json: JSON 형식 출력
        # 프롬프트는 stdin으로 전달하여 쉘 이스케이프 문제 및 길이 제한 해결
        cmd = f'gemini -m {self.model} --yolo -o json'

        if self.debug:
            print(f"\n{'='*60}")
            print(f"[DEBUG-CMD] {cmd}")
            print(f"[DEBUG-PROMPT] {prompt[:500]}{'...' if len(prompt) > 500 else ''}")
            print(f"{'='*60}")

        try:
            # Popen 사용으로 타임아웃 시 프로세스 강제 종료 가능
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,  # stdin으로 프롬프트 전달
                text=True,
                encoding='utf-8',  # UTF-8 명시
                env=env,
                cwd=str(self.project_root),
                shell=True  # Windows PowerShell에서 .cmd 파일 인식
            )

            try:
                # 프롬프트를 stdin으로 전달 (개행 문자 추가)
                stdout, stderr = process.communicate(input=prompt + "\n", timeout=self.timeout)

                if process.returncode != 0:
                    print(f"  [WARN] Gemini CLI 종료 코드: {process.returncode}")
                    if stderr:
                        print(f"  [STDERR] {stderr[:200]}")
                    # 에러가 있어도 stdout에 JSON이 있을 수 있으므로 계속 진행
                
                if self.debug:
                    print(f"[DEBUG-RAW] 응답 길이: {len(stdout)}자")
                    if len(stdout) < 5000:
                        print(f"{stdout}")
                    else:
                        print(f"{stdout[:2000]}...[생략]...{stdout[-500:]}")
                    print(f"{'='*60}")

                return self._parse_json_response(stdout)

            except subprocess.TimeoutExpired:
                process.kill()  # 프로세스 강제 종료
                process.wait(timeout=5)  # 종료 대기
                print(f"  [ERROR] Gemini CLI 타임아웃 ({self.timeout}초) - 프로세스 종료됨")
                return None

        except FileNotFoundError:
            print("  [ERROR] Gemini CLI를 찾을 수 없습니다.")
            print("         - 설치: npm install -g @google/gemini-cli")
            print("         - 확인: where gemini (PowerShell에서)")
            return None
        except Exception as e:
            print(f"  [ERROR] Gemini CLI 실행 실패: {e}")
            return None

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """
        Gemini 응답에서 JSON 추출

        여러 패턴으로 JSON을 찾아 파싱
        """
        if not response:
            return None

        # 진단 메시지 필터링 (ASCII 아트, 로딩 메시지 등 제거)
        lines = response.split('\n')
        filtered_lines = [
            line for line in lines
            if not line.startswith('Loaded ')
            and 'Tips for getting started' not in line
            and 'has been cached' not in line
            and not line.strip().startswith('░')  # ASCII 아트 제거
            and not line.strip().startswith('█')  # ASCII 아트 제거
        ]
        response = '\n'.join(filtered_lines)

        result = None
        parse_method = None

        # 패턴 1: ```json ... ``` 코드 블록
        json_block_pattern = r'```json\s*(.*?)\s*```'
        match = re.search(json_block_pattern, response, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
                parse_method = "json 코드 블록"
            except json.JSONDecodeError:
                pass

        # 패턴 2: 일반 코드 블록
        if not result:
            code_block_pattern = r'```\s*(.*?)\s*```'
            match = re.search(code_block_pattern, response, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(1))
                    parse_method = "일반 코드 블록"
                except json.JSONDecodeError:
                    pass

        # 패턴 3: 순수 JSON 객체
        if not result:
            json_object_pattern = r'\{[\s\S]*\}'
            match = re.search(json_object_pattern, response)
            if match:
                try:
                    result = json.loads(match.group(0))
                    parse_method = "순수 JSON 객체"
                except json.JSONDecodeError:
                    pass

        if result:
            # Gemini CLI -o json 출력의 경우 실제 응답은 'response' 필드에 있음
            if isinstance(result, dict) and 'response' in result and isinstance(result['response'], str):
                if self.debug:
                    print(f"[DEBUG-PARSED] 래핑된 응답 감지, 내부 파싱 시도")
                return self._parse_json_response(result['response'])

            if self.debug:
                print(f"[DEBUG-PARSED] 성공 ({parse_method}), 키: {list(result.keys())}")
            return result

        print("  [WARN] JSON 파싱 실패, 원본 응답 일부:")
        if len(response) < 300:
            print(f"  {response}")
        else:
            print(f"  {response[:300]}...")
        return None

    def extract_campaign_list(self, url: str) -> List[Dict]:
        """
        캠페인 목록 페이지에서 캠페인 URL 추출

        Args:
            url: 캠페인 목록 페이지 URL

        Returns:
            캠페인 정보 딕셔너리 리스트
        """
        from prompts.list_extraction import LIST_EXTRACTION_PROMPT

        prompt = LIST_EXTRACTION_PROMPT.format(url=url)
        result = self.execute_prompt(prompt)

        if result and "campaigns" in result:
            return result["campaigns"]
        return []

    def extract_campaign_detail(self, url: str) -> Optional[Dict]:
        """
        캠페인 상세 페이지에서 정보 추출

        Args:
            url: 캠페인 상세 페이지 URL

        Returns:
            캠페인 상세 정보 딕셔너리
        """
        from prompts.detail_extraction import DETAIL_EXTRACTION_PROMPT

        prompt = DETAIL_EXTRACTION_PROMPT.format(url=url)
        result = self.execute_prompt(prompt)

        if result and "campaign" in result:
            return result
        return None

    def analyze_and_extract(self, url: str) -> Optional[Dict]:
        """
        URL을 분석하고 환경 캠페인 정보 자동 추출

        LLM이 페이지 타입(목록/상세)을 판단하고 적절한 정보를 추출합니다.
        - 목록 페이지: 각 캠페인의 URL 수집
        - 상세 페이지: 캠페인 상세 정보 추출

        Args:
            url: 분석할 페이지 URL

        Returns:
            {
                "page_type": "list" | "detail",
                "is_environmental_campaign": bool,
                "campaigns": [...]
            }
        """
        from prompts.unified_extraction import UNIFIED_EXTRACTION_PROMPT

        prompt = UNIFIED_EXTRACTION_PROMPT.format(url=url)
        return self.execute_prompt(prompt)
