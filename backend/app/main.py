"""RescueFlow AI FastAPI application entrypoint.

Run locally (demo mode, no credentials needed):

    uvicorn app.main:app --reload --port 8000

With live Strands Decider 2B + Amazon Bedrock (set .env first):

    DECIDER_MODE=ugmdu DECIDER_API_KEY=... LLM_PROVIDER=bedrock \\
        uvicorn app.main:app --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import mode_info

app = FastAPI(
    title="RescueFlow AI",
    description="An agent that decides what needs attention first. "
                "Built with the AWS User Group Madurai Strands Decider hackathon kit. "
                "Uses Strands Decider 2B for the triage decision and the Strands Agents SDK "
                "(Amazon Bedrock) for the generative part.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production (the frontend origin)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    info = mode_info()
    return {
        "name": "RescueFlow AI",
        "tagline": "An agent that decides what needs attention first.",
        "mode": info["mode"],
        "decider_live": info["decider_live"],
        "llm_live": info["llm_live"],
        "kit_credit": info["kit_credit"],
        "docs": "/docs",
        "health": "/health",
    }
