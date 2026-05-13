def debug_mock_users():
    print(f"DEBUG: Mock database users: {_mock_database['users']}")
    for user in _mock_database['users']:
        print(f"DEBUG: User {user.get('email')} has role: {user.get('role')}")
