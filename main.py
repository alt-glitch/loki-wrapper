import logging

import httpx
import instructor
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from litellm import completion
from pydantic import BaseModel

from prompts import SYSTEM_PROMPT, USER_PROMPT

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
app = FastAPI()

client = instructor.from_litellm(completion)


class UserQuery(BaseModel):
    query: str
    model: str


class Label(BaseModel):
    label: str


class LogQLQuery(BaseModel):
    query: str


class LokiClient:
    def __init__(self) -> None:
        self.base_url = "http://localhost:3100/loki/api/v1"
        self.headers = {"X-Scope-OrgID": "tenant1"}
        self.httpx_client = httpx.Client(headers=self.headers)

    def query_streams(self):
        url = f"{self.base_url}/series"
        res = self.httpx_client.get(url)
        return res.json()

    def query_labels(self):
        url = f"{self.base_url}/labels"
        res = self.httpx_client.get(url)
        return res.json()

    def query_label_values(self, label: str):
        url = f"{self.base_url}/label/{label}/values"
        res = self.httpx_client.get(url)
        return res.json()

    def query_loki(self, query: str):
        url = f"{self.base_url}/query"
        params = {"query": query}
        res = self.httpx_client.get(url, params=params)
        return res.json()


async def query_loki(query: str, ranged: bool = False):
    loki_url = "http://localhost:3100/loki/api/v1/query"
    headers = {
        "X-Scope-OrgID": "tenant1"
    }  # passing 'org-id' in request headers
    params = {"query": query}

    async with httpx.AsyncClient() as client:
        response = await client.get(loki_url, params=params, headers=headers)

    if response.status_code != 200:
        logging.debug(
            f"Loki query result: {response.text}"
        )  # Debug statement with the Loki response
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Loki query failed with response: {response.text}",
        )

    return response.json()


@app.post("/query")
async def process_query(query: UserQuery):
    query_string = query.query
    loki_client = LokiClient()
    query_streams = loki_client.query_streams()
    query_labels = loki_client.query_labels()
    label = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You understand the user's question about Grafana Loki's and pick the label they are searching for",
            },
            {
                "role": "user",
                "content": f"<query_string>{query_string}</query_string> <labels>{query_labels['data']}</labels>",
            },
        ],
        response_model=Label,
    )

    label_values = loki_client.query_label_values(label.label)
    logql_query = client.chat.completions.create(
        model=query.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    query_streams=query_streams,
                    query_labels=query_labels,
                    query_label=label.label,
                    label_values=label_values,
                    query=query_string,
                ),
            },
        ],
        response_model=LogQLQuery,
    )
    logs = loki_client.query_loki(logql_query.query)

    return logs
    #
    # resp = client.chat.completions.create(
    #     model="gpt-4-turbo",
    #     messages=[
    #         {
    #             "role": "user",
    #             "content": "Extract Jason is 25 years old",
    #         }
    #     ],
    #     response_model=User,
    # )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

# # Dummy function to convert natural language to LogQL
# def natural_language_to_logql(query: str) -> str:
#     # This is a placeholder. In a real implementation, you'd use NLP techniques here.
#     dummy_conversations = {
#         "show me all errors": '{container="run_loki-flog-1"} | json status | line_format "{{.status}}" |~ "500"',
#         "list recent logs": '{container="run_loki-flog-1"}',
#         "count GET requests in the last hour": '{container="run_loki-flog-1"} | json method | line_format "{{.method}}" |~ "GET" | count_over_time( [1h])',
#         "show all logs for a specific request": '{container="run_loki-flog-1"} | json request | line_format "{{.request}}" |~ "/proactive/architectures/revolutionary/24%2f365"',
#     }
#     return dummy_conversations.get(
#         query.lower(), '{container="run_loki-flog-1"}'
#     )
