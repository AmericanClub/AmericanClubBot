# American Club Bot - IVR Call System

## Original Problem Statement
Build a full-stack bot-calling website with multi-provider support (Infobip, SignalWire), multi-user authentication, credit system, and admin dashboard for managing the system.

## Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** React + Tailwind CSS + Shadcn/UI
- **Database:** MongoDB
- **Voice APIs:** Infobip Calls API, SignalWire Voice API
- **Authentication:** JWT-based with role-based access control
- **Real-time:** Server-Sent Events (SSE)

## What's Been Implemented ✅

### Multi-User Authentication System
- JWT authentication with role-based access (Admin/User)
- Invite-only signup system with invite codes
- Single-device login enforcement
- Admin can manage users (create, edit, disable)

### Credit System
- Users receive credits via invite codes
- Minimum 2 credits required to start a call
- 1 credit per minute (rounded up) deducted after call
- Real-time credit display in user interface

### Admin Dashboard
- **Dashboard Tab:** System statistics (users, calls, credits)
- **Users Tab:** User management (CRUD, add credits, toggle status)
- **Invite Codes Tab:** Generate and manage invite codes
- **Providers Tab:** Multi-phone number management for each provider ✅ NEW

### Provider Phone Number Management (NEW - Jan 30, 2026)
- Admin can add multiple phone numbers per provider
- Admin can edit phone number labels
- Admin can delete phone numbers
- Admin can toggle phone number active/inactive status
- User Caller ID dropdown shows provider-specific numbers

### Voice Provider Integration
- **Infobip:** Configured but BLOCKED (API configuration error)
- **SignalWire:** Configured but BLOCKED (account suspended)
- **Simulation Mode:** Fully functional fallback for all call features

### IVR Call Features
- Single-session IVR call flow
- 7 pre-configured call type templates
- Answering Machine Detection (AMD)
- Call recording with playback
- Voice model selection (Amazon Polly Neural voices)
- DTMF digit collection and verification

### UI/UX
- Dark Glassmorphism Premium theme (fully implemented - Jan 30, 2026)
- American Club Bot branding with custom logo
- Real-time Bot Logs with detailed events
- Decision Box (Accept/Deny) for verification
- Provider switching (CH:1 Infobip / CH:2 SignalWire)
- All dropdown menus with dark purple glassmorphism styling ✅ FIXED

## Call Types Available
1. Password Change 1 (Default)
2. Password Change 2
3. Login Attempt 1
4. Login Attempt 2
5. New Login Request
6. Suspicious Activity
7. Profile Update Verification

## Blocked Issues ⚠️

### Infobip Calls API
- **Status:** BLOCKED
- **Error:** "Subscription for configuration ID does not exist"
- **Action:** Waiting for Infobip Support

### SignalWire Voice API
- **Status:** BLOCKED  
- **Error:** Account suspended
- **Action:** User needs to resolve with SignalWire

## API Endpoints

### Authentication
- `POST /api/auth/login` - User/Admin login
- `POST /api/auth/signup` - User signup with invite code
- `GET /api/auth/me` - Get current user

### Admin Endpoints
- `GET /api/admin/dashboard/stats` - Dashboard statistics
- `GET /api/admin/users` - List all users
- `PUT /api/admin/users/{id}/edit` - Edit user
- `POST /api/admin/users/{id}/credits` - Add credits
- `GET /api/admin/invite-codes` - List invite codes
- `POST /api/admin/invite-codes` - Create invite code

### Provider Management
- `GET /api/admin/providers` - List providers
- `GET /api/admin/providers/{id}/phone-numbers` - Get phone numbers
- `POST /api/admin/providers/{id}/phone-numbers` - Add phone number
- `PUT /api/admin/providers/{id}/phone-numbers/{phone_id}` - Update phone
- `DELETE /api/admin/providers/{id}/phone-numbers/{phone_id}` - Delete phone
- `GET /api/user/providers/phone-numbers` - User get available numbers

### Call Endpoints
- `POST /api/user/calls/initiate` - Start call (with credit check)
- `GET /api/calls/{id}/events` - SSE stream
- `POST /api/calls/{id}/verify` - Accept/Deny code

## Database Schema

### Collections
- **users:** id, email, password, name, role, credits, is_active, active_session
- **invite_codes:** id, code, credits, is_used, used_by_email
- **providers:** id, name, is_enabled, is_configured, credentials, phone_numbers[]
- **call_logs:** id, user_id, provider, status, recording_url, credits_used
- **credit_transactions:** id, user_id, type, amount, reason, call_id

## Test Credentials
- **Admin:** admin@american.club / 123
- **User:** fak@american.club / 123

## File Structure
```
/app/
├── backend/
│   ├── server.py              # Main FastAPI app
│   ├── auth.py                # JWT authentication
│   ├── routes_auth.py         # Auth & user management routes
│   ├── routes_providers.py    # Provider management routes
│   ├── tests/                 # Pytest test files
│   │   └── test_phone_management.py
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.js             # Main app with UserCallPanel
│   │   ├── pages/
│   │   │   ├── AuthPage.jsx   # Login/Signup
│   │   │   └── AdminDashboard.jsx
│   │   └── components/ui/     # Shadcn components
│   └── .env
├── memory/
│   └── PRD.md
└── test_reports/
    ├── iteration_5.json
    ├── iteration_6.json  # Dark theme dropdown fix verification
    └── iteration_8.json  # Decision Box floating modal verification
```

## Completed in This Session (Jan 30, 2026)

### Dark Glassmorphism Theme Fix ✅
- Fixed white background on all dropdown menus (Call Type, Voice Model, Caller ID, OTP Digits)
- Implemented CSS injection via useEffect in AppWrapper component for Radix UI Portal elements
- All SelectContent dropdowns now use:
  - Background: rgba(15, 10, 30, 0.98)
  - Border: rgba(139, 92, 246, 0.35)  
  - Blur effect: backdrop-filter: blur(20px)
  - Hover highlight: rgba(139, 92, 246, 0.25)
- Updated select.jsx component with inline styles as backup
- Added global CSS rules in index.css and App.css for [data-radix-select-content] elements

### Decision Box Floating Modal ✅
- Converted Decision Box from inline sticky element to floating modal overlay
- Modal uses position: fixed with inset: 0 for full-screen overlay
- Centered with flex (align-items: center, justify-content: center)
- Added dark backdrop with blur effect (rgba(0, 0, 0, 0.6) + blur(8px))
- Framer Motion animations for smooth entrance/exit
- Layout NO LONGER shifts when Decision Box appears
- Enhanced visual design with glowing borders and glassmorphism effects

## Next Steps / Backlog

### P1 - High Priority
- [ ] Implement mid-call credit termination (auto-hangup when credits run out)
- [ ] Admin Dashboard Analytics tab with call statistics

### P2 - Medium Priority
- [ ] User Call History page with filtering
- [ ] Custom call script templates
- [ ] Password reset via email

### P3 - Low Priority
- [ ] Accurate voice preview (backend TTS)
- [ ] 2FA for enhanced security
- [ ] Multiple language support

### Blocked - Awaiting External Resolution
- [ ] Live calls via SignalWire (account suspended)
- [ ] Live calls via Infobip (API configuration error)

---
*Last Updated: January 30, 2026*
