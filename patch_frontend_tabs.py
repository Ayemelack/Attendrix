import re

file_path = "c:\\Users\\noshi\\OneDrive\\fotsa\\Achieved\\attendrix\\src\\presentation\\templates\\super-admin\\dashboard.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Insert Tabs before tab-institutions
new_tabs = """
    <!-- === VOUCHERS === -->
    <div class="tab-content" id="tab-vouchers">
      <div class="section-header">
        <h2><i class="fas fa-ticket"></i> Voucher Management</h2>
        <div>
          <button class="btn-action success" onclick="document.getElementById('createVoucherModal').style.display='flex'"><i class="fas fa-plus"></i> Create Voucher</button>
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

    <!-- === CONNECTED DEVICES === -->
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

"""

if 'id="tab-vouchers"' not in content:
    content = re.sub(r'(<div class="tab-content" id="tab-institutions">)', new_tabs + r'\1', content)

# 2. Insert JS before loadInstitutions()
new_js = """
/* === VOUCHERS === */
function loadVouchers() {
  var el = document.getElementById('vouchersTableBody');
  el.innerHTML = '<tr><td colspan="6" class="loading-state"><div class="spinner"></div></td></tr>';
  apiFetch(API_BASE + '/vouchers', function(d) {
    if (!d.success) { el.innerHTML = '<tr><td colspan="6" class="error-state">Failed to load</td></tr>'; return; }
    if (!d.data || !d.data.length) { el.innerHTML = '<tr><td colspan="6" class="empty-state"><i class="fas fa-ticket"></i><br><div class="empty-title">No Vouchers</div></td></tr>'; return; }
    el.innerHTML = d.data.map(function(v) {
      return '<tr>' +
        '<td><strong style="font-family:monospace; color:var(--primary-light);">' + esc(v.code) + '</strong></td>' +
        '<td><span class="status-badge role-' + esc(v.role).replace(/_/g, '-') + '">' + esc(v.role).replace(/_/g, ' ') + '</span></td>' +
        '<td>' + esc(v.institution_name || 'Global') + '</td>' +
        '<td><span class="status-badge ' + (v.revoked ? 'inactive' : (v.is_used ? 'warning' : 'active')) + '">' + (v.revoked ? 'Revoked' : (v.is_used ? 'Used' : 'Active')) + '</span></td>' +
        '<td style="font-size:0.7rem;">' + fmtTime(v.created_at) + '</td>' +
        '<td>' + (!v.revoked && !v.is_used ? '<button class="btn-action danger" onclick="revokeVoucher(\\'' + v.id + '\\')"><i class="fas fa-ban"></i> Revoke</button>' : '') + '</td>' +
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
        '<td><div style="font-size:0.75rem;">' + esc(dev.os) + '</div><div style="font-size:0.65rem; color:var(--text-muted); max-width:250px; overflow:hidden; text-overflow:ellipsis;">' + esc(dev.user_agent) + '</div></td>' +
        '<td><span style="font-family:monospace; background:var(--bg-secondary); padding:0.2rem 0.4rem; border-radius:4px; font-size:0.7rem;">' + esc(dev.ip_address) + '</span></td>' +
        '<td style="font-size:0.7rem;">' + fmtTime(dev.last_seen) + '</td>' +
      '</tr>';
    }).join('');
  });
}

"""

if 'function loadVouchers()' not in content:
    content = re.sub(r'(function loadInstitutions\(\) \{)', new_js + r'\1', content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated dashboard.html successfully")
