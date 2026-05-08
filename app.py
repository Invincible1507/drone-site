import os
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_from_directory, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-random-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "drones.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'drones'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'avatars'), exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    avatar = db.Column(db.String(200), default='avatars/default.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='customer', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    drones = db.relationship('Drone', backref='category', lazy='dynamic')


class Drone(db.Model):
    __tablename__ = 'drones'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(200), default='drones/drone_default.jpg')
    max_speed = db.Column(db.Float, default=0)
    flight_time = db.Column(db.Integer, default=0)
    max_payload = db.Column(db.Float, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order_items = db.relationship('OrderItem', backref='drone', lazy='dynamic')


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy='dynamic')


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    drone_id = db.Column(db.Integer, db.ForeignKey('drones.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def save_image(file, folder='drones', size=(800, 600)):
    if not file:
        return None
    filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img = Image.open(file)
    img.thumbnail(size)
    img.save(filepath)
    return f"{folder}/{filename}"


@app.context_processor
def inject_categories():
    return {'categories': Category.query.all()}


@app.route('/')
def index():
    racing = Drone.query.filter_by(category_id=1).order_by(Drone.created_at.desc()).limit(4).all()
    agro = Drone.query.filter_by(category_id=2).order_by(Drone.created_at.desc()).limit(4).all()
    cargo = Drone.query.filter_by(category_id=3).order_by(Drone.created_at.desc()).limit(4).all()
    return render_template('index.html', racing=racing, agro=agro, cargo=cargo)


@app.route('/category/<slug>')
def category(slug):
    category_obj = Category.query.filter_by(slug=slug).first_or_404()
    drones = Drone.query.filter_by(category_id=category_obj.id).order_by(Drone.name).all()
    return render_template('category.html', category=category_obj, drones=drones)


@app.route('/drone/<slug>')
def drone_detail(slug):
    drone = Drone.query.filter_by(slug=slug).first_or_404()
    return render_template('drone_detail.html', drone=drone)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, email=email)
        user.set_password(password)
        avatar = request.files.get('avatar')
        if avatar:
            saved = save_image(avatar, folder='avatars', size=(200, 200))
            if saved:
                user.avatar = saved
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash('Logged in successfully.', 'success')
            return redirect(next_page or url_for('index'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/cart')
@login_required
def cart():
    order = Order.query.filter_by(user_id=current_user.id, status='pending').first()
    return render_template('cart.html', order=order)


@app.route('/api/cart/add', methods=['POST'])
@login_required
def api_cart_add():
    data = request.get_json()
    drone_id = data.get('drone_id')
    quantity = data.get('quantity', 1)
    drone = Drone.query.get_or_404(drone_id)
    if drone.stock < quantity:
        return jsonify({'error': 'Not enough stock'}), 400
    order = Order.query.filter_by(user_id=current_user.id, status='pending').first()
    if not order:
        order = Order(user_id=current_user.id)
        db.session.add(order)
        db.session.flush()
    item = OrderItem.query.filter_by(order_id=order.id, drone_id=drone_id).first()
    if item:
        item.quantity += quantity
        item.price = drone.price * item.quantity
    else:
        item = OrderItem(order_id=order.id, drone_id=drone_id, quantity=quantity, price=drone.price * quantity)
        db.session.add(item)
    order.total = sum(i.price for i in order.items.all())
    db.session.commit()
    return jsonify({'message': 'Added to cart', 'cart_count': order.items.count()})


@app.route('/api/cart/remove', methods=['POST'])
@login_required
def api_cart_remove():
    data = request.get_json()
    item_id = data.get('item_id')
    item = OrderItem.query.get_or_404(item_id)
    order = item.order
    if order.user_id != current_user.id:
        abort(403)
    db.session.delete(item)
    order.total = sum(i.price for i in order.items.all())
    db.session.commit()
    return jsonify({'message': 'Item removed'})


@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    order = Order.query.filter_by(user_id=current_user.id, status='pending').first()
    if not order or order.items.count() == 0:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart'))
    for item in order.items:
        drone = item.drone
        if drone.stock < item.quantity:
            flash(f'Not enough {drone.name} in stock.', 'danger')
            return redirect(url_for('cart'))
        drone.stock -= item.quantity
    order.status = 'completed'
    db.session.commit()
    flash('Order placed successfully!', 'success')
    return redirect(url_for('orders'))


@app.route('/orders')
@login_required
def orders():
    all_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=all_orders)


@app.route('/api/drones')
def api_drones():
    drones = Drone.query.all()
    return jsonify([{
        'id': d.id,
        'name': d.name,
        'price': d.price,
        'category': d.category.name,
        'max_speed': d.max_speed,
        'flight_time': d.flight_time,
        'max_payload': d.max_payload
    } for d in drones])


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def init_db():
    with app.app_context():
        db.create_all()
        if not Category.query.first():
            categories = [
                Category(name='Гоночные дроны', slug='racing',
                         description='Высокоскоростные дроны для гонок FPV'),
                Category(name='Агро дроны', slug='agro',
                         description='Дроны для сельского хозяйства и обработки полей'),
                Category(name='Грузовые дроны', slug='cargo',
                         description='Тяжелые дроны для доставки грузов')
            ]
            db.session.add_all(categories)
            db.session.commit()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@droneshop.ru', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
        if Drone.query.count() == 0:
            racing = Category.query.filter_by(slug='racing').first()
            agro = Category.query.filter_by(slug='agro').first()
            cargo = Category.query.filter_by(slug='cargo').first()
            drones = [
                Drone(
                    name='Racer X1', slug='racer-x1',
                    description='Гоночный FPV-дрон для профессионалов.',
                    price=49990, stock=10, max_speed=120,
                    flight_time=20, max_payload=0.5, category_id=racing.id
                ),
                Drone(
                    name='AgroFly Pro', slug='agrofly-pro',
                    description='Дрон для опрыскивания полей.',
                    price=89990, stock=5, max_speed=40,
                    flight_time=30, max_payload=10, category_id=agro.id
                ),
                Drone(
                    name='CargoMax 500', slug='cargomax-500',
                    description='Грузовой дрон для доставки до 50 кг.',
                    price=149990, stock=3, max_speed=60,
                    flight_time=25, max_payload=50, category_id=cargo.id
                )
            ]
            db.session.add_all(drones)
            db.session.commit()


if __name__ == '__main__':
    init_db()
    app.run(debug=True)

