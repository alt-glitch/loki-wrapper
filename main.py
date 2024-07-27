from fastapi import FastAPI, HTTPException
import httpx
import json
import logging

logging.basicConfig(level=logging.DEBUG)
app = FastAPI()

# Dummy function to convert natural language to LogQL
def natural_language_to_logql(query: str) -> str:
    # This is a placeholder. In a real implementation, you'd use NLP techniques here.
    dummy_conversations = {
        "show me all errors": '{container="run_loki-flog-1"} | json status | line_format "{{.status}}" |~ "500"',
        "list recent logs": '{container="run_loki-flog-1"}',
        "count GET requests in the last hour": '{container="run_loki-flog-1"} | json method | line_format "{{.method}}" |~ "GET" | count_over_time( [1h])',
        "show all logs for a specific request": '{container="run_loki-flog-1"} | json request | line_format "{{.request}}" |~ "/proactive/architectures/revolutionary/24%2f365"',
    }
    return dummy_conversations.get(query.lower(), '{container="run_loki-flog-1"}')

@app.post("/query")
async def process_query(query: dict):
    natural_query = query.get("query")
    if not natural_query:
        raise HTTPException(status_code=400, detail="Query is required")

    logql_query = natural_language_to_logql(natural_query)

    # Call Loki API
    loki_url = "http://localhost:3100/loki/api/v1/query"
    headers = {'X-Scope-OrgID': 'tenant1'}  # passing 'org-id' in request headers
    params = {"query": logql_query}

    async with httpx.AsyncClient() as client:
        response = await client.get(loki_url, params=params, headers=headers)

    if response.status_code != 200:
        logging.debug(f"Loki query result: {response.text}")  # Debug statement with the Loki response
        raise HTTPException(status_code=response.status_code, detail=f"Loki query failed with response: {response.text}")


    return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
