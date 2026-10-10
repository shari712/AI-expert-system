import sqlite3
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'parking.db')

def init_db(db_path=None):
    if db_path is None:
        db_path = DB_PATH
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

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

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS drivers (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   phone TEXT UNIQUE NOT NULL,
                   license_number TEXT UNIQUE NOT NULL,
                   experience_years INTEGER NOT NULL DEFAULT 1,
                   rating REAL NOT NULL DEFAULT 4.8,
                   hourly_rate REAL NOT NULL DEFAULT 150.0,
                   status TEXT CHECK(status IN ('available', 'busy', 'inactive')) NOT NULL DEFAULT 'available',
                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS driver_bookings (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER NOT NULL,
                   driver_id INTEGER NOT NULL,
                   reservation_id INTEGER DEFAULT NULL,
                   booking_type TEXT CHECK(booking_type IN ('valet', 'personal')) NOT NULL DEFAULT 'personal',
                   pickup_location TEXT NOT NULL,
                   destination_location TEXT,
                   vehicle_details TEXT,
                   start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   end_time TIMESTAMP DEFAULT NULL,
                   status TEXT CHECK(status IN ('active', 'completed', 'cancelled')) NOT NULL DEFAULT 'active',
                   total_cost REAL DEFAULT NULL,
                   notes TEXT,
                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                   FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
                   FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE SET NULL
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

    # Seed demo drivers if none exist
    cursor.execute('SELECT COUNT(*) FROM drivers')
    existing_drivers_count = cursor.fetchone()[0]
    if existing_drivers_count == 0:
        demo_drivers = [
            ('Rajesh Kumar', '9876543210', 'DL-0420180012345', 7, 4.9, 150.0, 'available'),
            ('Vikram Singh', '9876543211', 'DL-0720160054321', 5, 4.8, 180.0, 'available'),
            ('Amit Patel', '9876543212', 'MH-0120190098765', 4, 4.7, 140.0, 'available'),
            ('Suresh Nair', '9876543213', 'KA-0520150034567', 8, 5.0, 200.0, 'available'),
            ('Pooja Verma', '9876543214', 'UP-1620200087654', 6, 4.9, 160.0, 'available'),
        ]
        cursor.executemany('''
            INSERT INTO drivers (name, phone, license_number, experience_years, rating, hourly_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', demo_drivers)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
