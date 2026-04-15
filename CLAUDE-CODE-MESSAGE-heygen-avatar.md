# Task: Integrate HeyGen LiveAvatar for Voice Roleplay Sessions

> **Read these files FIRST before writing any code:**
> 1. `CLAUDE-CODE-BRIEFING.md` — overall architecture, tech stack
> 2. `app.py` — current codebase, all handlers, roleplay flow
> 3. `graphs/coach.py` — `roleplay_node()` and `continue_roleplay()` functions
> 4. `prompts/coach_prompts.py` — roleplay system prompts
> 5. `formatters/coach.py` — roleplay Block Kit formatters

---

## WHAT WE'RE BUILDING

When a user runs `/coach roleplay [scenario]`, they currently get a text-based roleplay in a Slack thread. We're adding an option to do the roleplay as a **live voice conversation with a video avatar** — the AI buyer persona appears on screen, speaks out loud, listens to the rep's voice, and responds in character.

**Architecture:**

```
Slack (/coach roleplay) → Bot posts "Start Voice Roleplay" link
    → Rep clicks link → Opens a Next.js web app
        → Web app connects to HeyGen Streaming Avatar SDK (avatar video/audio)
        → Web app connects to our Python backend API (LLM responses)
        → Rep speaks → HeyGen STT transcribes → Sent to our backend
        → Backend runs continue_roleplay() → Returns buyer response text
        → Web app sends text to HeyGen avatar.speak(TaskType.REPEAT)
        → Avatar speaks the response with lip-sync
        → After 3-4 turns → Backend generates debrief → Posted back to Slack
```

**Two components to build:**
1. `avatar-roleplay/` — A Next.js web app (the video UI)
2. `avatar_api.py` — A Flask/FastAPI backend that wraps our existing LangGraph coach logic as HTTP endpoints

---

## COMPONENT 1: Python Backend API (`avatar_api.py`)

This is a lightweight HTTP server that exposes the existing `continue_roleplay()` and `roleplay_node()` logic as API endpoints. The Next.js frontend calls these.

### Create `avatar_api.py` in the project root:

```python
"""
Avatar Roleplay API — HTTP endpoints for the HeyGen voice roleplay frontend.
Wraps existing LangGraph coach logic so the Next.js app can call it.
"""
import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

api = Flask(__name__)
CORS(api)  # Allow cross-origin from the Next.js frontend

# Import existing coach logic
from graphs.coach import roleplay_node, continue_roleplay
from graphs import build_main_graph
from tools.rag import search as rag_search
from mcp_setup import get_mcp_tools_safe
import asyncio

# Load graph (same as app.py)
try:
    mcp_tools = asyncio.run(get_mcp_tools_safe())
except Exception:
    mcp_tools = []

app_graph = build_main_graph(mcp_tools)

# In-memory session store (same pattern as active_roleplays in app.py)
avatar_sessions = {}


@api.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@api.route("/api/roleplay/start", methods=["POST"])
def start_roleplay():
    """Start a new avatar roleplay session.

    Request body:
        scenario: str — e.g., "discovery call with CFO"

    Returns:
        session_id: str
        persona: dict — {name, title, company, personality, objections}
        opening_line: str — The buyer's first spoken line
    """
    data = request.json
    scenario = data.get("scenario", "discovery call")
    session_id = str(uuid.uuid4())

    # Run the roleplay_node to generate persona + opening line
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/coach roleplay {scenario}")],
        "route": "coach",
        "workflow": "roleplay",
        "user_id": "avatar_user",
        "channel_id": "avatar",
        "thread_ts": None,
    })

    ai_response = result["messages"][-1].content

    # Parse persona and opening line (split on "---")
    parts = ai_response.split("---", 1)
    persona_text = parts[0].strip() if len(parts) > 1 else ""
    opening_line = parts[1].strip() if len(parts) > 1 else ai_response.strip()

    # Parse persona details from text
    persona = parse_persona_from_text(persona_text)

    # Get RAG context for the session
    rag_context = rag_search(f"roleplay {scenario} objections sales")

    # Store session state (same structure as active_roleplays in app.py)
    avatar_sessions[session_id] = {
        "messages": result["messages"],
        "turn_count": 0,
        "scenario": scenario,
        "persona": persona,
        "rag_context": rag_context,
        "created_at": datetime.now().isoformat(),
    }

    return jsonify({
        "session_id": session_id,
        "persona": persona,
        "opening_line": opening_line,
    })


@api.route("/api/roleplay/respond", methods=["POST"])
def roleplay_respond():
    """Process the rep's spoken message and return the buyer's response.

    Request body:
        session_id: str
        message: str — The rep's transcribed speech

    Returns:
        response: str — The buyer's spoken response
        is_debrief: bool — Whether this is the final debrief
        debrief: dict|null — {score, strengths, improvements, next_practice} if is_debrief
        turn_count: int
    """
    data = request.json
    session_id = data.get("session_id")
    user_message = data.get("message", "")

    if session_id not in avatar_sessions:
        return jsonify({"error": "Session not found"}), 404

    session = avatar_sessions[session_id]
    session["turn_count"] += 1
    turn_count = session["turn_count"]

    # Use the existing continue_roleplay function
    result = continue_roleplay(
        state={
            "messages": session["messages"] + [HumanMessage(content=user_message)],
            "rag_context": session["rag_context"],
        },
        turn_count=turn_count,
    )

    ai_response = result["messages"][-1].content

    # Update stored messages
    session["messages"] = result["messages"]

    # Check if this is a debrief (turn 4+)
    is_debrief = turn_count >= 4
    debrief = None

    if is_debrief:
        debrief = parse_debrief_from_text(ai_response)
        # Clean up session
        del avatar_sessions[session_id]

    return jsonify({
        "response": ai_response,
        "is_debrief": is_debrief,
        "debrief": debrief,
        "turn_count": turn_count,
    })


@api.route("/api/roleplay/end", methods=["POST"])
def end_roleplay():
    """End a session early (user closes the avatar window)."""
    data = request.json
    session_id = data.get("session_id")
    if session_id in avatar_sessions:
        del avatar_sessions[session_id]
    return jsonify({"status": "ended"})


def parse_persona_from_text(text: str) -> dict:
    """Parse persona details from roleplay_node output."""
    persona = {
        "name": "Alex Johnson",
        "title": "VP of Operations",
        "company": "TechCorp",
        "personality": "Professional, detail-oriented",
        "objections": "Budget concerns, implementation timeline",
    }

    for line in text.split("\n"):
        line = line.strip().lstrip("•-* ")
        lower = line.lower()
        if lower.startswith("name:"):
            persona["name"] = line.split(":", 1)[1].strip()
        elif lower.startswith("title:"):
            persona["title"] = line.split(":", 1)[1].strip()
        elif lower.startswith("company"):
            persona["company"] = line.split(":", 1)[1].strip()
        elif lower.startswith("personality"):
            persona["personality"] = line.split(":", 1)[1].strip()
        elif lower.startswith("objection") or lower.startswith("hidden"):
            persona["objections"] = line.split(":", 1)[1].strip()

    return persona


def parse_debrief_from_text(text: str) -> dict:
    """Parse debrief details from the final roleplay response."""
    debrief = {
        "score": "N/A",
        "strengths": [],
        "improvements": [],
        "next_practice": "",
    }

    current_section = ""
    for line in text.split("\n"):
        stripped = line.strip()
        lower = stripped.lower()

        if "score" in lower and "/" in stripped:
            # Extract score like "7/10" or "Score: 8/10"
            import re
            match = re.search(r"(\d+)/10", stripped)
            if match:
                debrief["score"] = match.group(1)

        if "did well" in lower or "strength" in lower:
            current_section = "strengths"
            continue
        elif "improve" in lower or "area" in lower:
            current_section = "improvements"
            continue
        elif "recommend" in lower or "practice" in lower or "next" in lower:
            current_section = "next"
            continue

        cleaned = stripped.lstrip("•-*✅🔧📝 ")
        if not cleaned:
            continue

        if current_section == "strengths" and cleaned:
            debrief["strengths"].append(cleaned)
        elif current_section == "improvements" and cleaned:
            debrief["improvements"].append(cleaned)
        elif current_section == "next" and cleaned:
            debrief["next_practice"] = cleaned

    return debrief


if __name__ == "__main__":
    print("🎭 Avatar Roleplay API running on http://localhost:5001")
    api.run(host="0.0.0.0", port=5001, debug=True)
```

### Add to `requirements.txt`:

```
flask>=3.0.0
flask-cors>=4.0.0
```

Install: `pip install flask flask-cors --break-system-packages`

---

## COMPONENT 2: Next.js Avatar Frontend (`avatar-roleplay/`)

This is a standalone Next.js app that renders the HeyGen avatar and connects to our backend API.

### Project structure:

```
avatar-roleplay/
├── package.json
├── .env.local                  # HeyGen API key
├── next.config.js
├── tailwind.config.js
├── postcss.config.js
├── app/
│   ├── layout.tsx
│   ├── page.tsx                # Landing page with session setup
│   ├── session/
│   │   └── page.tsx            # The avatar video session page
│   ├── api/
│   │   └── get-access-token/
│   │       └── route.ts        # Server-side HeyGen token generation
│   └── globals.css
├── components/
│   ├── AvatarSession.tsx       # Main avatar component
│   ├── Debrief.tsx             # Debrief results overlay
│   └── SessionSetup.tsx        # Scenario selection form
└── lib/
    └── api.ts                  # Backend API client
```

### `package.json`:

```json
{
  "name": "avatar-roleplay",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3001",
    "build": "next build",
    "start": "next start -p 3001"
  },
  "dependencies": {
    "@heygen/streaming-avatar": "^2.0.0",
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0"
  }
}
```

### `.env.local`:

```
HEYGEN_API_KEY=your_heygen_api_key_here
NEXT_PUBLIC_BACKEND_URL=http://localhost:5001
```

### `app/api/get-access-token/route.ts` — Server-side token generation:

```typescript
import { NextResponse } from "next/server";

export async function POST() {
  try {
    const response = await fetch(
      "https://api.heygen.com/v1/streaming.create_token",
      {
        method: "POST",
        headers: {
          "x-api-key": process.env.HEYGEN_API_KEY!,
          "Content-Type": "application/json",
        },
      }
    );

    const data = await response.json();
    return NextResponse.json({ token: data.data.token });
  } catch (error) {
    console.error("Token generation error:", error);
    return NextResponse.json(
      { error: "Failed to generate token" },
      { status: 500 }
    );
  }
}
```

### `lib/api.ts` — Backend API client:

```typescript
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5001";

export interface Persona {
  name: string;
  title: string;
  company: string;
  personality: string;
  objections: string;
}

export interface StartResponse {
  session_id: string;
  persona: Persona;
  opening_line: string;
}

export interface RespondResponse {
  response: string;
  is_debrief: boolean;
  debrief: {
    score: string;
    strengths: string[];
    improvements: string[];
    next_practice: string;
  } | null;
  turn_count: number;
}

export async function startRoleplay(scenario: string): Promise<StartResponse> {
  const res = await fetch(`${BACKEND_URL}/api/roleplay/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario }),
  });
  return res.json();
}

export async function sendMessage(
  sessionId: string,
  message: string
): Promise<RespondResponse> {
  const res = await fetch(`${BACKEND_URL}/api/roleplay/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  return res.json();
}

export async function endRoleplay(sessionId: string): Promise<void> {
  await fetch(`${BACKEND_URL}/api/roleplay/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}
```

### `components/AvatarSession.tsx` — Main avatar component:

This is the core component. It connects to HeyGen, renders the avatar video, captures user speech, sends it to our backend, and makes the avatar speak the response.

```tsx
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import StreamingAvatar, {
  AvatarQuality,
  StreamingEvents,
  TaskType,
  VoiceChatTransport,
  STTProvider,
} from "@heygen/streaming-avatar";
import { sendMessage, endRoleplay, type Persona, type RespondResponse } from "@/lib/api";
import Debrief from "./Debrief";

interface AvatarSessionProps {
  sessionId: string;
  persona: Persona;
  openingLine: string;
  scenario: string;
}

export default function AvatarSession({
  sessionId,
  persona,
  openingLine,
  scenario,
}: AvatarSessionProps) {
  const avatarRef = useRef<StreamingAvatar | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isAvatarSpeaking, setIsAvatarSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [turnCount, setTurnCount] = useState(0);
  const [statusText, setStatusText] = useState("Connecting to avatar...");
  const [debrief, setDebrief] = useState<RespondResponse["debrief"] | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Initialize HeyGen avatar
  const initAvatar = useCallback(async () => {
    try {
      // 1. Get access token from our Next.js API route
      const tokenRes = await fetch("/api/get-access-token", { method: "POST" });
      const { token } = await tokenRes.json();

      // 2. Create StreamingAvatar instance
      const avatar = new StreamingAvatar({ token });
      avatarRef.current = avatar;

      // 3. Register event handlers
      avatar.on(StreamingEvents.STREAM_READY, (event: any) => {
        if (videoRef.current && event.detail) {
          videoRef.current.srcObject = event.detail;
          videoRef.current.onloadedmetadata = () => {
            videoRef.current?.play();
          };
        }
        setIsConnected(true);
        setStatusText(`Speaking with ${persona.name}...`);
      });

      avatar.on(StreamingEvents.STREAM_DISCONNECTED, () => {
        setIsConnected(false);
        setStatusText("Disconnected");
      });

      avatar.on(StreamingEvents.AVATAR_START_TALKING, () => {
        setIsAvatarSpeaking(true);
      });

      avatar.on(StreamingEvents.AVATAR_STOP_TALKING, () => {
        setIsAvatarSpeaking(false);
      });

      // 4. Handle user speech transcription
      // When the user finishes speaking, HeyGen transcribes it
      // We intercept this and send to OUR backend instead of HeyGen's built-in LLM
      avatar.on(StreamingEvents.USER_END_MESSAGE, async (event: any) => {
        const userMessage = event.detail?.message;
        if (!userMessage || isProcessing) return;

        setIsProcessing(true);
        setStatusText("Thinking...");

        try {
          // Send transcribed speech to our Python backend
          const result = await sendMessage(sessionId, userMessage);
          setTurnCount(result.turn_count);

          if (result.is_debrief) {
            // Show debrief UI instead of avatar speaking
            setDebrief(result.debrief);
            setStatusText("Session complete!");
            await avatar.stopAvatar();
          } else {
            // Make the avatar speak the buyer's response
            setStatusText(`${persona.name} is responding...`);
            await avatar.speak({
              text: result.response,
              taskType: TaskType.REPEAT,
            });
          }
        } catch (error) {
          console.error("Error processing response:", error);
          setStatusText("Error — try speaking again");
        } finally {
          setIsProcessing(false);
        }
      });

      // 5. Start the avatar session
      // Use a public avatar ID — pick one from labs.heygen.com/interactive-avatar
      await avatar.createStartAvatar({
        quality: AvatarQuality.Medium,
        avatarName: "default",  // Replace with a specific avatar ID
        voice: {
          voiceId: "",  // Use default voice, or pick from HeyGen voice list
          rate: 1.0,
        },
        language: "en",
        disableIdleTimeout: true,
      });

      // 6. Enable voice chat (microphone capture + STT)
      await avatar.startVoiceChat({
        useSilencePrompt: false,
        transport: VoiceChatTransport.WEBSOCKET,
        sttProvider: STTProvider.DEEPGRAM,
      });
      setIsListening(true);

      // 7. Avatar speaks the opening line (buyer's first message)
      setTimeout(async () => {
        await avatar.speak({
          text: openingLine,
          taskType: TaskType.REPEAT,
        });
      }, 1500);

    } catch (error) {
      console.error("Avatar init error:", error);
      setStatusText("Failed to connect — check your HeyGen API key");
    }
  }, [sessionId, persona, openingLine, isProcessing]);

  useEffect(() => {
    initAvatar();

    return () => {
      // Cleanup on unmount
      if (avatarRef.current) {
        avatarRef.current.stopAvatar();
      }
      endRoleplay(sessionId);
    };
  }, []);

  const handleEndSession = async () => {
    if (avatarRef.current) {
      await avatarRef.current.stopAvatar();
    }
    await endRoleplay(sessionId);
    setIsConnected(false);
    setStatusText("Session ended");
  };

  const handleInterrupt = async () => {
    if (avatarRef.current) {
      await avatarRef.current.interrupt();
    }
  };

  // Show debrief overlay if session is complete
  if (debrief) {
    return <Debrief debrief={debrief} scenario={scenario} persona={persona} />;
  }

  return (
    <div className="flex flex-col items-center gap-4 p-6 bg-gray-900 min-h-screen text-white">
      {/* Persona info bar */}
      <div className="w-full max-w-2xl bg-gray-800 rounded-lg p-4">
        <h2 className="text-xl font-bold">{persona.name}</h2>
        <p className="text-gray-400">
          {persona.title} at {persona.company}
        </p>
        <p className="text-sm text-gray-500 mt-1">
          Scenario: {scenario} • Turn {turnCount}/4
        </p>
      </div>

      {/* Avatar video */}
      <div className="relative w-full max-w-2xl aspect-video bg-black rounded-xl overflow-hidden">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          className="w-full h-full object-cover"
        />

        {/* Speaking indicator */}
        {isAvatarSpeaking && (
          <div className="absolute top-4 right-4 bg-green-500 text-white text-xs px-3 py-1 rounded-full animate-pulse">
            Speaking...
          </div>
        )}

        {/* Processing indicator */}
        {isProcessing && (
          <div className="absolute top-4 left-4 bg-blue-500 text-white text-xs px-3 py-1 rounded-full animate-pulse">
            Thinking...
          </div>
        )}

        {/* Listening indicator */}
        {isListening && !isAvatarSpeaking && !isProcessing && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-red-500 text-white text-xs px-3 py-1 rounded-full animate-pulse">
            🎤 Listening — speak now
          </div>
        )}
      </div>

      {/* Status bar */}
      <p className="text-gray-400 text-sm">{statusText}</p>

      {/* Controls */}
      <div className="flex gap-3">
        <button
          onClick={handleInterrupt}
          className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 rounded-lg text-sm"
          disabled={!isAvatarSpeaking}
        >
          Interrupt
        </button>
        <button
          onClick={handleEndSession}
          className="px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-sm"
        >
          End Session
        </button>
      </div>
    </div>
  );
}
```

### `components/Debrief.tsx` — Debrief overlay after session ends:

```tsx
"use client";

import type { Persona } from "@/lib/api";

interface DebriefProps {
  debrief: {
    score: string;
    strengths: string[];
    improvements: string[];
    next_practice: string;
  };
  scenario: string;
  persona: Persona;
}

export default function Debrief({ debrief, scenario, persona }: DebriefProps) {
  const score = parseInt(debrief.score) || 0;
  const level =
    score >= 8 ? "Excellent" : score >= 6 ? "Good, room to grow" : "Needs work";

  return (
    <div className="flex flex-col items-center gap-6 p-8 bg-gray-900 min-h-screen text-white">
      <div className="w-full max-w-xl bg-gray-800 rounded-xl p-6">
        <h1 className="text-2xl font-bold mb-2">🎯 Roleplay Debrief</h1>
        <p className="text-gray-400 mb-4">
          {scenario} with {persona.name} ({persona.title})
        </p>

        {/* Score */}
        <div className="bg-gray-700 rounded-lg p-4 mb-4 text-center">
          <p className="text-4xl font-bold">{debrief.score}/10</p>
          <p className="text-gray-400">{level}</p>
        </div>

        {/* Strengths */}
        <div className="mb-4">
          <h3 className="font-semibold text-green-400 mb-2">
            ✅ What You Did Well
          </h3>
          <ul className="space-y-1">
            {debrief.strengths.map((s, i) => (
              <li key={i} className="text-sm text-gray-300">• {s}</li>
            ))}
          </ul>
        </div>

        {/* Improvements */}
        <div className="mb-4">
          <h3 className="font-semibold text-yellow-400 mb-2">
            🔧 Areas to Improve
          </h3>
          <ul className="space-y-1">
            {debrief.improvements.map((s, i) => (
              <li key={i} className="text-sm text-gray-300">• {s}</li>
            ))}
          </ul>
        </div>

        {/* Next Practice */}
        {debrief.next_practice && (
          <div className="mb-4">
            <h3 className="font-semibold text-blue-400 mb-2">
              📝 Recommended Practice
            </h3>
            <p className="text-sm text-gray-300">{debrief.next_practice}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 mt-6">
          <button
            onClick={() => window.location.reload()}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm"
          >
            Practice Again
          </button>
          <button
            onClick={() => window.close()}
            className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg text-sm"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
```

### `components/SessionSetup.tsx` — Scenario selection:

```tsx
"use client";

import { useState } from "react";
import { startRoleplay, type StartResponse } from "@/lib/api";

interface SessionSetupProps {
  onSessionStart: (data: StartResponse & { scenario: string }) => void;
}

const SCENARIOS = [
  { label: "Discovery Call", value: "discovery call with a VP" },
  { label: "Pricing Objection", value: "pricing objection from a CFO" },
  { label: "Competitive Deal", value: "deal where they're evaluating a competitor" },
  { label: "Cold Call", value: "cold call to VP of Engineering" },
  { label: "Renewal Negotiation", value: "renewal negotiation with existing customer" },
];

export default function SessionSetup({ onSessionStart }: SessionSetupProps) {
  const [selectedScenario, setSelectedScenario] = useState(SCENARIOS[0].value);
  const [customScenario, setCustomScenario] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleStart = async () => {
    setIsLoading(true);
    const scenario = customScenario || selectedScenario;

    try {
      const result = await startRoleplay(scenario);
      onSessionStart({ ...result, scenario });
    } catch (error) {
      console.error("Failed to start session:", error);
      alert("Failed to start session. Is the backend running on port 5001?");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white p-8">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold mb-2">🎭 Voice Roleplay</h1>
        <p className="text-gray-400 mb-8">
          Practice sales conversations with an AI avatar. Choose a scenario to start.
        </p>

        {/* Scenario selection */}
        <div className="space-y-3 mb-6">
          {SCENARIOS.map((s) => (
            <button
              key={s.value}
              onClick={() => {
                setSelectedScenario(s.value);
                setCustomScenario("");
              }}
              className={`w-full text-left px-4 py-3 rounded-lg transition ${
                selectedScenario === s.value && !customScenario
                  ? "bg-blue-600 border-blue-400 border"
                  : "bg-gray-800 border-gray-700 border hover:bg-gray-700"
              }`}
            >
              {s.label}
              <span className="block text-sm text-gray-400 mt-1">{s.value}</span>
            </button>
          ))}
        </div>

        {/* Custom scenario input */}
        <div className="mb-6">
          <input
            type="text"
            placeholder="Or type a custom scenario..."
            value={customScenario}
            onChange={(e) => setCustomScenario(e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Start button */}
        <button
          onClick={handleStart}
          disabled={isLoading}
          className="w-full px-6 py-4 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 rounded-lg text-lg font-semibold transition"
        >
          {isLoading ? "Starting session..." : "🎤 Start Voice Roleplay"}
        </button>

        <p className="text-gray-500 text-xs mt-4 text-center">
          You'll need a microphone. The session lasts 3-4 turns, then you'll get a scored debrief.
        </p>
      </div>
    </div>
  );
}
```

### `app/page.tsx` — Main page:

```tsx
"use client";

import { useState } from "react";
import SessionSetup from "@/components/SessionSetup";
import AvatarSession from "@/components/AvatarSession";
import type { StartResponse } from "@/lib/api";

export default function Home() {
  const [sessionData, setSessionData] = useState<
    (StartResponse & { scenario: string }) | null
  >(null);

  if (!sessionData) {
    return <SessionSetup onSessionStart={setSessionData} />;
  }

  return (
    <AvatarSession
      sessionId={sessionData.session_id}
      persona={sessionData.persona}
      openingLine={sessionData.opening_line}
      scenario={sessionData.scenario}
    />
  );
}
```

### `app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SalesCoach AI — Voice Roleplay",
  description: "Practice sales conversations with an AI avatar",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

### `app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### `tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: { extend: {} },
  plugins: [],
};
```

### `postcss.config.js`:

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

### `next.config.js`:

```js
/** @type {import('next').NextConfig} */
const nextConfig = {};
module.exports = nextConfig;
```

### `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

---

## COMPONENT 3: Update `app.py` — Add "Start Voice Roleplay" Button

Add a new option in the `/coach` command handler and a button in the roleplay start formatter.

### In `app.py` — update `handle_coach()`:

When the workflow is "roleplay", add an extra message with a button to launch the voice session:

```python
# After posting the existing text-based roleplay start message, also post:
avatar_url = f"http://localhost:3001?scenario={scenario}"
say(
    text="🎭 Want to practice with voice instead?",
    blocks=[
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🎭 *Voice Roleplay Available*\nPractice this scenario face-to-face with an AI avatar. Uses your microphone for a realistic conversation.",
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Voice Session", "emoji": True},
                "url": avatar_url,
                "action_id": "open_avatar_session",
            }
        },
    ],
    channel=channel_id,
)
```

Note: The button uses `"url"` instead of `"value"` — this makes it a link button that opens the web app in the browser.

### Register a no-op handler for the link button:

```python
@app.action("open_avatar_session")
def handle_open_avatar(ack):
    """No-op — the button opens a URL, no server action needed."""
    ack()
```

---

## HOW TO RUN

### Terminal 1 — Slack bot (existing):
```bash
python app.py
```

### Terminal 2 — Avatar API backend:
```bash
python avatar_api.py
```

### Terminal 3 — Avatar frontend:
```bash
cd avatar-roleplay
npm install
npm run dev
```

Then in Slack: `/coach roleplay discovery call` → click "Start Voice Session" → browser opens → avatar appears → start talking.

---

## ENVIRONMENT VARIABLES NEEDED

### Existing `.env` (add nothing new):
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `OPENROUTER_API_KEY`, etc. — already set

### `avatar-roleplay/.env.local` (NEW):
```
HEYGEN_API_KEY=your_heygen_enterprise_api_key
NEXT_PUBLIC_BACKEND_URL=http://localhost:5001
```

### How to get the HeyGen API key:
1. Go to https://app.heygen.com/settings → API section
2. Copy your API key (Enterprise) or Trial Token (free, limited to 3 sessions, 10-min timeout)
3. For the POC demo, a Trial Token is fine

---

## THE FLOW (step by step)

1. Rep types `/coach roleplay pricing objection` in Slack
2. Bot posts the normal text-based roleplay start + a "Start Voice Session" button
3. Rep clicks the button → browser opens `http://localhost:3001?scenario=pricing+objection`
4. Next.js app shows scenario selection (pre-filled from URL param) → rep clicks "Start"
5. Frontend calls `POST /api/roleplay/start` on our Python backend
6. Backend runs `roleplay_node()` → generates persona + opening line → returns JSON
7. Frontend connects to HeyGen streaming avatar (gets token, starts session)
8. Avatar appears on screen, speaks the opening line via `avatar.speak(TaskType.REPEAT)`
9. HeyGen enables microphone → rep speaks → Deepgram STT transcribes
10. `USER_END_MESSAGE` event fires → frontend sends transcribed text to `POST /api/roleplay/respond`
11. Backend runs `continue_roleplay()` → returns buyer response
12. Frontend calls `avatar.speak(TaskType.REPEAT)` → avatar speaks the response
13. Steps 9-12 repeat for 3-4 turns
14. On turn 4+, backend returns `is_debrief: true` → frontend shows debrief overlay
15. Avatar session stops → rep sees scored debrief with strengths/improvements

---

## GOTCHAS

1. **HeyGen API key types:**
   - **Trial Token**: Free, 3 concurrent sessions max, auto-closes after 10 minutes idle. Fine for POC demo.
   - **Enterprise API Key**: Required for production. Contact HeyGen sales.
   - You get the token at https://app.heygen.com/settings (API section)

2. **Avatar ID:** The code uses `"default"` for `avatarName`. Replace with a specific avatar ID from https://labs.heygen.com/interactive-avatar. Pick a professional-looking avatar for the demo.

3. **Voice ID:** Leave empty for default, or browse HeyGen's voice library and set a specific `voiceId` for the buyer persona. You could even match the voice to the persona gender/style.

4. **CORS:** The Flask backend has `CORS(api)` enabled. The Next.js frontend runs on port 3001, the backend on port 5001. If you get CORS errors, check that `flask-cors` is installed.

5. **Microphone permissions:** The browser will ask for microphone access. In the demo, approve it before the audience sees the screen.

6. **HeyGen STT provider:** The code uses Deepgram for speech-to-text. It's built into HeyGen's SDK — no additional Deepgram API key needed.

7. **`TaskType.REPEAT`** is the key to "bring your own LLM." Instead of HeyGen using its built-in LLM, the avatar just repeats whatever text we send. Our LangGraph coach generates the content, HeyGen just provides the face and voice.

8. **Session cleanup:** The `useEffect` cleanup function calls `endRoleplay()` and `stopAvatar()` when the component unmounts (browser tab closes). This prevents orphaned HeyGen sessions.

9. **The text-based roleplay still works.** The voice option is additive — reps can choose either. The "Start Voice Session" button appears alongside the existing text roleplay.

10. **No new Slack slash commands needed.** This uses the existing `/coach roleplay` command + a link button.

---

## DO NOT

- Do NOT modify `graphs/coach.py` or `prompts/coach_prompts.py` — the avatar backend wraps the existing logic
- Do NOT modify the existing text-based roleplay flow — voice is additive
- Do NOT hardcode the HeyGen API key in client-side code — it goes in `.env.local` and is accessed server-side only
- Do NOT use HeyGen's built-in LLM — always use `TaskType.REPEAT` with our own LangGraph responses

## DO

- Test the Python backend independently first: `curl -X POST http://localhost:5001/api/roleplay/start -H "Content-Type: application/json" -d '{"scenario":"discovery call"}'`
- Test the Next.js app connects to HeyGen: check the browser console for "STREAM_READY" event
- Pick a good-looking avatar from labs.heygen.com for the demo
- Practice the demo flow once before presenting — microphone permissions, avatar load time (~3-5 seconds), and network latency all need to work smoothly
