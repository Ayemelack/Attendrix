import requests

def test_admin_pages():
    pages = [
        '/admin/dashboard',
        '/admin/institutions',
        '/admin/institutions/create',
        '/admin/users',
        '/admin/monitoring',
        '/admin/security',
        '/admin/backup',
        '/admin/notifications',
        '/admin/audit',
        '/admin/roles',
        '/admin/profile',
        '/admin/settings',
        '/admin/reports'
    ]
    
    print("Testing all Super Admin pages...")
    print("=" * 50)
    
    for page in pages:
        try:
            response = requests.get(f'http://localhost:5000{page}', timeout=5)
            status = response.status_code
            content_length = len(response.text)
            
            if status == 200:
                print(f"  {page:<30} -> {status} OK ({content_length:,} bytes)")
            else:
                print(f"  {page:<30} -> {status} ERROR")
        except Exception as e:
            print(f"  {page:<30} -> ERROR: {str(e)}")
    
    print("=" * 50)
    print("All admin pages tested!")

if __name__ == "__main__":
    test_admin_pages()
