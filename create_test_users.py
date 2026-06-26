import bcrypt

def create_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# Create hashes for test users
test_password = "password123"  # Simple test password
hash = create_hash(test_password)
print(f"Password: {test_password}")
print(f"Hash: {hash}")
