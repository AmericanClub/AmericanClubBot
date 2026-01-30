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
  User as UserIcon
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
  
  // Modal states
  const [showCreateCode, setShowCreateCode] = useState(false);
  const [showAddCredits, setShowAddCredits] = useState(false);
  const [showEditUser, setShowEditUser] = useState(false);
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

  useEffect(() => {
    fetchStats();
    fetchUsers();
    fetchInviteCodes();
  }, [fetchStats, fetchUsers, fetchInviteCodes]);

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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-full w-64 bg-slate-900/80 backdrop-blur-xl border-r border-white/10 p-4 flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 px-2">
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center overflow-hidden">
            <img src="/logo.png" alt="American Club" className="w-8 h-8 object-contain" />
          </div>
          <div>
            <h1 className="font-bold text-white text-sm">American Club</h1>
            <p className="text-[10px] text-cyan-400 font-mono">ADMIN PANEL</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="space-y-1 flex-1">
          {[
            { id: "dashboard", label: "Dashboard", icon: BarChart3 },
            { id: "users", label: "Users", icon: Users },
            { id: "invite-codes", label: "Invite Codes", icon: Ticket },
            { id: "providers", label: "Providers", icon: Settings },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                activeTab === item.id
                  ? "bg-cyan-500/20 text-cyan-400"
                  : "text-slate-400 hover:bg-white/5 hover:text-white"
              }`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm font-medium">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* User info */}
        <div className="border-t border-white/10 pt-4 mt-4">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-purple-500 flex items-center justify-center text-white text-xs font-bold">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user.name}</p>
              <p className="text-[10px] text-slate-400 truncate">{user.email}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onLogout}
            className="w-full justify-start text-red-400 hover:text-red-300 hover:bg-red-500/10"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="ml-64 p-6">
        {/* Dashboard Tab */}
        {activeTab === "dashboard" && stats && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white">Dashboard</h2>
            
            <div className="grid grid-cols-4 gap-4">
              <StatCard
                icon={Users}
                label="Total Users"
                value={stats.users.total}
                subtext={`${stats.users.active} active`}
                color="cyan"
              />
              <StatCard
                icon={Phone}
                label="Total Calls"
                value={stats.calls.total}
                color="purple"
              />
              <StatCard
                icon={Coins}
                label="Credits Used"
                value={stats.credits.total_used}
                color="yellow"
              />
              <StatCard
                icon={Ticket}
                label="Invite Codes"
                value={stats.invite_codes.total}
                subtext={`${stats.invite_codes.unused} unused`}
                color="emerald"
              />
            </div>
          </div>
        )}

        {/* Users Tab */}
        {activeTab === "users" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-white">Users</h2>
              <Button onClick={() => fetchUsers()} variant="outline" size="sm">
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>

            <div className="bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-800/50">
                  <tr>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">User</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Role</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Credits</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Status</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Invite Code</th>
                    <th className="text-right text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-white/5">
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-white">{u.name}</p>
                          <p className="text-xs text-slate-400">{u.email}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 text-[10px] font-medium rounded-full ${
                          u.role === "admin" ? "bg-purple-500/20 text-purple-400" : "bg-slate-500/20 text-slate-400"
                        }`}>
                          {u.role.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-mono text-cyan-400">{u.credits}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full ${
                          u.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                        }`}>
                          {u.is_active ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-mono text-slate-400">{u.invite_code_used || "-"}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {u.role !== "admin" && (
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditUser(u)}
                              className="text-slate-400 hover:text-white"
                              title="Edit User"
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setSelectedUser(u);
                                setShowAddCredits(true);
                              }}
                              className="text-cyan-400 hover:text-cyan-300"
                              title="Add Credits"
                            >
                              <Coins className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleUser(u.id)}
                              className={u.is_active ? "text-red-400 hover:text-red-300" : "text-emerald-400 hover:text-emerald-300"}
                              title={u.is_active ? "Disable User" : "Enable User"}
                            >
                              {u.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                            </Button>
                          </div>
                        )}
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
              <h2 className="text-2xl font-bold text-white">Invite Codes</h2>
              <Button onClick={() => setShowCreateCode(true)} className="bg-cyan-500 hover:bg-cyan-600">
                <Plus className="w-4 h-4 mr-2" />
                Create Code
              </Button>
            </div>

            <div className="bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-800/50">
                  <tr>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Code</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Credits</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Status</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Used By</th>
                    <th className="text-left text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Notes</th>
                    <th className="text-right text-xs font-medium text-slate-400 uppercase tracking-wider px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {inviteCodes.map((code) => (
                    <tr key={code.id} className="hover:bg-white/5">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm text-white">{code.code}</span>
                          <button
                            onClick={() => copyCode(code.code)}
                            className="text-slate-400 hover:text-white"
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
                        <span className="text-sm font-mono text-cyan-400">{code.credits}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 text-[10px] font-medium rounded-full ${
                          code.is_used ? "bg-slate-500/20 text-slate-400" : "bg-emerald-500/20 text-emerald-400"
                        }`}>
                          {code.is_used ? "Used" : "Available"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {code.used_by_name ? (
                          <div>
                            <p className="text-xs text-white">{code.used_by_name}</p>
                            <p className="text-[10px] text-slate-400">{code.used_by_email}</p>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-slate-400">{code.notes || "-"}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {!code.is_used && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteCode(code.id)}
                            className="text-red-400 hover:text-red-300"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
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
      </div>

      {/* Create Code Modal */}
      <AnimatePresence>
        {showCreateCode && (
          <Modal onClose={() => setShowCreateCode(false)} title="Create Invite Code">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Credits</label>
                <Input
                  type="number"
                  value={newCodeCredits}
                  onChange={(e) => setNewCodeCredits(parseInt(e.target.value) || 0)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  min={0}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Notes (optional)</label>
                <Input
                  value={newCodeNotes}
                  onChange={(e) => setNewCodeNotes(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="e.g., For new employee"
                />
              </div>
              <Button
                onClick={handleCreateCode}
                disabled={isLoading}
                className="w-full bg-cyan-500 hover:bg-cyan-600"
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
              <div className="bg-slate-800 rounded-lg p-3">
                <p className="text-xs text-slate-400">Current Balance</p>
                <p className="text-2xl font-mono text-cyan-400">{selectedUser.credits} credits</p>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Amount to Add</label>
                <Input
                  type="number"
                  value={creditAmount}
                  onChange={(e) => setCreditAmount(parseInt(e.target.value) || 0)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  min={1}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Reason (optional)</label>
                <Input
                  value={creditReason}
                  onChange={(e) => setCreditReason(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="e.g., Bonus, Promo"
                />
              </div>
              <Button
                onClick={handleAddCredits}
                disabled={isLoading}
                className="w-full bg-cyan-500 hover:bg-cyan-600"
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
                <label className="text-xs font-medium text-slate-400 uppercase flex items-center gap-2">
                  <UserIcon className="w-3 h-3" />
                  Name
                </label>
                <Input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="User name"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase flex items-center gap-2">
                  <Mail className="w-3 h-3" />
                  Email
                </label>
                <Input
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="user@example.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase flex items-center gap-2">
                  <Key className="w-3 h-3" />
                  New Password
                </label>
                <Input
                  type="password"
                  value={editPassword}
                  onChange={(e) => setEditPassword(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="Leave blank to keep current"
                />
                <p className="text-[10px] text-slate-500 mt-1">User will be logged out if password is changed</p>
              </div>
              <Button
                onClick={handleEditUser}
                disabled={isLoading}
                className="w-full bg-cyan-500 hover:bg-cyan-600"
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Save Changes
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
    cyan: "from-cyan-500/20 to-cyan-500/5 border-cyan-500/30 text-cyan-400",
    purple: "from-purple-500/20 to-purple-500/5 border-purple-500/30 text-purple-400",
    yellow: "from-yellow-500/20 to-yellow-500/5 border-yellow-500/30 text-yellow-400",
    emerald: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-400",
  };

  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-xl p-4`}>
      <div className="flex items-center gap-3">
        <Icon className="w-5 h-5" />
        <span className="text-xs font-medium text-slate-400 uppercase">{label}</span>
      </div>
      <p className="text-3xl font-bold text-white mt-2">{value}</p>
      {subtext && <p className="text-xs text-slate-400 mt-1">{subtext}</p>}
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
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-slate-900 border border-white/10 rounded-xl p-6 w-full max-w-md shadow-xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-bold text-white mb-4">{title}</h3>
        {children}
      </motion.div>
    </motion.div>
  );
}

// Providers Tab Component
function ProvidersTab({ authHeaders }) {
  const [providers, setProviders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingProvider, setEditingProvider] = useState(null);
  
  // SignalWire form
  const [swProjectId, setSwProjectId] = useState("");
  const [swAuthToken, setSwAuthToken] = useState("");
  const [swSpaceUrl, setSwSpaceUrl] = useState("");
  const [swPhoneNumber, setSwPhoneNumber] = useState("");
  
  // Infobip form
  const [ibApiKey, setIbApiKey] = useState("");
  const [ibBaseUrl, setIbBaseUrl] = useState("api.infobip.com");
  const [ibAppId, setIbAppId] = useState("");
  const [ibPhoneNumber, setIbPhoneNumber] = useState("");

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
  }, []);

  const handleSaveSignalWire = async () => {
    setIsLoading(true);
    try {
      const phoneNumbers = swPhoneNumber ? [{ number: swPhoneNumber, label: "Main", is_active: true }] : [];
      
      await axios.put(`${API}/admin/providers/signalwire?is_enabled=true`, {
        project_id: swProjectId,
        auth_token: swAuthToken,
        space_url: swSpaceUrl,
        phone_numbers: phoneNumbers
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
      const phoneNumbers = ibPhoneNumber ? [{ number: ibPhoneNumber, label: "Main", is_active: true }] : [];
      
      await axios.put(`${API}/admin/providers/infobip?is_enabled=true`, {
        api_key: ibApiKey,
        base_url: ibBaseUrl,
        app_id: ibAppId || null,
        phone_numbers: phoneNumbers
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
        <h2 className="text-2xl font-bold text-white">Provider Settings</h2>
        <Button onClick={fetchProviders} variant="outline" size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* SignalWire Card */}
        <div className="bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                <Phone className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h3 className="font-bold text-white">SignalWire</h3>
                <p className="text-xs text-slate-400">Voice & SMS Provider</p>
              </div>
            </div>
            {providers.find(p => p.id === "signalwire")?.is_configured && (
              <button
                onClick={() => handleToggleProvider("signalwire")}
                className={`px-2 py-1 rounded text-xs font-medium ${
                  providers.find(p => p.id === "signalwire")?.is_enabled
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-slate-500/20 text-slate-400"
                }`}
              >
                {providers.find(p => p.id === "signalwire")?.is_enabled ? "Enabled" : "Disabled"}
              </button>
            )}
          </div>

          {providers.find(p => p.id === "signalwire")?.is_configured ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Status:</span>
                <span className="text-emerald-400">Configured</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Phone Numbers:</span>
                <span className="text-white">{providers.find(p => p.id === "signalwire")?.phone_numbers?.length || 0}</span>
              </div>
              <Button
                onClick={() => setEditingProvider("signalwire")}
                variant="outline"
                size="sm"
                className="w-full mt-3"
              >
                <Edit className="w-4 h-4 mr-2" />
                Edit Configuration
              </Button>
            </div>
          ) : (
            <div>
              <p className="text-slate-400 text-sm mb-3">Not configured yet</p>
              <Button
                onClick={() => setEditingProvider("signalwire")}
                className="w-full bg-emerald-500 hover:bg-emerald-600"
              >
                <Plus className="w-4 h-4 mr-2" />
                Configure
              </Button>
            </div>
          )}
        </div>

        {/* Infobip Card */}
        <div className="bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center">
                <Phone className="w-5 h-5 text-orange-400" />
              </div>
              <div>
                <h3 className="font-bold text-white">Infobip</h3>
                <p className="text-xs text-slate-400">Voice & Messaging</p>
              </div>
            </div>
            {providers.find(p => p.id === "infobip")?.is_configured && (
              <button
                onClick={() => handleToggleProvider("infobip")}
                className={`px-2 py-1 rounded text-xs font-medium ${
                  providers.find(p => p.id === "infobip")?.is_enabled
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-slate-500/20 text-slate-400"
                }`}
              >
                {providers.find(p => p.id === "infobip")?.is_enabled ? "Enabled" : "Disabled"}
              </button>
            )}
          </div>

          {providers.find(p => p.id === "infobip")?.is_configured ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Status:</span>
                <span className="text-emerald-400">Configured</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Phone Numbers:</span>
                <span className="text-white">{providers.find(p => p.id === "infobip")?.phone_numbers?.length || 0}</span>
              </div>
              <Button
                onClick={() => setEditingProvider("infobip")}
                variant="outline"
                size="sm"
                className="w-full mt-3"
              >
                <Edit className="w-4 h-4 mr-2" />
                Edit Configuration
              </Button>
            </div>
          ) : (
            <div>
              <p className="text-slate-400 text-sm mb-3">Not configured yet</p>
              <Button
                onClick={() => setEditingProvider("infobip")}
                className="w-full bg-orange-500 hover:bg-orange-600"
              >
                <Plus className="w-4 h-4 mr-2" />
                Configure
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* SignalWire Edit Modal */}
      <AnimatePresence>
        {editingProvider === "signalwire" && (
          <Modal onClose={() => setEditingProvider(null)} title="Configure SignalWire">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Project ID *</label>
                <Input
                  value={swProjectId}
                  onChange={(e) => setSwProjectId(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Auth Token *</label>
                <Input
                  type="password"
                  value={swAuthToken}
                  onChange={(e) => setSwAuthToken(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="PTxxxxxxxxxxxxxxxxxxxxxxxxxx"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Space URL *</label>
                <Input
                  value={swSpaceUrl}
                  onChange={(e) => setSwSpaceUrl(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="your-space.signalwire.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Phone Number</label>
                <Input
                  value={swPhoneNumber}
                  onChange={(e) => setSwPhoneNumber(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="+1234567890"
                />
              </div>
              <Button
                onClick={handleSaveSignalWire}
                disabled={isLoading || !swProjectId || !swAuthToken || !swSpaceUrl}
                className="w-full bg-emerald-500 hover:bg-emerald-600"
              >
                {isLoading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : null}
                Save Configuration
              </Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Infobip Edit Modal */}
      <AnimatePresence>
        {editingProvider === "infobip" && (
          <Modal onClose={() => setEditingProvider(null)} title="Configure Infobip">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">API Key *</label>
                <Input
                  type="password"
                  value={ibApiKey}
                  onChange={(e) => setIbApiKey(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="Your Infobip API Key"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Base URL</label>
                <Input
                  value={ibBaseUrl}
                  onChange={(e) => setIbBaseUrl(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="api.infobip.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">App ID (optional)</label>
                <Input
                  value={ibAppId}
                  onChange={(e) => setIbAppId(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="App ID from Infobip"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase">Phone Number</label>
                <Input
                  value={ibPhoneNumber}
                  onChange={(e) => setIbPhoneNumber(e.target.value)}
                  className="mt-1 bg-slate-800 border-slate-700 text-white"
                  placeholder="+1234567890"
                />
              </div>
              <Button
                onClick={handleSaveInfobip}
                disabled={isLoading || !ibApiKey}
                className="w-full bg-orange-500 hover:bg-orange-600"
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

