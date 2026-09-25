import sqlite3
import os

def fix_database():
    # Remove old database to start fresh
    if os.path.exists('cloud_storage.db'):
        print("Removing old database...")
        os.remove('cloud_storage.db')

    conn = sqlite3.connect('cloud_storage.db')
    cursor = conn.cursor()

    try:
        # Create users table with all required columns
        cursor.execute('''CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            twofa_secret TEXT,
            twofa_enabled INTEGER DEFAULT 0,
            face_enrolled INTEGER DEFAULT 0,
            fingerprint_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        print("✓ Users table created")

        # Create files table
        cursor.execute('''CREATE TABLE files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            file_type TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        print("✓ Files table created")

        # Insert a test user (optional)
        cursor.execute('''INSERT INTO users (username, password, email)
                         VALUES (?, ?, ?)''',
                         ('testuser', 'pbkdf2:sha256:600000$test', 'test@example.com'))
        print("✓ Test user created")

        conn.commit()
        print("\n✅ Database setup complete!")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    fix_database()
