# catprint

Needs uv: https://docs.astral.sh/uv/getting-started/installation/

Install with: `uv sync`

Run UI with: `uv run streamlit run app.py`

Run Server with: `uv run uvicorn api_server:app --reload --port 5000`

Try server endpoints:
```
$ curl -sS -X GET 'http://127.0.0.1:5000/printers' -H 'accept: application/json' -w '\nHTTP_CODE:%{http_code}\n' ✘  ~/Projects/catprint   main  curl -sS -X GET 'http://127.0.0.1:5000/printers' -H 'accept: application/json' -w '\nHTTP_CODE:%{http_code}\n'
{"success":true,"printers":[{"name":"MX06","address":"AA:BB:CC:DD:EE:01"},{"name":"MX06","address":"AA:BB:CC:DD:EE:02"}]}
HTTP_CODE:200
 ~/Projects/catprint   main  curl -X 'GET' \                                    
  'http://localhost:5000/printers' \
  -H 'accept: application/json'
{"success":true,"printers":[{"name":"MX06","address":"AA:BB:CC:DD:EE:01"},{"name":"MX06","address":"AA:BB:CC:DD:EE:02"}]}%                                                                 ~/Projects/catprint   main  git push -u origin main                                
^R
 ✘  ~/Projects/catprint   main  curl -X POST http://localhost:5000/print \         
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
