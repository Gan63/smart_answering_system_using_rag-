import requests

base_url = "http://localhost:8000"

def test_auth():
    print("Testing Registration...")
    reg_data = {
        "full_name": "Test User",
        "email": "testuser@example.com",
        "password": "password123"
    }
    
    # Register
    res = requests.post(f"{base_url}/api/auth/register", json=reg_data)
    print(f"Register status: {res.status_code}")
    print(f"Register response: {res.text}")
    
    print("\nTesting Login...")
    login_data = {
        "email": "testuser@example.com",
        "password": "password123"
    }
    
    # Login
    res = requests.post(f"{base_url}/api/auth/login", json=login_data)
    print(f"Login status: {res.status_code}")
    print(f"Login response: {res.text}")

if __name__ == "__main__":
    test_auth()
