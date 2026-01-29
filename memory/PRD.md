# Bot Calling Application PRD

## Original Problem Statement
Build a bot calling website using Infobip provider with:
1. Futuristic Glassmorphism UI/UX with Dark Mode theme
2. Two column layout: Bot Logs (left) and Call Setup (right)
3. Real-time logs via SSE with timestamp, event name, details
4. Call/Hang Up button with glow effects and state transformation

## User Personas
- **Business Operators**: Users who need to make automated outbound voice calls for verification, OTP delivery, or reminders
- **Service Providers**: Companies requiring voice bot integration for customer communication

## Core Requirements (Static)
- Dark Mode with Deep Navy gradient background
- Glassmorphism panels with backdrop blur effects
- Monospace font (JetBrains Mono) for logs and inputs
- Two-column responsive layout
- Real-time SSE for call events
- Call flow: PENDING → CALLING → RINGING → ESTABLISHED → FINISHED

## What's Been Implemented (January 29, 2025)
### Backend (FastAPI)
- [x] Call initiation endpoint (POST /api/calls/initiate)
- [x] Call hangup endpoint (POST /api/calls/{id}/hangup)
- [x] SSE streaming endpoint (GET /api/calls/{id}/events)
- [x] Webhook handler for Infobip events (POST /api/webhook/call-events)
- [x] Voice models and call types endpoints
- [x] MongoDB integration for call logs
- [x] Simulated call flow (mock Infobip integration)

### Frontend (React)
- [x] Futuristic Glassmorphism design
- [x] Bot Logs panel with real-time SSE updates
- [x] Call Configuration form (Call Type, Voice Model, Numbers, etc.)
- [x] Message Scripts section (Greetings, Prompt, Retry, End Message)
- [x] Call Steps Configuration with tabs
- [x] Start Call / Hang Up button with animations
- [x] Status indicator with pulse animation
- [x] Clear Logs functionality

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui + Framer Motion
- **Backend**: FastAPI + MongoDB
- **Real-time**: Server-Sent Events (SSE)
- **Voice Provider**: Infobip (MOCKED - awaiting API credentials)

## Prioritized Backlog
### P0 (Critical - Next Session)
- [ ] Integrate actual Infobip API when credentials provided
- [ ] Add error handling for API failures

### P1 (Important)
- [ ] Call history panel with past calls
- [ ] Voice preview functionality
- [ ] Export logs feature

### P2 (Nice to Have)
- [ ] Dashboard analytics
- [ ] Batch calling feature
- [ ] Template management for scripts

## API Credentials Required
- **INFOBIP_API_KEY**: Required for actual voice calls
- **INFOBIP_BASE_URL**: Provider's API base URL

## Next Tasks
1. User provides Infobip API Key and Base URL
2. Replace mock call simulation with real Infobip API calls
3. Add call history panel
4. Implement voice preview feature
