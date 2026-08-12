from flask import request, render_template, redirect, url_for, session, flash # type: ignore
from app import app, get_db_connection
import sqlite3
from datetime import datetime

@app.route('/user/book-spot/<int:lot_id>', methods=['POST'])
def user_book_spot(lot_id):
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    try:
        spot = conn.execute('''
                                SELECT * FROM parking_spots 
                                WHERE lot_id = ? AND status = 'A' 
                                ORDER BY id LIMIT 1
                            ''', (lot_id,)).fetchone()
        
        if not spot:
            flash('No available spots in this parking lot!')
            return redirect(url_for('user_dashboard'))
        
        conn.execute('''
                        INSERT INTO reservations (spot_id, user_id, parking_timestamp)
                        VALUES (?, ?, ?)
                    ''', (spot['id'], session['user_id'], datetime.now()))
        
        conn.execute('''
                        UPDATE parking_spots SET status = 'O'
                        WHERE id = ?
                    ''', (spot['id'],))
        
        conn.commit()
        flash(f'Parking spot {spot["id"]} booked successfully!')
        
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
                                    SELECT r.*, ps.id, pl.price_per_hour
                                    FROM reservations r
                                    JOIN parking_spots ps ON r.spot_id = ps.id
                                    JOIN parking_lots pl ON ps.lot_id = pl.id
                                    WHERE r.id = ? AND r.user_id = ?
                                ''', (reservation_id, session['user_id'])).fetchone()
        
        if not reservation:
            flash('Reservation not found!')
            return redirect(url_for('user_dashboard'))
        
        parking_start = datetime.fromisoformat(reservation['parking_timestamp'])
        parking_end = datetime.now()
        duration_hours = (parking_end - parking_start).total_seconds() / 3600
        parking_cost = duration_hours * reservation['price_per_hour']

        conn.execute('''
                        UPDATE reservations 
                        SET parking_cost = ?, leaving_timestamp = ?
                        WHERE id = ?
                    ''', (parking_cost, parking_end, reservation_id))
        conn.execute('''
                        UPDATE parking_spots SET status = 'A'
                        WHERE id = ?
                    ''', (reservation['spot_id'],))
        
        conn.commit()
        flash(f'Parking spot {reservation["spot_id"]} released successfully! Total cost: ₹{parking_cost:.2f}')
        
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
                                SELECT r.*, ps.id, pl.location_name, pl.address
                                FROM reservations r
                                JOIN parking_spots ps ON r.spot_id = ps.id
                                JOIN parking_lots pl ON ps.lot_id = pl.id
                                WHERE r.user_id = ?
                                ORDER BY r.parking_timestamp DESC
                            ''', (session['user_id'],)).fetchall()
    conn.close()
    
    
    return render_template('user_history.html', history=history)
