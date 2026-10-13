from flask import request, render_template, redirect, url_for, session, flash # type: ignore
from app import app, get_db_connection
import sqlite3
from datetime import datetime

@app.route('/admin/parking-lots')
def admin_parking_lots():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    lots = conn.execute('''
        SELECT pl.*, COUNT(ps.id) as total_spots,
            SUM(CASE WHEN ps.status = 'A' THEN 1 ELSE 0 END) as available_spots,
            SUM(CASE WHEN ps.status = 'O' THEN 1 ELSE 0 END) as occupied_spots
        FROM parking_lots pl
        LEFT JOIN parking_spots ps ON pl.id = ps.lot_id
        GROUP BY pl.id
    ''').fetchall()
    conn.close()
    
    return render_template('admin_parking_lots.html', lots=lots)

@app.route('/admin/create-lot', methods=['GET', 'POST'])
def admin_create_lot():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        location_name = request.form['location_name']
        address = request.form['address']
        pin_code = request.form['pin_code']
        price_per_hour = float(request.form['price_per_hour'])
        max_spots = int(request.form['max_spots'])
        
        conn = get_db_connection()
        try:
            cursor = conn.execute('''
                INSERT INTO parking_lots (location_name, address, pincode, price_per_hour, maximum_number_of_spots)
                VALUES (?, ?, ?, ?, ?)
            ''', (location_name, address, pin_code, price_per_hour, max_spots))
            
            lot_id = cursor.lastrowid
            
            for i in range(1, max_spots + 1):
                conn.execute('''
                    INSERT INTO parking_spots (lot_id, status)
                    VALUES (?, 'A')
                ''', (lot_id,))
            
            conn.commit()
            flash('Parking lot created successfully!')
            return redirect(url_for('admin_parking_lots'))
            
        except sqlite3.Error as e:
            flash(f'Error creating parking lot: {str(e)}')
        finally:
            conn.close()
    
    return render_template('admin_create_lot.html')

@app.route('/admin/edit-lot/<int:lot_id>', methods=['GET', 'POST'])
def admin_edit_lot(lot_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        location_name = request.form['location_name']
        address = request.form['address']
        pin_code = request.form['pincode']
        price_per_hour = float(request.form['price_per_hour'])
        max_spots = int(request.form['max_spots'])
        is_active = int(request.form['is_active'])
        
        try:
            current_spots = conn.execute('SELECT COUNT(*) as count FROM parking_spots WHERE lot_id = ?', (lot_id,)).fetchone()['count']
            
            conn.execute('''
                UPDATE parking_lots 
                SET location_name = ?, address = ?, pincode = ?, price_per_hour = ?, 
                    maximum_number_of_spots = ?, is_active = ?
                WHERE id = ?
            ''', (location_name, address, pin_code, price_per_hour, max_spots, is_active, lot_id))
            
            if max_spots > current_spots:
                for i in range(current_spots, max_spots):
                    conn.execute('''
                        INSERT INTO parking_spots (lot_id, status)
                        VALUES (?, 'A')
                    ''', (lot_id,))
            elif max_spots < current_spots:
                spots_to_remove = conn.execute('''
                    SELECT id FROM parking_spots 
                    WHERE lot_id = ? AND status = 'A' 
                    ORDER BY id DESC LIMIT ?
                ''', (lot_id, current_spots - max_spots)).fetchall()
                
                for spot in spots_to_remove:
                    conn.execute('DELETE FROM parking_spots WHERE id = ?', (spot['id'],))
            
            conn.commit()
            flash('Parking lot updated successfully!')
            return redirect(url_for('admin_parking_lots'))
            
        except sqlite3.Error as e:
            flash(f'Error updating parking lot: {str(e)}')
    
    lot = conn.execute('SELECT * FROM parking_lots WHERE id = ?', (lot_id,)).fetchone()
    conn.close()
    
    if not lot:
        flash('Parking lot not found!')
        return redirect(url_for('admin_parking_lots'))
    
    return render_template('admin_edit_lot.html', lot=lot)

@app.route('/admin/delete-lot/<int:lot_id>')
def admin_delete_lot(lot_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    occupied_spots = conn.execute('''
        SELECT COUNT(*) as count FROM parking_spots 
        WHERE lot_id = ? AND status = 'O'
    ''', (lot_id,)).fetchone()['count']
    
    if occupied_spots > 0:
        flash('Cannot delete parking lot. Some spots are currently occupied.')
    else:
        try:
            conn.execute('DELETE FROM parking_lots WHERE id = ?', (lot_id,))
            conn.commit()
            flash('Parking lot deleted successfully!')
        except sqlite3.Error as e:
            flash(f'Error deleting parking lot: {str(e)}')
    
    conn.close()
    return redirect(url_for('admin_parking_lots'))

@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    users = conn.execute('''
        SELECT u.*, COUNT(r.id) as total_reservations, SUM(r.parking_cost) as total_spend,
               (SELECT COUNT(*) FROM driver_bookings WHERE user_id = u.id) as total_driver_trips
        FROM users u
        LEFT JOIN reservations r ON u.id = r.user_id
        WHERE u.role = 'user'
        GROUP BY u.id
        ORDER BY u.registered_at DESC
    ''').fetchall()
    conn.close()
    
    return render_template('admin_users.html', users=users)

# --- DRIVER MANAGEMENT (ADMIN) ---

@app.route('/admin/drivers')
def admin_drivers():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    drivers = conn.execute('''
        SELECT d.*, 
               (SELECT COUNT(*) FROM driver_bookings WHERE driver_id = d.id AND status = 'completed') as completed_trips,
               (SELECT SUM(total_cost) FROM driver_bookings WHERE driver_id = d.id AND status = 'completed') as total_revenue,
               (SELECT u.username FROM driver_bookings db JOIN users u ON db.user_id = u.id WHERE db.driver_id = d.id AND db.status = 'active' LIMIT 1) as active_user
        FROM drivers d
        ORDER BY d.id DESC
    ''').fetchall()
    
    total_drivers = len(drivers)
    available_drivers = sum(1 for d in drivers if d['status'] == 'available')
    busy_drivers = sum(1 for d in drivers if d['status'] == 'busy')
    
    conn.close()
    return render_template('admin_drivers.html', 
                           drivers=drivers,
                           total_drivers=total_drivers,
                           available_drivers=available_drivers,
                           busy_drivers=busy_drivers)

@app.route('/admin/add-driver', methods=['GET', 'POST'])
def admin_add_driver():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form['phone'].strip()
        license_number = request.form['license_number'].strip()
        experience_years = int(request.form.get('experience_years', 1))
        rating = float(request.form.get('rating', 4.8))
        hourly_rate = float(request.form.get('hourly_rate', 150.0))
        status = request.form.get('status', 'available')
        
        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO drivers (name, phone, license_number, experience_years, rating, hourly_rate, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, phone, license_number, experience_years, rating, hourly_rate, status))
            conn.commit()
            flash(f"Driver '{name}' registered successfully!")
            return redirect(url_for('admin_drivers'))
        except sqlite3.IntegrityError:
            flash('Phone number or license number already exists for another driver.')
        except sqlite3.Error as e:
            flash(f'Error adding driver: {str(e)}')
        finally:
            conn.close()
            
    return render_template('admin_add_driver.html')

@app.route('/admin/edit-driver/<int:driver_id>', methods=['GET', 'POST'])
def admin_edit_driver(driver_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form['phone'].strip()
        license_number = request.form['license_number'].strip()
        experience_years = int(request.form.get('experience_years', 1))
        rating = float(request.form.get('rating', 4.8))
        hourly_rate = float(request.form.get('hourly_rate', 150.0))
        status = request.form.get('status', 'available')
        
        try:
            conn.execute('''
                UPDATE drivers 
                SET name = ?, phone = ?, license_number = ?, experience_years = ?, rating = ?, hourly_rate = ?, status = ?
                WHERE id = ?
            ''', (name, phone, license_number, experience_years, rating, hourly_rate, status, driver_id))
            conn.commit()
            flash(f"Driver '{name}' updated successfully!")
            return redirect(url_for('admin_drivers'))
        except sqlite3.IntegrityError:
            flash('Phone number or license number already exists.')
        except sqlite3.Error as e:
            flash(f'Error updating driver: {str(e)}')
            
    driver = conn.execute('SELECT * FROM drivers WHERE id = ?', (driver_id,)).fetchone()
    conn.close()
    
    if not driver:
        flash('Driver not found.')
        return redirect(url_for('admin_drivers'))
        
    return render_template('admin_edit_driver.html', driver=driver)

@app.route('/admin/delete-driver/<int:driver_id>')
def admin_delete_driver(driver_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    try:
        driver = conn.execute('SELECT * FROM drivers WHERE id = ?', (driver_id,)).fetchone()
        if not driver:
            flash('Driver not found.')
            return redirect(url_for('admin_drivers'))
            
        if driver['status'] == 'busy':
            flash('Cannot delete driver who is currently on active duty/busy!')
            return redirect(url_for('admin_drivers'))
            
        conn.execute('DELETE FROM drivers WHERE id = ?', (driver_id,))
        conn.commit()
        flash(f"Driver '{driver['name']}' deleted successfully.")
    except sqlite3.Error as e:
        flash(f'Error deleting driver: {str(e)}')
    finally:
        conn.close()
        
    return redirect(url_for('admin_drivers'))

@app.route('/admin/driver-bookings')
def admin_driver_bookings():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT db.*, u.username, u.full_name as user_full_name, u.phone as user_phone,
               d.name as driver_name, d.phone as driver_phone, d.hourly_rate
        FROM driver_bookings db
        JOIN users u ON db.user_id = u.id
        JOIN drivers d ON db.driver_id = d.id
        ORDER BY db.start_time DESC
    ''').fetchall()
    conn.close()
    
    return render_template('admin_driver_bookings.html', bookings=bookings)