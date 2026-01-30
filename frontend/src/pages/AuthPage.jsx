import { useState } from "react";
import { motion } from "framer-motion";
import { Phone, Mail, Lock, User, Ticket, Loader2, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export default function AuthPage({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  
  // Form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [inviteCode, setInviteCode] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (isLogin) {
        // Login
        const response = await axios.post(`${API}/auth/login`, {
          email,
          password
        });
        
        const { access_token, user } = response.data;
        
        // Store token and user
        localStorage.setItem("token", access_token);
        localStorage.setItem("user", JSON.stringify(user));
        
        toast.success(`Welcome back, ${user.name}!`);
        onLogin(user, access_token);
      } else {
        // Signup
        if (!inviteCode) {
          toast.error("Invite code is required");
          setIsLoading(false);
          return;
        }
        
        const response = await axios.post(`${API}/auth/signup`, {
          email,
          password,
          name,
          invite_code: inviteCode
        });
        
        const { access_token, user } = response.data;
        
        // Store token and user
        localStorage.setItem("token", access_token);
        localStorage.setItem("user", JSON.stringify(user));
        
        toast.success(`Welcome, ${user.name}! You have ${user.credits} credits.`);
        onLogin(user, access_token);
      }
    } catch (error) {
      const message = error.response?.data?.detail || "Authentication failed";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-50 via-white to-purple-50 flex items-center justify-center p-4">
      {/* Background decorations */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-br from-violet-200/40 to-purple-200/40 rounded-full blur-3xl transform translate-x-1/3 -translate-y-1/3" />
        <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-gradient-to-tr from-cyan-200/30 to-teal-200/30 rounded-full blur-3xl transform -translate-x-1/3 translate-y-1/3" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-md"
      >
        {/* Logo/Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 mb-4 overflow-hidden shadow-lg shadow-violet-200">
            <img src="/logo.png" alt="American Club Bot" className="w-14 h-14 object-contain" />
          </div>
          <h1 className="text-2xl font-bold text-gray-800">American Club Bot</h1>
          <p className="text-gray-500 text-sm mt-1">
            {isLogin ? "Sign in to your account" : "Create your account"}
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-xl shadow-violet-100/50">
          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <>
                {/* Invite Code (Signup only) */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Invite Code *
                  </label>
                  <div className="relative">
                    <Ticket className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      type="text"
                      placeholder="Enter invite code"
                      value={inviteCode}
                      onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                      className="pl-10 bg-gray-50 border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-violet-500 focus:ring-violet-500/20 rounded-xl h-11"
                      required={!isLogin}
                      data-testid="invite-code-input"
                    />
                  </div>
                </div>

                {/* Name (Signup only) */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Full Name *
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      type="text"
                      placeholder="Enter your name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="pl-10 bg-gray-50 border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-violet-500 focus:ring-violet-500/20 rounded-xl h-11"
                      required={!isLogin}
                      data-testid="name-input"
                    />
                  </div>
                </div>
              </>
            )}

            {/* Email */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Email Address *
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 bg-gray-50 border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-violet-500 focus:ring-violet-500/20 rounded-xl h-11"
                  required
                  data-testid="email-input"
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Password *
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 pr-10 bg-gray-50 border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-violet-500 focus:ring-violet-500/20 rounded-xl h-11"
                  required
                  data-testid="password-input"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={isLoading}
              className="w-full bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white font-semibold py-3 mt-6 rounded-xl shadow-lg shadow-violet-200 h-12"
              data-testid="submit-btn"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              {isLogin ? "Sign In" : "Create Account"}
            </Button>
          </form>

          {/* Toggle Login/Signup */}
          <div className="mt-6 text-center">
            <p className="text-gray-500 text-sm">
              {isLogin ? "Don't have an account?" : "Already have an account?"}
              <button
                onClick={() => setIsLogin(!isLogin)}
                className="ml-2 text-violet-600 hover:text-violet-700 font-semibold"
                data-testid="toggle-auth-mode"
              >
                {isLogin ? "Sign up" : "Sign in"}
              </button>
            </p>
          </div>
        </div>

        {/* Footer note */}
        <p className="text-center text-gray-400 text-xs mt-6">
          {isLogin 
            ? "Sign in to access American Club dashboard" 
            : "Invite code required to create an account"}
        </p>
      </motion.div>
    </div>
  );
}
