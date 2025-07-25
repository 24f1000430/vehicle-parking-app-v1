from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import func
from datetime import datetime
from models import db, User, ParkingLot, ParkingSpot, Reservation
import os

app = Flask(__name__)
load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db.init_app(app)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        admin = User(
            full_name='Admin',
            username='admin@parking.com',
            password_hash=generate_password_hash('admin'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        full_name = request.form['full_name']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))

        user = User(
            username=username,
            full_name=full_name,
            password_hash=generate_password_hash(password),
            role='user'
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['role'] = user.role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        flash('Invalid credentials')

    return render_template('login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/admin/lots')
def admin_lots():
    if session.get('role')!='admin':  
        return redirect(url_for('login'))
    lots = ParkingLot.query.all()
    return render_template('admin_lots.html', lots=lots)

# --- Create lot (auto-generate spots) ---
@app.route('/admin/lots/create', methods=['GET','POST'])
def create_lot():
    if session.get('role')!='admin': return redirect(url_for('login'))
    if request.method=='POST':
        form = request.form
        lot = ParkingLot(
            prime_location_name=form['name'],
            address=form['address'],
            pincode=form['pincode'],
            price_per_hour=float(form['price']),
            max_spots=int(form['max_spots'])
        )
        db.session.add(lot) 
        db.session.commit()
        # auto-create spots
        for i in range(lot.max_spots):
            db.session.add(ParkingSpot(lot_id=lot.id))
        db.session.commit()
        flash('Parking lot created.')
        return redirect(url_for('admin_lots'))
    return render_template('admin_edit_lot.html')

# --- Edit lot & adjust spot count ---
@app.route('/admin/lots/<int:lot_id>/edit', methods=['GET','POST'])
def edit_lot(lot_id):
    if session.get('role')!='admin': return redirect(url_for('login'))
    lot = ParkingLot.query.get_or_404(lot_id)
    if request.method=='POST':
        form = request.form
        lot.prime_location_name = form['name']
        lot.address = form['address']
        lot.pincode = form['pincode']
        lot.price_per_hour = float(form['price'])
        new_max = int(form['max_spots'])
        diff = new_max - lot.max_spots
        if diff > 0:
            for _ in range(diff):
                db.session.add(ParkingSpot(lot_id=lot.id))
        elif diff < 0:
            # only delete available spots
            extras = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').limit(-diff)
            for s in extras: db.session.delete(s)
        lot.max_spots = new_max
        db.session.commit()
        flash('Parking lot updated.')
        return redirect(url_for('admin_lots'))
    return render_template('admin_edit_lot.html', lot=lot)

# --- Delete lot if empty ---
@app.route('/admin/lots/<int:lot_id>/delete', methods=['POST'])
def delete_lot(lot_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    lot = ParkingLot.query.get_or_404(lot_id)
    occupied = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
    if occupied:
        flash('Cannot delete: some spots are occupied.')
    else:
        ParkingSpot.query.filter_by(lot_id=lot.id).delete()
        db.session.delete(lot)
        db.session.commit()
        flash('Parking lot deleted.')
    return redirect(url_for('admin_lots'))

# --- View lot details & spot statuses ---
@app.route('/admin/lots/<int:lot_id>')
def lot_details(lot_id):
    if session.get('role')!='admin': return redirect(url_for('login'))
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
    return render_template('admin_lot_details.html', lot=lot, spots=spots)

# --- List all users & their current spot (if any) ---
@app.route('/admin/users')
def admin_users():
    if session.get('role')!='admin': return redirect(url_for('login'))
    data = []
    for u in User.query.filter_by(role='user').all():
        res = Reservation.query.filter_by(user_id=u.id, end_time=None).first()
        data.append({'user': u, 'spot': res.spot if res else None})
    return render_template('admin_users.html', data=data)

@app.route('/dashboard')
def user_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')

# ----- List available lots -----
@app.route('/lots')
def user_lots():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    # annotate with availability count
    lots = ParkingLot.query.all()
    return render_template('user_lots.html', lots=lots)

# ----- Reserve first available spot in a lot -----
@app.route('/lots/<int:lot_id>/reserve', methods=['POST'])
def reserve_spot(lot_id):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    user_id = session['user_id']
    # find first available spot
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    if not spot:
        flash('No available spots in this lot.')
        return redirect(url_for('user_lots'))

    # occupy it
    spot.status = 'O'
    res = Reservation(
        spot_id=spot.id,
        user_id=user_id,
        start_time=datetime.utcnow(),
        cost=None,
        end_time=None
    )
    db.session.add(res)
    db.session.commit()
    flash(f'Spot #{spot.id} reserved.')
    return redirect(url_for('user_parking'))

# ----- User parking dashboard (current + history) -----
@app.route('/parking')
def user_parking():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    uid = session['user_id']
    # current active reservation
    active = Reservation.query.filter_by(user_id=uid, end_time=None).all()
    # full history
    history = Reservation.query.filter(
        Reservation.user_id==uid,
        Reservation.end_time!=None
    ).order_by(Reservation.start_time.desc()).all()
    return render_template('user_parking.html', active=active, history=history)

# ----- Release a spot -----
@app.route('/parking/<int:res_id>/release', methods=['POST'])
def release_spot(res_id):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    res = Reservation.query.get_or_404(res_id)
    if res.end_time is not None:
        flash('Reservation already closed.')
        return redirect(url_for('user_parking'))

    # compute timestamps & cost
    res.end_time = datetime.utcnow()
    duration = (res.end_time - res.start_time).total_seconds() / 3600  # hours
    price = res.spot.lot.price_per_hour
    res.cost = round(duration * price, 2)

    # free the spot
    res.spot.status = 'A'
    db.session.commit()
    flash(f'Released spot #{res.spot.id}, cost: ₹{res.cost}')
    return redirect(url_for('user_parking'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)