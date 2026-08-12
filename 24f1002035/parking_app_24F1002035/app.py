from flask import Flask, render_template, request, redirect, url_for, session, flash # type: ignore
from flask_session import Session # type: ignore
import sqlite3
import hashlib
from datetime import datetime

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

DATABASE = 'parking.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    return render_template('home.html')

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
    
    conn.close()
    return render_template('admin_dashboard.html', 
                         lots=lots, 
                         total_users=total_users,
                         active_reservations=active_reservations)

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
                                    SELECT r.*, pl.location_name
                                    FROM reservations r
                                    JOIN parking_spots ps ON r.spot_id = ps.id
                                    JOIN parking_lots pl ON ps.lot_id = pl.id
                                    WHERE r.user_id = ? AND r.leaving_timestamp IS NULL
                                ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('user_dashboard.html', lots=lots, reservations=reservations)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

from controllers.admin_controller import *
from controllers.user_controller import *

if __name__ == '__main__':
    app.run(debug=True)