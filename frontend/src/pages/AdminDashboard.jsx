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
        background: 'linear-gradient(-45deg, #0f0a1e, #1e1145, #2d1b69, #1a1333)',
        backgroundSize: '400% 400%',
        animation: 'gradientShift 15s ease infinite'
      }}>
      
      {/* Background orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 right-0 w-[500px] h-[500px] rounded-full opacity-20"
          style={{ background: 'radial-gradient(circle, rgba(139, 92, 246, 0.5) 0%, transparent 70%)' }} />
        <div className="absolute bottom-0 left-1/4 w-[400px] h-[400px] rounded-full opacity-15"
          style={{ background: 'radial-gradient(circle, rgba(34, 211, 238, 0.5) 0%, transparent 70%)' }} />
      </div>

      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-full w-64 p-4 flex flex-col z-20"
        style={{
          background: 'rgba(255, 255, 255, 0.02)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRight: '1px solid rgba(255, 255, 255, 0.05)'
        }}>
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 px-2">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.3), rgba(168, 85, 247, 0.2))',
              border: '1px solid rgba(167, 139, 250, 0.3)',
              boxShadow: '0 0 20px rgba(139, 92, 246, 0.3)'
            }}>
            <img src="/logo.png" alt="American Club" className="w-7 h-7 object-contain" />
          </div>
          <div>
            <h1 className="font-bold text-white text-sm" style={{ textShadow: '0 0 20px rgba(167, 139, 250, 0.3)' }}>American Club</h1>
            <p className="text-[10px] text-purple-400 font-semibold">ADMIN PANEL</p>
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
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-300`}
              style={{
                background: activeTab === item.id ? 'linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(168, 85, 247, 0.1))' : 'transparent',
                border: activeTab === item.id ? '1px solid rgba(139, 92, 246, 0.3)' : '1px solid transparent',
                color: activeTab === item.id ? '#a78bfa' : '#94a3b8',
                boxShadow: activeTab === item.id ? '0 0 20px rgba(139, 92, 246, 0.2)' : 'none'
              }}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm font-medium">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* User info */}
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)' }} className="pt-4 mt-4">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold"
              style={{
                background: 'linear-gradient(135deg, #8b5cf6, #a855f7)',
                boxShadow: '0 0 20px rgba(139, 92, 246, 0.4)'
              }}>
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white truncate">{user.name}</p>
              <p className="text-[10px] text-white/50 truncate">{user.email}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onLogout}
            className="w-full justify-start text-red-400 hover:text-red-300 hover:bg-red-500/10"
            style={{
              border: '1px solid rgba(239, 68, 68, 0.2)',
              transition: 'all 0.3s ease'
            }}
          >
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="ml-64 p-6 relative z-10">
        {/* Dashboard Tab */}
        {activeTab === "dashboard" && stats && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white neon-text">Dashboard</h2>
            
            <div className="grid grid-cols-4 gap-4">
              <StatCard
                icon={Users}
                label="Total Users"
                value={stats.users.total}
                subtext={`${stats.users.active} active`}
                color="violet"
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
          </div>
        )}

        {/* Users Tab */}
        {activeTab === "users" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-white neon-text">Users</h2>
              <Button 
                onClick={() => fetchUsers()} 
                variant="outline" 
                size="sm" 
                className="glass-card border-white/20 text-white/80 hover:bg-white/10 hover:text-white"
                style={{ backdropFilter: 'blur(10px)' }}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>

            <div className="glass-table">
              <table className="w-full">
                <thead className="glass-table-header">
                  <tr>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">User</th>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Role</th>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Credits</th>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Status</th>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Invite Code</th>
                    <th className="text-right text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {users.map((u) => (
                    <tr key={u.id} className="glass-table-row">
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-white">{u.name}</p>
                          <p className="text-xs text-white/50">{u.email}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 text-[10px] font-medium rounded-full ${
                          u.role === "admin" ? "bg-purple-500/20 text-purple-400 badge-glow" : "bg-slate-500/20 text-white/60"
                        }`}>
                          {u.role.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-mono text-cyan-400 neon-text">{u.credits}</span>
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
                        {u.role !== "admin" && (
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
              <h2 className="text-2xl font-bold text-white neon-text">Invite Codes</h2>
              <Button 
                onClick={() => setShowCreateCode(true)} 
                className="glow-button text-white"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Code
              </Button>
            </div>

            <div className="glass-table">
              <table className="w-full">
                <thead className="glass-table-header">
                  <tr>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Code</th>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Credits</th>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Status</th>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Used By</th>
                    <th className="text-left text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Notes</th>
                    <th className="text-right text-xs font-medium text-white/70 uppercase tracking-wider px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {inviteCodes.map((code) => (
                    <tr key={code.id} className="glass-table-row">
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
                        <span className="text-sm font-mono text-cyan-400 neon-text">{code.credits}</span>
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
                          disabled={code.is_used}
                          title={code.is_used ? "Cannot delete used code" : "Delete Code"}
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
              <div className="glass-card-static p-3" style={{ background: 'rgba(34, 211, 238, 0.1)', border: '1px solid rgba(34, 211, 238, 0.3)' }}>
                <p className="text-xs text-white/70">Current Balance</p>
                <p className="text-2xl font-mono text-cyan-400 neon-text">{selectedUser.credits} credits</p>
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
    </div>
  );
}

// Stat Card Component
function StatCard({ icon: Icon, label, value, subtext, color }) {
  const colors = {
    violet: { bg: 'rgba(139, 92, 246, 0.1)', border: 'rgba(139, 92, 246, 0.3)', text: '#a78bfa', glow: 'rgba(139, 92, 246, 0.2)' },
    teal: { bg: 'rgba(20, 184, 166, 0.1)', border: 'rgba(20, 184, 166, 0.3)', text: '#5eead4', glow: 'rgba(20, 184, 166, 0.2)' },
    amber: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.3)', text: '#fbbf24', glow: 'rgba(245, 158, 11, 0.2)' },
    emerald: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.3)', text: '#6ee7b7', glow: 'rgba(16, 185, 129, 0.2)' },
    cyan: { bg: 'rgba(34, 211, 238, 0.1)', border: 'rgba(34, 211, 238, 0.3)', text: '#67e8f9', glow: 'rgba(34, 211, 238, 0.2)' },
    purple: { bg: 'rgba(168, 85, 247, 0.1)', border: 'rgba(168, 85, 247, 0.3)', text: '#c084fc', glow: 'rgba(168, 85, 247, 0.2)' },
    yellow: { bg: 'rgba(234, 179, 8, 0.1)', border: 'rgba(234, 179, 8, 0.3)', text: '#facc15', glow: 'rgba(234, 179, 8, 0.2)' },
  };

  const colorScheme = colors[color];

  return (
    <div 
      className="glass-card p-5 transition-all duration-300 hover:scale-105"
      style={{
        background: `linear-gradient(135deg, ${colorScheme.bg}, rgba(255, 255, 255, 0.02))`,
        border: `1px solid ${colorScheme.border}`,
        boxShadow: `0 8px 32px rgba(0, 0, 0, 0.3), 0 0 20px ${colorScheme.glow}`
      }}
    >
      <div className="flex items-center gap-3 mb-4">
        <div 
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{
            background: `linear-gradient(135deg, ${colorScheme.text}, ${colorScheme.border})`,
            boxShadow: `0 0 15px ${colorScheme.glow}`
          }}
        >
          <Icon className="w-5 h-5 text-white" />
        </div>
        <span className="text-xs font-semibold text-white/70 uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-3xl font-bold text-white neon-text" style={{ color: colorScheme.text }}>{value}</p>
      {subtext && <p className="text-sm text-white/50 mt-1">{subtext}</p>}
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
      style={{ background: 'rgba(0, 0, 0, 0.5)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="glass-card p-6 w-full max-w-md max-h-[90vh] overflow-y-auto"
        style={{
          background: 'rgba(15, 10, 30, 0.9)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(167, 139, 250, 0.3)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5), 0 0 40px rgba(139, 92, 246, 0.2)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-bold text-white neon-text mb-4">{title}</h3>
        {children}
      </motion.div>
    </motion.div>
  );
}

// Providers Tab Component - Full Phone Number Management
function ProvidersTab({ authHeaders }) {
  const [providers, setProviders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
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
        <h2 className="text-2xl font-bold text-white neon-text">Provider Settings</h2>
        <Button 
          onClick={fetchProviders} 
          variant="outline" 
          size="sm"
          className="glass-card border-white/20 text-white/80 hover:bg-white/10 hover:text-white"
          style={{ backdropFilter: 'blur(10px)' }}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SignalWire Card */}
        <div className="glass-card overflow-hidden">
          <div className="p-5" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
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
                    className="flex items-center justify-between p-2 rounded-lg glass-card-static"
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full status-glow ${phone.is_active ? 'bg-emerald-400' : 'bg-slate-500'}`} />
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
        <div className="glass-card overflow-hidden">
          <div className="p-5" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
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
              <p className="text-gray-400 text-sm">No phone numbers configured</p>
            ) : (
              <div className="space-y-2">
                {providers.find(p => p.id === "infobip")?.phone_numbers?.map((phone) => (
                  <div 
                    key={phone.id || phone.number}
                    className="flex items-center justify-between p-2 rounded-lg bg-gray-50 border border-gray-200"
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${phone.is_active ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                      <span className="font-mono text-sm text-gray-800">{phone.number}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTogglePhoneActive("infobip", phone)}
                        className={`h-7 w-7 p-0 ${phone.is_active ? 'text-emerald-400' : 'text-gray-400'}`}
                        title={phone.is_active ? "Deactivate" : "Activate"}
                      >
                        {phone.is_active ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditPhone("infobip", phone)}
                        className="h-7 w-7 p-0 text-gray-500 hover:text-gray-800"
                      >
                        <Edit className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeletePhoneNumber("infobip", phone.id)}
                        className="h-7 w-7 p-0 text-red-400 hover:text-red-300"
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
                Note: Add phone numbers after saving credentials using the "Add Number" button.
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
                <label className="text-xs font-medium text-gray-500 uppercase">API Key *</label>
                <Input
                  type="password"
                  value={ibApiKey}
                  onChange={(e) => setIbApiKey(e.target.value)}
                  className="mt-1 bg-gray-100 border-gray-300 text-gray-800"
                  placeholder="Your Infobip API Key"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 uppercase">Base URL</label>
                <Input
                  value={ibBaseUrl}
                  onChange={(e) => setIbBaseUrl(e.target.value)}
                  className="mt-1 bg-gray-100 border-gray-300 text-gray-800"
                  placeholder="api.infobip.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 uppercase">App ID (optional)</label>
                <Input
                  value={ibAppId}
                  onChange={(e) => setIbAppId(e.target.value)}
                  className="mt-1 bg-gray-100 border-gray-300 text-gray-800"
                  placeholder="App ID from Infobip"
                />
              </div>
              <p className="text-xs text-gray-400">
                Note: Add phone numbers after saving credentials using the "Add Number" button.
              </p>
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

