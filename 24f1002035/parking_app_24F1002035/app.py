import os
import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash # type: ignore
from flask_session import Session # type: ignore
from models.init_db import init_db

app = Flask(__name__)

app.secret_key = 'parkeasy-secure-session-secret-key'
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parking.db')

# Ensure tables and initial data are ready
init_db(DATABASE)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def parse_db_timestamp(ts_val):
    if isinstance(ts_val, datetime):
        return ts_val
    if not ts_val:
        return datetime.now()
    ts_str = str(ts_val).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        return datetime.now()

@app.route('/')
def index():
    conn = get_db_connection()
    available_drivers_count = conn.execute("SELECT COUNT(*) as count FROM drivers WHERE status = 'available'").fetchone()['count']
    available_spots_count = conn.execute("SELECT COUNT(*) as count FROM parking_spots WHERE status = 'A'").fetchone()['count']
    conn.close()
    return render_template('home.html', 
                           available_drivers_count=available_drivers_count,
                           available_spots_count=available_spots_count)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hash_password(password)
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND hash = ?',
            (username, password_hash)
        ).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        full_name = request.form['full_name']
        phone = request.form['phone']
        
        password_hash = hash_password(password)
        
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, hash, email, full_name, phone, role) VALUES (?, ?, ?, ?, ?, ?)',
                (username, password_hash, email, full_name, phone, 'user')
            )
            conn.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    
    lots = conn.execute('''
        SELECT pl.*, 
            COUNT(ps.id) as total_spots,
            SUM(CASE WHEN ps.status = 'A' THEN 1 ELSE 0 END) as available_spots,
            SUM(CASE WHEN ps.status = 'O' THEN 1 ELSE 0 END) as occupied_spots
        FROM parking_lots pl
        LEFT JOIN parking_spots ps ON pl.id = ps.lot_id
        WHERE pl.is_active = 1
        GROUP BY pl.id
    ''').fetchall()
    
    total_users = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "user"').fetchone()['count']
    active_reservations = conn.execute('SELECT COUNT(*) as count FROM reservations WHERE leaving_timestamp IS NULL').fetchone()['count']
    total_drivers = conn.execute('SELECT COUNT(*) as count FROM drivers').fetchone()['count']
    active_drivers = conn.execute('SELECT COUNT(*) as count FROM drivers WHERE status = "busy"').fetchone()['count']
    available_drivers = conn.execute('SELECT COUNT(*) as count FROM drivers WHERE status = "available"').fetchone()['count']
    active_driver_bookings = conn.execute('SELECT COUNT(*) as count FROM driver_bookings WHERE status = "active"').fetchone()['count']
    
    conn.close()
    return render_template('admin_dashboard.html', 
                         lots=lots, 
                         total_users=total_users,
                         active_reservations=active_reservations,
                         total_drivers=total_drivers,
                         active_drivers=active_drivers,
                         available_drivers=available_drivers,
                         active_driver_bookings=active_driver_bookings)

@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    lots = conn.execute('''
        SELECT pl.*, 
            COUNT(ps.id) as total_spots,
            SUM(CASE WHEN ps.status = 'A' THEN 1 ELSE 0 END) as available_spots
        FROM parking_lots pl
        LEFT JOIN parking_spots ps ON pl.id = ps.lot_id
        WHERE pl.is_active = 1
        GROUP BY pl.id
        HAVING available_spots > 0
    ''').fetchall()
    
    reservations = conn.execute('''
        SELECT r.*, pl.location_name, pl.address,
               db.id as valet_booking_id, db.status as valet_status, d.name as valet_driver_name, d.phone as valet_driver_phone
        FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        LEFT JOIN driver_bookings db ON db.reservation_id = r.id AND db.status = 'active'
        LEFT JOIN drivers d ON db.driver_id = d.id
        WHERE r.user_id = ? AND r.leaving_timestamp IS NULL
    ''', (session['user_id'],)).fetchall()
    
    # Active driver bookings for this user
    active_driver_bookings = conn.execute('''
        SELECT db.*, d.name as driver_name, d.phone as driver_phone, d.rating as driver_rating, d.hourly_rate as driver_hourly_rate
        FROM driver_bookings db
        JOIN drivers d ON db.driver_id = d.id
        WHERE db.user_id = ? AND db.status = 'active'
        ORDER BY db.start_time DESC
    ''', (session['user_id'],)).fetchall()
    
    # Available drivers for valet selection
    available_drivers = conn.execute('''
        SELECT * FROM drivers WHERE status = 'available' ORDER BY rating DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('user_dashboard.html', 
                           lots=lots, 
                           reservations=reservations,
                           active_driver_bookings=active_driver_bookings,
                           available_drivers=available_drivers)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

from controllers.admin_controller import *
from controllers.user_controller import *

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"\n🚀 ParkEasy server is running at: http://127.0.0.1:{port}\n")
    app.run(debug=True, port=port)