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
- Dark Navy Modern theme (fully implemented - Jan 30, 2026)
- American Club Bot branding with custom logo
- Real-time Bot Logs with detailed events (newest at top)
- Decision Box inline in Bot Logs panel (Accept/Deny)
- Provider switching (CH:1 Infobip / CH:2 SignalWire)
- All dropdown menus with dark navy styling
- Blue color scheme throughout (#3b82f6 primary)

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
- **users:** id, email, password, name, role, credits, is_active, active_session, **is_super_admin** (boolean for admin hierarchy)
- **invite_codes:** id, code, credits, is_used, used_by_email
- **providers:** id, name, is_enabled, is_configured, credentials, phone_numbers[]
- **call_logs:** id, user_id, provider, status, recording_url, credits_used
- **credit_transactions:** id, user_id, type, amount, reason, call_id

## Security Features ✅ (Jan 31, 2026)

### Layer 1: Rate Limiting
- Maximum 5 login attempts per minute per IP
- After exceeding limit, IP blocked for 5 minutes
- Automatically resets on successful login

### Layer 2: Math CAPTCHA (Security Check)
- Simple math questions: addition, subtraction, multiplication
- CAPTCHA expires after 5 minutes
- New CAPTCHA generated on each failed login
- Refresh button to get new question

### Layer 3: Honeypot Field
- Hidden field only bots will fill
- If filled, request silently rejected
- No user interaction needed

### Layer 4: Security Headers
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: geolocation=(), microphone=(), camera=()
- Content-Security-Policy: frame-ancestors 'none'
- Strict-Transport-Security: max-age=31536000

### Layer 5: Request Size Limiter
- Maximum request body: 1MB
- Prevents DoS via large payloads

### Layer 6: Input Validation & NoSQL Injection Prevention
- Sanitizes all input strings
- Detects and blocks NoSQL injection patterns ($where, $regex, $gt, etc.)
- Detects XSS patterns (<script>, javascript:, etc.)
- Logs suspicious activity

### Layer 7: Security Monitoring Dashboard (Super Admin)
- Real-time security event logs
- Statistics: High/Medium severity, Total events, Unique IPs
- Event types: login_success, login_failed, captcha_failed, rate_limit_exceeded
- Filter by severity and event type

### Implementation Files
- `/app/backend/security.py` - Rate limiting & CAPTCHA
- `/app/backend/security_advanced.py` - Headers, validation, logging
- `/app/frontend/src/pages/AuthPage.jsx` - Security Check UI
- `/app/frontend/src/pages/AdminDashboard.jsx` - Security Monitor tab

## Test Credentials
- **Super Admin:** admin@american.club / 123 (is_super_admin: true)
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
    ├── iteration_8.json  # Decision Box floating modal verification
    └── iteration_9.json  # Decision Box inline + log order reversal
```

## Completed in This Session (Jan 31, 2026)

### User Panel UI Verified & Header Styling Enhanced ✅
- Verified User Panel (`App.js`) is functioning correctly
- **Header Premium Glass Morphism Styling:**
  - Gradient accent strip animasi di atas header
  - Glass morphism dengan backdrop blur 24px
  - Double border dengan inner glow line
  - Logo dengan subtle glow effect (blur 4px)
  - Credits box dengan hover scale effect
  - User info dalam glass container
  - Shadow dramatis dengan multiple layers
- Bot Logs panel dengan status indicator, History/Clear buttons
- Voice Bot Control dengan semua konfigurasi
- All components render correctly with Dark Navy Modern theme

## Completed in Previous Session (Jan 30, 2026)

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

### Decision Box Restructure ✅
- Moved Decision Box from floating modal to INLINE sticky element inside Bot Logs panel
- Decision Box only appears when there's a code to verify (no placeholder)
- Smooth animation: scale 0.95->1, opacity 0->1, y -10->0 (300ms)
- Layout NO LONGER shifts when Decision Box appears

### Log Order Reversal ✅
- Logs now display NEWEST at TOP, OLDEST at bottom
- Users can see the most recent events without scrolling
- Implemented using [...logs].reverse()

### Theme Change to Dark Navy Modern ✅ (Jan 30, 2026)
- Complete theme overhaul from purple glassmorphism to blue navy modern
- Applied to all pages: Login, User Panel, Admin Dashboard
- Color scheme: Primary #3b82f6 (blue), Background #0a0e1a (dark navy)
- Blue gradient accent on left side of pages
- Clean, professional look matching fintech reference design
- All purple colors replaced with blue equivalents

### Multi-Admin System ✅ (Jan 30, 2026)
- Super Admin can create new admins (non-super admin by default)
- Super Admin can change their own password via sidebar button
- Create Admin modal with name, email, password fields
- Change Password modal with current/new/confirm password fields
- Buttons only visible for Super Admin (hidden for regular users and non-super admins)
- Backend protection: only super admin can call create-admin endpoint
- Super Admin cannot be deleted by anyone

## Test Credentials
- **Super Admin:** admin@american.club / 123 (is_super_admin: true)
- **User:** fak@american.club / 123

## API Endpoints

### Authentication
- `POST /api/auth/login` - User/Admin login (returns is_super_admin for admins)
- `POST /api/auth/signup` - User signup with invite code
- `GET /api/auth/me` - Get current user (returns is_super_admin for admins)
- `PUT /api/auth/change-password` - Change own password (query params: old_password, new_password)

### Admin Endpoints
- `GET /api/admin/dashboard/stats` - Dashboard statistics
- `GET /api/admin/users` - List all users
- `PUT /api/admin/users/{id}/edit` - Edit user
- `POST /api/admin/users/{id}/credits` - Add credits
- `DELETE /api/admin/users/{id}` - Delete user (Super Admin can delete admins)
- `POST /api/admin/create-admin` - Create new admin (Super Admin only)
- `GET /api/admin/invite-codes` - List invite codes
- `POST /api/admin/invite-codes` - Create invite code

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
*Last Updated: January 30, 2026 - Multi-Admin System implemented*
