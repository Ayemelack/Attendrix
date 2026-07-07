
var API_BASE = '/api/super-admin';
var currentTab = 'overview';
var REFRESH_MS = 15000;
var retryCount = {};

function fmtTime(t) { if (!t) return '\u2014'; try { return new Date(t).toLocaleString(); } catch(e) { return t; } }
function fmtDate(t) { if (!t) return '\u2014'; try { return new Date(t).toLocaleDateString(); } catch(e) { return t; } }
function esc(s) { if (!s) return '\u2014'; var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function riskColor(s) { var n = parseInt(s) || 0; if (n >= 7) return 'high'; if (n >= 4) return 'medium'; return 'low'; }
function riskPct(s) { return Math.min(parseInt(s) || 0, 10) * 10; }

function skeletonCards(n) { return Array(n).fill(0).map(function() { return '<div class="skeleton skeleton-card"></div>'; }).join(''); }
function skeletonRows(n) { return Array(n).fill(0).map(function() { return '<div class="skeleton skeleton-row"></div>'; }).join(''); }
function spinner() { return '<div class="loading-state"><div class="spinner"></div></div>'; }
function emptyState(icon, title, desc) { return '<div class="empty-state"><i class="fas fa-' + icon + '"></i><div class="empty-title">' + title + '</div>' + (desc ? '<div class="empty-desc">' + desc + '</div>' : '') + '</div>'; }
function errorState(msg) { return '<div class="error-state"><i class="fas fa-triangle-exclamation"></i><div>' + esc(msg || 'Failed to load data') + '</div><button class="btn-action auto-refresh-btn" onclick="loadTab(currentTab)"><i class="fas fa-rotate"></i> Retry</button></div>'; }

function toggleSidebar() {
  document.getElementById('sidebarOverlay').classList.toggle('active');
  document.querySelector('.sidebar').classList.toggle('open');
}

function closeSidebarMobile() {
  if (window.innerWidth <= 768) {
    document.getElementById('sidebarOverlay').classList.remove('active');
    document.querySelector('.sidebar').classList.remove('open');
  }
}

function apiFetch(url, cb, key) {
  var k = key || url;
  retryCount[k] = (retryCount[k] || 0) + 1;
  var token = localStorage.getItem('accessToken') || '';
  fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
    .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function(d) { retryCount[k] = 0; cb(d); })
    .catch(function(err) { console.warn('API error:', url, err); if (typeof cb.error === 'function') cb.error(err); });
}

document.querySelectorAll('.nav-item[data-tab]').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('.nav-item').forEach(function(b) { b.classList.remove('active'); });
    this.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(function(t) { t.classList.remove('active'); });
    var tab = this.getAttribute('data-tab');
    document.getElementById('tab-' + tab).classList.add('active');
    var spanText = this.querySelector('span') ? this.querySelector('span').textContent : 'Command';
    document.getElementById('pageTitle').innerHTML = esc(spanText) + ' <span>Command Center</span>';
    currentTab = tab;
    loadTab(tab);
    closeSidebarMobile();
  });
});

function loadTab(tab) {
  var fns = {
    overview: loadOverview, institutions: loadInstitutions, users: loadUsers,
    governance: loadGovernance, attendance: loadAttendance, network: loadNetwork,
    health: loadHealth, security: loadSecurity, 'anti-proxy': loadAntiProxy,
    suspicious: loadSuspicious, 'ai-risk': loadAiRisk, activity: loadActivity,
    audit: loadAudit, analytics: loadAnalytics, bookings: loadBookings,
    feedback: loadFeedback,
  };
  if (fns[tab]) fns[tab]();
}
function refreshAll() {
  if (document.getElementById('tab-vouchers').classList.contains('active')) { loadVouchers(); return; }
  if (document.getElementById('tab-connected-devices').classList.contains('active')) { loadConnectedDevices(); return; } loadTab(currentTab); }


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• OVERVIEW â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadOverview() {
  var statsEl = document.getElementById('overviewStats');
  statsEl.innerHTML = skeletonCards(6);
  apiFetch(API_BASE + '/overview', function(d) {
    if (!d.success) { statsEl.innerHTML = errorState(); return; }
    var o = d.data;
    statsEl.innerHTML =
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-building-columns"></i></div><div class="stat-label">Institutions</div><div class="stat-value">' + (o.total_institutions || 0) + '</div><div class="stat-sub">' + (o.active_institutions || 0) + ' active <span style="color:var(--text-muted)">\u00b7</span> ' + (o.pending_institutions || 0) + ' pending</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-user-graduate"></i></div><div class="stat-label">Users</div><div class="stat-value">' + (o.total_users || 0) + '</div><div class="stat-sub">' + (o.total_students || 0) + ' students <span style="color:var(--text-muted)">\u00b7</span> ' + (o.total_lecturers || 0) + ' lecturers</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-clipboard-check"></i></div><div class="stat-label">Attendance Records</div><div class="stat-value">' + (o.total_attendance_records || 0).toLocaleString() + '</div><div class="stat-sub">' + (o.today_records || 0) + ' today <span style="color:var(--text-muted)">\u00b7</span> ' + (o.attendance_completion_rate || 0) + '% rate</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-triangle-exclamation"></i></div><div class="stat-label">Fraud Intelligence</div><div class="stat-value" style="color:' + ((o.suspicious_records || 0) > 0 ? 'var(--warning)' : 'var(--success)') + '">' + (o.suspicious_records || 0) + '</div><div class="stat-sub">' + (o.proxy_flags || 0) + ' proxy flags <span style="color:var(--text-muted)">\u00b7</span> ' + (o.attendance_fraud_probability || 0) + '% fraud prob.</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-shield"></i></div><div class="stat-label">Security Posture</div><div class="stat-value" style="color:' + ((o.unresolved_alerts || 0) > 0 ? 'var(--danger)' : 'var(--success)') + '">' + (o.security_events || 0) + '</div><div class="stat-sub">' + (o.unresolved_alerts || 0) + ' open <span style="color:var(--text-muted)">\u00b7</span> ' + (o.high_risk_events || 0) + ' high risk</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-gauge"></i></div><div class="stat-label">System</div><div class="stat-value">' + (o.active_sessions || 0) + '</div><div class="stat-sub">' + (o.active_security_incidents || 0) + ' active incidents <span style="color:var(--text-muted)">\u00b7</span> ' + (o.system_uptime_hours || 0) + 'h uptime</div></div>';
    loadOverviewFeed();
    loadOverviewSecurity();
  });
}

function loadOverviewFeed() {
  var el = document.getElementById('overviewFeed');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/activity-feed', function(d) {
    if (!d.success || !d.data || !d.data.length) { el.innerHTML = emptyState('rss', 'No Recent Activity', 'System activity will appear here as users interact with the platform.'); var _e=document.getElementById('overviewFeedCount');if(_e)_e.textContent='0'; return; }
    var _e=document.getElementById('overviewFeedCount');if(_e)_e.textContent=d.data.length;
    el.innerHTML = d.data.slice(0, 8).map(function(a) {
      var icon = 'info';
      if (a.action && a.action.includes('LOGIN')) icon = 'success';
      else if (a.action && (a.action.includes('DELETE') || a.action.includes('SECURITY'))) icon = 'danger';
      else if (a.action && a.action.includes('CREATE')) icon = 'success';
      else if (a.action && a.action.includes('UPDATE')) icon = 'warning';
      return '<div class="feed-item"><div class="feed-icon ' + icon + '"><i class="fas ' + (icon==='info'?'fa-circle-info':icon==='success'?'fa-right-to-bracket':icon==='danger'?'fa-trash':'fa-pen') + '"></i></div><div class="feed-content"><div class="feed-title">' + esc(a.action) + '</div><div class="feed-desc">' + esc(a.resource_type || 'system') + (a.institution_name ? ' \u00b7 ' + esc(a.institution_name) : '') + '</div><div class="feed-meta">' + fmtTime(a.timestamp) + (a.ip_address ? ' \u00b7 ' + esc(a.ip_address) : '') + '</div></div></div>';
    }).join('');
  });
}

function loadOverviewSecurity() {
  var el = document.getElementById('overviewSecurity');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/security-events?min_risk=4', function(d) {
    if (!d.success || !d.data || !d.data.length) { el.innerHTML = emptyState('shield-check', 'No Security Events', 'No medium-to-high risk security events detected.'); var _e=document.getElementById('overviewSecurityCount');if(_e)_e.textContent='0'; return; }
    var _e=document.getElementById('overviewSecurityCount');if(_e)_e.textContent=d.data.length;
    el.innerHTML = d.data.slice(0, 8).map(function(e) {
      var cls = riskColor(e.risk_score);
      return '<div class="feed-item"><div class="feed-icon ' + cls + '"><i class="fas fa-bolt"></i></div><div class="feed-content"><div class="feed-title">' + esc(e.event_type) + '</div><div class="feed-desc">' + esc(e.description || '') + (e.institution_name ? ' \u00b7 ' + esc(e.institution_name) : '') + '</div><div class="feed-meta">Risk: ' + (e.risk_score || 0) + '/10 \u00b7 ' + fmtTime(e.created_at) + '</div></div></div>';
    }).join('');
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• INSTITUTIONS â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

/* === VOUCHERS === */
var allVouchersData = [];
function loadVouchers() {
  var el = document.getElementById('vouchersTableBody');
  el.innerHTML = '<tr><td colspan="6" class="loading-state"><div class="spinner"></div></td></tr>';
  
  loadVoucherAnalytics();
  loadVoucherTimeline();
  
  var cb = function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="6" class="error-state">Failed to load</td></tr>'; return; }
    if (!d.data || !d.data.length) { el.innerHTML = '<tr><td colspan="6" class="empty-state"><i class="fas fa-ticket"></i><br><div class="empty-title">No Vouchers</div></td></tr>'; return; }
    
    allVouchersData = d.data;
    renderVouchersTable(allVouchersData);
  };
  
  cb.error = function(err) {
    el.innerHTML = '<tr><td colspan="6" class="error-state">Failed to load vouchers: API Error</td></tr>';
  };
  
  apiFetch(API_BASE + '/vouchers', cb);
}

function renderVouchersTable(data) {
  var el = document.getElementById('vouchersTableBody');
  el.innerHTML = data.map(function(v) {
    var roleBadge = '<span class="status-badge role-' + esc(v.role).replace(/_/g, '-') + '">' + esc(v.role).replace(/_/g, ' ') + '</span>';
    var statusBadge = '<span class="status-badge ' + (v.revoked ? 'inactive' : (v.is_used ? 'success' : 'active')) + '">' + (v.revoked ? 'Revoked' : (v.is_used ? 'Redeemed' : 'Pending')) + '</span>';
    
    var assignHtml = v.assigned_to_email ? 
      ('<div style="font-size:0.8rem;color:var(--text);"><i class="fas fa-user"></i> ' + esc(v.assigned_to_name || 'User') + '</div><div style="font-size:0.75rem;color:var(--text-muted);"><i class="fas fa-envelope"></i> ' + esc(v.assigned_to_email) + '</div>') : 
      '<span style="color:var(--text-muted);font-style:italic;font-size:0.8rem;">Unassigned</span>';
      
    var emailStatusHtml = '';
    if (v.email_sent_status === 'sent') emailStatusHtml = '<i class="fas fa-check-double" style="color:var(--success);" title="Sent"></i>';
    else if (v.email_sent_status === 'queued') emailStatusHtml = '<i class="fas fa-clock" style="color:var(--warning);" title="Queued"></i>';
    else if (v.email_sent_status === 'failed') emailStatusHtml = '<i class="fas fa-triangle-exclamation" style="color:var(--danger);" title="Failed"></i>';
    
    if (emailStatusHtml) assignHtml += '<div style="margin-top:2px;">' + emailStatusHtml + ' <span style="font-size:0.75rem;color:var(--text-muted);">' + fmtTime(v.email_sent_at) + '</span></div>';

    var actions = '<button class="btn-action" onclick="copyVoucherCode(\'" + v.code + "\')" title="Copy Code"><i class="fas fa-copy"></i></button>';
    if (!v.revoked && !v.is_used) {
      actions += '<button class="btn-action primary" onclick="openEmailVoucherModal(\'" + v.id + "\')" title="Send via Email"><i class="fas fa-paper-plane"></i></button>';
      actions += '<button class="btn-action danger" onclick="revokeVoucher(\'" + v.id + "\')" title="Revoke"><i class="fas fa-ban"></i></button>';
    }

    return '<tr>' +
      '<td><strong style="font-family:monospace; color:var(--primary-light);font-size:1.1rem;letter-spacing:1px;">' + esc(v.code) + '</strong></td>' +
      '<td>' + roleBadge + '<div style="font-size:0.8rem;color:var(--text-muted);margin-top:4px;">' + esc(v.institution_name || 'Global') + '</div></td>' +
      '<td>' + assignHtml + '</td>' +
      '<td>' + statusBadge + '</td>' +
      '<td style="font-size:0.8rem;color:var(--text-secondary);">' +
        '<div><i class="fas fa-plus-circle" style="color:var(--text-muted);width:14px;"></i> ' + fmtTime(v.created_at) + '</div>' +
        (v.used_at ? '<div><i class="fas fa-check-circle" style="color:var(--success);width:14px;"></i> ' + fmtTime(v.used_at) + '</div>' : '') +
      '</td>' +
      '<td><div style="display:flex;gap:0.4rem;">' + actions + '</div></td>' +
    '</tr>';
  }).join('');
}

function filterVouchers() {
  var q = document.getElementById('voucherSearchInput').value.toLowerCase();
  if (!q) { renderVouchersTable(allVouchersData); return; }
  var f = allVouchersData.filter(function(v) {
    return v.code.toLowerCase().includes(q) || 
           (v.assigned_to_email && v.assigned_to_email.toLowerCase().includes(q)) || 
           (v.assigned_to_name && v.assigned_to_name.toLowerCase().includes(q)) ||
           (v.institution_name && v.institution_name.toLowerCase().includes(q));
  });
  renderVouchersTable(f);
}

function copyVoucherCode(code) {
  navigator.clipboard.writeText(code).then(function() {
    alert("Voucher copied successfully.");
  }).catch(function() {
    prompt("Copy code manually:", code);
  });
}

function openEmailVoucherModal(id) {
  document.getElementById('emailVoucherId').value = id;
  document.getElementById('emailVoucherName').value = '';
  document.getElementById('emailVoucherAddress').value = '';
  document.getElementById('emailVoucherMessage').value = '';
  document.getElementById('emailVoucherModal').style.display = 'flex';
}

function submitEmailVoucher() {
  var id = document.getElementById('emailVoucherId').value;
  var email = document.getElementById('emailVoucherAddress').value;
  var name = document.getElementById('emailVoucherName').value;
  var msg = document.getElementById('emailVoucherMessage').value;
  
  if (!email) { alert("Email address is required"); return; }
  
  document.getElementById('btnSendVoucherEmail').innerHTML = '<div class="spinner" style="width:14px;height:14px;"></div> Sending...';
  
  fetch(API_BASE + '/vouchers/' + id + '/email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + localStorage.getItem('accessToken') },
    body: JSON.stringify({ email: email, name: name, message: msg })
  }).then(r => r.json()).then(d => {
    document.getElementById('btnSendVoucherEmail').innerHTML = '<i class="fas fa-paper-plane"></i> Send Email';
    if (d.success) {
      document.getElementById('emailVoucherModal').style.display = 'none';
      loadVouchers(); // Refresh
    } else {
      alert('Failed: ' + d.error);
    }
  }).catch(err => {
    document.getElementById('btnSendVoucherEmail').innerHTML = '<i class="fas fa-paper-plane"></i> Send Email';
    alert('Request failed');
  });
}

function loadVoucherAnalytics() {
  apiFetch(API_BASE + '/vouchers/analytics', function(d) {
    if (!d.success) return;
    var s = d.data;
    var cards = document.getElementById('voucherAnalyticsCards');
    if (cards) {
      cards.innerHTML = 
        '<div class="stat-card"><div class="stat-icon"><i class="fas fa-ticket"></i></div><div class="stat-label">Total Created</div><div class="stat-value">' + s.total_created + '</div><div class="stat-sub">' + (s.generation.this_month) + ' this month</div></div>' +
        '<div class="stat-card"><div class="stat-icon"><i class="fas fa-envelope-circle-check"></i></div><div class="stat-label">Assigned</div><div class="stat-value" style="color:var(--primary-light);">' + s.total_assigned + '</div><div class="stat-sub">' + s.total_emailed + ' emailed</div></div>' +
        '<div class="stat-card"><div class="stat-icon"><i class="fas fa-check-to-slot"></i></div><div class="stat-label">Redeemed</div><div class="stat-value" style="color:var(--success);">' + s.total_redeemed + '</div><div class="stat-sub">Successfully used</div></div>' +
        '<div class="stat-card"><div class="stat-icon"><i class="fas fa-clock-rotate-left"></i></div><div class="stat-label">Pending</div><div class="stat-value" style="color:var(--warning);">' + s.pending + '</div><div class="stat-sub">Awaiting redemption</div></div>';
    }
  });
}

function loadVoucherTimeline() {
  apiFetch(API_BASE + '/vouchers/timeline', function(d) {
    var tb = document.getElementById('voucherTimelineBody');
    if (!tb) return;
    if (!d.success || !d.data.length) { tb.innerHTML = emptyState('history', 'No Activity', 'Timeline will populate as vouchers are created and used.'); return; }
    
    tb.innerHTML = '<div class="activity-feed">' + d.data.map(function(e) {
      var icon = 'fa-circle-info';
      var color = 'var(--text-muted)';
      if (e.type === 'created') { icon = 'fa-plus'; color = 'var(--primary-light)'; }
      else if (e.type === 'assigned' || e.type === 'emailed') { icon = 'fa-envelope'; color = 'var(--warning)'; }
      else if (e.type === 'redeemed') { icon = 'fa-check'; color = 'var(--success)'; }
      else if (e.type === 'revoked') { icon = 'fa-ban'; color = 'var(--danger)'; }
      
      return '<div style="display:flex;gap:1rem;margin-bottom:1rem;position:relative;">' +
             '<div style="width:2px;background:var(--border-color);position:absolute;left:11px;top:24px;bottom:-16px;z-index:0;"></div>' +
             '<div style="width:24px;height:24px;border-radius:50%;background:var(--surface);border:2px solid ' + color + ';display:flex;align-items:center;justify-content:center;z-index:1;color:' + color + ';font-size:0.7rem;"><i class="fas ' + icon + '"></i></div>' +
             '<div style="flex:1;">' +
               '<div style="font-size:0.9rem;color:var(--text);">' + esc(e.message) + '</div>' +
               '<div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">' + fmtTime(e.timestamp) + ' · <strong style="font-family:monospace;">' + esc(e.code) + '</strong></div>' +
             '</div>' +
             '</div>';
    }).join('') + '</div>';
  });
}


function submitCreateVoucher() {
  var role = document.getElementById('newVoucherRole').value;
  var inst = document.getElementById('newVoucherInstitution').value;
  fetch(API_BASE + '/vouchers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + localStorage.getItem('accessToken') },
    body: JSON.stringify({ role: role, institution_id: inst || null })
  }).then(r => r.json()).then(d => {
    if (d.success) {
      document.getElementById('createVoucherModal').style.display = 'none';
      loadVouchers();
    } else {
      alert('Failed: ' + d.error);
    }
  });
}

function revokeVoucher(id) {
  if (!confirm('Revoke this voucher?')) return;
  fetch(API_BASE + '/vouchers/' + id + '/revoke', { method: 'POST', headers: { 'Authorization': 'Bearer ' + localStorage.getItem('accessToken') } })
  .then(r => r.json()).then(d => {
    if (d.success) loadVouchers();
    else alert('Failed: ' + d.error);
  });
}

/* === CONNECTED DEVICES === */
function loadConnectedDevices() {
  var el = document.getElementById('devicesTableBody');
  el.innerHTML = '<tr><td colspan="4" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(API_BASE + '/connected-devices', function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="4" class="error-state">Failed to load</td></tr>'; return; }
    var _e = document.getElementById('devicesCount'); if (_e) _e.textContent = d.data.length + ' online';
    if (!d.data || !d.data.length) { el.innerHTML = '<tr><td colspan="4" class="empty-state"><i class="fas fa-mobile-screen"></i><br><div class="empty-title">No Connected Devices</div><div class="empty-desc">No devices currently connected to the system.</div></td></tr>'; return; }
    el.innerHTML = d.data.map(function(dev) {
      return '<tr>' +
        '<td><strong>' + esc(dev.user_name) + '</strong></td>' +
        '<td><div style=" font-size: 0.9rem;">' + esc(dev.os) + '</div><div style="font-size:0.8rem; color:var(--text-muted); max-width:250px; overflow:hidden; text-overflow:ellipsis;">' + esc(dev.user_agent) + '</div></td>' +
        '<td><span style="font-family:monospace; background:var(--bg-secondary); padding:0.2rem 0.4rem; border-radius:4px; font-size:0.85rem;">' + esc(dev.ip_address) + '</span></td>' +
        '<td style="font-size:0.85rem;">' + fmtTime(dev.last_seen) + '</td>' +
      '</tr>';
    }).join('');
  });
}

function loadInstitutions() {
  var el = document.getElementById('instTableBody');
  el.innerHTML = '<tr><td colspan="10" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(API_BASE + '/institutions', function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="10" class="error-state">Failed to load</td></tr>'; return; }
    var _e=document.getElementById('instCount');if(_e)_e.textContent=d.data.length;
    if (!d.data.length) { el.innerHTML = '<tr><td colspan="10" class="empty-state"><i class="fas fa-building-columns"></i><br><div class="empty-title">No Institutions Registered</div><div class="empty-desc">Institutions will appear here once they register on the platform.</div></td></tr>'; return; }
    el.innerHTML = d.data.map(function(i) {
      return '<tr><td><strong>' + esc(i.name) + '</strong></td><td>' + esc(i.code) + '</td>' +
        '<td><span class="status-badge ' + (i.is_active ? 'active' : 'inactive') + '"><span class="status-dot ' + (i.is_active ? 'online' : 'offline') + '"></span>' + (i.is_active ? 'Active' : 'Inactive') + '</span></td>' +
        '<td>' + (i.total_admins || 0) + '</td><td>' + (i.total_lecturers || 0) + '</td><td>' + (i.total_students || 0) + '</td><td>' + (i.total_employees || 0) + '</td>' +
        '<td><span style="font-weight:600;color:' + ((i.attendance_rate || 0) >= 70 ? 'var(--success)' : (i.attendance_rate || 0) >= 40 ? 'var(--warning)' : 'var(--danger)') + '">' + (i.attendance_rate || 0) + '%</span></td>' +
        '<td><span class="status-badge ' + ((i.high_risk_events || 0) > 0 ? 'high' : 'low') + '">' + (i.security_events || 0) + ' events</span></td>' +
        '<td><button class="btn-action" onclick="toggleInstitution(\'' + esc(i.id) + '\')"><i class="fas ' + (i.is_active ? 'fa-pause' : 'fa-play') + '"></i></button></td></tr>';
    }).join('');
  });
}

function toggleInstitution(id) {
  if (!confirm('Toggle this institution\'s status?')) return;
  fetch(API_BASE + '/institution/' + id + '/toggle-status', { method: 'POST' }).then(function(r) { return r.json(); }).then(function(d) { if (d.success) loadInstitutions(); else alert('Failed: ' + (d.error || 'Unknown')); });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• USERS â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadUsers() {
  var role = document.getElementById('userRoleFilter').value;
  var search = document.getElementById('userSearch').value;
  var url = API_BASE + '/users?';
  if (role) url += 'role=' + encodeURIComponent(role) + '&';
  if (search) url += 'search=' + encodeURIComponent(search) + '&';
  var el = document.getElementById('userTableBody');
  el.innerHTML = '<tr><td colspan="8" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(url, function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="8" class="error-state">Failed to load</td></tr>'; return; }
    var _e=document.getElementById('userCount');if(_e)_e.textContent=d.data.length;
    if (!d.data.length) { el.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-users"></i><br><div class="empty-title">No Users Found</div><div class="empty-desc">' + (search || role ? 'No users match the current filters.' : 'No users registered yet.') + '</div></td></tr>'; return; }
    el.innerHTML = d.data.map(function(u) {
      return '<tr><td><strong>' + esc(u.full_name || u.email) + '</strong></td><td>' + esc(u.email) + '</td>' +
        '<td><span class="status-badge role-' + esc(u.role || '').replace(/_/g, '-') + '">' + esc(u.role || '').replace(/_/g, ' ') + '</span></td>' +
        '<td>' + esc(u.institution_name) + '</td>' +
        '<td><span class="status-badge ' + (u.is_active ? 'active' : 'inactive') + '">' + (u.is_active ? 'Active' : 'Inactive') + '</span></td>' +
        '<td>' + (u.email_verified ? '<i class="fas fa-check-circle" style="color:var(--success)"></i>' : '<i class="fas fa-times-circle" style="color:var(--text-muted)"></i>') + '</td>' +
        '<td style="font-size:0.85rem;">' + fmtTime(u.last_login) + '</td>' +
        '<td><button class="btn-action" onclick="toggleUser(\'' + esc(u.id) + '\')"><i class="fas ' + (u.is_active ? 'fa-ban' : 'fa-check') + '"></i></button></td></tr>';
    }).join('');
  });
}

function toggleUser(id) {
  if (!confirm('Toggle this user\'s active status?')) return;
  fetch(API_BASE + '/user/' + id + '/toggle-status', { method: 'POST' }).then(function(r) { return r.json(); }).then(function(d) { if (d.success) loadUsers(); else alert('Failed: ' + (d.error || 'Unknown')); });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• ROLE GOVERNANCE â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadGovernance() {
  var el = document.getElementById('governanceContent');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/role-governance', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    var g = d.data;
    var roles = g.role_distribution || {};
    var roleKeys = Object.keys(roles);
    var roleCards = roleKeys.length ? roleKeys.map(function(r) {
      var iconMap = { super_admin: 'fa-crown', institutional_admin: 'fa-building-shield', lecturer: 'fa-chalkboard-user', student: 'fa-user-graduate', employee: 'fa-user-tie' };
      var colorMap = { super_admin: 'var(--danger)', institutional_admin: 'var(--warning)', lecturer: 'var(--info)', student: 'var(--success)', employee: 'var(--accent)' };
      return '<div class="gov-role-card"><div class="gov-icon" style="color:' + (colorMap[r] || 'var(--text-muted)') + '"><i class="fas ' + (iconMap[r] || 'fa-user') + '"></i></div><div class="gov-count">' + (roles[r] || 0) + '</div><div class="gov-label">' + esc(r.replace(/_/g, ' ')) + '</div></div>';
    }).join('') : '<div class="empty-state" style="grid-column:1/-1"><i class="fas fa-users"></i><div class="empty-title">No Users Registered</div><div class="empty-desc">User role distribution will appear once users are onboarded.</div></div>';

    el.innerHTML =
      '<div class="section-header"><h2><i class="fas fa-scale-balanced"></i> Role Distribution</h2><span class="badge-count">' + (g.total_users || 0) + ' total</span></div>' +
      '<div class="four-col">' + roleCards + '</div>' +
      '<div class="two-col" style="margin-top:1rem;">' +
      '<div><div class="section-header"><h2>Account Status</h2></div><div class="table-wrap"><table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>' +
      '<tr><td>Total Users</td><td><strong>' + (g.total_users || 0) + '</strong></td></tr>' +
      '<tr><td><span style="color:var(--success)">\u25cf</span> Active</td><td><strong>' + (g.active_users || 0) + '</strong></td></tr>' +
      '<tr><td><span style="color:var(--danger)">\u25cf</span> Suspended</td><td><strong>' + (g.suspended_users || 0) + '</strong></td></tr>' +
      '<tr><td><span style="color:var(--info)">\u25cf</span> Verified</td><td><strong>' + (g.verified_users || 0) + '</strong></td></tr>' +
      '<tr><td><span style="color:var(--warning)">\u25cf</span> Unverified</td><td><strong>' + (g.unverified_users || 0) + '</strong></td></tr>' +
      '</tbody></table></div></div>' +
      '<div><div class="section-header"><h2>Security Overview</h2></div><div class="table-wrap">' +
      emptyState('shield-check', 'Governance Controls Active', 'Role-based access controls and permission boundaries are enforced across all institutions.') +
      '</div></div></div>';
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• ATTENDANCE â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadAttendance() {
  var el = document.getElementById('attendanceContent');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/attendance/overview', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    var o = d.data;
    el.innerHTML =
      '<div class="stats-grid">' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-chart-simple"></i></div><div class="stat-label">Attendance Rate</div><div class="stat-value" style="color:' + ((o.attendance_rate || 0) >= 80 ? 'var(--success)' : (o.attendance_rate || 0) >= 60 ? 'var(--warning)' : 'var(--danger)') + '">' + (o.attendance_rate || 0) + '%</div><div class="stat-sub">' + (o.total_sessions || 0) + ' total sessions</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-clock"></i></div><div class="stat-label">Active Sessions</div><div class="stat-value">' + (o.active_sessions || 0) + '</div><div class="stat-sub">Currently running</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-user-graduate"></i></div><div class="stat-label">Students Tracked</div><div class="stat-value">' + (o.students_with_attendance || 0) + '</div><div class="stat-sub">of ' + (o.enrolled_students || 0) + ' enrolled</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-record-vinyl"></i></div><div class="stat-label">Avg Per Session</div><div class="stat-value">' + (o.avg_records_per_session || 0) + '</div><div class="stat-sub">Records per session</div></div>' +
      '</div>' +
      '<div class="section-header"><h2>Attendance Breakdown</h2></div>' +
      '<div class="table-wrap"><table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>' +
      (o.total_records > 0 ?
      '<tr><td><strong>Total Records</strong></td><td>' + (o.total_records || 0).toLocaleString() + '</td></tr>' +
      '<tr><td><span style="color:var(--success)">\u25cf</span> Present</td><td>' + (o.present || 0).toLocaleString() + '</td></tr>' +
      '<tr><td><span style="color:var(--warning)">\u25cf</span> Late</td><td>' + (o.late || 0).toLocaleString() + '</td></tr>' +
      '<tr><td><span style="color:var(--danger)">\u25cf</span> Absent</td><td>' + (o.absent || 0).toLocaleString() + '</td></tr>' +
      '<tr><td><span style="color:var(--info)">\u25cf</span> Excused</td><td>' + (o.excused || 0).toLocaleString() + '</td></tr>' +
      '<tr><td><span style="color:var(--danger)">\u26a0</span> Suspicious</td><td>' + (o.suspicious_records || 0) + '</td></tr>'
      : '<tr><td colspan="2" class="empty-state"><i class="fas fa-clipboard-check"></i><br><div class="empty-title">No Attendance Data</div><div class="empty-desc">Attendance records will appear here once sessions are created and students start marking attendance.</div></td></tr>') +
      '</tbody></table></div>';
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• NETWORK â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadNetwork() {
  var el = document.getElementById('networkContent');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/network-infrastructure', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    var n = d.data;
    var nodes = n.institutions || [];
    el.innerHTML =
      '<div class="section-header"><h2><i class="fas fa-network-wired"></i> Distributed Network Topology</h2><span class="badge-count">' + (n.total_nodes || 0) + ' nodes</span></div>' +
      '<div class="stats-grid">' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-server"></i></div><div class="stat-label">Total Nodes</div><div class="stat-value">' + (n.total_nodes || 0) + '</div><div class="stat-sub">Institutional endpoints</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-wifi"></i></div><div class="stat-label">Online</div><div class="stat-value" style="color:var(--success)">' + (n.online_nodes || 0) + '</div><div class="stat-sub">' + (n.offline_nodes || 0) + ' offline</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-clock-rotate-left"></i></div><div class="stat-label">Sync Latency</div><div class="stat-value" style="color:' + ((n.sync_latency_ms || 0) > 30 ? 'var(--warning)' : 'var(--success)') + '">' + (n.sync_latency_ms || 0) + 'ms</div><div class="stat-sub">MQTT sync</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-tower-broadcast"></i></div><div class="stat-label">MQTT Broker</div><div class="stat-value" style="color:var(--success);font-size:1rem;"><span class="status-dot online" style="margin-right:0.3rem;"></span>' + esc(n.mqtt_status || 'connected') + '</div><div class="stat-sub">Message queue</div></div>' +
      '</div>' +
      '<div class="section-header"><h2>Node Status</h2><span class="badge-count">' + nodes.length + '</span></div>' +
      '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:0.65rem;">' +
      (nodes.length ? nodes.map(function(node) {
        return '<div class="node-card"><div class="node-status" style="background:' + (node.is_active ? 'var(--success)' : 'var(--danger)') + ';box-shadow:0 0 8px ' + (node.is_active ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)') + '"></div><div><div class="node-name">' + esc(node.name || 'Unknown') + '</div><div class="node-meta">' + esc(node.code || '') + ' \u00b7 ' + (node.is_active ? 'Online' : 'Offline') + '</div></div></div>';
      }).join('') : '<div class="empty-state" style="grid-column:1/-1"><i class="fas fa-network-wired"></i><div class="empty-title">No Network Nodes</div><div class="empty-desc">Institutional nodes will appear here as they connect to the distributed network.</div></div>') +
      '</div>';
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• SYSTEM HEALTH â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadHealth() {
  var el = document.getElementById('healthContent');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/system-health', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    var h = d.data;
    var statusColor = h.status === 'operational' ? 'var(--success)' : 'var(--warning)';
    var statusIcon = h.status === 'operational' ? 'fa-check-circle' : 'fa-exclamation-triangle';
    el.innerHTML =
      '<div class="section-header"><h2><i class="fas fa-heart-pulse"></i> System Health Dashboard</h2></div>' +
      '<div class="health-grid">' +
      '<div class="health-card"><div class="hc-icon" style="color:' + statusColor + '"><i class="fas ' + statusIcon + '"></i></div><div class="hc-value" style="color:' + statusColor + ';text-transform:capitalize;">' + esc(h.status.replace(/_/g, ' ')) + '</div><div class="hc-label">System Status</div></div>' +
      '<div class="health-card"><div class="hc-icon" style="color:var(--info)"><i class="fas fa-clock"></i></div><div class="hc-value">' + (h.uptime_hours || 0) + 'h</div><div class="hc-label">Uptime</div></div>' +
      '<div class="health-card"><div class="hc-icon" style="color:var(--success)"><i class="fas fa-building-columns"></i></div><div class="hc-value">' + (h.active_institutions || 0) + '</div><div class="hc-label">Active Institutions</div></div>' +
      '<div class="health-card"><div class="hc-icon" style="color:var(--primary-light)"><i class="fas fa-users"></i></div><div class="hc-value">' + (h.users_active_today || 0) + '</div><div class="hc-label">Users Today</div></div>' +
      '<div class="health-card"><div class="hc-icon" style="color:' + ((h.events_last_hour || 0) > 0 ? 'var(--warning)' : 'var(--success)') + '"><i class="fas fa-bolt"></i></div><div class="hc-value">' + (h.events_last_hour || 0) + '</div><div class="hc-label">Events (1h)</div></div>' +
      '<div class="health-card"><div class="hc-icon" style="color:var(--text-muted)"><i class="fas fa-database"></i></div><div class="hc-value">' + (h.total_users || 0) + '</div><div class="hc-label">Total Users</div></div>' +
      '<div class="health-card"><div class="hc-icon" style="color:var(--accent)"><i class="fas fa-tower-broadcast"></i></div><div class="hc-value" style="text-transform:capitalize;">' + esc(h.mqtt_health || 'operational') + '</div><div class="hc-label">MQTT</div></div>' +
      '<div class="health-card"><div class="hc-icon" style="color:var(--info)"><i class="fas fa-arrows-rotate"></i></div><div class="hc-value" style="text-transform:capitalize;">' + esc(h.sync_status || 'synchronized') + '</div><div class="hc-label">Sync Status</div></div>' +
      '</div>' +
      '<div class="empty-state"><i class="fas fa-heart-pulse" style="color:var(--success);opacity:1;"></i><div class="empty-title">All Systems ' + (h.status === 'operational' ? 'Operational' : 'Monitored') + '</div><div class="empty-desc">Last checked: ' + fmtTime(h.last_checked) + '</div></div>';
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• SOC / SECURITY â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadSecurity() {
  var el = document.getElementById('securityContent');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/security-events', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    var data = d.data || [];
    var high = data.filter(function(e) { return (e.risk_score || 0) >= 7; }).length;
    var unresolved = data.filter(function(e) { return !e.is_resolved; }).length;
    var _e=document.getElementById('socBadge');if(_e)_e.textContent=unresolved;

    el.innerHTML =
      '<div class="section-header"><h2><i class="fas fa-shield-halved"></i> Security Operations Center</h2><span class="badge-count">' + data.length + ' events</span></div>' +
      '<div class="security-summary">' +
      '<div class="security-card"><div class="sc-value" style="color:var(--' + (data.length > 0 ? 'danger' : 'success') + ')">' + (data.length || 0) + '</div><div class="sc-label">Total Events</div></div>' +
      '<div class="security-card"><div class="sc-value" style="color:var(--danger)">' + high + '</div><div class="sc-label">High Risk</div></div>' +
      '<div class="security-card"><div class="sc-value" style="color:var(--warning)">' + unresolved + '</div><div class="sc-label">Unresolved</div></div>' +
      '</div>' +
      '<div class="section-header"><h2>Threat Log</h2><select id="riskFilter" onchange="loadSecurityTable()"><option value="0">All Levels</option><option value="7">High (7+)</option><option value="4">Medium (4+)</option></select></div>' +
      '<div class="table-wrap"><table><thead><tr><th>Event Type</th><th>Description</th><th>Institution</th><th>Risk</th><th>Status</th><th>Actions</th></tr></thead><tbody id="securityTableBody"></tbody></table></div>';
    loadSecurityTable();
  });
}

function loadSecurityTable() {
  var minRisk = (document.getElementById('riskFilter') || {}).value || '0';
  var el = document.getElementById('securityTableBody');
  if (!el) return;
  el.innerHTML = '<tr><td colspan="6" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(API_BASE + '/security-events?min_risk=' + minRisk, function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="6" class="error-state">Failed to load</td></tr>'; return; }
    var data = d.data || [];
    if (!data.length) { el.innerHTML = '<tr><td colspan="6" class="empty-state"><i class="fas fa-shield-check" style="color:var(--success)"></i><br><div class="empty-title">No Security Events</div><div class="empty-desc">No events at this risk level. The system is secure.</div></td></tr>'; return; }
    el.innerHTML = data.map(function(e) {
      return '<tr><td><strong>' + esc(e.event_type) + '</strong></td><td>' + esc(e.description || '') + '</td><td>' + esc(e.institution_name || '\u2014') + '</td>' +
        '<td><div class="risk-bar"><div class="risk-bar-fill" style="width:' + riskPct(e.risk_score) + '%;background:var(--' + riskColor(e.risk_score) + ')"></div></div><span style="font-size:0.8rem;">' + (e.risk_score || 0) + '/10</span></td>' +
        '<td><span class="status-badge ' + (e.is_resolved ? 'active' : 'high') + '">' + (e.is_resolved ? 'Resolved' : 'Open') + '</span></td>' +
        '<td>' + (e.is_resolved ? '' : '<button class="btn-action success" onclick="resolveSecurity(\'' + esc(e.id) + '\')"><i class="fas fa-check"></i> Resolve</button>') + '</td></tr>';
    }).join('');
  });
}

function resolveSecurity(id) {
  fetch(API_BASE + '/security-events/' + id + '/resolve', { method: 'POST' }).then(function(r) { return r.json(); }).then(function(d) { if (d.success) loadSecurity(); else alert('Failed: ' + (d.error || 'Unknown')); });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• ANTI-PROXY INTELLIGENCE â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadAntiProxy() {
  var el = document.getElementById('antiProxyContent');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/anti-proxy-intelligence', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    var a = d.data;
    var reasons = a.reasons || {};
    var reasonKeys = Object.keys(reasons);
    el.innerHTML =
      '<div class="section-header"><h2><i class="fas fa-user-secret"></i> Anti-Proxy Intelligence</h2><span class="badge-count">' + (a.total_suspicious || 0) + ' flagged</span></div>' +
      '<div class="security-summary">' +
      '<div class="security-card"><div class="sc-value" style="color:' + ((a.total_suspicious || 0) > 0 ? 'var(--warning)' : 'var(--success)') + '">' + (a.total_suspicious || 0) + '</div><div class="sc-label">Suspicious Records</div></div>' +
      '<div class="security-card"><div class="sc-value" style="color:' + ((a.proxy_attendance_flags || 0) > 0 ? 'var(--danger)' : 'var(--success)') + '">' + (a.proxy_attendance_flags || 0) + '</div><div class="sc-label">Proxy/VPN Flags</div></div>' +
      '<div class="security-card"><div class="sc-value" style="color:' + ((a.geolocation_mismatches || 0) > 0 ? 'var(--warning)' : 'var(--success)') + '">' + (a.geolocation_mismatches || 0) + '</div><div class="sc-label">Geo Mismatches</div></div>' +
      '<div class="security-card"><div class="sc-value" style="color:' + ((a.device_fingerprint_anomalies || 0) > 0 ? 'var(--warning)' : 'var(--success)') + '">' + (a.device_fingerprint_anomalies || 0) + '</div><div class="sc-label">Device Anomalies</div></div>' +
      '<div class="security-card"><div class="sc-value" style="color:' + ((a.duplicate_attendance_flags || 0) > 0 ? 'var(--danger)' : 'var(--success)') + '">' + (a.duplicate_attendance_flags || 0) + '</div><div class="sc-label">Duplicate Flags</div></div>' +
      '<div class="security-card"><div class="sc-value" style="color:' + ((a.fraud_probability || 0) > 10 ? 'var(--danger)' : (a.fraud_probability || 0) > 5 ? 'var(--warning)' : 'var(--success)') + '">' + (a.fraud_probability || 0) + '%</div><div class="sc-label">Fraud Probability</div></div>' +
      '</div>' +
      '<div class="section-header"><h2>Detection Breakdown</h2></div>' +
      '<div class="table-wrap"><table><thead><tr><th>Detection Type</th><th>Count</th><th>Severity</th></tr></thead><tbody>' +
      (reasonKeys.length ? reasonKeys.map(function(k) {
        var count = reasons[k] || 0;
        var sev = count > 10 ? 'high' : count > 3 ? 'medium' : 'low';
        return '<tr><td><strong>' + esc(k.charAt(0).toUpperCase() + k.slice(1)) + '</strong></td><td>' + count + '</td><td><span class="status-badge ' + sev + '">' + sev.charAt(0).toUpperCase() + sev.slice(1) + '</span></td></tr>';
      }).join('') : '<tr><td colspan="3" class="empty-state"><i class="fas fa-shield-check" style="color:var(--success)"></i><br><div class="empty-title">No Detection Data</div><div class="empty-desc">Anti-proxy intelligence will activate when suspicious patterns are detected across attendance records.</div></td></tr>') +
      '</tbody></table></div>';
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• SUSPICIOUS ACTIVITY â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadSuspicious() {
  var el = document.getElementById('suspiciousTableBody');
  el.innerHTML = '<tr><td colspan="7" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(API_BASE + '/suspicious-activity', function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="7" class="error-state">Failed to load</td></tr>'; return; }
    var data = d.data || [];
    var _e=document.getElementById('suspiciousCount');if(_e)_e.textContent=data.length;
    if (!data.length) { el.innerHTML = '<tr><td colspan="7" class="empty-state"><i class="fas fa-check-circle" style="color:var(--success)"></i><br><div class="empty-title">No Suspicious Activity</div><div class="empty-desc">All attendance records appear legitimate. Suspicious patterns will be flagged here.</div></td></tr>'; return; }
    el.innerHTML = data.map(function(r) {
      return '<tr><td><strong>' + esc(r.student_name || 'Unknown') + '</strong></td><td>' + esc(r.student_email || '') + '</td>' +
        '<td>' + esc(r.institution_name || '\u2014') + '</td>' +
        '<td><span class="status-badge ' + (r.status === 'present' ? 'active' : 'inactive') + '">' + esc(r.status) + '</span></td>' +
        '<td style="color:var(--warning)">' + esc(r.suspicion_reason || '\u2014') + '</td>' +
        '<td style="font-size:0.85rem;">' + esc(r.ip_address || '\u2014') + '</td><td style="font-size:0.85rem;">' + fmtTime(r.marked_at || r.created_at) + '</td></tr>';
    }).join('');
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• AI RISK INTELLIGENCE â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadAiRisk() {
  var el = document.getElementById('aiRiskContent');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/ai-risk-intelligence', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    var r = d.data;
    var riskIndex = r.overall_risk_index || 0;
    var recs = r.recommendations || [];

    var riskLevel = riskIndex < 3 ? 'low' : riskIndex < 6 ? 'moderate' : riskIndex < 8 ? 'high' : 'critical';
    var riskLabel = riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1);
    var riskColorVal = riskLevel === 'low' ? 'var(--success)' : riskLevel === 'moderate' ? 'var(--info)' : riskLevel === 'high' ? 'var(--warning)' : 'var(--danger)';

    var highRiskInsts = r.high_risk_institutions || [];

    el.innerHTML =
      '<div class="section-header"><h2><i class="fas fa-brain"></i> AI-Powered Risk Intelligence</h2><span class="badge-count" style="background:rgba(' + (riskLevel==='critical'?'239,68,68':riskLevel==='high'?'245,158,11':riskLevel==='moderate'?'6,182,212':'16,185,129') + ',0.15);color:' + riskColorVal + '">' + riskLabel + '</span></div>' +
      '<div class="stats-grid">' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-gauge-high"></i></div><div class="stat-label">Overall Risk Index</div><div class="stat-value" style="color:' + riskColorVal + '">' + riskIndex + '/10</div><div class="stat-sub">' + riskLabel + ' risk level</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-timer"></i></div><div class="stat-label">Today\'s Suspicious</div><div class="stat-value" style="color:' + ((r.today_suspicious_count || 0) > 0 ? 'var(--warning)' : 'var(--success)') + '">' + (r.today_suspicious_count || 0) + '</div><div class="stat-sub">Flagged today</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-building-columns"></i></div><div class="stat-label">High-Risk Institutions</div><div class="stat-value" style="color:var(--danger)">' + highRiskInsts.length + '</div><div class="stat-sub">Flagged for review</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-chart-line"></i></div><div class="stat-label">Prediction</div><div class="stat-value" style="font-size:1rem;text-transform:capitalize;color:' + (r.prediction === 'elevated_risk' ? 'var(--warning)' : 'var(--success)') + ';">' + esc((r.prediction || 'stable').replace(/_/g, ' ')) + '</div><div class="stat-sub">AI forecast</div></div>' +
      '</div>' +
      (highRiskInsts.length ? '<div class="section-header"><h2>High-Risk Institutions</h2><span class="badge-count">' + highRiskInsts.length + '</span></div><div class="table-wrap"><table><thead><tr><th>Institution</th><th>Risk Score</th><th>Suspicious Records</th><th>Security Events</th></tr></thead><tbody>' + highRiskInsts.map(function(inst) {
        return '<tr><td><strong>' + esc(inst.name) + '</strong></td><td><span class="risk-indicator ' + (inst.risk_score >= 7 ? 'high' : 'moderate') + '">' + inst.risk_score + '/10</span></td><td>' + (inst.suspicious_records || 0) + '</td><td>' + (inst.security_events || 0) + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '') +
      '<div class="section-header" style="margin-top:1rem;"><h2>AI Recommendations</h2></div>' +
      (recs.length ? recs.map(function(rec) {
        return '<div class="recommendation-card"><div class="rec-text"><i class="fas fa-lightbulb" style="color:var(--accent);margin-right:0.4rem;"></i>' + esc(rec) + '</div></div>';
      }).join('') : '<div class="empty-state"><i class="fas fa-lightbulb" style="opacity:0.5;"></i><div class="empty-title">No Recommendations</div><div class="empty-desc">AI risk intelligence will generate recommendations as data patterns emerge.</div></div>');
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• ACTIVITY â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadActivity() {
  var el = document.getElementById('activityFeedList');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/activity-feed', function(d) {
    if (!d.success) { el.innerHTML = '<div class="error-state">Failed to load</div>'; return; }
    var data = d.data || [];
    var _e=document.getElementById('activityCount');if(_e)_e.textContent=data.length;
    if (!data.length) { el.innerHTML = emptyState('rss', 'No Activity Recorded', 'System activity will appear here as users interact with the platform.'); return; }
    el.innerHTML = data.map(function(a) {
      var icon = 'info';
      if (a.action && a.action.includes('LOGIN')) icon = 'success';
      else if (a.action && (a.action.includes('DELETE') || a.action.includes('SECURITY'))) icon = 'danger';
      else if (a.action && a.action.includes('CREATE')) icon = 'success';
      else if (a.action && a.action.includes('UPDATE')) icon = 'warning';
      var actionStr = a.action || 'Unknown';
      return '<div class="feed-item"><div class="feed-icon ' + icon + '"><i class="fas ' + (icon==='info'?'fa-circle-info':icon==='success'?'fa-right-to-bracket':icon==='danger'?'fa-trash':'fa-pen') + '"></i></div><div class="feed-content"><div class="feed-title">' + esc(actionStr.replace(/_/g,' ')) + '</div><div class="feed-desc">' + esc(a.resource_type || 'system') + (a.institution_name ? ' \u00b7 ' + esc(a.institution_name) : '') + '</div><div class="feed-meta">' + fmtTime(a.timestamp) + (a.ip_address ? ' \u00b7 ' + esc(a.ip_address) : '') + '</div></div></div>';
    }).join('');
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• AUDIT â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadAudit() {
  var action = (document.getElementById('auditActionFilter') || {}).value;
  var url = API_BASE + '/audit-logs';
  if (action) url += '?action=' + encodeURIComponent(action);
  var el = document.getElementById('auditTableBody');
  el.innerHTML = '<tr><td colspan="6" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(url, function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="6" class="error-state">Failed to load</td></tr>'; return; }
    var data = d.data || [];
    if (!data.length) { el.innerHTML = '<tr><td colspan="6" class="empty-state"><i class="fas fa-list"></i><br><div class="empty-title">No Audit Logs</div><div class="empty-desc">' + (action ? 'No logs match the selected filter.' : 'Audit logs will appear here as system actions are recorded.') + '</div></td></tr>'; return; }
    el.innerHTML = data.map(function(l) {
      return '<tr><td><strong>' + esc((l.action || '').replace(/_/g,' ')) + '</strong></td><td>' + esc(l.resource_type || '\u2014') + '</td><td>' + esc(l.institution_name || '\u2014') + '</td><td style="font-size:0.85rem;">' + esc(l.user_id || '').substring(0,12) + '...</td><td style="font-size:0.85rem;">' + esc(l.ip_address || '\u2014') + '</td><td style="font-size:0.85rem;">' + fmtTime(l.timestamp) + '</td></tr>';
    }).join('');
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• ANALYTICS â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadAnalytics() {
  var el = document.getElementById('analyticsContent');
  el.innerHTML = spinner();
  apiFetch(API_BASE + '/attendance-analytics', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    var a = d.data;
    var rate = a.overall_rate || 0;
    var rateColor = rate >= 80 ? 'var(--success)' : rate >= 60 ? 'var(--warning)' : 'var(--danger)';

    var instRows = '';
    if (a.institution_performance && a.institution_performance.length > 0) {
      instRows = a.institution_performance.slice(0, 15).map(function(i) {
        var ir = i.attendance_rate || 0;
        var ic = ir >= 80 ? 'success' : ir >= 60 ? 'warning' : 'danger';
        return '<tr><td>' + esc(i.institution_name) + '</td><td>' + (i.total_records || 0) + '</td><td>' + (i.present || 0) + '</td><td>' + (i.absent || 0) + '</td><td>' + (i.late || 0) + '</td><td><div class="risk-bar"><div class="risk-bar-fill" style="width:' + ir + '%;background:var(--' + ic + ')"></div></div><span style="font-size:0.8rem;">' + ir + '%</span></td><td>' + (i.suspicious || 0) + '</td></tr>';
      }).join('');
    } else {
      instRows = '<tr><td colspan="7" class="empty-state"><i class="fas fa-chart-simple"></i><br><div class="empty-title">No Institution Data</div><div class="empty-desc">Performance data will appear once institutions have attendance records.</div></td></tr>';
    }

    el.innerHTML =
      '<div class="section-header"><h2><i class="fas fa-chart-line"></i> Attendance Analytics</h2></div>' +
      '<div class="stats-grid">' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-chart-pie"></i></div><div class="stat-label">Overall Rate</div><div class="stat-value" style="color:' + rateColor + '">' + rate + '%</div><div class="stat-sub">' + (a.total_records || 0) + ' total records</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-clock"></i></div><div class="stat-label">Today\'s Rate</div><div class="stat-value" style="color:' + ((a.today_rate || 0) >= 80 ? 'var(--success)' : 'var(--warning)') + '">' + (a.today_rate || 0) + '%</div><div class="stat-sub">' + (a.today_records || 0) + ' today</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-triangle-exclamation"></i></div><div class="stat-label">Low Performing</div><div class="stat-value" style="color:' + ((a.low_performing_institutions || []).length > 0 ? 'var(--danger)' : 'var(--success)') + '">' + (a.low_performing_institutions || []).length + '</div><div class="stat-sub">Below 50% rate</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-clock"></i></div><div class="stat-label">Active Sessions</div><div class="stat-value">' + (a.active_sessions || 0) + '</div><div class="stat-sub">' + (a.total_sessions || 0) + ' total</div></div>' +
      '</div>' +
      '<div class="section-header"><h2>Institution Performance Rankings</h2><span class="badge-count">' + (a.institution_performance ? a.institution_performance.length : 0) + '</span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>Institution</th><th>Records</th><th>Present</th><th>Absent</th><th>Late</th><th>Rate</th><th>Suspicious</th></tr></thead><tbody>' + instRows + '</tbody></table></div>';
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• DEMO BOOKINGS â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
function loadBookings() {
  var el = document.getElementById('bookingTableBody');
  el.innerHTML = '<tr><td colspan="8" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(API_BASE + '/demo-bookings', function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="8" class="error-state">Failed to load</td></tr>'; return; }
    var data = d.data || [];
    var _e=document.getElementById('bookingCount');if(_e)_e.textContent=data.length;
    if (!data.length) { el.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-calendar-check"></i><br><div class="empty-title">No Demo Bookings</div><div class="empty-desc">Demo booking requests will appear here when institutions request a demo of the platform.</div></td></tr>'; return; }
    el.innerHTML = data.map(function(b) {
      var statusCls = 'pending';
      if (b.status === 'confirmed' || b.status === 'completed') statusCls = 'active';
      else if (b.status === 'cancelled' || b.status === 'expired') statusCls = 'inactive';
      var prog = b.onboarding_progress || 0;
      return '<tr><td><strong>' + esc(b.full_name) + '</strong></td><td>' + esc(b.email) + '</td><td>' + esc(b.institution) + '</td><td>' + esc(b.institution_type) + '</td><td>' + (b.number_of_students || 0) + '</td>' +
        '<td><span class="status-badge ' + statusCls + '">' + esc(b.status) + '</span></td>' +
        '<td style="font-size:0.85rem;">' + (b.preferred_date ? fmtDate(b.preferred_date) : '\u2014') + '</td>' +
        '<td><div class="risk-bar"><div class="risk-bar-fill" style="width:' + prog + '%;background:var(--' + (prog >= 80 ? 'success' : prog >= 40 ? 'warning' : 'info') + ')"></div></div><span style="font-size:0.8rem;">' + prog + '%</span></td></tr>';
    }).join('');
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• FEEDBACK INTELLIGENCE CENTER â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
/* â”€â”€â”€ Enterprise SaaS Feedback Control Center â”€â”€â”€ */
var fbSSESource = null;

function loadFeedback() {
  var el = document.getElementById('feedbackContent');
  el.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';

  var FDB = '/api/super-admin/feedback';

  // Connect SSE for real-time updates
  connectFeedbackSSE();

  function renderUI(overview) {
    var o = overview || {};
    var badge = document.getElementById('feedbackBadge');
    if (badge) badge.textContent = (o.unviewed || 0) || '0';

    var sevColors = {critical:'#EF4444',high:'#F59E0B',medium:'#3B82F6',low:'#6B7280'};
    var sevHtml = o.severity_counts ? Object.entries(o.severity_counts).map(function(e) {
      return '<div class="stat-card" style="min-width:90px;"><div class="stat-label">' + e[0].charAt(0).toUpperCase() + e[0].slice(1) + '</div><div class="stat-value" style="color:' + (sevColors[e[0]]||'var(--text)') + ';font-size:1.2rem;">' + e[1] + '</div></div>';
    }).join('') : '';

    var sentColors = {positive:'#22C55E',negative:'#EF4444',neutral:'#6B7280'};
    var sentHtml = o.sentiment_counts ? Object.entries(o.sentiment_counts).map(function(e) {
      return '<span style="color:' + (sentColors[e[0]]||'var(--text-muted)') + ';font-weight:600;font-size:0.85rem;">' + e[0].charAt(0).toUpperCase() + e[0].slice(1) + ': ' + e[1] + '</span>';
    }).join(' \u00b7 ') : '';

    var trendingHtml = (o.trending && o.trending.length) ? o.trending.map(function(f) {
      return '<div class="policy-card" style="padding:0.65rem;cursor:pointer;" onclick="viewFeedbackDetail(\'' + f.id + '\')"><div style="display:flex;justify-content:space-between;align-items:center;"><strong style="font-size:0.85rem;">' + esc(f.title) + '</strong><span class="status-badge ' + (f.severity === 'critical' ? 'inactive' : f.severity === 'high' ? 'pending' : 'active') + '" style="font-size:0.55rem;">' + f.severity + '</span></div><div style="display:flex;gap:1rem;margin-top:0.2rem;font-size:0.85rem;color:var(--text-muted);"><span>' + esc(f.category.replace(/_/g,' ')) + '</span><span><i class="fas fa-arrow-up"></i> ' + f.upvotes + '</span><span>' + fmtTime(f.created_at) + '</span></div></div>';
    }).join('') : '<div style="font-size:0.85rem;color:var(--text-muted);padding:1rem;text-align:center;">No trending issues</div>';

    el.innerHTML =
      '<div class="section-header"><h2><i class="fas fa-comments"></i> Feedback Control Center</h2>' +
      '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;">' +
      '<span class="badge-count" style="background:rgba(239,68,68,0.15);color:#FCA5A5;">' + (o.critical||0) + ' Critical</span>' +
      '<span class="badge-count" style="background:rgba(245,158,11,0.15);color:#FDE68A;">' + (o.high||0) + ' High</span>' +
      '<span class="badge-count" style="background:rgba(59,130,246,0.15);color:#93C5FD;">' + (o.unviewed||0) + ' Unviewed</span>' +
      '<span class="badge-count" style="background:rgba(34,197,94,0.15);color:#86EFAC;">' + (o.resolved||0) + ' Resolved</span>' +
      '<span style="font-size:0.85rem;color:var(--text-muted);display:flex;align-items:center;" id="fbLiveIndicator"><i class="fas fa-circle" style="color:var(--success);font-size:0.4rem;margin-right:0.3rem;"></i> Live</span>' +
      '</div></div>' +

      '<div class="stats-grid">' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-message"></i></div><div class="stat-label">Total Feedback</div><div class="stat-value">' + (o.total||0) + '</div><div class="stat-sub">' + (o.today||0) + ' today</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-clock"></i></div><div class="stat-label">Open</div><div class="stat-value" style="color:' + ((o.open||0) > (o.total||1) * 0.5 ? 'var(--warning)' : 'var(--text)') + '">' + (o.open||0) + '</div><div class="stat-sub">' + (o.hidden||0) + ' hidden \u00b7 ' + (o.flagged||0) + ' flagged</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-arrow-up"></i></div><div class="stat-label">Upvotes</div><div class="stat-value">' + (o.upvotes_total||0) + '</div><div class="stat-sub">Community engagement</div></div>' +
      '<div class="stat-card"><div class="stat-icon"><i class="fas fa-check-circle"></i></div><div class="stat-label">Resolution</div><div class="stat-value" style="color:var(--success);">' + (o.total > 0 ? Math.round(o.resolved/o.total*100) : 0) + '%</div><div class="stat-sub">' + (o.resolved||0) + ' resolved</div></div>' +
      '</div>' +

      '<div class="two-col">' +
      '<div><div class="section-header" style="margin-top:0.5rem;"><h2>Severity</h2></div><div class="stats-grid" style="grid-template-columns:repeat(auto-fill,minmax(80px,1fr));">' + sevHtml + '</div></div>' +
      '<div><div class="section-header" style="margin-top:0.5rem;"><h2>Sentiment</h2></div><div style="display:flex;gap:0.5rem;flex-wrap:wrap;padding:0.75rem;background:var(--surface);border-radius:12px;">' + (sentHtml || '<span style="color:var(--text-muted);font-size:0.85rem;">No sentiment data</span>') + '</div></div>' +
      '</div>' +

      '<div class="two-col">' +
      '<div><div class="section-header" style="margin-top:0.5rem;"><h2>Trending Issues</h2></div><div style="display:grid;gap:0.4rem;">' + trendingHtml + '</div></div>' +
      '<div><div class="section-header" style="margin-top:0.5rem;"><h2>Top Institutions</h2></div><div class="table-wrap" style="max-height:240px;"><table><thead><tr><th>Institution</th><th>Reports</th></tr></thead><tbody>' + ((o.top_institutions && o.top_institutions.length) ? o.top_institutions.map(function(i) { return '<tr><td>' + esc(i.name||'Unknown') + '</td><td>' + i.count + '</td></tr>'; }).join('') : '<tr><td colspan="2" style="text-align:center;color:var(--text-muted);font-size:0.85rem;">No data</td></tr>') + '</tbody></table></div></div>' +
      '</div>' +

      '<div class="section-header" style="margin-top:1rem;"><h2><i class="fas fa-chart-line"></i> Trends & Analytics</h2></div>' +
      '<div id="feedbackAnalyticsSection"><div class="loading-state"><div class="spinner"></div></div></div>' +

      '<div class="section-header" style="margin-top:1rem;"><h2><i class="fas fa-users"></i> User Activity Insights</h2></div>' +
      '<div id="feedbackActivitySection"><div class="loading-state"><div class="spinner"></div></div></div>' +

      '<div class="section-header" style="margin-top:1rem;"><h2><i class="fas fa-list"></i> All Feedback</h2>' +
      '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;">' +
      '<select id="fbFilterStatus" onchange="loadFeedbackList()"><option value="">All Status</option><option value="open">Open</option><option value="in_review">In Review</option><option value="resolved">Resolved</option><option value="archived">Archived</option><option value="hidden">Hidden</option></select>' +
      '<select id="fbFilterCategory" onchange="loadFeedbackList()"><option value="">All Categories</option><option value="attendance_issue">Attendance</option><option value="bug_report">Bug</option><option value="feature_request">Feature</option><option value="network_failure">Network</option><option value="security_concern">Security</option><option value="sync_failure">Sync</option><option value="suggestion">Suggestion</option><option value="general">General</option></select>' +
      '<select id="fbFilterSeverity" onchange="loadFeedbackList()"><option value="">All Severity</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>' +
      '<input type="text" id="fbSearch" placeholder="Search..." style="width:130px;max-width:100%;font-size:0.78rem;" oninput="var t=this;setTimeout(function(){if(t.value===t._v)loadFeedbackList();t._v=t.value;},300)">' +
      '<label style="display:flex;align-items:center;gap:0.2rem;font-size:0.72rem;cursor:pointer;white-space:nowrap;"><input type="checkbox" id="fbUnviewedOnly" onchange="loadFeedbackList()"> Unviewed</label>' +
      '<label style="display:flex;align-items:center;gap:0.2rem;font-size:0.72rem;cursor:pointer;white-space:nowrap;"><input type="checkbox" id="fbFlaggedOnly" onchange="loadFeedbackList()"> Flagged</label>' +
      '<label style="display:flex;align-items:center;gap:0.2rem;font-size:0.72rem;cursor:pointer;white-space:nowrap;"><input type="checkbox" id="fbHiddenOnly" onchange="loadFeedbackList()"> Hidden</label>' +
      '<label style="display:flex;align-items:center;gap:0.2rem;font-size:0.72rem;cursor:pointer;white-space:nowrap;"><input type="checkbox" id="fbEscalatedOnly" onchange="loadFeedbackList()"> Escalated</label>' +
      '<select id="fbSort" onchange="loadFeedbackList()" style="font-size:0.72rem;"><option value="latest">Latest</option><option value="upvotes">Upvoted</option><option value="severity">Severity</option><option value="oldest">Oldest</option></select>' +
      '<button class="btn-action" onclick="loadFeedbackList()" title="Apply filters"><i class="fas fa-filter"></i></button>' +
      '<a href="/api/super-admin/feedback/export?format=csv" class="btn-action" title="Export CSV" style="text-decoration:none;"><i class="fas fa-download"></i></a>' +
      '</div></div>' +
      '<div class="table-wrap" style="max-height:500px;overflow-y:auto;"><table><thead><tr><th>Title</th><th>Category</th><th>Severity</th><th>Status</th><th>Inst.</th><th>Upvotes</th><th>Replies</th><th>Sentiment</th><th>Esc.</th><th>Viewed</th><th>Created</th><th>Actions</th></tr></thead><tbody id="feedbackListBody"></tbody></table></div>' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.5rem;"><span id="fbPaginationInfo" style="font-size:0.78rem;color:var(--text-muted);"></span><div id="fbPaginationBtns" style="display:flex;gap:0.4rem;"></div></div>';

    loadFeedbackList();
    loadFeedbackAnalytics();
    loadFeedbackActivity();
  }

  apiFetch(FDB + '/overview', function(d) {
    if (!d.success) { el.innerHTML = errorState(); return; }
    renderUI(d.data);
  });
}

function connectFeedbackSSE() {
  if (fbSSESource) { fbSSESource.close(); }
  fbSSESource = new EventSource('/api/feedback/events/stream');
  fbSSESource.onmessage = function(e) {
    try {
      var d = JSON.parse(e.data);
      if (d.type === 'overview' && d.data) {
        var badge = document.getElementById('feedbackBadge');
        if (badge) badge.textContent = (d.data.unviewed || 0) || '0';
        var liveDot = document.querySelector('#fbLiveIndicator i');
        if (liveDot) liveDot.style.color = 'var(--success)';
      }
    } catch(ex) {}
  };
  fbSSESource.onerror = function() {
    var liveDot = document.querySelector('#fbLiveIndicator i');
    if (liveDot) liveDot.style.color = 'var(--danger)';
    setTimeout(connectFeedbackSSE, 5000);
  };
}

function loadFeedbackAnalytics() {
  var section = document.getElementById('feedbackAnalyticsSection');
  if (!section) return;
  apiFetch('/api/super-admin/feedback/analytics', function(d) {
    if (!d.success || !d.data) { section.innerHTML = '<div class="error-state">Analytics unavailable</div>'; return; }
    var a = d.data;
    var dailyHtml = '';
    if (a.daily_counts && a.daily_counts.length) {
      var maxCount = Math.max.apply(null, a.daily_counts.map(function(dd) { return dd.count; })) || 1;
      dailyHtml = '<div style="display:flex;align-items:flex-end;gap:4px;min-height:80px;">' +
        a.daily_counts.slice(-14).map(function(dd) {
          var pct = (dd.count / maxCount) * 100;
          return '<div title="' + dd.date + ': ' + dd.count + '" style="flex:1;display:flex;flex-direction:column;align-items:center;"><div style="width:100%;background:linear-gradient(180deg,var(--primary),var(--accent));border-radius:3px 3px 0 0;height:' + pct + 'px;min-height:4px;transition:height 0.3s;" onmouseover="this.style.opacity=\'0.8\'" onmouseout="this.style.opacity=\'1\'"></div><span style="font-size:0.5rem;color:var(--text-muted);margin-top:2px;">' + dd.date.slice(-5) + '</span></div>';
        }).join('') + '</div>';
    } else {
      dailyHtml = '<div style="font-size:0.85rem;color:var(--text-muted);padding:1rem;text-align:center;">No daily data yet</div>';
    }

    var catHtml = '';
    if (a.category_distribution && a.category_distribution.length) {
      var catMax = Math.max.apply(null, a.category_distribution.map(function(c) { return c.count; })) || 1;
      catHtml = a.category_distribution.map(function(c) {
        var pct = (c.count / catMax) * 100;
        return '<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.3rem;"><span style="width:90px;font-size:0.72rem;color:var(--text-muted);text-align:right;">' + c.name.replace(/_/g,' ') + '</span><div style="flex:1;height:16px;background:var(--surface-card);border-radius:8px;overflow:hidden;"><div style="height:100%;width:' + pct + '%;background:linear-gradient(90deg,var(--primary),var(--accent));border-radius:8px;transition:width 0.5s;"></div></div><span style="font-size:0.72rem;color:var(--text-secondary);min-width:30px;">' + c.count + '</span></div>';
      }).join('');
    }

    var deviceHtml = '';
    if (a.device_breakdown && a.device_breakdown.length) {
      deviceHtml = a.device_breakdown.map(function(dd) {
        return '<span style="font-size:0.78rem;color:var(--text-secondary);"><i class="fas fa-' + (dd.type === 'mobile' ? 'mobile-screen' : 'desktop') + '"></i> ' + dd.type + ': ' + dd.count + '</span>';
      }).join(' \u00b7 ');
    }

    section.innerHTML =
      '<div class="two-col">' +
      '<div><div class="section-header"><h3 style="font-size:0.85rem;">Daily Submissions (14 days)</h3></div>' + dailyHtml + '</div>' +
      '<div><div class="section-header"><h3 style="font-size:0.85rem;">Category Distribution</h3></div>' + catHtml + '</div>' +
      '</div>' +
      '<div class="two-col" style="margin-top:0.5rem;">' +
      '<div style="display:flex;gap:1rem;flex-wrap:wrap;padding:0.75rem;background:var(--surface);border-radius:12px;">' +
      '<span style="font-size:0.78rem;color:var(--text-muted);"><i class="fas fa-chart-pie"></i> Network Issues: <strong style="color:var(--text);">' + (a.network_issues||0) + '</strong></span>' +
      '<span style="font-size:0.78rem;color:var(--text-muted);"><i class="fas fa-gauge-high"></i> Resolution Rate: <strong style="color:var(--success);">' + (a.resolution_rate||0) + '%</strong></span>' +
      '<span style="font-size:0.78rem;color:var(--text-muted);"><i class="fas fa-arrow-up"></i> Avg Upvotes: <strong style="color:var(--text);">' + (a.avg_upvotes||0) + '</strong></span>' +
      '</div>' +
      '<div style="padding:0.75rem;background:var(--surface);border-radius:12px;display:flex;flex-wrap:wrap;gap:0.5rem;">' +
      (deviceHtml || '<span style="font-size:0.78rem;color:var(--text-muted);">No device data</span>') +
      '</div>' +
      '</div>';
  });
}

function loadFeedbackActivity() {
  var section = document.getElementById('feedbackActivitySection');
  if (!section) return;
  apiFetch('/api/super-admin/feedback/activity', function(dAct) {
    apiFetch('/api/super-admin/feedback/response-times', function(dResp) {
      var actHtml = '', respHtml = '';
      if (dAct.success && dAct.data) {
        var a = dAct.data;
        actHtml = '<div class="two-col"><div style="display:flex;gap:1rem;flex-wrap:wrap;padding:0.75rem;background:var(--surface);border-radius:12px;">' +
          '<span style="font-size:0.78rem;color:var(--text-muted);">Unique Contributors: <strong style="color:var(--text);">' + (a.total_unique_contributors||0) + '</strong></span>' +
          '<span style="font-size:0.78rem;color:var(--text-muted);">Repeat Contributors: <strong style="color:var(--text);">' + (a.repeat_contributors||0) + '</strong></span>' +
          '<span style="font-size:0.78rem;color:var(--text-muted);">Avg Upvotes/User: <strong style="color:var(--text);">' + (a.avg_upvotes_per_user||0) + '</strong></span>' +
          '</div><div></div></div>';
        if (a.top_contributors && a.top_contributors.length) {
          actHtml += '<div style="margin-top:0.5rem;"><table><thead><tr><th>User ID</th><th>Role</th><th>Submissions</th><th>Total Upvotes</th></tr></thead><tbody>' +
            a.top_contributors.map(function(u) {
              return '<tr><td style="font-size:0.85rem;">' + esc(u.user_id.slice(0,12)) + '...</td><td style="font-size:0.72rem;">' + esc(u.role) + '</td><td>' + u.submissions + '</td><td>' + u.total_upvotes + '</td></tr>';
            }).join('') + '</tbody></table></div>';
        }
      }
      if (dResp.success && dResp.data) {
        var r = dResp.data;
        respHtml = '<div style="display:flex;gap:1rem;flex-wrap:wrap;padding:0.75rem;background:var(--surface);border-radius:12px;margin-top:0.5rem;">' +
          '<span style="font-size:0.78rem;color:var(--text-muted);"><i class="fas fa-clock"></i> Avg Resolution: <strong style="color:var(--text);">' + (r.avg_resolution_hours||0) + 'h</strong></span>' +
          '<span style="font-size:0.78rem;color:var(--text-muted);"><i class="fas fa-arrow-up"></i> Max: <strong style="color:var(--warning);">' + (r.max_resolution_hours||0) + 'h</strong></span>' +
          '<span style="font-size:0.78rem;color:var(--text-muted);"><i class="fas fa-arrow-down"></i> Min: <strong style="color:var(--success);">' + (r.min_resolution_hours||0) + 'h</strong></span>' +
          '<span style="font-size:0.78rem;color:var(--text-muted);"><i class="fas fa-check-circle"></i> Resolved (7d): <strong style="color:var(--accent);">' + (r.recently_resolved_7d||0) + '</strong></span>' +
          '</div>';
      }
      section.innerHTML = actHtml + respHtml;
    });
  });
}

var fbCurrentPage = 1;

function loadFeedbackList() {
  var tb = document.getElementById('feedbackListBody');
  if (!tb) return;
  tb.innerHTML = '<tr><td colspan="12" class="loading-state"><div class="spinner"></div></td></tr>';
  var params = 'page=' + fbCurrentPage + '&per_page=30';
  var s = document.getElementById('fbSearch');
  if (s && s.value.trim()) params += '&search=' + encodeURIComponent(s.value.trim());
  var st = document.getElementById('fbFilterStatus');
  if (st && st.value) params += '&status=' + st.value;
  var ct = document.getElementById('fbFilterCategory');
  if (ct && ct.value) params += '&category=' + ct.value;
  var sv = document.getElementById('fbFilterSeverity');
  if (sv && sv.value) params += '&severity=' + sv.value;
  var sort = document.getElementById('fbSort');
  if (sort && sort.value) params += '&sort=' + sort.value;
  var uv = document.getElementById('fbUnviewedOnly');
  if (uv && uv.checked) params += '&unviewed_only=true';
  var fl = document.getElementById('fbFlaggedOnly');
  if (fl && fl.checked) params += '&flagged_only=true';
  var hl = document.getElementById('fbHiddenOnly');
  if (hl && hl.checked) params += '&hidden_only=true';
  var el = document.getElementById('fbEscalatedOnly');
  if (el && el.checked) params += '&escalated_only=true';

  apiFetch('/api/super-admin/feedback/list?' + params, function(d) {
    if (!d.success) { tb.innerHTML = '<tr><td colspan="12" class="error-state">Failed</td></tr>'; return; }
    var items = d.data || [];
    if (!items.length) {
      tb.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:2rem;color:var(--text-muted);font-size:0.9rem;"><i class="fas fa-comments" style="font-size:1.5rem;margin-bottom:0.5rem;display:block;"></i>No feedback matching filters</td></tr>';
      var pi = document.getElementById('fbPaginationInfo');
      if (pi) pi.textContent = '';
      var pb = document.getElementById('fbPaginationBtns');
      if (pb) pb.innerHTML = '';
      return;
    }
    var pi = document.getElementById('fbPaginationInfo');
    if (pi) pi.textContent = 'Page ' + d.page + ' of ' + d.total_pages + ' (' + d.total + ' total)';
    var pb = document.getElementById('fbPaginationBtns');
    if (pb) {
      var bHtml = '';
      if (d.page > 1) bHtml += '<button class="btn-action" onclick="fbPage(' + (d.page - 1) + ')">Prev</button>';
      bHtml += '<span style="font-size:0.72rem;color:var(--text-muted);padding:0 0.4rem;">' + d.page + '</span>';
      if (d.page < d.total_pages) bHtml += '<button class="btn-action" onclick="fbPage(' + (d.page + 1) + ')">Next</button>';
      pb.innerHTML = bHtml;
    }
    tb.innerHTML = items.map(function(f) {
      var sevCls = f.severity === 'critical' ? 'inactive' : f.severity === 'high' ? 'pending' : 'active';
      var viewedIcon = f.admin_viewed ? '<i class="fas fa-eye" style="color:var(--success);font-size:0.85rem;" title="Viewed ' + (f.admin_viewed_at ? fmtTime(f.admin_viewed_at) : '') + '"></i>' : '<i class="fas fa-eye-slash" style="color:var(--text-muted);font-size:0.85rem;" title="Unviewed"></i>';
      var hideIcon = f.is_hidden ? '<i class="fas fa-eye-slash" style="color:var(--warning);font-size:0.85rem;"></i>' : '';
      var flagIcon = f.is_flagged ? '<i class="fas fa-flag" style="color:var(--danger);font-size:0.85rem;"></i>' : '';
      var escLevel = f.escalation_level !== 'none' ? '<span class="status-badge inactive" style="font-size:0.55rem;">' + f.escalation_level + '</span>' : '\u2014';
      return '<tr>' +
        '<td><strong style="font-size:0.85rem;">' + esc(f.title) + '</strong></td>' +
        '<td style="font-size:0.85rem;">' + esc(f.category.replace(/_/g,' ')) + '</td>' +
        '<td><span class="status-badge ' + sevCls + '" style="font-size:0.55rem;">' + f.severity + '</span></td>' +
        '<td><span class="status-badge ' + (f.status === 'resolved' ? 'active' : f.status === 'hidden' || f.status === 'archived' ? 'inactive' : 'pending') + '" style="font-size:0.55rem;">' + f.status + '</span></td>' +
        '<td style="font-size:0.85rem;">' + esc(f.institution || '\u2014') + '</td>' +
        '<td style="font-size:0.8rem;">' + f.upvotes + '</td>' +
        '<td style="font-size:0.8rem;">' + f.reply_count + '</td>' +
        '<td><span style="color:' + (f.sentiment_label === 'positive' ? 'var(--success)' : f.sentiment_label === 'negative' ? 'var(--danger)' : 'var(--text-muted)') + ';font-size:0.85rem;">' + esc(f.sentiment_label || '\u2014') + '</span></td>' +
        '<td>' + escLevel + '</td>' +
        '<td>' + viewedIcon + ' ' + hideIcon + ' ' + flagIcon + '</td>' +
        '<td style="font-size:0.8rem;">' + fmtTime(f.created_at) + '</td>' +
        '<td><button class="btn-action" onclick="viewFeedbackDetail(\'' + f.id + '\')" title="View & Manage"><i class="fas fa-eye"></i></button></td>' +
        '</tr>';
    }).join('');
  });
}

function fbPage(p) {
  fbCurrentPage = p;
  loadFeedbackList();
}

function viewFeedbackDetail(id) {
  var existing = document.getElementById('feedbackDetailModal');
  if (existing) existing.remove();
  var html = '<div id="feedbackDetailModal" style="position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;padding:1rem;" onclick="if(event.target===this)closeFeedbackDetail()">' +
    '<div style="background:var(--darker);border-radius:24px;max-width:720px;width:100%;max-height:90vh;overflow-y:auto;padding:1.5rem;border:1px solid var(--border);box-shadow:0 32px 80px rgba(0,0,0,0.5);" onclick="event.stopPropagation()">' +
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;"><h3 style="margin:0;font-size:1.1rem;" id="fbDetailTitle">Loading...</h3><button class="btn-action" onclick="closeFeedbackDetail()" style="border:none;background:transparent;font-size:1.2rem;"><i class="fas fa-times"></i></button></div>' +
    '<div id="fbDetailBody">Loading...</div></div></div>';
  document.body.insertAdjacentHTML('beforeend', html);

  apiFetch('/api/super-admin/feedback/' + id + '/detail', function(d) {
    if (!d.success || !d.data) {
      document.getElementById('fbDetailBody').innerHTML = '<div class="error-state">Failed to load feedback</div>';
      return;
    }
    var f = d.data;
    document.getElementById('fbDetailTitle').textContent = f.title;
    var sevColor = f.severity === 'critical' ? 'var(--danger)' : f.severity === 'high' ? 'var(--warning)' : f.severity === 'medium' ? 'var(--primary-light)' : 'var(--text-muted)';
    var sevRgb = f.severity === 'critical' ? '239,68,68' : f.severity === 'high' ? '245,158,11' : '59,130,246';

    var repliesHtml = (f.replies && f.replies.length) ? f.replies.map(function(r) {
      return '<div style="padding:0.65rem;background:var(--surface-card);border-radius:12px;margin-bottom:0.4rem;"><div style="display:flex;justify-content:space-between;font-size:0.85rem;color:var(--text-muted);"><span>' + esc(r.display_name) + (r.is_admin ? ' <span style="color:var(--accent);font-weight:600;">(Admin)</span>' : '') + '</span><span>' + fmtTime(r.created_at) + '</span></div><div style="margin-top:0.25rem;font-size:0.85rem;color:var(--text-secondary);">' + esc(r.body) + '</div></div>';
    }).join('') : '<div style="font-size:0.85rem;color:var(--text-muted);padding:0.75rem;text-align:center;">No replies yet.</div>';

    document.getElementById('fbDetailBody').innerHTML =
      '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.75rem;">' +
      '<span class="badge-count" style="font-size:0.8rem;">' + esc(f.category.replace(/_/g,' ')) + '</span>' +
      '<span class="badge-count" style="background:rgba(' + sevRgb + ',0.15);color:' + sevColor + ';font-size:0.8rem;">' + f.severity + '</span>' +
      '<span class="badge-count" style="background:rgba(79,70,229,0.15);color:var(--primary-light);font-size:0.8rem;">' + (f.status || 'open') + '</span>' +
      (f.is_resolved ? '<span class="badge-count" style="background:rgba(34,197,94,0.15);color:#86EFAC;font-size:0.8rem;"><i class="fas fa-check-circle"></i> Resolved</span>' : '') +
      (f.institution ? '<span class="badge-count" style="background:rgba(107,114,128,0.15);color:var(--text-muted);font-size:0.8rem;">' + esc(f.institution) + '</span>' : '') +
      (f.sentiment_label ? '<span class="badge-count" style="background:' + (f.sentiment_label==='positive'?'rgba(34,197,94,0.15)':f.sentiment_label==='negative'?'rgba(239,68,68,0.15)':'rgba(107,114,128,0.15)') + ';color:' + (f.sentiment_label==='positive'?'#86EFAC':f.sentiment_label==='negative'?'#FCA5A5':'var(--text-muted)') + ';font-size:0.8rem;">' + f.sentiment_label + '</span>' : '') +
      '</div>' +
      '<div style="margin-bottom:0.75rem;line-height:1.7;font-size:0.9rem;color:var(--text-secondary);padding:0.75rem;background:var(--surface-card);border-radius:12px;">' + esc(f.description) + '</div>' +
      '<div style="display:flex;gap:1rem;font-size:0.9rem;color:var(--text-muted);margin-bottom:0.75rem;flex-wrap:wrap;">' +
      '<span><i class="fas fa-user-secret"></i> ' + esc(f.display_name || 'Anonymous') + '</span>' +
      '<span><i class="fas fa-arrow-up"></i> ' + f.upvotes + '</span>' +
      '<span><i class="fas fa-reply"></i> ' + (f.reply_count||0) + '</span>' +
      '<span><i class="fas fa-clock"></i> ' + fmtTime(f.created_at) + '</span>' +
      (f.experience_rating ? '<span><i class="fas fa-star"></i> Rating: ' + f.experience_rating + '/5</span>' : '') +
      '</div>' +

      '<div class="section-header" style="margin-top:0.75rem;"><h3 style="font-size:0.85rem;">Status Workflow</h3></div>' +
      '<div style="display:flex;gap:0.4rem;flex-wrap:wrap;margin-bottom:0.75rem;">' +
      '<button class="btn-action" onclick="updateFeedbackStatus(\'' + id + '\',\'open\')" style="background:rgba(79,70,229,0.15);color:var(--primary-light);font-size:0.85rem;"><i class="fas fa-folder-open"></i> Open</button>' +
      '<button class="btn-action" onclick="updateFeedbackStatus(\'' + id + '\',\'in_review\')" style="background:rgba(245,158,11,0.15);color:#FDE68A;font-size:0.85rem;"><i class="fas fa-search"></i> In Review</button>' +
      '<button class="btn-action" onclick="updateFeedbackStatus(\'' + id + '\',\'resolved\')" style="background:rgba(34,197,94,0.15);color:#86EFAC;font-size:0.85rem;"><i class="fas fa-check"></i> Resolved</button>' +
      '<button class="btn-action" onclick="updateFeedbackStatus(\'' + id + '\',\'archived\')" style="background:rgba(107,114,128,0.15);color:var(--text-muted);font-size:0.85rem;"><i class="fas fa-archive"></i> Archive</button>' +
      '</div>' +

      '<div class="section-header" style="margin-top:0.75rem;"><h3 style="font-size:0.85rem;">Replies</h3></div><div style="display:grid;gap:0.4rem;margin-bottom:0.75rem;">' + repliesHtml + '</div>' +
      '<div style="display:flex;gap:0.5rem;margin-bottom:0.75rem;">' +
      '<input type="text" id="fbAdminReply" placeholder="Write a public reply..." style="flex:1;padding:0.5rem 0.75rem;border-radius:12px;background:var(--surface-card);border:1px solid var(--border);color:var(--text);font-size:0.82rem;">' +
      '<button class="btn-action" onclick="submitAdminReply(\'' + id + '\')"><i class="fas fa-paper-plane"></i></button>' +
      '</div>' +

      '<div class="section-header" style="margin-top:0.75rem;"><h3 style="font-size:0.85rem;">Private Admin Notes</h3></div>' +
      '<div style="display:flex;gap:0.5rem;margin-bottom:0.75rem;">' +
      '<input type="text" id="fbAdminNote" placeholder="Add private note (invisible to users)..." style="flex:1;padding:0.5rem 0.75rem;border-radius:12px;background:var(--surface-card);border:1px solid var(--border);color:var(--text);font-size:0.82rem;">' +
      '<button class="btn-action" onclick="submitAdminNote(\'' + id + '\')"><i class="fas fa-sticky-note"></i></button>' +
      '</div>' +

      '<div class="section-header" style="margin-top:0.75rem;"><h3 style="font-size:0.85rem;">Moderation Actions</h3></div>' +
      '<div style="display:flex;gap:0.4rem;flex-wrap:wrap;">' +
      '<button class="btn-action" onclick="moderateFeedback(\'' + id + '\',\'hide\')" style="background:rgba(239,68,68,0.15);color:#FCA5A5;font-size:0.85rem;"><i class="fas fa-eye-slash"></i> Hide</button>' +
      '<button class="btn-action" onclick="moderateFeedback(\'' + id + '\',\'unhide\')" style="background:rgba(34,197,94,0.15);color:#86EFAC;font-size:0.85rem;"><i class="fas fa-eye"></i> Unhide</button>' +
      '<button class="btn-action" onclick="moderateFeedback(\'' + id + '\',\'flag\')" style="background:rgba(245,158,11,0.15);color:#FDE68A;font-size:0.85rem;"><i class="fas fa-flag"></i> Flag</button>' +
      '<button class="btn-action" onclick="moderateFeedback(\'' + id + '\',\'resolve\')" style="background:rgba(34,197,94,0.15);color:#86EFAC;font-size:0.85rem;"><i class="fas fa-check"></i> Resolve</button>' +
      '<button class="btn-action" onclick="moderateFeedback(\'' + id + '\',\'archive\')" style="background:rgba(107,114,128,0.15);color:var(--text-muted);font-size:0.85rem;"><i class="fas fa-archive"></i> Archive</button>' +
      '</div>';
  });
}

function closeFeedbackDetail() {
  var el = document.getElementById('feedbackDetailModal');
  if (el) { el.remove(); loadFeedback(); }
}

function updateFeedbackStatus(id, status) {
  var token = localStorage.getItem('accessToken') || '';
  fetch('/api/super-admin/feedback/' + id + '/moderate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
    body: JSON.stringify({action: status === 'resolved' ? 'resolve' : status === 'archived' ? 'archive' : status, reason: 'Status update via workflow'})
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) { viewFeedbackDetail(id); loadFeedbackList(); }
    else { alert('Failed: ' + (d.error || 'Unknown')); }
  });
}

function submitAdminReply(id) {
  var input = document.getElementById('fbAdminReply');
  if (!input || !input.value.trim()) return;
  var token = localStorage.getItem('accessToken') || '';
  fetch('/api/super-admin/feedback/' + id + '/reply-admin', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
    body: JSON.stringify({body: input.value.trim()})
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) { input.value = ''; viewFeedbackDetail(id); loadFeedbackList(); }
    else { alert('Failed: ' + (d.error || 'Unknown')); }
  });
}

function submitAdminNote(id) {
  var input = document.getElementById('fbAdminNote');
  if (!input || !input.value.trim()) return;
  var token = localStorage.getItem('accessToken') || '';
  fetch('/api/super-admin/feedback/' + id + '/note', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
    body: JSON.stringify({note: input.value.trim()})
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) { input.value = ''; alert('Private note saved.'); }
    else { alert('Failed: ' + (d.error || 'Unknown')); }
  });
}

function moderateFeedback(id, action) {
  var reason = action === 'flag' ? prompt('Flag reason:') : '';
  if (action === 'flag' && !reason) return;
  var token = localStorage.getItem('accessToken') || '';
  fetch('/api/super-admin/feedback/' + id + '/moderate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
    body: JSON.stringify({action: action, reason: reason || 'Moderated by admin'})
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) { viewFeedbackDetail(id); loadFeedbackList(); }
    else { alert('Failed: ' + (d.error || 'Unknown')); }
  });
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• AUTO-REFRESH â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
setInterval(function() {
  if (document.visibilityState !== 'hidden') loadTab(currentTab);
}, REFRESH_MS);


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• INIT â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
loadOverview();
// SSE Logic
let sseSource = null;
function startSSE() {
  if (sseSource) return;
  const token = localStorage.getItem('accessToken');
  if (!token) return;
  
  sseSource = new EventSource('/api/super-admin/events/stream?token=' + encodeURIComponent(token));
  
  sseSource.onmessage = function(e) {
    // Basic keepalive parsing logic
    if (e.data === ": keepalive") return;
    
    try {
      const payload = JSON.parse(e.data);
      if (payload.status === 'connected') return;
      
      // Auto refresh current tab slightly to simulate real-time updates
      const activeTabId = document.querySelector('.nav-item.active').getAttribute('data-tab');
      if (['overview', 'attendance', 'security', 'activity', 'connected-devices'].includes(activeTabId)) {
        refreshAll();
      }
    } catch(err) {}
  };
  
  sseSource.onerror = function() {
    sseSource.close();
    sseSource = null;
    setTimeout(startSSE, 5000);
  };
}

// Start SSE after DOM load
document.addEventListener('DOMContentLoaded', startSSE);
