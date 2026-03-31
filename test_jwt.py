import jwt
try:
    token = jwt.encode({"test": "data"}, "secret", algorithm="HS256")
    print(f"SUCCESS: {token}")
    decoded = jwt.decode(token, "secret", algorithms=["HS256"])
    print(f"DECODED: {decoded}")
except Exception as e:
    print(f"ERROR: {e}")
