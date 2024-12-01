from flask import Flask, render_template, request, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
import razorpay
from dotenv import load_dotenv
import os
import requests
from datetime import datetime
import pytz

load_dotenv()


secret_key = os.environ.get('secret_key')
db_uri = os.environ.get('db_uri2')
mailPort = int(os.environ.get('port'))
mailServer = os.environ.get('server')
mailUsername = os.environ.get('sender_email')
mailPassword = os.environ.get('mailpasswd')

app = Flask(__name__)

app.config['SECRET_KEY'] = secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
app.config['MAIL_SERVER'] = mailServer
app.config['MAIL_PORT'] = mailPort
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = mailUsername
app.config['MAIL_PASSWORD'] = mailPassword
app.config['MAIL_DEFAULT_SENDER'] = mailUsername

db = SQLAlchemy(app)
mail = Mail(app)

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
    ip = db.Column(db.String(50))


class Counter(db.Model):
    ID = db.Column(db.Integer, primary_key=True)
    count = db.Column(db.Integer, default=0)


with app.app_context():
    db.create_all()

# Razorpay credentials
RAZORPAY_KEY_ID = os.environ.get(
    'RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get(
    'RAZORPAY_KEY_SECRET')

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def send_mail(name, grade, ano, oi, rec, g_name, address):
    try:
        msg = Message(
            subject="Thank You for registering for TAMC-2024!",
            recipients=[str(rec)],
            html=f'''<h4>प्रिय छात्र, TAMC-2024 के लिए आपका आवेदन इस प्रकार प्राप्त हुआ है:</h4>
            <p>
            नाम / Name: <b>{name}</b><br>
            अभिभावक का नाम / Guardian's Name: <b>{g_name}</b><br>
            कक्षा / Class: <b>{grade}</b><br>
            आधार / Aadhaar: <b>{ano}</b><br>
            पता / Address: <b>{address}</b><br>
            Order ID: <b>{oi}</b>
            </p>

<h5>हम जल्द ही आपके एडमिट कार्ड के साथ आपसे संपर्क करेंगे।</h5> :)
            '''
        )
        mail.send(msg)
        return True
    except Exception as e:
        return False


def send_mail_manually(name, grade, address, ph, email, ip, school, g_name, order_id, prevAtt, ano):
    try:
        msg = Message(
            subject="Add user manually",
            recipients=['rmctkg@gmail.com'],
            html=f'''INSERT INTO user(name,grade,address,ph,email,school,gName,order_id,prevAtt,paymentStatus,ano,created_at,ip)
            VALUES("{name}","{grade}","{address}","{ph}","{email}","{school}","{g_name}","{order_id}","{prevAtt}","paid","{ano}","{str(datetime.now(IST))}","{ip}");
            '''
        )
        mail.send(msg)
        return True
    except Exception as e:
        return False


def countReload():
    visitorNumber = Counter.query.first()
    if visitorNumber is None:
        # Assuming 'count' column exists
        visitorNumber = Counter(count=1)
        db.session.add(visitorNumber)
    visitorNumber.count = visitorNumber.count + 1
    db.session.commit()


@app.route('/')
def index():
    countReload()
    return render_template('home.html', key_id=RAZORPAY_KEY_ID)


@app.get('/what_is')
def what_is():
    return render_template('whatis.html')


@app.get('/rules')
def rules():
    return render_template('rules.html')


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
    amount = 20 * 100

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

    url = f'https://api.razorpay.com/v1/orders/{order_id}'
    auth = (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)  # Tuple of Key ID and Secret

    response = requests.get(url, auth=auth)
    if response.status_code == 200:
        print(response.json()['status'])
        if response.json()['status'] in ['captured', 'paid']:
            return True
        return False
    else:
        return False

    # try:
    #     order = razorpay_client.order.fetch(order_id)
    #     return order.get("status") == "paid"
    # except razorpay.errors.BadRequestError:
    #     return False


@app.route('/get_status', methods=['POST'])
def get_status():
    data = request.form
    ano = data.get("ano")

    student = User.query.filter_by(ano=ano).first()

    if student:
        return {"name": student.name,
                "g_name": student.gName,
                "grade": student.grade,
                "phone": student.ph[0:4]+"xxxxxx",
                "email": "xxxxx"+student.email[5:],
                "time": str(student.created_at)
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

    if is_status_paid:
        if is_payment_valid:
            return jsonify({"status": "success", "message": "Amount paid and payment verified successfully"}), 200
        else:
            return jsonify({"status": "success", "message": "Amount paid but payment NOT verified successfully"}), 200
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
    ip = 0

    try:
        user = User(name=name, grade=grade, address=address, ph=ph,
                    email=email, ip=ip, school=school, gName=g_name, order_id=order_id, prevAtt=prevAtt, paymentStatus="paid", ano=ano)

        db.session.add(user)
        db.session.commit()

        mailSent = send_mail(name, grade, ano, order_id,
                             email, g_name, address)
        # mailSent = True

        if mailSent:
            return jsonify({"status": "success", "message": ("User added to the database", "Mail sent.")}), 200
        else:
            return jsonify({"status": "success", "message": ("User added to the database", "Mail not sent.")}), 200
    except Exception as e:
        db.session.rollback()  # Roll back for any unexpected error
        send_mail(name, grade, ano, order_id,
                  email, g_name, address)
        send_mail_manually(name, grade, address, ph, email,
                           ip, school, g_name, order_id, prevAtt, ano)
        return jsonify(error="UnexpectedError", message=str(e)), 500


@app.get('/getdata')
def getData():
    totalStudents = User.query.count()
    totalReload = Counter.query.first().count
    totalClassSixStudent = User.query.filter(User.grade == '6').count()
    totalClassSevenStudent = User.query.filter(User.grade == '7').count()
    totalClassEightStudent = User.query.filter(User.grade == '8').count()
    totalClassNineStudent = User.query.filter(User.grade == '9').count()
    totalClassTenStudent = User.query.filter(User.grade == '10').count()

    info = f'''<h3 style="padding: 20%">
        Total Students: {totalStudents} <br><br>
        Class 6: {totalClassSixStudent}; {round((totalClassSixStudent*100)/totalStudents,2)}% of total students. <br>
        Class 7: {totalClassSevenStudent}; {round((totalClassSevenStudent*100)/totalStudents,2)}% of total students. <br>
        Class 8: {totalClassEightStudent}; {round((totalClassEightStudent*100)/totalStudents,2)}% of total students. <br>
        Class 9: {totalClassNineStudent}; {round((totalClassNineStudent*100)/totalStudents,2)}% of total students. <br>
        Class 10: {totalClassTenStudent}; {round((totalClassTenStudent*100)/totalStudents,2)}% of total students. <br><br>
        Expected Fee Collection: ₹{20*(totalStudents - totalClassSixStudent)}. <br><br>
        Total Main Page Reload: {totalReload}</h3>
    '''
    return info


@app.get('/tc')
def tc():
    return render_template('tc.html')


if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0", port="5000")


def create_app():
    return app
