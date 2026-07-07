import re

def patch_dashboard():
    with open('src/presentation/templates/super-admin/dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Replace the tab-vouchers HTML structure
    old_tab_html_pattern = r'<div class="tab-content" id="tab-vouchers">.*?<tbody id="vouchersTableBody"></tbody>\s*</table>\s*</div>\s*</div>'
    
    new_tab_html = """<div class="tab-content" id="tab-vouchers">
      <div class="section-header">
        <h2><i class="fas fa-ticket"></i> Voucher Management</h2>
        <div>
          <button class="btn-action success" onclick="document.getElementById('createVoucherModal').style.display='flex'"><i class="fas fa-plus"></i> Create Voucher</button>
        </div>
      </div>
      
      <!-- Analytics Cards -->
      <div class="stats-grid" id="voucherAnalyticsCards">
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
      </div>
      
      <!-- Timeline and Table Split -->
      <div style="display:flex; gap:1.5rem; margin-top:1.5rem; flex-wrap:wrap;">
        <div style="flex:2; min-width:600px;">
          <div class="section-header">
            <h3>Voucher Directory</h3>
            <div class="search-bar" style="width:250px;">
              <i class="fas fa-search"></i>
              <input type="text" id="voucherSearchInput" placeholder="Search vouchers..." onkeyup="filterVouchers()">
            </div>
          </div>
          <div class="table-wrap">
            <table id="vouchersTable">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Role / Inst</th>
                  <th>Assignment</th>
                  <th>Status</th>
                  <th>Timeline</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody id="vouchersTableBody"></tbody>
            </table>
          </div>
        </div>
        
        <div style="flex:1; min-width:300px;">
          <div class="section-header">
            <h3><i class="fas fa-history"></i> Activity Timeline</h3>
          </div>
          <div class="card" style="padding:1.5rem; max-height:600px; overflow-y:auto;">
            <div id="voucherTimelineBody">
              <div class="loading-state"><div class="spinner"></div></div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Email Delivery Modal -->
    <div class="modal-overlay" id="emailVoucherModal">
      <div class="modal">
        <div class="modal-header">
          <h2><i class="fas fa-envelope"></i> Email Voucher</h2>
          <button class="btn-action" onclick="document.getElementById('emailVoucherModal').style.display='none'"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
          <input type="hidden" id="emailVoucherId">
          <div class="form-group">
            <label>Recipient Name</label>
            <input type="text" id="emailVoucherName" class="input-field" placeholder="Dr. John Doe">
          </div>
          <div class="form-group">
            <label>Recipient Email</label>
            <input type="email" id="emailVoucherAddress" class="input-field" placeholder="john@university.edu">
          </div>
          <div class="form-group">
            <label>Custom Message (Optional)</label>
            <textarea id="emailVoucherMessage" class="input-field" rows="3" placeholder="Welcome to the platform!"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-action" onclick="document.getElementById('emailVoucherModal').style.display='none'">Cancel</button>
          <button class="btn-action primary" onclick="submitEmailVoucher()" id="btnSendVoucherEmail"><i class="fas fa-paper-plane"></i> Send Email</button>
        </div>
      </div>
    </div>"""
    
    html = re.sub(old_tab_html_pattern, new_tab_html, html, flags=re.DOTALL)

    # 2. Replace the loadVouchers JS block
    old_js_pattern = r'function loadVouchers\(\) \{.*?apiFetch\(API_BASE \+ \'/vouchers\', cb\);\s*\}'
    
    new_js = """var allVouchersData = [];
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

    var actions = '<button class="btn-action" onclick="copyVoucherCode(\'' + v.code + '\')" title="Copy Code"><i class="fas fa-copy"></i></button>';
    if (!v.revoked && !v.is_used) {
      actions += '<button class="btn-action primary" onclick="openEmailVoucherModal(\'' + v.id + '\')" title="Send via Email"><i class="fas fa-paper-plane"></i></button>';
      actions += '<button class="btn-action danger" onclick="revokeVoucher(\'' + v.id + '\')" title="Revoke"><i class="fas fa-ban"></i></button>';
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
               '<div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">' + fmtTime(e.timestamp) + ' \u00b7 <strong style="font-family:monospace;">' + esc(e.code) + '</strong></div>' +
             '</div>' +
             '</div>';
    }).join('') + '</div>';
  });
}
"""
    
    html = re.sub(old_js_pattern, new_js, html, flags=re.DOTALL)
    
    with open('src/presentation/templates/super-admin/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Dashboard patched successfully.")

if __name__ == '__main__':
    patch_dashboard()
