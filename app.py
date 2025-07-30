from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import func, or_, and_
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

    return render_template('register.html', role=session.get('role'))

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

    return render_template('login.html', role=session.get('role'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        # Fetch all lots
    lots = ParkingLot.query.all()

    # Compute revenue per lot
    lot_names = []
    revenues = []
    for lot in lots:
        # Sum cost of all completed reservations for spots in this lot
        total = (
            db.session.query(func.sum(Reservation.cost))
            .join(ParkingSpot, Reservation.spot_id == ParkingSpot.id)
            .filter(ParkingSpot.lot_id == lot.id, Reservation.cost != None)
            .scalar()
        ) or 0.0
        lot_names.append(lot.prime_location_name)
        revenues.append(round(total, 2))

    # Compute average revenue across lots
    avg_revenue = round(sum(revenues) / len(revenues), 2) if revenues else 0.0

    return render_template(
        'admin_dashboard.html',
        lot_names=lot_names,
        revenues=revenues,
        avg_revenue=avg_revenue,
        role=session.get('role')
    )

@app.route('/admin/lots')
def admin_lots():
    if session.get('role')!='admin':  
        return redirect(url_for('login'))
    lots = ParkingLot.query.all()
    return render_template('admin_lots.html', lots=lots, role=session.get('role'))

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
    return render_template('admin_edit_lot.html', role=session.get('role'))

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
    return render_template('admin_edit_lot.html', lot=lot, role=session.get('role'))

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
    return render_template('admin_lot_details.html', lot=lot, spots=spots, role=session.get('role'))

# --- List all users & their current spot ---
@app.route('/admin/users')
def admin_users():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    data = []
    for u in User.query.filter_by(role='user').all():
        reservations = Reservation.query.filter_by(user_id=u.id, end_time=None).all()
        spots = [r.spot for r in reservations]
        data.append({'user': u, 'spots': spots})
    
    return render_template('admin_users.html', data=data, role=session.get('role'))

# --- Search through lots and users ---

@app.route('/admin/search')
def admin_search():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    q = request.args.get('q', '').strip()
    user_q = User.query.filter_by(role='user')
    user_q = user_q.outerjoin(Reservation,and_(Reservation.user_id == User.id, Reservation.end_time == None)
    ).outerjoin(ParkingSpot, ParkingSpot.id == Reservation.spot_id)

    if q:
        filters = [
            User.username.ilike(f'%{q}%'),
            User.full_name.ilike(f'%{q}%'),]
        if q.isdigit():
            filters.append(ParkingSpot.id == int(q))
        user_q = user_q.filter(or_(*filters))
    users = user_q.all()

    data = []
    for u in users:
        reservations = Reservation.query.filter_by(user_id=u.id, end_time=None).all()
        spots = [r.spot for r in reservations]
        data.append({'user': u, 'spots': spots})

    lot_q = ParkingLot.query
    if q:
        lot_filters = [
            ParkingLot.prime_location_name.ilike(f'%{q}%'),
            ParkingLot.address.ilike(f'%{q}%'),
            ParkingLot.pincode.ilike(f'%{q}%'),]
        if q.isdigit():
            lot_filters.append(ParkingLot.max_spots == int(q))

        lot_q = lot_q.filter(or_(*lot_filters))
    lots = lot_q.all()

    return render_template('admin_search.html', data=data, lots=lots, role=session.get('role'), q=q)

@app.route('/dashboard')
def user_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    return render_template('user_dashboard.html', role=session.get('role'))

# ----- List available lots -----
@app.route('/lots')
def user_lots():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    # annotate with availability count
    lots = ParkingLot.query.all()
    return render_template('user_lots.html', lots=lots, role=session.get('role'))

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
    return render_template('user_parking.html', active=active, history=history, role=session.get('role'))

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

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # Must be logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get_or_404(session['user_id'])

    if request.method == 'POST':
        # Update full name
        user.full_name = request.form['full_name']

        # Update username/email if changed and not already taken
        new_email = request.form['username']
        if new_email != user.username:
            if User.query.filter_by(username=new_email).first():
                flash('Email already in use.', 'error')
                return redirect(url_for('profile'))
            user.username = new_email

        # Update password if field non-empty
        new_pw = request.form['password']
        confirm_pw = request.form.get('confirm_password', '')
        if new_pw:
            if new_pw != confirm_pw:
                flash('Passwords do not match.', 'error')
                return redirect(url_for('profile'))
            user.password_hash = generate_password_hash(new_pw)

        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user, role=session.get('role'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)