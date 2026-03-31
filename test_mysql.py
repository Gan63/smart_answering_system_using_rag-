import mysql.connector
import os

def test_connection(user, password, host="localhost", database=None):
    try:
        config = {
            "user": user,
            "password": password,
            "host": host
        }
        if database:
            config["database"] = database
            
        conn = mysql.connector.connect(**config)
        print(f"✅ SUCCESS: Connected as '{user}' with password '{password}'")
        conn.close()
        return True
    except mysql.connector.Error as err:
        if err.errno == 1045:
            print(f"❌ FAILED: Access Denied for '{user}' with password '{password}'")
        elif err.errno == 1049:
            print(f"⚠️  CONNECTED: '{user}' authenticated, but database '{database}' doesn't exist.")
            return True
        else:
            print(f"❌ ERROR {err.errno}: {err.msg}")
        return False

if __name__ == "__main__":
    print("--- MySQL Connection Diagnostic Tool ---")
    
    # Common combinations
    combinations = [
        ("root", "root@1234"),
        ("root", "root"),
        ("root", ""),
        ("root", "password"),
        ("root", "1234"),
        ("root", "12345678"),
    ]
    
    found = False
    for u, p in combinations:
        if test_connection(u, p):
            print(f"\n💡 ACTION: Update your 'database/db_config.py' with:")
            print(f"   user: {u}")
            print(f"   password: {p}")
            found = True
            break
            
    if not found:
        print("\n❌ No common password combination worked.")
        print("Please verify your MySQL root password manually or reset it.")
