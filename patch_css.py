import re

file_path = "c:\\Users\\noshi\\OneDrive\\fotsa\\Achieved\\attendrix\\src\\presentation\\templates\\super-admin\\dashboard.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# CSS adjustments
css_replacements = [
    # General table font sizes are too small
    (r'table\s*\{\s*width:\s*100%;\s*min-width:\s*820px;\s*border-collapse:\s*collapse;\s*font-size:\s*0.78rem;',
     'table { width: 100%; min-width: 820px; border-collapse: collapse; font-size: 0.95rem;'),
    (r'th\s*\{\s*text-align:\s*left;\s*padding:\s*0.7rem\s*1rem;\s*font-size:\s*0.65rem;',
     'th { text-align: left; padding: 0.9rem 1.2rem; font-size: 0.85rem;'),
    (r'td\s*\{\s*padding:\s*0.6rem\s*1rem;',
     'td { padding: 0.8rem 1.2rem;'),
    
    # Sidebar
    (r'\.sidebar-brand\s*span\s*\{\s*font-weight:\s*800;\s*font-size:\s*0.95rem;\s*\}',
     '.sidebar-brand span { font-weight: 800; font-size: 1.1rem; }'),
    (r'\.sidebar-brand\s*\.badge\s*\{\s*font-size:\s*0.55rem;',
     '.sidebar-brand .badge { font-size: 0.75rem;'),
    (r'\.nav-item\s*\{\s*(.*?)\s*font-size:\s*0.8rem;',
     r'.nav-item { \1 font-size: 0.95rem;'),
    (r'\.nav-item\s*\.nav-badge\s*\{\s*margin-left:\s*auto;\s*font-size:\s*0.55rem;',
     '.nav-item .nav-badge { margin-left: auto; font-size: 0.75rem;'),
    (r'\.nav-item\s*i\s*\{\s*width:\s*18px;\s*text-align:\s*center;\s*font-size:\s*0.85rem;\s*\}',
     '.nav-item i { width: 22px; text-align: center; font-size: 1.05rem; }'),
    (r'\.nav-section-label\s*\{\s*font-size:\s*0.6rem;',
     '.nav-section-label { font-size: 0.8rem;'),
    
    # Topbar
    (r'\.topbar\s*h1\s*\{\s*font-size:\s*1.2rem;',
     '.topbar h1 { font-size: 1.5rem;'),
    (r'\.live-indicator\s*\{\s*(.*?)\s*font-size:\s*0.72rem;',
     r'.live-indicator { \1 font-size: 0.9rem;'),
    (r'\.auto-refresh-btn\s*\{\s*font-size:\s*0.72rem;',
     '.auto-refresh-btn { font-size: 0.9rem;'),
    
    # Stat Cards
    (r'\.stat-card\s*\.stat-label\s*\{\s*font-size:\s*0.65rem;',
     '.stat-card .stat-label { font-size: 0.85rem;'),
    (r'\.stat-card\s*\.stat-value\s*\{\s*font-size:\s*1.5rem;',
     '.stat-card .stat-value { font-size: 1.8rem;'),
    (r'\.stat-card\s*\.stat-sub\s*\{\s*font-size:\s*0.7rem;',
     '.stat-card .stat-sub { font-size: 0.85rem;'),
    
    # Section Header
    (r'\.section-header\s*h2\s*\{\s*font-size:\s*1rem;',
     '.section-header h2 { font-size: 1.25rem;'),
    (r'\.section-header\s*\.badge-count\s*\{\s*font-size:\s*0.65rem;',
     '.section-header .badge-count { font-size: 0.85rem;'),
    (r'\.section-header\s*select,\s*\.section-header\s*input\s*\{\s*(.*?)\s*font-size:\s*0.75rem;',
     r'.section-header select, .section-header input { \1 font-size: 0.9rem;'),
     
    # Status badges and buttons
    (r'\.status-badge\s*\{\s*(.*?)\s*font-size:\s*0.72rem;',
     r'.status-badge { \1 font-size: 0.85rem;'),
    (r'\.btn-action\s*\{\s*(.*?)\s*font-size:\s*0.7rem;',
     r'.btn-action { \1 font-size: 0.85rem;'),
     
    # Feeds
    (r'\.feed-content\s*\.feed-title\s*\{\s*font-size:\s*0.78rem;',
     '.feed-content .feed-title { font-size: 0.95rem;'),
    (r'\.feed-content\s*\.feed-desc\s*\{\s*font-size:\s*0.7rem;',
     '.feed-content .feed-desc { font-size: 0.85rem;'),
    (r'\.feed-content\s*\.feed-meta\s*\{\s*font-size:\s*0.62rem;',
     '.feed-content .feed-meta { font-size: 0.75rem;'),
     
    # Governance Role Cards
    (r'\.gov-role-card\s*\.gov-count\s*\{\s*font-size:\s*1.6rem;',
     '.gov-role-card .gov-count { font-size: 2rem;'),
    (r'\.gov-role-card\s*\.gov-label\s*\{\s*font-size:\s*0.65rem;',
     '.gov-role-card .gov-label { font-size: 0.85rem;'),
    
    # Empty States
    (r'\.empty-state\s*\{\s*(.*?)\s*font-size:\s*0.85rem;',
     r'.empty-state { \1 font-size: 1.05rem;'),
    (r'\.empty-state\s*\.empty-title\s*\{\s*font-size:\s*1rem;',
     '.empty-state .empty-title { font-size: 1.25rem;'),
    (r'\.empty-state\s*\.empty-desc\s*\{\s*font-size:\s*0.78rem;',
     '.empty-state .empty-desc { font-size: 0.95rem;'),
]

for old_regex, new_val in css_replacements:
    content = re.sub(old_regex, new_val, content, flags=re.DOTALL)

# In JS, adjust inline font sizes
content = content.replace("font-size:0.7rem;", "font-size:0.85rem;")
content = content.replace("font-size:0.75rem;", "font-size:0.9rem;")
content = content.replace("font-size:0.65rem;", "font-size:0.8rem;")
content = content.replace("font-size:0.6rem;", "font-size:0.8rem;")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated CSS for better readability")
