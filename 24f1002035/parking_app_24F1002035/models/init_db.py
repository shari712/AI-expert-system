import sqlite3
import hashlib

conn = sqlite3.connect('parking.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               email TEXT UNIQUE NOT NULL,
               full_name TEXT NOT NULL,     
               phone TEXT UNIQUE NOT NULL,    
               username TEXT UNIQUE NOT NULL,
               hash TEXT NOT NULL,
               role TEXT CHECK(role IN ('admin', 'user')) NOT NULL DEFAULT 'user',
               registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS parking_lots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,         
               location_name TEXT NOT NULL,
               address TEXT NOT NULL,
               pincode TEXT NOT NULL,
               price_per_hour REAL NOT NULL,
               maximum_number_of_spots INTEGER NOT NULL,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               is_active BOOLEAN DEFAULT 1
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS parking_spots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               lot_id INTEGER NOT NULL,
               status TEXT CHECK(status IN ('O', 'A')) NOT NULL DEFAULT 'A',
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               FOREIGN KEY (lot_id) REFERENCES parking_lots(id) ON DELETE CASCADE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS reservations (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               spot_id INTEGER NOT NULL,
               user_id INTEGER NOT NULL,
               parking_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               leaving_timestamp TIMESTAMP DEFAULT NULL,
               parking_cost REAL,
               FOREIGN KEY (spot_id) REFERENCES parking_spots(id) ON DELETE CASCADE,
               FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
''')

demo_users = (
    ('admin', 'admin@parkeasy.local', 'Demo Admin', '0000000001', 'admin123', 'admin'),
    ('user', 'user@parkeasy.local', 'Demo User', '0000000002', 'password123', 'user'),
)

for username, email, full_name, phone, password, role in demo_users:
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute('''
        INSERT INTO users (username, email, full_name, phone, hash, role)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            hash = excluded.hash,
            role = excluded.role
    ''', (username, email, full_name, phone, password_hash, role))

conn.commit()
conn.close()
