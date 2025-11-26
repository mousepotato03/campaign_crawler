# 환경 캠페인 크롤러

## 환경설정

1. 가상환경 생성 및 의존성 설치

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. 환경변수 설정

.env 파일을 새로 만들고, .env.example 파일의 내용을 .env로 복사하여 환경변수를 설정합니다.

3. .gemini 폴더 생성
.gemini/settings.json 파일을 생성하고, mcp tool을 추가합니다.

```json
{
  "mcpServers": {
    "supabase": {
      "httpUrl": "https://mcp.supabase.com/mcp?project_ref=${SUPABASE_PROJECT_REF}",
      "headers": {
        "Authorization": "Bearer ${SUPABASE_MCP_SECRET}"
      }
    },
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--headless"]
    }
  }
}
```

## 사용법

```bash
(venv) python main.py
```




