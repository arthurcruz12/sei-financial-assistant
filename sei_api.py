"""HTTP bridge to the verified SEI multi-agent Python engine."""
import os
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from sei_multi_agent import MultiAgentChat
from sei_agents import result_to_markdown

app = FastAPI(title="SEI Multi-Agent API", version="1.0.0")
engine = MultiAgentChat()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)

@app.get("/health")
def health():
    return {"status": "ok", "service": "sei-multi-agent"}

@app.post("/chat")
def chat(body: ChatRequest, authorization: str | None = Header(default=None)):
    secret = os.getenv("SEI_BRIDGE_TOKEN")
    if not secret:
        raise HTTPException(status_code=503, detail="Service authentication is not configured")
    import hmac
    if not hmac.compare_digest(authorization or "", "Bearer " + secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    results = engine.chat(body.message)
    return {
        "answer": "\n\n---\n\n".join(result_to_markdown(r) for r in results),
        "agents": [r.agent for r in results],
        "sources": list(dict.fromkeys(src for r in results for src in r.sources)),
    }
