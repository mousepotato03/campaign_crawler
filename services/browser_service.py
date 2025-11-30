import asyncio
from playwright.async_api import async_playwright, Browser, Playwright

class BrowserService:
    """
    Playwright 브라우저 관리 서비스 (Async)
    - 단일 브라우저 인스턴스 공유
    - 요청마다 독립된 Context 생성 (병렬 처리 시 충돌 방지)
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright: Playwright = None
        self.browser: Browser = None

    async def launch(self):
        """브라우저 시작"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        if not self.browser:
            # 봇 탐지 회피를 위한 기본 인자 설정
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )

    async def get_page_content(self, url: str) -> str:
        """
        URL에 접속하여 페이지 HTML 콘텐츠 반환
        - 새 Context 생성 -> 페이지 접속 -> HTML 추출 -> Context 종료
        """
        if not self.browser:
            await self.launch()

        # 봇 탐지 회피를 위한 User-Agent 설정
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        page = await context.new_page()
        
        try:
            # 페이지 접속
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 스크롤을 내려서 Lazy Loading 이미지/콘텐츠 로드 유도
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3) # 스크롤 후 대기 (충분히)
            
            # HTML 추출
            content = await page.content()
            return content
            
        except Exception as e:
            error_msg = str(e)
            # SSL 인증서 관련 에러 처리
            if "ERR_CERT" in error_msg:
                print(f"[Browser] SSL 인증서 오류로 스킵: {url}")
            elif "ERR_CONNECTION_REFUSED" in error_msg:
                print(f"[Browser] 연결 거부됨: {url}")
            elif "ERR_NAME_NOT_RESOLVED" in error_msg:
                print(f"[Browser] 도메인 찾을 수 없음: {url}")
            elif "Timeout" in error_msg:
                print(f"[Browser] 타임아웃: {url}")
            else:
                print(f"[Browser] Error fetching {url}: {e}")
            return ""
            
        finally:
            await context.close()

    async def close(self):
        """브라우저 및 Playwright 종료"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
