# Bot Calling Application PRD

## Original Problem Statement
Build a bot calling website using Infobip provider with IVR (Interactive Voice Response) flow:
1. Step 1: Greeting + DTMF choice (Press 1 if suspicious, Press 0 if it was you)
2. Step 2: Ask for OTP security code
3. Step 3: Verification wait message
4. Accept/Reject based on code verification

## User Personas
- **Security Teams**: Users who need to verify suspicious account activities via voice calls
- **OTP Verification**: Companies requiring phone-based code verification

## Core Requirements (Static)
- Dark Mode Glassmorphism UI
- IVR flow with DTMF input collection
- 5 Call Steps: Step 1, Step 2, Step 3, Accepted, Rejected
- Real-time SSE logs with DTMF code display
- Copy functionality for security codes

## What's Been Implemented (January 29, 2025)

### Backend (FastAPI)
- [x] IVR call initiation endpoint
- [x] Multi-step IVR flow (Step 1 → Step 2 → Step 3 → Result)
- [x] DTMF webhook handlers for each step
- [x] SSE streaming for real-time events
- [x] Verify endpoint for manual Accept/Reject
- [x] Infobip Voice API integration (/tts/3/advanced)
- [x] Call history with DTMF codes

### Frontend (React)
- [x] Call Configuration form
- [x] Call Steps Configuration with 5 tabs (removed Message Scripts)
- [x] DTMF code display with copy button
- [x] Accept/Reject buttons after code received
- [x] Step progression indicator
- [x] Real-time log display with icons

## IVR Flow
```
Step 1 (Greeting)
├── Press 1: Continue to Step 2
└── Press 0: Continue to Step 2

Step 2 (Ask OTP Code)
└── User enters {digits}-digit code → Display in logs

Step 3 (Verification Wait)
└── Manual Accept/Reject

Accepted → Play accepted message → End call
Rejected → Play rejected message (retry option)
```

## Infobip Configuration
- **API Base URL**: 55v2qx.api.infobip.com
- **From Number**: +18085821342
- **Test Number**: +525547000906
- **API Endpoint**: /tts/3/advanced (with DTMF collection)

## Prioritized Backlog
### P0 (Critical) - COMPLETED
- [x] IVR flow with multi-step TTS
- [x] DTMF collection and display
- [x] Accept/Reject verification

### P1 (Important)
- [ ] Retry logic when code is rejected
- [ ] Voice preview functionality
- [ ] Export call logs

### P2 (Nice to Have)
- [ ] Batch calling
- [ ] Dashboard analytics
- [ ] Template management

## Next Tasks
1. Implement retry flow when code is rejected (loop back to Step 2)
2. Add voice preview functionality
3. Dashboard analytics for call statistics
