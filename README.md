# catprint

Needs uv: https://docs.astral.sh/uv/getting-started/installation/

Install with: `uv sync`

Run UI with: `uv run streamlit run app.py`

Run Server with: `uv run uvicorn api_server:app --reload --port 5000`

Try server endpoints:
```
$ curl -sS -X POST "http://127.0.0.1:5000/scan?mock=true"
```
```
$ curl -X 'GET' \                                    
  'http://localhost:5000/printers' \
  -H 'accept: application/json'                                              
```
```
$ curl -X POST http://localhost:5000/print \         
  -H "Content-Type: application/json" \
  -d '{
    "printer": "AA:BB:CC:DD:EE:01",
    "blocks": [
      {"type": "text", "data": "Hello World"},
      {"type": "banner", "data": "SALE"}
    ],
    "include_template": true,
    "mock": true
  }'
```
