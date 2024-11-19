from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
# from sqlalchemy.sql import func
# from sqlalchemy_utils import TimeZone
import razorpay
from dotenv import load_dotenv
import os
from datetime import datetime
import pytz

load_dotenv()

app = Flask(__name__)

secret_key = os.environ.get('secret_key')
db_uri = os.environ.get('db_uri2')

app.config['SECRET_KEY'] = secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

db = SQLAlchemy(app)

IST = pytz.timezone('Asia/Kolkata')


class User(db.Model):
    __tablename__ = 'user'

    ID = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    grade = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(240), nullable=False)
    ph = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    school = db.Column(db.String(120), nullable=False)
    gName = db.Column(db.String(120), nullable=False)
    order_id = db.Column(db.String(120))
    prevAtt = db.Column(db.String(2))
    paymentStatus = db.Column(db.String(10))
    ano = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(IST))


with app.app_context():
    db.create_all()

# Razorpay credentials
RAZORPAY_KEY_ID = os.environ.get(
    'RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get(
    'RAZORPAY_KEY_SECRET')

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


@app.route('/')
def index():
    return render_template('home.html', key_id=RAZORPAY_KEY_ID)


@app.post('/validate_data')
def validate_data():
    data = request.form
    ano = data.get("ano")
    student = User.query.filter_by(ano=ano).first()

    if student:
        return "success", 200
    else:
        return "fail", 404


@app.route('/create_order', methods=['POST'])
def create_order():
    # Amount in paise (e.g., ₹100.50 is 10050)
    amount = 25 * 100

    # Create Razorpay order
    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": "1"  # Auto-capture after payment success
    })

    return jsonify(order)


def verify_payment(data):
    """Verify payment signature."""
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def verify_status(order_id):
    """Verify payment status using Razorpay order ID."""
    try:
        order = razorpay_client.order.fetch(order_id)
        return order.get("status") == "paid"
    except razorpay.errors.BadRequestError:
        return False


@app.route('/get_status', methods=['POST'])
def get_status():
    data = request.form
    ano = data.get("ano")

    student = User.query.filter_by(ano=ano).first()

    if student:
        return {"name": student.name,
                "g_name": student.gName,
                "phone": student.ph[0:4]+"xxxxxx",
                "email": "xxxxx"+student.email[5:],
                "ano": student.ano,
                "time": student.created_at
                }, 200
    else:
        return {"error": "Record not found"}, 404


@app.route('/verify_payment', methods=['POST'])
def verify_all():
    """Combine payment signature verification and status check."""
    data = request.form
    order_id = data.get("orderID")

    if not order_id:
        return jsonify({"error": "Order ID is required"}), 400

    is_payment_valid = verify_payment(data)
    is_status_paid = verify_status(order_id)

    if is_payment_valid and is_status_paid:
        return jsonify({"status": "success", "message": "Payment verified successfully"}), 200
    else:
        return jsonify({"status": "failure", "message": "Payment verification failed"}), 400


@app.route('/save_in_databse', methods=['POST'])
def save_in_databse():
    data = request.form

    name = data.get("name")
    grade = data.get("grade")
    address = data.get("address")
    ph = data.get("phone")
    email = data.get("email")
    school = data.get("school")
    g_name = data.get("g_name")
    order_id = data.get("order_id")
    prevAtt = data.get("prevAtt")
    ano = data.get("ano")

    user = User(name=name, grade=grade, address=address, ph=ph,
                email=email, school=school, gName=g_name, order_id=order_id, prevAtt=prevAtt, paymentStatus="paid", ano=ano)

    db.session.add(user)
    db.session.commit()

    return jsonify({"status": "success", "message": "User added to the database"}), 200


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port="5000")
