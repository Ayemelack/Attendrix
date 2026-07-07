import re

def fix_dashboard():
    with open('src/presentation/templates/super-admin/dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Fix the unescaped quotes syntax error
    html = html.replace(
        """onclick="copyVoucherCode('' + v.code + '')\"""",
        """onclick="copyVoucherCode(\\'" + v.code + "\\')\""""
    )
    html = html.replace(
        """onclick="openEmailVoucherModal('' + v.id + '')\"""",
        """onclick="openEmailVoucherModal(\\'" + v.id + "\\')\""""
    )
    html = html.replace(
        """onclick="revokeVoucher('' + v.id + '')\"""",
        """onclick="revokeVoucher(\\'" + v.id + "\\')\""""
    )
    
    # 2. Fix the SSE Logic position
    # The SSE Logic is currently sitting at the end of the file, outside </html>
    sse_pattern = r'</script>\s*</body>\s*</html>\s*(// SSE Logic\s*let sseSource = null;.*?)$'
    match = re.search(sse_pattern, html, flags=re.DOTALL)
    
    if match:
        sse_code = match.group(1)
        # Move it inside the script tag
        html = re.sub(sse_pattern, sse_code + '\n</script>\n</body>\n</html>', html, flags=re.DOTALL)

    with open('src/presentation/templates/super-admin/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Fix applied.")

if __name__ == '__main__':
    fix_dashboard()
