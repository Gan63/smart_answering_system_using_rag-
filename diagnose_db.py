from database.db_config import get_db_connection
import sys

def check_db():
    conn = get_db_connection()
    if not conn:
        print("❌ FAILED: get_db_connection() returned None")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'users'")
        if cursor.fetchone():
            print("✅ 'users' table exists.")
        else:
            print("❌ 'users' table DOES NOT exist.")
            
            # Try initializing it now
            from database.db_config import init_db
            print("Running init_db()...")
            init_db()
            
            cursor.execute("SHOW TABLES LIKE 'users'")
            if cursor.fetchone():
                print("✅ 'users' table successfully created.")
            else:
                print("❌ FAILED to create 'users' table.")
        
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        print(f"ℹ️ Total users in DB: {count}")
        
    except Exception as e:
        print(f"❌ ERROR while checking DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
