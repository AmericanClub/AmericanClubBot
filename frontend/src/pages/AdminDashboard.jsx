import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Users, 
  Ticket, 
  Settings, 
  BarChart3, 
  LogOut,
  Plus,
  Copy,
  Check,
  Trash2,
  ChevronRight,
  CreditCard,
  Phone,
  RefreshCw,
  Search,
  MoreVertical,
  UserCheck,
  UserX,
  Coins,
  Edit,
  Key,
  Mail,
  User as UserIcon,
  Shield,
  Lock,
  ShieldAlert,
  Activity,
  AlertTriangle,
  Eye
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export default function AdminDashboard({ user, token, onLogout }) {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [inviteCodes, setInviteCodes] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  // Use user prop to determine if super admin (set immediately on load)
  const isSuperAdmin = user?.is_super_admin || false;
  
  // Security logs state (Super Admin only)
  const [securityLogs, setSecurityLogs] = useState([]);
  const [securityStats, setSecurityStats] = useState(null);
  const [seenAlertIds, setSeenAlertIds] = useState(() => {
    // Load seen alerts from localStorage
    const saved = localStorage.getItem('seenSecurityAlerts');
    return saved ? JSON.parse(saved) : [];
  });
  
  // Modal states
  const [showCreateCode, setShowCreateCode] = useState(false);
  const [showAddCredits, setShowAddCredits] = useState(false);
  const [showEditUser, setShowEditUser] = useState(false);
  const [showCreateAdmin, setShowCreateAdmin] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  
  // Form states
  const [newCodeCredits, setNewCodeCredits] = useState(50);
  const [newCodeNotes, setNewCodeNotes] = useState("");
  const [creditAmount, setCreditAmount] = useState(10);
  const [creditReason, setCreditReason] = useState("");
  
  // Edit user form states
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPassword, setEditPassword] = useState("");
  
  // Create admin form states
  const [newAdminName, setNewAdminName] = useState("");
  const [newAdminEmail, setNewAdminEmail] = useState("");
  const [newAdminPassword, setNewAdminPassword] = useState("");
  
  // Change password modal state
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  
  // Search states
  const [userSearch, setUserSearch] = useState("");
  const [securitySearch, setSecuritySearch] = useState("");
  
  const authHeaders = { Authorization: `Bearer ${token}` };

  // Fetch dashboard stats
  const fetchStats = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/dashboard/stats`, { headers: authHeaders });
      setStats(response.data);
    } catch (error) {
      console.error("Error fetching stats:", error);
    }
  }, [token]);

  // Fetch users
  const fetchUsers = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/users`, { headers: authHeaders });
      setUsers(response.data.users);
    } catch (error) {
      console.error("Error fetching users:", error);
    }
  }, [token]);

  // Fetch invite codes
  const fetchInviteCodes = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/invite-codes`, { headers: authHeaders });
      setInviteCodes(response.data.codes);
    } catch (error) {
      console.error("Error fetching invite codes:", error);
    }
  }, [token]);

  // Fetch security logs (Super Admin only)
  const fetchSecurityLogs = useCallback(async () => {
    if (!isSuperAdmin) return;
    try {
      const [logsRes, statsRes] = await Promise.all([
        axios.get(`${API}/security/logs?limit=50`, { headers: authHeaders }),
        axios.get(`${API}/security/stats`, { headers: authHeaders })
      ]);
      setSecurityLogs(logsRes.data.logs);
      setSecurityStats(statsRes.data);
    } catch (error) {
      console.error("Error fetching security logs:", error);
    }
  }, [token, isSuperAdmin]);

  // Create new admin
  const handleCreateAdmin = async () => {
    if (!newAdminName || !newAdminEmail || !newAdminPassword) {
      toast.error("All fields are required");
      return;
    }
    
    setIsLoading(true);
    try {
      await axios.post(`${API}/admin/create-admin`, {
        name: newAdminName,
        email: newAdminEmail,
        password: newAdminPassword
      }, { headers: authHeaders });
      
      toast.success(`Admin ${newAdminName} created successfully!`);
      setShowCreateAdmin(false);
      setNewAdminName("");
      setNewAdminEmail("");
      setNewAdminPassword("");
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create admin");
    }
    setIsLoading(false);
  };

  // Change password (for Super Admin)
  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast.error("All fields are required");
      return;
    }
    
    if (newPassword !== confirmPassword) {
      toast.error("New passwords do not match");
      return;
    }
    
    if (newPassword.length < 4) {
      toast.error("Password must be at least 4 characters");
      return;
    }
    
    setIsLoading(true);
    try {
      await axios.put(`${API}/auth/change-password?old_password=${encodeURIComponent(currentPassword)}&new_password=${encodeURIComponent(newPassword)}`, {}, { headers: authHeaders });
      
      toast.success("Password changed successfully!");
      setShowChangePassword(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to change password");
    }
    setIsLoading(false);
  };

  useEffect(() => {
    fetchStats();
    fetchUsers();
    fetchInviteCodes();
    // Fetch security logs on initial load for Super Admin
    if (isSuperAdmin) {
      fetchSecurityLogs();
    }
  }, [fetchStats, fetchUsers, fetchInviteCodes, fetchSecurityLogs, isSuperAdmin]);

  // Auto-refresh all data every 15 seconds based on active tab
  useEffect(() => {
    const interval = setInterval(() => {
      // Always refresh security logs for Super Admin (for badge updates)
      if (isSuperAdmin) {
        fetchSecurityLogs();
      }
      
      // Refresh data based on active tab
      switch (activeTab) {
        case 'dashboard':
          fetchStats();
          break;
        case 'users':
          fetchUsers();
          break;
        case 'invite-codes':
          fetchInviteCodes();
          break;
        // providers tab has its own refresh in ProvidersTab component
        default:
          break;
      }
    }, 15000); // 15 seconds
    
    return () => clearInterval(interval);
  }, [activeTab, isSuperAdmin, fetchStats, fetchUsers, fetchInviteCodes, fetchSecurityLogs]);

  // Get dangerous events for dashboard (high/medium severity, excluding success events and already seen)
  const dangerousEvents = securityLogs.filter(log => 
    (log.severity === 'high' || log.severity === 'medium' || log.severity === 'critical') &&
    !log.event_type.includes('success') &&
    !log.event_type.includes('cleared') &&
    !seenAlertIds.includes(log.id)
  ).slice(0, 5);

  // Count high severity events for badge (only unseen)
  const highSeverityCount = securityLogs.filter(log => 
    (log.severity === 'high' || log.severity === 'critical') &&
    !log.event_type.includes('success') &&
    !seenAlertIds.includes(log.id)
  ).length;

  // Filtered users based on search
  const filteredUsers = users.filter(user => {
    if (!userSearch) return true;
    const search = userSearch.toLowerCase();
    return (
      user.name?.toLowerCase().includes(search) ||
      user.email?.toLowerCase().includes(search) ||
      user.role?.toLowerCase().includes(search)
    );
  });

  // Filtered security logs based on search
  const filteredSecurityLogs = securityLogs.filter(log => {
    if (!securitySearch) return true;
    const search = securitySearch.toLowerCase();
    return (
      log.event_type?.toLowerCase().includes(search) ||
      log.ip?.toLowerCase().includes(search) ||
      log.severity?.toLowerCase().includes(search) ||
      log.details?.email?.toLowerCase().includes(search)
    );
  });

  // Mark all current dangerous alerts as seen
  const markAlertsAsSeen = () => {
    const dangerousIds = securityLogs
      .filter(log => 
        (log.severity === 'high' || log.severity === 'medium' || log.severity === 'critical') &&
        !log.event_type.includes('success') &&
        !log.event_type.includes('cleared')
      )
      .map(log => log.id);
    
    const newSeenIds = [...new Set([...seenAlertIds, ...dangerousIds])];
    setSeenAlertIds(newSeenIds);
    localStorage.setItem('seenSecurityAlerts', JSON.stringify(newSeenIds));
  };

  // Create invite code
  const handleCreateCode = async () => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${API}/admin/invite-codes`, {
        credits: newCodeCredits,
        notes: newCodeNotes
      }, { headers: authHeaders });
      
      toast.success(`Invite code created: ${response.data.code}`);
      setShowCreateCode(false);
      setNewCodeCredits(50);
      setNewCodeNotes("");
      fetchInviteCodes();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create code");
    } finally {
      setIsLoading(false);
    }
  };

  // Delete invite code
  const handleDeleteCode = async (codeId) => {
    try {
      await axios.delete(`${API}/admin/invite-codes/${codeId}`, { headers: authHeaders });
      toast.success("Invite code deleted");
      fetchInviteCodes();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to delete code");
    }
  };

  // Toggle user active status
  const handleToggleUser = async (userId) => {
    try {
      const response = await axios.put(`${API}/admin/users/${userId}/toggle-active`, {}, { headers: authHeaders });
      toast.success(response.data.message);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update user");
    }
  };

  // Delete user
  const handleDeleteUser = async (userId) => {
    if (!window.confirm("Are you sure you want to delete this user? This action cannot be undone.")) return;
    
    try {
      const response = await axios.delete(`${API}/admin/users/${userId}`, { headers: authHeaders });
      toast.success(response.data.message);
      fetchUsers();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to delete user");
    }
  };

  // Add credits to user
  const handleAddCredits = async () => {
    if (!selectedUser) return;
    setIsLoading(true);
    try {
      await axios.post(`${API}/admin/users/${selectedUser.id}/credits`, {
        amount: creditAmount,
        reason: creditReason || "Admin top-up"
      }, { headers: authHeaders });
      
      toast.success(`Added ${creditAmount} credits to ${selectedUser.name}`);
      setShowAddCredits(false);
      setSelectedUser(null);
      setCreditAmount(10);
      setCreditReason("");
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to add credits");
    } finally {
      setIsLoading(false);
    }
  };

  // Edit user (name, email, password)
  const openEditUser = (u) => {
    setSelectedUser(u);
    setEditName(u.name);
    setEditEmail(u.email);
    setEditPassword("");
    setShowEditUser(true);
  };

  const handleEditUser = async () => {
    if (!selectedUser) return;
    setIsLoading(true);
    
    try {
      const updateData = {};
      if (editName && editName !== selectedUser.name) updateData.name = editName;
      if (editEmail && editEmail !== selectedUser.email) updateData.email = editEmail;
      if (editPassword) updateData.new_password = editPassword;
      
      if (Object.keys(updateData).length === 0) {
        toast.info("No changes to save");
        setIsLoading(false);
        return;
      }
      
      const response = await axios.put(`${API}/admin/users/${selectedUser.id}/edit`, updateData, { headers: authHeaders });
      
      toast.success(response.data.message);
      if (response.data.changes) {
        response.data.changes.forEach(change => console.log("Change:", change));
      }
      
      setShowEditUser(false);
      setSelectedUser(null);
      setEditPassword("");
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update user");
    } finally {
      setIsLoading(false);
    }
  };

  // Copy to clipboard
  const [copiedCode, setCopiedCode] = useState(null);
  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  return (
    <div className="min-h-screen relative overflow-hidden"
      style={{
        background: '#0a0e1a'
      }}>
      
      {/* Background gradient */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-0 w-1/2 h-full"
          style={{ background: 'radial-gradient(ellipse at 0% 50%, rgba(59, 130, 246, 0.12) 0%, transparent 60%)' }} />
        <div className="absolute top-0 right-0 w-1/3 h-1/2"
          style={{ background: 'radial-gradient(circle at 100% 0%, rgba(6, 182, 212, 0.08) 0%, transparent 50%)' }} />
      </div>

      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-full w-64 p-4 flex flex-col z-20"
        style={{
          background: 'rgba(15, 23, 42, 0.8)',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
          borderRight: '1px solid rgba(59, 130, 246, 0.15)'
        }}>
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 px-2">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center overflow-hidden bg-blue-600/20 border border-blue-500/30">
            <img src="/logo.png" alt="American Club" className="w-7 h-7 object-contain" />
          </div>
          <div>
            <h1 className="font-bold text-white text-sm">American Club</h1>
            <p className="text-[10px] text-blue-400 font-semibold">ADMIN PANEL</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="space-y-1 flex-1">
          {[
            { id: "dashboard", label: "Dashboard", icon: BarChart3 },
            { id: "users", label: "Users", icon: Users },
            { id: "invite-codes", label: "Invite Codes", icon: Ticket },
            { id: "providers", label: "Providers", icon: Settings },
            ...(isSuperAdmin ? [{ id: "security", label: "Security", icon: ShieldAlert, badge: highSeverityCount }] : []),
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setActiveTab(item.id);
                if (item.id === "security") fetchSecurityLogs();
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200`}
              style={{
                background: activeTab === item.id ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                color: activeTab === item.id ? '#60a5fa' : '#94a3b8',
                border: activeTab === item.id ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent'
              }}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm font-medium flex-1 text-left">{item.label}</span>
              {item.badge > 0 && (
                <span className="px-1.5 py-0.5 text-[10px] font-bold bg-red-500 text-white rounded-full min-w-[18px] text-center animate-pulse">
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* User info */}
        <div style={{ borderTop: '1px solid rgba(59, 130, 246, 0.15)' }} className="pt-4 mt-4">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold bg-blue-600">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white truncate">{user.name}</p>
              <p className="text-[10px] text-slate-500 truncate">{user.email}</p>
            </div>
          </div>
          <div className="space-y-2">
            {isSuperAdmin && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowChangePassword(true)}
                className="w-full justify-start text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 border border-blue-500/20"
              >
                <Lock className="w-4 h-4 mr-2" />
                Change Password
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={onLogout}
              className="w-full justify-start text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/20"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="ml-64 p-6 relative z-10">
        {/* Dashboard Tab */}
        {activeTab === "dashboard" && stats && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-white">Dashboard</h2>
                <span className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Live
                </span>
              </div>
              <Button 
                onClick={async () => {
                  setIsRefreshing(true);
                  await fetchStats();
                  await fetchUsers();
                  await fetchInviteCodes();
                  if (isSuperAdmin) await fetchSecurityLogs();
                  setTimeout(() => setIsRefreshing(false), 500);
                }} 
                variant="outline" 
                size="sm" 
                className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
                disabled={isRefreshing}
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                {isRefreshing ? 'Refreshing...' : 'Refresh'}
              </Button>
            </div>
            
            <div className="grid grid-cols-4 gap-4">
              <StatCard
                icon={Users}
                label="Total Users"
                value={stats.users.total}
                subtext={`${stats.users.active} active`}
                color="blue"
              />
              <StatCard
                icon={Phone}
                label="Total Calls"
                value={stats.calls.total}
                color="teal"
              />
              <StatCard
                icon={Coins}
                label="Credits Used"
                value={stats.credits.total_used}
                color="amber"
              />
              <StatCard
                icon={Ticket}
                label="Invite Codes"
                value={stats.invite_codes.total}
                subtext={`${stats.invite_codes.unused} unused`}
                color="emerald"
              />
            </div>

            {/* Security Alerts Card - Only for Super Admin */}
            {isSuperAdmin && dangerousEvents.length > 0 && (
              <div className="rounded-xl overflow-hidden" style={{ 
                background: 'rgba(239, 68, 68, 0.05)', 
                border: '1px solid rgba(239, 68, 68, 0.2)' 
              }}>
                <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid rgba(239, 68, 68, 0.15)' }}>
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-5 h-5 text-red-400" />
                    <h3 className="text-sm font-bold text-red-400">SECURITY ALERTS</h3>
                    <span className="px-2 py-0.5 text-[10px] font-bold bg-red-500/20 text-red-400 rounded-full border border-red-500/30">
                      {dangerousEvents.length} new
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      markAlertsAsSeen();
                      setActiveTab("security");
                    }}
                    className="text-red-400 hover:text-red-300 hover:bg-red-500/10 text-xs"
                  >
                    View All
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
                <div className="divide-y divide-red-500/10">
                  {dangerousEvents.map((event) => (
                    <div key={event.id} className="px-4 py-3 flex items-center gap-4 hover:bg-red-500/5 transition-colors">
                      <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${
                        event.severity === 'critical' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                        event.severity === 'high' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                        'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                      }`}>
                        {event.severity}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white font-medium truncate">
                          {event.event_type.replace(/_/g, ' ').toUpperCase()}
                        </p>
                        <p className="text-xs text-slate-400">
                          {event.details?.email || event.ip} • {new Date(event.timestamp).toLocaleString()}
                        </p>
                      </div>
                      <AlertTriangle className={`w-4 h-4 flex-shrink-0 ${
                        event.severity === 'high' || event.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'
                      }`} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* No alerts message */}
            {isSuperAdmin && dangerousEvents.length === 0 && (
              <div className="rounded-xl p-4 flex items-center gap-3" style={{ 
                background: 'rgba(16, 185, 129, 0.05)', 
                border: '1px solid rgba(16, 185, 129, 0.2)' 
              }}>
                <Shield className="w-5 h-5 text-emerald-400" />
                <p className="text-sm text-emerald-400">All systems secure. No security alerts.</p>
              </div>
            )}
          </div>
        )}

        {/* Users Tab */}
        {activeTab === "users" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-white">Users</h2>
                <span className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Live
                </span>
              </div>
              <div className="flex gap-2">
                <Button 
                  onClick={async () => {
                    setIsRefreshing(true);
                    await fetchUsers();
                    setTimeout(() => setIsRefreshing(false), 500);
                  }} 
                  variant="outline" 
                  size="sm" 
                  className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
                  disabled={isRefreshing}
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                  {isRefreshing ? 'Refreshing...' : 'Refresh'}
                </Button>
                {isSuperAdmin && (
                  <Button 
                    onClick={() => setShowCreateAdmin(true)} 
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    <Shield className="w-4 h-4 mr-2" />
                    Create Admin
                  </Button>
                )}
              </div>
            </div>

            {/* Search Box */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <Input
                type="text"
                placeholder="Search by name, email, or role..."
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                className="pl-10 bg-slate-900/50 border-slate-700/50 text-white placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-blue-500/20 rounded-lg h-10"
              />
              {userSearch && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">
                  {filteredUsers.length} result{filteredUsers.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>

            <div className="rounded-xl overflow-hidden" style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(59, 130, 246, 0.15)' }}>
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(59, 130, 246, 0.15)' }}>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">User</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Role</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Credits</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Status</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Invite Code</th>
                    <th className="text-right text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                        {userSearch ? `No users found matching "${userSearch}"` : 'No users found'}
                      </td>
                    </tr>
                  ) : filteredUsers.map((u) => (
                    <tr key={u.id} style={{ borderBottom: '1px solid rgba(59, 130, 246, 0.1)' }} className="hover:bg-white/5">
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-white">{u.name}</p>
                          <p className="text-xs text-white/50">{u.email}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 text-[10px] font-medium rounded-full ${
                          u.role === "admin" ? "bg-blue-500/20 text-blue-400 badge-glow" : "bg-slate-500/20 text-white/60"
                        }`}>
                          {u.role.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-mono text-cyan-400 ">{u.credits}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full status-glow ${
                          u.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                        }`}>
                          {u.is_active ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-mono text-white/50">{u.invite_code_used || "-"}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {/* Show actions based on role and super admin status */}
                        {(() => {
                          // Current user is the logged-in admin
                          const isCurrentUser = u.id === user?.id;
                          const isTargetSuperAdmin = u.is_super_admin;
                          const isTargetAdmin = u.role === "admin";
                          
                          // Don't show any actions for current user's own row
                          if (isCurrentUser) return null;
                          
                          // For admin users: only super admin can see actions, and cannot act on other super admins
                          if (isTargetAdmin) {
                            if (!isSuperAdmin || isTargetSuperAdmin) return null;
                          }
                          
                          return (
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openEditUser(u)}
                                className="text-white/60 hover:text-white hover:bg-white/10"
                                title="Edit User"
                              >
                                <Edit className="w-4 h-4" />
                              </Button>
                              {/* Credits button only for non-admin users */}
                              {!isTargetAdmin && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setSelectedUser(u);
                                    setShowAddCredits(true);
                                  }}
                                  className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                                  title="Add Credits"
                                >
                                  <Coins className="w-4 h-4" />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleToggleUser(u.id)}
                                className={u.is_active ? "text-yellow-400 hover:text-yellow-300 hover:bg-yellow-500/10" : "text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"}
                                title={u.is_active ? "Disable User" : "Enable User"}
                              >
                                {u.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteUser(u.id)}
                                className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                title="Delete User"
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          );
                        })()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Invite Codes Tab */}
        {activeTab === "invite-codes" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-white">Invite Codes</h2>
                <span className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Live
                </span>
              </div>
              <div className="flex gap-2">
                <Button 
                  onClick={async () => {
                    setIsRefreshing(true);
                    await fetchInviteCodes();
                    setTimeout(() => setIsRefreshing(false), 500);
                  }} 
                  variant="outline" 
                  size="sm" 
                  className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
                  disabled={isRefreshing}
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                  {isRefreshing ? 'Refreshing...' : 'Refresh'}
                </Button>
                <Button 
                  onClick={() => setShowCreateCode(true)} 
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Create Code
                </Button>
              </div>
            </div>

            <div className="rounded-xl overflow-hidden" style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(59, 130, 246, 0.15)' }}>
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(59, 130, 246, 0.15)' }}>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Code</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Credits</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Status</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Used By</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Notes</th>
                    <th className="text-right text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {inviteCodes.map((code) => (
                    <tr key={code.id} style={{ borderBottom: '1px solid rgba(59, 130, 246, 0.1)' }} className="hover:bg-white/5">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm text-white">{code.code}</span>
                          <button
                            onClick={() => copyCode(code.code)}
                            className="text-white/60 hover:text-white transition-colors"
                          >
                            {copiedCode === code.code ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-mono text-cyan-400 ">{code.credits}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 text-[10px] font-medium rounded-full status-glow ${
                          code.is_used ? "bg-slate-500/20 text-white/60" : "bg-emerald-500/20 text-emerald-400"
                        }`}>
                          {code.is_used ? "Used" : "Available"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {code.used_by_name ? (
                          <div>
                            <p className="text-xs text-white">{code.used_by_name}</p>
                            <p className="text-[10px] text-white/50">{code.used_by_email}</p>
                          </div>
                        ) : (
                          <span className="text-xs text-white/40">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-white/50">{code.notes || "-"}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteCode(code.id)}
                          className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          title="Delete Code"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Providers Tab */}
        {activeTab === "providers" && (
          <ProvidersTab authHeaders={authHeaders} />
        )}

        {/* Security Tab (Super Admin Only) */}
        {activeTab === "security" && isSuperAdmin && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-red-400" />
                  Security Monitor
                </h2>
                <span className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Live
                </span>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    setIsRefreshing(true);
                    await fetchSecurityLogs();
                    setTimeout(() => setIsRefreshing(false), 500);
                  }}
                  disabled={isRefreshing}
                  className="text-white border-blue-500/30 hover:bg-blue-500/10"
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    if (!window.confirm("Are you sure you want to clear all security logs? This action cannot be undone.")) return;
                    try {
                      await axios.delete(`${API}/security/logs`, { headers: authHeaders });
                      toast.success("Security logs cleared");
                      // Also clear seen alerts from localStorage
                      setSeenAlertIds([]);
                      localStorage.removeItem('seenSecurityAlerts');
                      setSecuritySearch(""); // Clear search
                      fetchSecurityLogs();
                    } catch (error) {
                      toast.error(error.response?.data?.detail || "Failed to clear logs");
                    }
                  }}
                  className="text-red-400 border-red-500/30 hover:bg-red-500/10 hover:text-red-300"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Clear Logs
                </Button>
              </div>
            </div>

            {/* Security Stats Cards */}
            {securityStats && (
              <div className="grid grid-cols-4 gap-4">
                <div className="rounded-xl p-4" style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                    <span className="text-xs text-red-400 uppercase font-semibold">High Severity</span>
                  </div>
                  <p className="text-2xl font-bold text-red-400">{securityStats.events_by_severity?.high || 0}</p>
                </div>
                <div className="rounded-xl p-4" style={{ background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="w-4 h-4 text-yellow-400" />
                    <span className="text-xs text-yellow-400 uppercase font-semibold">Medium</span>
                  </div>
                  <p className="text-2xl font-bold text-yellow-400">{securityStats.events_by_severity?.medium || 0}</p>
                </div>
                <div className="rounded-xl p-4" style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
                  <div className="flex items-center gap-2 mb-2">
                    <Eye className="w-4 h-4 text-blue-400" />
                    <span className="text-xs text-blue-400 uppercase font-semibold">Total Events</span>
                  </div>
                  <p className="text-2xl font-bold text-blue-400">{securityStats.total_events || 0}</p>
                </div>
                <div className="rounded-xl p-4" style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs text-emerald-400 uppercase font-semibold">Unique IPs</span>
                  </div>
                  <p className="text-2xl font-bold text-emerald-400">{securityStats.unique_ips || 0}</p>
                </div>
              </div>
            )}

            {/* Search Box */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <Input
                type="text"
                placeholder="Search by event type, IP, severity, or email..."
                value={securitySearch}
                onChange={(e) => setSecuritySearch(e.target.value)}
                className="pl-10 bg-slate-900/50 border-slate-700/50 text-white placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-blue-500/20 rounded-lg h-10"
              />
              {securitySearch && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">
                  {filteredSecurityLogs.length} result{filteredSecurityLogs.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>

            {/* Security Logs Table */}
            <div className="rounded-xl overflow-hidden" style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(59, 130, 246, 0.15)' }}>
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(59, 130, 246, 0.15)' }}>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Time</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Event</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">IP Address</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Severity</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSecurityLogs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                        {securitySearch ? `No logs found matching "${securitySearch}"` : 'No security events recorded yet'}
                      </td>
                    </tr>
                  ) : filteredSecurityLogs.map((log) => (
                    <tr key={log.id} style={{ borderBottom: '1px solid rgba(59, 130, 246, 0.1)' }} className="hover:bg-white/5">
                      <td className="px-4 py-3 text-xs text-slate-400 font-mono">
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-medium ${
                          log.event_type.includes('success') ? 'text-emerald-400' :
                          log.event_type.includes('failed') ? 'text-red-400' :
                          log.event_type.includes('blocked') ? 'text-yellow-400' :
                          'text-blue-400'
                        }`}>
                          {log.event_type.replace(/_/g, ' ').toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-white/70">{log.ip}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase ${
                          log.severity === 'critical' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                          log.severity === 'high' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                          log.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                          'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        }`}>
                          {log.severity}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400 max-w-xs truncate">
                        {log.details?.email || log.details?.user_id?.slice(0, 8) || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Create Code Modal */}
      <AnimatePresence>
        {showCreateCode && (
          <Modal onClose={() => setShowCreateCode(false)} title="Create Invite Code">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Credits</label>
                <Input
                  type="number"
                  value={newCodeCredits}
                  onChange={(e) => setNewCodeCredits(parseInt(e.target.value) || 0)}
                  className="mt-1 glass-input"
                  min={0}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Notes (optional)</label>
                <Input
                  value={newCodeNotes}
                  onChange={(e) => setNewCodeNotes(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="e.g., For new employee"
                />
              </div>
              <Button
                onClick={handleCreateCode}
                disabled={isLoading}
                className="w-full glow-button text-white"
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Generate Code
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Add Credits Modal */}
      <AnimatePresence>
        {showAddCredits && selectedUser && (
          <Modal onClose={() => { setShowAddCredits(false); setSelectedUser(null); }} title={`Add Credits to ${selectedUser.name}`}>
            <div className="space-y-4">
              <div className="rounded-xl-static p-3" style={{ background: 'rgba(34, 211, 238, 0.1)', border: '1px solid rgba(34, 211, 238, 0.3)' }}>
                <p className="text-xs text-white/70">Current Balance</p>
                <p className="text-2xl font-mono text-cyan-400 ">{selectedUser.credits} credits</p>
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Amount to Add</label>
                <Input
                  type="number"
                  value={creditAmount}
                  onChange={(e) => setCreditAmount(parseInt(e.target.value) || 0)}
                  className="mt-1 glass-input"
                  min={1}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Reason (optional)</label>
                <Input
                  value={creditReason}
                  onChange={(e) => setCreditReason(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="e.g., Bonus, Promo"
                />
              </div>
              <Button
                onClick={handleAddCredits}
                disabled={isLoading}
                className="w-full glow-button text-white"
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Add {creditAmount} Credits
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Edit User Modal */}
      <AnimatePresence>
        {showEditUser && selectedUser && (
          <Modal onClose={() => { setShowEditUser(false); setSelectedUser(null); setEditPassword(""); }} title={`Edit User: ${selectedUser.name}`}>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <UserIcon className="w-3 h-3" />
                  Name
                </label>
                <Input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="User name"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <Mail className="w-3 h-3" />
                  Email
                </label>
                <Input
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="user@example.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <Key className="w-3 h-3" />
                  New Password
                </label>
                <Input
                  type="password"
                  value={editPassword}
                  onChange={(e) => setEditPassword(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="Leave blank to keep current"
                />
                <p className="text-[10px] text-white/40 mt-1">User will be logged out if password is changed</p>
              </div>
              <Button
                onClick={handleEditUser}
                disabled={isLoading}
                className="w-full glow-button text-white"
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Save Changes
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Create Admin Modal */}
      <AnimatePresence>
        {showCreateAdmin && (
          <Modal onClose={() => setShowCreateAdmin(false)} title="Create New Admin">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <UserIcon className="w-3 h-3" />
                  Name
                </label>
                <Input
                  value={newAdminName}
                  onChange={(e) => setNewAdminName(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="Admin name"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <Mail className="w-3 h-3" />
                  Email
                </label>
                <Input
                  type="email"
                  value={newAdminEmail}
                  onChange={(e) => setNewAdminEmail(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="admin@example.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <Key className="w-3 h-3" />
                  Password
                </label>
                <Input
                  type="password"
                  value={newAdminPassword}
                  onChange={(e) => setNewAdminPassword(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="Enter password"
                />
              </div>
              <p className="text-[10px] text-white/40">New admin will NOT have Super Admin privileges</p>
              <Button
                onClick={handleCreateAdmin}
                disabled={isLoading || !newAdminName || !newAdminEmail || !newAdminPassword}
                className="w-full text-white"
                style={{
                  background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
                  boxShadow: '0 0 20px rgba(59, 130, 246, 0.3)'
                }}
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : <Shield className="w-4 h-4 mr-2" />}
                Create Admin
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Change Password Modal */}
      <AnimatePresence>
        {showChangePassword && (
          <Modal onClose={() => { setShowChangePassword(false); setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); }} title="Change Password">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <Lock className="w-3 h-3" />
                  Current Password
                </label>
                <Input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="Enter current password"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <Key className="w-3 h-3" />
                  New Password
                </label>
                <Input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="Enter new password"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase flex items-center gap-2">
                  <Key className="w-3 h-3" />
                  Confirm New Password
                </label>
                <Input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="Confirm new password"
                />
              </div>
              <Button
                onClick={handleChangePassword}
                disabled={isLoading || !currentPassword || !newPassword || !confirmPassword}
                className="w-full text-white"
                style={{
                  background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
                  boxShadow: '0 0 20px rgba(59, 130, 246, 0.3)'
                }}
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : <Lock className="w-4 h-4 mr-2" />}
                Update Password
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>
    </div>
  );
}

// Stat Card Component
function StatCard({ icon: Icon, label, value, subtext, color }) {
  const colors = {
    blue: { bg: 'rgba(59, 130, 246, 0.1)', border: 'rgba(59, 130, 246, 0.3)', text: '#60a5fa', glow: 'rgba(59, 130, 246, 0.2)' },
    teal: { bg: 'rgba(20, 184, 166, 0.1)', border: 'rgba(20, 184, 166, 0.3)', text: '#5eead4', glow: 'rgba(20, 184, 166, 0.2)' },
    amber: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', text: '#fbbf24', glow: 'rgba(245, 158, 11, 0.2)' },
    emerald: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.3)', text: '#6ee7b7', glow: 'rgba(16, 185, 129, 0.2)' },
    cyan: { bg: 'rgba(34, 211, 238, 0.1)', border: 'rgba(34, 211, 238, 0.3)', text: '#67e8f9', glow: 'rgba(34, 211, 238, 0.2)' },
    sky: { bg: 'rgba(14, 165, 233, 0.1)', border: 'rgba(14, 165, 233, 0.3)', text: '#38bdf8', glow: 'rgba(14, 165, 233, 0.2)' },
    yellow: { bg: 'rgba(234, 179, 8, 0.1)', border: 'rgba(234, 179, 8, 0.3)', text: '#facc15', glow: 'rgba(234, 179, 8, 0.2)' },
  };

  const colorScheme = colors[color] || colors.blue;

  return (
    <div 
      className="p-5 transition-all duration-200 hover:scale-[1.02] rounded-xl"
      style={{
        background: `linear-gradient(135deg, ${colorScheme.bg}, rgba(15, 23, 42, 0.8))`,
        border: `1px solid ${colorScheme.border}`,
        boxShadow: `0 4px 16px rgba(0, 0, 0, 0.2)`
      }}
    >
      <div className="flex items-center gap-3 mb-4">
        <div 
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{
            background: `${colorScheme.bg}`,
            border: `1px solid ${colorScheme.border}`
          }}
        >
          <Icon className="w-5 h-5" style={{ color: colorScheme.text }} />
        </div>
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-3xl font-bold" style={{ color: colorScheme.text }}>{value}</p>
      {subtext && <p className="text-sm text-slate-500 mt-1">{subtext}</p>}
    </div>
  );
}

// Modal Component
function Modal({ children, onClose, title }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 backdrop-blur-sm flex items-center justify-center z-50"
      style={{ background: 'rgba(0, 0, 0, 0.6)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="p-6 w-full max-w-md max-h-[90vh] overflow-y-auto rounded-xl"
        style={{
          background: 'rgba(15, 23, 42, 0.95)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(59, 130, 246, 0.25)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-bold text-white mb-4">{title}</h3>
        {children}
      </motion.div>
    </motion.div>
  );
}

// Providers Tab Component - Full Phone Number Management
function ProvidersTab({ authHeaders }) {
  const [providers, setProviders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [editingProvider, setEditingProvider] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState(null);
  
  // Phone number management
  const [showAddPhone, setShowAddPhone] = useState(false);
  const [showEditPhone, setShowEditPhone] = useState(false);
  const [editingPhone, setEditingPhone] = useState(null);
  const [newPhoneNumber, setNewPhoneNumber] = useState("");
  const [newPhoneLabel, setNewPhoneLabel] = useState("Main");
  
  // SignalWire form
  const [swProjectId, setSwProjectId] = useState("");
  const [swAuthToken, setSwAuthToken] = useState("");
  const [swSpaceUrl, setSwSpaceUrl] = useState("");
  
  // Infobip form
  const [ibApiKey, setIbApiKey] = useState("");
  const [ibBaseUrl, setIbBaseUrl] = useState("api.infobip.com");
  const [ibAppId, setIbAppId] = useState("");

  const fetchProviders = async () => {
    try {
      const response = await axios.get(`${API}/admin/providers`, { headers: authHeaders });
      setProviders(response.data.providers);
    } catch (error) {
      console.error("Error fetching providers:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProviders();
    
    // Auto-refresh every 15 seconds
    const interval = setInterval(() => {
      fetchProviders();
    }, 15000);
    
    return () => clearInterval(interval);
  }, []);

  const handleSaveSignalWire = async () => {
    setIsLoading(true);
    try {
      await axios.put(`${API}/admin/providers/signalwire?is_enabled=true`, {
        project_id: swProjectId,
        auth_token: swAuthToken,
        space_url: swSpaceUrl,
        phone_numbers: []
      }, { headers: authHeaders });
      
      toast.success("SignalWire configuration saved");
      setEditingProvider(null);
      fetchProviders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save configuration");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveInfobip = async () => {
    setIsLoading(true);
    try {
      await axios.put(`${API}/admin/providers/infobip?is_enabled=true`, {
        api_key: ibApiKey,
        base_url: ibBaseUrl,
        app_id: ibAppId || null,
        phone_numbers: []
      }, { headers: authHeaders });
      
      toast.success("Infobip configuration saved");
      setEditingProvider(null);
      fetchProviders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save configuration");
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleProvider = async (providerId) => {
    try {
      const response = await axios.put(`${API}/admin/providers/${providerId}/toggle`, {}, { headers: authHeaders });
      toast.success(response.data.message);
      fetchProviders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to toggle provider");
    }
  };

  // Phone number management functions
  const handleAddPhoneNumber = async () => {
    if (!selectedProvider || !newPhoneNumber) return;
    
    setIsLoading(true);
    try {
      await axios.post(`${API}/admin/providers/${selectedProvider}/phone-numbers`, {
        number: newPhoneNumber,
        label: newPhoneLabel || "Main",
        is_active: true
      }, { headers: authHeaders });
      
      toast.success("Phone number added");
      setShowAddPhone(false);
      setNewPhoneNumber("");
      setNewPhoneLabel("Main");
      fetchProviders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to add phone number");
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdatePhoneNumber = async () => {
    if (!selectedProvider || !editingPhone) return;
    
    setIsLoading(true);
    try {
      await axios.put(`${API}/admin/providers/${selectedProvider}/phone-numbers/${editingPhone.id}`, {
        number: newPhoneNumber,
        label: newPhoneLabel,
        is_active: editingPhone.is_active
      }, { headers: authHeaders });
      
      toast.success("Phone number updated");
      setShowEditPhone(false);
      setEditingPhone(null);
      setNewPhoneNumber("");
      setNewPhoneLabel("Main");
      fetchProviders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update phone number");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeletePhoneNumber = async (providerId, phoneId) => {
    if (!window.confirm("Are you sure you want to delete this phone number?")) return;
    
    try {
      await axios.delete(`${API}/admin/providers/${providerId}/phone-numbers/${phoneId}`, { headers: authHeaders });
      toast.success("Phone number deleted");
      fetchProviders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to delete phone number");
    }
  };

  const handleTogglePhoneActive = async (providerId, phone) => {
    try {
      await axios.put(`${API}/admin/providers/${providerId}/phone-numbers/${phone.id}`, {
        is_active: !phone.is_active
      }, { headers: authHeaders });
      toast.success(`Phone number ${!phone.is_active ? 'activated' : 'deactivated'}`);
      fetchProviders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update phone number");
    }
  };

  const openEditPhone = (providerId, phone) => {
    setSelectedProvider(providerId);
    setEditingPhone(phone);
    setNewPhoneNumber(phone.number);
    setNewPhoneLabel(phone.label);
    setShowEditPhone(true);
  };

  const openAddPhone = (providerId) => {
    setSelectedProvider(providerId);
    setNewPhoneNumber("");
    setNewPhoneLabel("Main");
    setShowAddPhone(true);
  };

  if (isLoading && providers.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-cyan-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold text-white">Provider Settings</h2>
          <span className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            Live
          </span>
        </div>
        <Button 
          onClick={async () => {
            setIsRefreshing(true);
            await fetchProviders();
            setTimeout(() => setIsRefreshing(false), 500);
          }} 
          variant="outline" 
          size="sm"
          disabled={isRefreshing}
          className="border-blue-500/30 text-white hover:bg-blue-500/10"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SignalWire Card */}
        <div className="rounded-xl overflow-hidden" style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(59, 130, 246, 0.15)' }}>
          <div className="p-5" style={{ borderBottom: '1px solid rgba(59, 130, 246, 0.15)' }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center"
                  style={{ boxShadow: '0 0 15px rgba(16, 185, 129, 0.3)' }}>
                  <Phone className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <h3 className="font-bold text-white">SignalWire</h3>
                  <p className="text-xs text-white/60">Voice & SMS Provider</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {providers.find(p => p.id === "signalwire")?.is_configured && (
                  <button
                    onClick={() => handleToggleProvider("signalwire")}
                    className={`px-2 py-1 rounded text-xs font-medium status-glow ${
                      providers.find(p => p.id === "signalwire")?.is_enabled
                        ? "bg-emerald-500/20 text-emerald-400"
                        : "bg-slate-500/20 text-white/60"
                    }`}
                  >
                    {providers.find(p => p.id === "signalwire")?.is_enabled ? "Enabled" : "Disabled"}
                  </button>
                )}
                <Button
                  onClick={() => setEditingProvider("signalwire")}
                  variant="ghost"
                  size="sm"
                  className="text-white/60 hover:text-white hover:bg-white/10"
                >
                  <Settings className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>

          {/* Phone Numbers Section */}
          <div className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-white/70">Phone Numbers</h4>
              <Button
                onClick={() => openAddPhone("signalwire")}
                size="sm"
                className="h-7 text-xs text-white"
                style={{
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  boxShadow: '0 0 15px rgba(16, 185, 129, 0.3)'
                }}
              >
                <Plus className="w-3 h-3 mr-1" />
                Add Number
              </Button>
            </div>
            
            {(providers.find(p => p.id === "signalwire")?.phone_numbers?.length || 0) === 0 ? (
              <p className="text-white/40 text-sm">No phone numbers configured</p>
            ) : (
              <div className="space-y-2">
                {providers.find(p => p.id === "signalwire")?.phone_numbers?.map((phone) => (
                  <div 
                    key={phone.id || phone.number}
                    className="flex items-center justify-between p-2 rounded-lg"
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.08)'
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${phone.is_active ? 'bg-emerald-400' : 'bg-slate-500'}`} style={{ boxShadow: phone.is_active ? '0 0 8px #10b981' : 'none' }} />
                      <span className="font-mono text-sm text-white">{phone.number}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTogglePhoneActive("signalwire", phone)}
                        className={`h-7 w-7 p-0 hover:bg-white/10 ${phone.is_active ? 'text-emerald-400' : 'text-white/40'}`}
                        title={phone.is_active ? "Deactivate" : "Activate"}
                      >
                        {phone.is_active ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditPhone("signalwire", phone)}
                        className="h-7 w-7 p-0 text-white/60 hover:text-white hover:bg-white/10"
                      >
                        <Edit className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeletePhoneNumber("signalwire", phone.id)}
                        className="h-7 w-7 p-0 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Infobip Card */}
        <div className="rounded-xl overflow-hidden" style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(59, 130, 246, 0.15)' }}>
          <div className="p-5" style={{ borderBottom: '1px solid rgba(59, 130, 246, 0.15)' }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center"
                  style={{ boxShadow: '0 0 15px rgba(251, 146, 60, 0.3)' }}>
                  <Phone className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <h3 className="font-bold text-white">Infobip</h3>
                  <p className="text-xs text-white/60">Voice & Messaging</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {providers.find(p => p.id === "infobip")?.is_configured && (
                  <button
                    onClick={() => handleToggleProvider("infobip")}
                    className={`px-2 py-1 rounded text-xs font-medium status-glow ${
                      providers.find(p => p.id === "infobip")?.is_enabled
                        ? "bg-emerald-500/20 text-emerald-400"
                        : "bg-slate-500/20 text-white/60"
                    }`}
                  >
                    {providers.find(p => p.id === "infobip")?.is_enabled ? "Enabled" : "Disabled"}
                  </button>
                )}
                <Button
                  onClick={() => setEditingProvider("infobip")}
                  variant="ghost"
                  size="sm"
                  className="text-white/60 hover:text-white hover:bg-white/10"
                >
                  <Settings className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>

          {/* Phone Numbers Section */}
          <div className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-white/70">Phone Numbers</h4>
              <Button
                onClick={() => openAddPhone("infobip")}
                size="sm"
                className="h-7 text-xs text-white"
                style={{
                  background: 'linear-gradient(135deg, #f97316, #ea580c)',
                  boxShadow: '0 0 15px rgba(249, 115, 22, 0.3)'
                }}
              >
                <Plus className="w-3 h-3 mr-1" />
                Add Number
              </Button>
            </div>
            
            {(providers.find(p => p.id === "infobip")?.phone_numbers?.length || 0) === 0 ? (
              <p className="text-white/40 text-sm">No phone numbers configured</p>
            ) : (
              <div className="space-y-2">
                {providers.find(p => p.id === "infobip")?.phone_numbers?.map((phone) => (
                  <div 
                    key={phone.id || phone.number}
                    className="flex items-center justify-between p-2 rounded-lg"
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.08)'
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${phone.is_active ? 'bg-emerald-400' : 'bg-slate-500'}`} style={{ boxShadow: phone.is_active ? '0 0 8px #10b981' : 'none' }} />
                      <span className="font-mono text-sm text-white">{phone.number}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTogglePhoneActive("infobip", phone)}
                        className={`h-7 w-7 p-0 hover:bg-white/10 ${phone.is_active ? 'text-emerald-400' : 'text-white/40'}`}
                        title={phone.is_active ? "Deactivate" : "Activate"}
                      >
                        {phone.is_active ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditPhone("infobip", phone)}
                        className="h-7 w-7 p-0 text-white/60 hover:text-white hover:bg-white/10"
                      >
                        <Edit className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeletePhoneNumber("infobip", phone.id)}
                        className="h-7 w-7 p-0 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add Phone Number Modal */}
      <AnimatePresence>
        {showAddPhone && (
          <Modal onClose={() => setShowAddPhone(false)} title={`Add Phone Number - ${selectedProvider?.toUpperCase()}`}>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Phone Number *</label>
                <Input
                  value={newPhoneNumber}
                  onChange={(e) => setNewPhoneNumber(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="+1234567890"
                />
              </div>
              <Button
                onClick={handleAddPhoneNumber}
                disabled={isLoading || !newPhoneNumber}
                className="w-full glow-button text-white"
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Add Phone Number
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Edit Phone Number Modal */}
      <AnimatePresence>
        {showEditPhone && editingPhone && (
          <Modal onClose={() => { setShowEditPhone(false); setEditingPhone(null); }} title="Edit Phone Number">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Phone Number *</label>
                <Input
                  value={newPhoneNumber}
                  onChange={(e) => setNewPhoneNumber(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="+1234567890"
                />
              </div>
              <Button
                onClick={handleUpdatePhoneNumber}
                disabled={isLoading || !newPhoneNumber}
                className="w-full glow-button text-white"
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Save Changes
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* SignalWire Config Modal */}
      <AnimatePresence>
        {editingProvider === "signalwire" && (
          <Modal onClose={() => setEditingProvider(null)} title="Configure SignalWire">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Project ID *</label>
                <Input
                  value={swProjectId}
                  onChange={(e) => setSwProjectId(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Auth Token *</label>
                <Input
                  type="password"
                  value={swAuthToken}
                  onChange={(e) => setSwAuthToken(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="PTxxxxxxxxxxxxxxxxxxxxxxxxxx"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Space URL *</label>
                <Input
                  value={swSpaceUrl}
                  onChange={(e) => setSwSpaceUrl(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="your-space.signalwire.com"
                />
              </div>
              <p className="text-xs text-white/40">
                Note: Add phone numbers after saving credentials using the &quot;Add Number&quot; button.
              </p>
              <Button
                onClick={handleSaveSignalWire}
                disabled={isLoading || !swProjectId || !swAuthToken || !swSpaceUrl}
                className="w-full text-white"
                style={{
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  boxShadow: '0 0 20px rgba(16, 185, 129, 0.3)'
                }}
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Save Configuration
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Infobip Config Modal */}
      <AnimatePresence>
        {editingProvider === "infobip" && (
          <Modal onClose={() => setEditingProvider(null)} title="Configure Infobip">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">API Key *</label>
                <Input
                  type="password"
                  value={ibApiKey}
                  onChange={(e) => setIbApiKey(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="Your Infobip API Key"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">Base URL</label>
                <Input
                  value={ibBaseUrl}
                  onChange={(e) => setIbBaseUrl(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="api.infobip.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-white/70 uppercase">App ID (optional)</label>
                <Input
                  value={ibAppId}
                  onChange={(e) => setIbAppId(e.target.value)}
                  className="mt-1 glass-input"
                  placeholder="App ID from Infobip"
                />
              </div>
              <p className="text-xs text-white/40">
                Note: Add phone numbers after saving credentials using the &quot;Add Number&quot; button.
              </p>
              <Button
                onClick={handleSaveInfobip}
                disabled={isLoading || !ibApiKey}
                className="w-full text-white"
                style={{
                  background: 'linear-gradient(135deg, #f97316, #ea580c)',
                  boxShadow: '0 0 20px rgba(249, 115, 22, 0.3)'
                }}
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Save Configuration
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>
    </div>
  );
}

