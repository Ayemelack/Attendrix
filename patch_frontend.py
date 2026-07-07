import re

file_path = "c:\\Users\\noshi\\OneDrive\\fotsa\\Achieved\\attendrix\\src\\presentation\\templates\\super-admin\\dashboard.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Sidebar Links
sidebar_users = """<button class="nav-item" data-tab="users"><i class="fas fa-lg fa-users-gear"></i><span>Users</span></button>"""
sidebar_vouchers = sidebar_users + """\n      <button class="nav-item" data-tab="vouchers"><i class="fas fa-lg fa-ticket"></i><span>Vouchers</span></button>"""
content = content.replace(sidebar_users, sidebar_vouchers)

sidebar_network = """<button class="nav-item" data-tab="network"><i class="fas fa-lg fa-network-wired"></i><span>Network</span></button>"""
sidebar_devices = sidebar_network + """\n      <button class="nav-item" data-tab="connected-devices"><i class="fas fa-lg fa-mobile-screen"></i><span>Connected Devices</span></button>"""
content = content.replace(sidebar_network, sidebar_devices)

# 2. Add Tab Contents for Vouchers and Connected Devices
tab_insert_point = "<!-- â• â• â•  INSTITUTIONS â• â• â•  -->"
new_tabs = """<!-- â• â• â•  VOUCHERS â• â• â•  -->
    <div class="tab-content" id="tab-vouchers">
      <div class="section-header">
        <h2><i class="fas fa-ticket"></i> Voucher Management</h2>
        <div>
          <button class="btn-action success" onclick="document.getElementById('createVoucherModal').style.display='block'"><i class="fas fa-plus"></i> Create Voucher</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Role</th>
              <th>Institution</th>
              <th>Status</th>
              <th>Created</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="vouchersTableBody"></tbody>
        </table>
      </div>
      
      <!-- Create Voucher Modal -->
      <div id="createVoucherModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999; justify-content:center; align-items:center;">
        <div style="background:var(--bg-card); padding:2rem; border-radius:12px; width:400px; max-width:90%; border:1px solid var(--border);">
          <h3 style="margin-bottom:1rem; font-size:1.1rem;">Create Access Voucher</h3>
          <div style="margin-bottom:1rem;">
            <label style="font-size:0.8rem; color:var(--text-muted);">Role</label>
            <select id="newVoucherRole" style="width:100%; padding:0.5rem; background:var(--bg-secondary); border:1px solid var(--border); color:white; border-radius:6px; margin-top:0.3rem;">
              <option value="student">Student</option>
              <option value="lecturer">Lecturer</option>
              <option value="institutional_admin">Institutional Admin</option>
            </select>
          </div>
          <div style="margin-bottom:1rem;">
            <label style="font-size:0.8rem; color:var(--text-muted);">Institution ID</label>
            <input type="text" id="newVoucherInstitution" placeholder="Optional" style="width:100%; padding:0.5rem; background:var(--bg-secondary); border:1px solid var(--border); color:white; border-radius:6px; margin-top:0.3rem;">
          </div>
          <div style="display:flex; justify-content:flex-end; gap:0.5rem;">
            <button class="btn-action" onclick="document.getElementById('createVoucherModal').style.display='none'">Cancel</button>
            <button class="btn-action success" onclick="submitCreateVoucher()">Create</button>
          </div>
        </div>
      </div>
    </div>

    <!-- â• â• â•  CONNECTED DEVICES â• â• â•  -->
    <div class="tab-content" id="tab-connected-devices">
      <div class="section-header">
        <h2><i class="fas fa-mobile-screen"></i> Connected Devices</h2>
        <span class="badge-count" id="devicesCount">0 online</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Device & OS</th>
              <th>IP Address</th>
              <th>Last Seen</th>
            </tr>
          </thead>
          <tbody id="devicesTableBody"></tbody>
        </table>
      </div>
    </div>

    """ + tab_insert_point

content = content.replace(tab_insert_point, new_tabs)

# 3. Add JS Functions for Vouchers and Connected Devices
js_insert_point = "/* â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•  INSTITUTIONS"
new_js = """/* â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•  VOUCHERS â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•  */
function loadVouchers() {
  var el = document.getElementById('vouchersTableBody');
  el.innerHTML = '<tr><td colspan="6" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(API_BASE + '/vouchers', function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="6" class="error-state">Failed to load</td></tr>'; return; }
    if (!d.data.length) { el.innerHTML = '<tr><td colspan="6" class="empty-state"><i class="fas fa-ticket"></i><br><div class="empty-title">No Vouchers</div></td></tr>'; return; }
    el.innerHTML = d.data.map(function(v) {
      return '<tr>' +
        '<td><strong style="font-family:monospace; color:var(--primary-light);">' + esc(v.code) + '</strong></td>' +
        '<td><span class="status-badge role-' + esc(v.role).replace(/_/g, '-') + '">' + esc(v.role).replace(/_/g, ' ') + '</span></td>' +
        '<td>' + esc(v.institution_name) + '</td>' +
        '<td><span class="status-badge ' + (v.revoked ? 'inactive' : (v.is_used ? 'warning' : 'active')) + '">' + (v.revoked ? 'Revoked' : (v.is_used ? 'Used' : 'Available')) + '</span></td>' +
        '<td style="font-size:0.7rem;">' + fmtTime(v.created_at) + '</td>' +
        '<td>' + (!v.revoked && !v.is_used ? '<button class="btn-action danger" onclick="revokeVoucher(\\'' + v.id + '\\')"><i class="fas fa-ban"></i></button>' : '') + '</td>' +
      '</tr>';
    }).join('');
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

/* â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•  CONNECTED DEVICES â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•  */
function loadConnectedDevices() {
  var el = document.getElementById('devicesTableBody');
  el.innerHTML = '<tr><td colspan="4" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(API_BASE + '/connected-devices', function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="4" class="error-state">Failed to load</td></tr>'; return; }
    var _e = document.getElementById('devicesCount'); if (_e) _e.textContent = d.data.length + ' online';
    if (!d.data.length) { el.innerHTML = '<tr><td colspan="4" class="empty-state"><i class="fas fa-mobile-screen"></i><br><div class="empty-title">No Connected Devices</div></td></tr>'; return; }
    el.innerHTML = d.data.map(function(dev) {
      return '<tr>' +
        '<td><strong>' + esc(dev.user_name) + '</strong></td>' +
        '<td><div style="font-size:0.75rem;">' + esc(dev.os) + '</div><div style="font-size:0.65rem; color:var(--text-muted); max-width:250px; overflow:hidden; text-overflow:ellipsis;">' + esc(dev.user_agent) + '</div></td>' +
        '<td><span style="font-family:monospace; background:var(--bg-secondary); padding:0.2rem 0.4rem; border-radius:4px; font-size:0.7rem;">' + esc(dev.ip_address) + '</span></td>' +
        '<td style="font-size:0.7rem;">' + fmtTime(dev.last_seen) + '</td>' +
      '</tr>';
    }).join('');
  });
}

""" + js_insert_point

content = content.replace(js_insert_point, new_js)

# 4. Add load handlers to refreshAll
refresh_insert = "function refreshAll() {"
new_refresh = "function refreshAll() {\n  if (document.getElementById('tab-vouchers').classList.contains('active')) { loadVouchers(); return; }\n  if (document.getElementById('tab-connected-devices').classList.contains('active')) { loadConnectedDevices(); return; }"
content = content.replace(refresh_insert, new_refresh)

# 5. Add initial load mapping for tabs
tab_map_insert = "case 'analytics': loadAnalytics(); break;"
new_tab_map = tab_map_insert + "\n      case 'vouchers': loadVouchers(); break;\n      case 'connected-devices': loadConnectedDevices(); break;"
content = content.replace(tab_map_insert, new_tab_map)

# 6. Add SSE code logic to start automatically
sse_logic = """
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
"""
content = content + "\n" + sse_logic

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated dashboard.html")
