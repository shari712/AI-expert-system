from flask import request, render_template, redirect, url_for, session, flash # type: ignore
from app import app, get_db_connection, parse_db_timestamp
import sqlite3
from datetime import datetime

@app.route('/user/drivers')
def user_drivers():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    drivers = conn.execute('''
        SELECT d.*, 
               (SELECT COUNT(*) FROM driver_bookings WHERE driver_id = d.id AND status = 'completed') as total_trips
        FROM drivers d
        WHERE d.status != 'inactive'
        ORDER BY (d.status = 'available') DESC, d.rating DESC
    ''').fetchall()
    
    available_count = conn.execute("SELECT COUNT(*) as count FROM drivers WHERE status = 'available'").fetchone()['count']
    conn.close()
    
    return render_template('user_drivers.html', drivers=drivers, available_count=available_count)

@app.route('/user/book-driver', methods=['POST'])
def user_book_driver():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
        
    driver_id = request.form.get('driver_id')
    pickup_location = request.form.get('pickup_location', '').strip()
    destination_location = request.form.get('destination_location', '').strip()
    booking_type = request.form.get('booking_type', 'personal')
    vehicle_details = request.form.get('vehicle_details', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not pickup_location:
        flash('Pickup location is required to book a driver.')
        return redirect(url_for('user_drivers'))
        
    conn = get_db_connection()
    try:
        # Check if specific driver was chosen or auto-assign
        if driver_id and driver_id != 'auto':
            driver = conn.execute('SELECT * FROM drivers WHERE id = ? AND status = "available"', (driver_id,)).fetchone()
        else:
            driver = conn.execute('SELECT * FROM drivers WHERE status = "available" ORDER BY rating DESC LIMIT 1').fetchone()
            
        if not driver:
            flash('Sorry, no drivers are currently available. Please try again in a few minutes.')
            conn.close()
            return redirect(url_for('user_drivers'))
            
        now = datetime.now()
        
        # Mark driver as busy
        conn.execute("UPDATE drivers SET status = 'busy' WHERE id = ?", (driver['id'],))
        
        # Create booking record
        conn.execute('''
            INSERT INTO driver_bookings 
            (user_id, driver_id, booking_type, pickup_location, destination_location, vehicle_details, notes, status, start_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
        ''', (session['user_id'], driver['id'], booking_type, pickup_location, destination_location, vehicle_details, notes, now))
        
        conn.commit()
        flash(f"Driver {driver['name']} booked successfully! They will arrive at {pickup_location}.")
    except sqlite3.Error as e:
        flash(f'Error booking driver: {str(e)}')
    finally:
        conn.close()
        
    return redirect(url_for('user_dashboard'))

@app.route('/user/release-driver/<int:booking_id>')
def user_release_driver(booking_id):
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    try:
        booking = conn.execute('''
            SELECT db.*, d.name as driver_name, d.hourly_rate
            FROM driver_bookings db
            JOIN drivers d ON db.driver_id = d.id
            WHERE db.id = ? AND db.user_id = ? AND db.status = 'active'
        ''', (booking_id, session['user_id'])).fetchone()
        
        if not booking:
            flash('Active driver booking not found.')
            conn.close()
            return redirect(url_for('user_dashboard'))
            
        start_time = parse_db_timestamp(booking['start_time'])
        end_time = datetime.now()
        duration_hours = max((end_time - start_time).total_seconds() / 3600, 0.05)
        total_cost = round(duration_hours * booking['hourly_rate'], 2)
        
        # Update booking
        conn.execute('''
            UPDATE driver_bookings 
            SET status = 'completed', end_time = ?, total_cost = ?
            WHERE id = ?
        ''', (end_time, total_cost, booking_id))
        
        # Free the driver
        conn.execute("UPDATE drivers SET status = 'available' WHERE id = ?", (booking['driver_id'],))
        
        conn.commit()
        flash(f"Driver service for {booking['driver_name']} completed! Total cost: ₹{total_cost:.2f}")
    except sqlite3.Error as e:
        flash(f'Error completing driver service: {str(e)}')
    finally:
        conn.close()
        
    return redirect(url_for('user_dashboard'))

@app.route('/user/book-spot/<int:lot_id>', methods=['POST'])
def user_book_spot(lot_id):
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
        
    need_valet = request.form.get('need_valet')
    valet_driver_id = request.form.get('valet_driver_id')
    vehicle_details = request.form.get('vehicle_details', '').strip()
    
    conn = get_db_connection()
    
    try:
        spot = conn.execute('''
            SELECT * FROM parking_spots 
            WHERE lot_id = ? AND status = 'A' 
            ORDER BY id LIMIT 1
        ''', (lot_id,)).fetchone()
        
        lot = conn.execute('SELECT * FROM parking_lots WHERE id = ?', (lot_id,)).fetchone()
        
        if not spot or not lot:
            flash('No available spots in this parking lot!')
            conn.close()
            return redirect(url_for('user_dashboard'))
        
        now = datetime.now()
        
        # Create reservation
        cursor = conn.execute('''
            INSERT INTO reservations (spot_id, user_id, parking_timestamp)
            VALUES (?, ?, ?)
        ''', (spot['id'], session['user_id'], now))
        
        reservation_id = cursor.lastrowid
        
        # Update spot status
        conn.execute("UPDATE parking_spots SET status = 'O' WHERE id = ?", (spot['id'],))
        
        assigned_driver_name = None
        # Handle Valet Driver request if selected
        if need_valet:
            driver = None
            if valet_driver_id and valet_driver_id != 'auto':
                driver = conn.execute('SELECT * FROM drivers WHERE id = ? AND status = "available"', (valet_driver_id,)).fetchone()
            if not driver:
                driver = conn.execute('SELECT * FROM drivers WHERE status = "available" ORDER BY rating DESC LIMIT 1').fetchone()
                
            if driver:
                assigned_driver_name = driver['name']
                # Mark driver busy
                conn.execute("UPDATE drivers SET status = 'busy' WHERE id = ?", (driver['id'],))
                # Add valet driver booking linked to this reservation
                conn.execute('''
                    INSERT INTO driver_bookings 
                    (user_id, driver_id, reservation_id, booking_type, pickup_location, vehicle_details, notes, status, start_time)
                    VALUES (?, ?, ?, 'valet', ?, ?, 'Valet parking assistance', 'active', ?)
                ''', (session['user_id'], driver['id'], reservation_id, lot['location_name'], vehicle_details, now))
            else:
                flash('Spot booked! However, no valet drivers were currently available.')
                
        conn.commit()
        if assigned_driver_name:
            flash(f"Parking spot {spot['id']} booked with Valet Driver {assigned_driver_name} assigned!")
        else:
            flash(f"Parking spot {spot['id']} booked successfully!")
        
    except sqlite3.Error as e:
        flash(f'Error booking spot: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('user_dashboard'))

@app.route('/user/release-spot/<int:reservation_id>')
def user_release_spot(reservation_id):
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    try:
        reservation = conn.execute('''
            SELECT r.*, ps.id as spot_num, pl.price_per_hour
            FROM reservations r
            JOIN parking_spots ps ON r.spot_id = ps.id
            JOIN parking_lots pl ON ps.lot_id = pl.id
            WHERE r.id = ? AND r.user_id = ? AND r.leaving_timestamp IS NULL
        ''', (reservation_id, session['user_id'])).fetchone()
        
        if not reservation:
            flash('Active reservation not found!')
            conn.close()
            return redirect(url_for('user_dashboard'))
        
        parking_start = parse_db_timestamp(reservation['parking_timestamp'])
        parking_end = datetime.now()
        duration_hours = max((parking_end - parking_start).total_seconds() / 3600, 0.05)
        parking_cost = round(duration_hours * reservation['price_per_hour'], 2)

        conn.execute('''
            UPDATE reservations 
            SET parking_cost = ?, leaving_timestamp = ?
            WHERE id = ?
        ''', (parking_cost, parking_end, reservation_id))
        
        conn.execute("UPDATE parking_spots SET status = 'A' WHERE id = ?", (reservation['spot_id'],))
        
        # Check if there is an active valet driver booking tied to this reservation
        valet_booking = conn.execute('''
            SELECT db.*, d.name as driver_name, d.hourly_rate
            FROM driver_bookings db
            JOIN drivers d ON db.driver_id = d.id
            WHERE db.reservation_id = ? AND db.status = 'active'
        ''', (reservation_id,)).fetchone()
        
        driver_message = ""
        if valet_booking:
            driver_start = parse_db_timestamp(valet_booking['start_time'])
            driver_duration = max((parking_end - driver_start).total_seconds() / 3600, 0.05)
            driver_cost = round(driver_duration * valet_booking['hourly_rate'], 2)
            
            conn.execute('''
                UPDATE driver_bookings 
                SET status = 'completed', end_time = ?, total_cost = ?
                WHERE id = ?
            ''', (parking_end, driver_cost, valet_booking['id']))
            
            conn.execute("UPDATE drivers SET status = 'available' WHERE id = ?", (valet_booking['driver_id'],))
            total_combined = parking_cost + driver_cost
            driver_message = f" | Valet ({valet_booking['driver_name']}): ₹{driver_cost:.2f} | Total: ₹{total_combined:.2f}"
        
        conn.commit()
        flash(f"Parking spot released! Parking Fee: ₹{parking_cost:.2f}{driver_message}")
        
    except sqlite3.Error as e:
        flash(f'Error releasing spot: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('user_dashboard'))

@app.route('/user/history')
def user_history():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    history = conn.execute('''
        SELECT r.*, ps.id as spot_number, pl.location_name, pl.address,
               CASE WHEN r.leaving_timestamp IS NULL THEN 'active' ELSE 'completed' END as calculated_status,
               d.name as valet_driver_name, db.total_cost as valet_cost
        FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        LEFT JOIN driver_bookings db ON db.reservation_id = r.id
        LEFT JOIN drivers d ON db.driver_id = d.id
        WHERE r.user_id = ?
        ORDER BY r.parking_timestamp DESC
    ''', (session['user_id'],)).fetchall()
    
    driver_history = conn.execute('''
        SELECT db.*, d.name as driver_name, d.phone as driver_phone, d.rating as driver_rating, d.hourly_rate
        FROM driver_bookings db
        JOIN drivers d ON db.driver_id = d.id
        WHERE db.user_id = ?
        ORDER BY db.start_time DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('user_history.html', history=history, driver_history=driver_history)
