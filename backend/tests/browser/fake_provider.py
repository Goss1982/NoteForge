import json

from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/v1/responses")
async def responses(request: Request):
    body = await request.json()
    if body["text"]["format"]["name"] == "Extraction":
        value = {
            "transcript": "Alex to send the proposal on Friday. Budget: GBP 2500.",
            "category": "Meeting",
            "purpose": "A planning meeting",
            "blocks": [
                {
                    "kind": "text",
                    "text": "Alex to send the proposal on Friday. Budget: GBP 2500.",
                    "evidence_quote": "Budget: GBP 2500.",
                    "confidence": 0.9,
                    "uncertain": False,
                }
            ],
            "insights": [
                {
                    "kind": "action",
                    "text": "Send the proposal",
                    "evidence_quote": "Alex to send the proposal on Friday.",
                    "owner": "Alex",
                    "due_date": "Friday",
                    "confidence": 0.9,
                }
            ],
            "uncertainties": [],
        }
    else:
        pages = json.loads(body["input"].split("Source pages (JSON):\n")[1])
        value = {
            "title": "Meeting follow-up",
            "sections": [
                {
                    "heading": "Actions",
                    "paragraphs": [
                        {
                            "kind": "fact",
                            "text": "Alex is to send the proposal on Friday.",
                            "citations": [
                                {
                                    "page_id": pages[0]["page_id"],
                                    "quote": "Alex to send the proposal on Friday.",
                                }
                            ],
                        }
                    ],
                }
            ],
            "missing_information": ["Meeting date not specified"],
        }
    return {
        "id": "resp_e2e",
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": "fixture",
        "output": [
            {
                "id": "msg_e2e",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(value), "annotations": []}],
            }
        ],
        "parallel_tool_calls": False,
        "tools": [],
        "tool_choice": "auto",
        "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
    }
