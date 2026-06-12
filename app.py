# app.py
from flask import Flask, render_template, request, redirect, url_for
import cv2
import numpy as np
import face_recognition
import os
import calendar
import sqlite3
from datetime import datetime
from flask import send_file
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from datetime import datetime, timedelta
import re
import base64
from datetime import datetime, timedelta
from flask import render_template
from flask import Flask, render_template, request, redirect, url_for, session
import glob

app = Flask(__name__)
app.secret_key = "your_secret_key_here"   # put any random string

# Path for face images
FACE_FOLDER = 'faces'
DB_PATH = 'database/attendance.db'

# Ensure database exists
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    roll_no TEXT,
                    name TEXT,
                    date TEXT,
                    time TEXT,
                    lecture TEXT,
                    class_name TEXT,
                    teacher_name TEXT
                )''')

                 # Students table (new)
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    roll_no TEXT PRIMARY KEY,
                    name TEXT
                )''')
    conn.commit()
    conn.close()

init_db()


# Load known faces
def load_known_faces():
    known_encodings = []
    known_roll_nos = []
    known_names = []

    for file_name in os.listdir(FACE_FOLDER):
        if file_name.endswith(('.jpg', '.png')):
            path = os.path.join(FACE_FOLDER, file_name)
            image = face_recognition.load_image_file(path)
            encoding = face_recognition.face_encodings(image)
            if encoding:
                known_encodings.append(encoding[0])
                roll_no, name = file_name.split('.')[0].split('_', 1)
                known_roll_nos.append(roll_no)
                known_names.append(name)
    return known_encodings, known_roll_nos, known_names

@app.route('/export/excel')
def export_excel():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM attendance", conn)
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance')

    output.seek(0)
    return send_file(output, download_name="attendance.xlsx", as_attachment=True)

@app.route('/export/pdf')
def export_pdf():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM attendance").fetchall()
    conn.close()

    output = BytesIO()
    c = canvas.Canvas(output)
    c.setFont("Helvetica", 12)
    c.drawString(200, 800, "Attendance Report")

    y = 760
    for row in rows:
        c.drawString(50, y, f"{row[0]}  |  {row[1]}  |  {row[2]}  |  {row[3]}")
        y -= 20

    c.save()
    output.seek(0)
    return send_file(output, download_name="attendance.pdf", as_attachment=True)



# UPDATED ➜ Export Registered Students to Excel
@app.route('/students/export/excel')
def export_students_excel():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT roll_no, name FROM students ORDER BY roll_no", conn)
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Students')

    output.seek(0)
    return send_file(output, download_name="students.xlsx", as_attachment=True)

# Excel and Pdf Download for List_of_all_register_student
# UPDATED ➜ Export Registered Students to PDF
@app.route('/students/export/pdf')
def export_students_pdf():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT roll_no, name FROM students ORDER BY roll_no").fetchall()
    conn.close()

    output = BytesIO()
    c = canvas.Canvas(output)
    c.setFont("Helvetica", 12)

    c.drawString(200, 800, "Registered Students")

    y = 760
    for row in rows:
        c.drawString(100, y, f"{row[0]}  |  {row[1]}")
        y -= 20

    c.save()
    output.seek(0)
    return send_file(output, download_name="students.pdf", as_attachment=True)


# UPDATED ➜ Delete student route
@app.route('/delete_student/<int:roll_no>')
def delete_student(roll_no):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM students WHERE roll_no = ?", (roll_no,))
    conn.commit()
    conn.close()
    # UPDATED ➜ Delete face images folder
    # UPDATED ➜ Delete all images of that student
    face_folder = "faces"

    for file in os.listdir(face_folder):
        # Check if file belongs to that student
        if file.startswith(str(roll_no) + "_"):
            os.remove(os.path.join(face_folder, file))

    return redirect('/teacher_check_allregister_student_login_form')  # ⚠️ change if your route is different


@app.route('/')
def home():
    return render_template("load.html")

@app.route('/role')
def role():
    return render_template("role.html")

@app.route('/role/student')
def role_student():
    return render_template("student_role_authentication.html")

@app.route('/role/teacher')
def role_teacher():
    return render_template("teacher_role_authenticate.html")

@app.route('/student_login', methods=['GET'])
def show_student_form():
    return render_template('student_login.html')
    
# new student login code 
@app.route('/student_login', methods=['POST'])
def student_login():
    # Get teacher details from session (set when teacher starts attendance)
    lecture = session.get('lecture')
    class_name = session.get('class_name')
    teacher_name = session.get('teacher_name')

    if not lecture or not class_name or not teacher_name:
        return "Teacher has not started attendance session."

    # Get the image from hidden input (base64)
    image_data = request.form['image']
    if not image_data:
        return "No image captured"

    # Decode base64 image
    image_data = image_data.split(",")[1]  # remove "data:image/png;base64,"
    file_bytes = base64.b64decode(image_data)
    img_np = np.frombuffer(file_bytes, np.uint8)
    frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

    # Detect face encoding
    face_encodings = face_recognition.face_encodings(frame)
    if not face_encodings:
        return render_template('denied.html', reason="No face detected.")

    # Load known faces from database
    known_encodings, known_roll_nos, known_names = load_known_faces()

    matches = face_recognition.compare_faces(known_encodings, face_encodings[0])
    face_distances = face_recognition.face_distance(known_encodings, face_encodings[0])

    best_match_index = np.argmin(face_distances) if face_distances.size > 0 else -1

    if best_match_index != -1 and matches[best_match_index]:
        roll_no = known_roll_nos[best_match_index]
        name = known_names[best_match_index]

        now = datetime.now()
        date_today = now.strftime("%Y-%m-%d")
        time_now = now.strftime("%H:%M:%S")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Check duplicate attendance
        c.execute("""
            SELECT time FROM attendance 
            WHERE roll_no=? AND date=? AND lecture=?
            ORDER BY time DESC LIMIT 1
        """, (roll_no, date_today, lecture))
        last_entry = c.fetchone()

        if last_entry:
            last_time = datetime.strptime(last_entry[0], "%H:%M:%S")
            time_diff = datetime.strptime(time_now, "%H:%M:%S") - last_time
            if time_diff < timedelta(minutes=45):
                conn.close()
                return render_template(
                    'duplicate.html',
                    name=name,
                    roll_no=roll_no,
                    date=date_today,
                    lecture=lecture,
                    minutes_left=45 - int(time_diff.total_seconds() / 60)
                )

        # Insert attendance
        c.execute("INSERT INTO attendance (roll_no, name, date, time, lecture, class_name, teacher_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (roll_no, name, date_today, time_now, lecture, class_name, teacher_name))
        conn.commit()
        conn.close()

        return render_template(
            'attendance_success.html',
            name=name,
            roll_no=roll_no,
            date=date_today,
            time=time_now,
            lecture=lecture,
            class_name=class_name,
            teacher_name=teacher_name
        )
    else:
        return render_template('denied.html', reason="Face not recognized.")

@app.route('/student_dashboard', methods=['GET', 'POST'])
def student_dashboard():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        name = request.form['name']

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
    SELECT date, time FROM attendance
    WHERE roll_no=? AND LOWER(name) LIKE LOWER(? || '%')
    ORDER BY date DESC, time DESC
""", (roll_no, name))

        # c.execute("SELECT date, time FROM attendance WHERE roll_no=? AND name=? ORDER BY date DESC, time DESC", (roll_no, name))
#         c.execute("""
#     SELECT date, time FROM attendance
#     WHERE roll_no=? AND LOWER(name)=LOWER(?)
#     ORDER BY date DESC, time DESC
# """, (roll_no, name))

        records = c.fetchall()
        conn.close()

        total_days = len(set([r[0] for r in records]))
        total_classes = len(records)

        return render_template(
            'student_dashboard.html',
            records=records,
            name=name,
            roll_no=roll_no,
            total_days=total_days,
            total_classes=total_classes
        )

    return render_template('student_dashboard.html', records=None)



@app.route('/teacher_login')
def teacher_login():
    return render_template('teacher_login.html')


@app.route('/dashboard', methods=['POST'])
def dashboard():
    username = request.form['username']
    password = request.form['password']
    if username == 'admin' and password == 'admin123':
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # c.execute("SELECT * FROM attendance ORDER BY date DESC, time DESC")
        c.execute("SELECT DISTINCT lecture FROM attendance")
        lectures = [row[0] for row in c.fetchall()]

        c.execute("SELECT DISTINCT date FROM attendance ORDER BY date DESC")
        dates = [row[0] for row in c.fetchall()]

        c.execute("SELECT DISTINCT class_name FROM attendance")
        classes = [row[0] for row in c.fetchall()]

        c.execute("SELECT * FROM attendance ORDER BY date DESC, time DESC")
        records = c.fetchall()

        # records = c.fetchall()
        conn.close()
        return render_template('dashboard_teacher.html', records=records, lectures=lectures, dates=dates, classes=classes)
    else:
        return render_template('wrong_pass.html')

@app.route('/register_student', methods=['GET'])
def register_form():
    return render_template('register_student.html')




@app.route('/register_student', methods=['POST'])
def register_student():
    roll_no = request.form['roll_no']
    name = request.form['name']
    files = request.files.getlist('images')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # checking for duplicate student by roll_no
    c.execute("SELECT * FROM students WHERE roll_no=? ", (roll_no,))
    existing = c.fetchone()

    if existing:
        conn.close()
        return render_template('newregister_dublicate.html',
                               message=f"⚠️ Student with Roll No : {roll_no} already exists!")

    if len(files) < 4:
        conn.close()  # UPDATED 
        return "Please upload at least 4 face images."

    # --- Check if face already exists (compare embeddings) ---
    for file in files[:4]:
        img_np = np.frombuffer(file.read(), np.uint8)
        frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_img)

        if len(encodings) == 0:
            return "⚠️ No face detected in one of the images. Please upload clear face images."
            

        new_face_encoding = encodings[0]

        # compare with existing face encodings in folder
        for existing_file in os.listdir(FACE_FOLDER):
            if existing_file.endswith(".jpg"):
                existing_img = face_recognition.load_image_file(os.path.join(FACE_FOLDER, existing_file))
                existing_enc = face_recognition.face_encodings(existing_img)
                if len(existing_enc) > 0:
                    match = face_recognition.compare_faces([existing_enc[0]], new_face_encoding, tolerance=0.5)
                    if match[0]:
                        return render_template('newregister_dublicate.html',
                                               message=f"⚠️ This face already exists in the system (file: {existing_file}).")

    # if new student then insert into DB
    c.execute("INSERT INTO students (roll_no, name) VALUES (?, ?)", (roll_no, name))
    conn.commit()
    conn.close()

    # Save images
    for i, file in enumerate(files[:4]):
        file.stream.seek(0)  # reset file pointer after reading once
        img_np = np.frombuffer(file.read(), np.uint8)
        frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        filename = f"{roll_no}_{name}_{i+1}.jpg"
        path = os.path.join(FACE_FOLDER, filename)
        cv2.imwrite(path, frame)

    # return render_template('registered_success.html', roll_no=roll_no, name=name)
    return redirect(f"/register_success?roll_no={roll_no}&name={name}")

# UPDATED ➜ Success page route
@app.route('/register_success')
def register_success():
    roll_no = request.args.get('roll_no')
    name = request.args.get('name')
    return render_template('registered_success.html', roll_no=roll_no, name=name)


@app.route("/attendance_report")
def attendance_report():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT date, COUNT(*) FROM attendance GROUP BY date ORDER BY date ASC")
    records = c.fetchall()
    conn.close()

    dates = [r[0] for r in records]
    counts = [r[1] for r in records]

    return render_template("attendance_report.html", dates=dates, counts=counts)

#defaulter list calculation
COLLEGE_START_DATE = datetime(2025, 5, 1)
MIN_MONTHS_BEFORE_CHECK = 4

import calendar

# NEW FUNCTION ➜ Count working days (Mon–Sat), Sundays excluded
def count_working_days(year, month):
    total_days = calendar.monthrange(year, month)[1]
    working_days = 0
    for day in range(1, total_days + 1):
        weekday = datetime(year, month, day).weekday()
        if weekday != 6:  # 6 = Sunday
            working_days += 1
    return working_days


@app.route("/defaulters")
def defaulters():
    today = datetime.now()
    selected_month = request.args.get("month", today.strftime("%Y-%m"))

    year, month = map(int, selected_month.split("-"))
    month_start = datetime(year, month, 1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    message = None
    final_list = []

    # 1️⃣ Month BEFORE college start
    if month_start < COLLEGE_START_DATE:
        message = "Defaulter list is not calculated because classes had not started yet."
        return render_template("defaulters.html",
                               defaulters=None,
                               selected_month=selected_month,
                               message=message)

    # 2️⃣ Too early after start? (Minimum 4 months rule)
    months_since_start = (today.year - COLLEGE_START_DATE.year) * 12 + (today.month - COLLEGE_START_DATE.month)
    if months_since_start < MIN_MONTHS_BEFORE_CHECK:
        message = "Defaulter list will be available after completing 4 months of attendance."
        return render_template("defaulters.html",
                               defaulters=None,
                               selected_month=selected_month,
                               message=message)

    # 3️⃣ FUTURE MONTH selected
    if month_start > today.replace(day=1):
        message = "Attendance for this month is not available yet."
        return render_template("defaulters.html",
                               defaulters=None,
                               selected_month=selected_month,
                               message=message)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all students ALWAYS
    cursor.execute("SELECT roll_no, name FROM students ORDER BY roll_no")
    all_students = cursor.fetchall()

    # 🔥 NEW FIX: Total working days of selected month (Mon–Sat)
    
    total_classes = count_working_days(year, month)
    total_classes = total_classes * 3

    # Present map (unique dates student attended)
    cursor.execute("""
        SELECT roll_no, COUNT(DISTINCT date) 
        FROM attendance
        WHERE date >= ? AND date < ?
        GROUP BY roll_no
    """, (month_start.strftime("%Y-%m-%d"), next_month.strftime("%Y-%m-%d")))
    present_map = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()

    # 4️⃣ If no attendance recorded at all → show all as 0%
    if total_classes == 0:
        message = "No attendance recorded for this month. All students are marked 0%."
        for roll_no, name in all_students:
            final_list.append((roll_no, name, 0, 0, 0))
        return render_template("defaulters.html",
                               defaulters=final_list,
                               selected_month=selected_month,
                               message=message)

    # 5️⃣ Normal calculation using working days
    for roll_no, name in all_students:
        present = present_map.get(roll_no, 0)
        percentage = round((present / total_classes) * 100, 2)

        if percentage < 65:
            final_list.append((roll_no, name, total_classes, present, percentage))

    return render_template("defaulters.html",
                           defaulters=final_list,
                           selected_month=selected_month,
                           message=message)




    

@app.route('/teacher_form', methods=['GET', 'POST'])
def teacher_form():
    if request.method == 'POST':
        teacher_name = request.form['teacher_name']
        lecture = request.form['lecture_name']   # <-- FIXED
        class_name = request.form['class_name']

        # Store in session so we can use them in student_login
        session['teacher_name'] = teacher_name
        session['lecture'] = lecture
        session['class_name'] = class_name

        # Redirect to student login page after teacher fills form
        return render_template('student_login.html')

    return render_template('teacher_form.html')  # <-- also add this for GETzz


# Utility to fetch registered students
def get_registered_students():
    conn = sqlite3.connect(DB_PATH)   # use the correct path
    cursor = conn.cursor()
    cursor.execute("SELECT roll_no, name FROM students ORDER BY roll_no ASC")
    students = cursor.fetchall()
    conn.close()
    return students

# Route to ask for admin login before showing registered students
@app.route("/teacher_check_allregister_student_login_form", methods=["GET", "POST"])
def teacher_check_allregister_student_login_form():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":
            students = get_registered_students()
            return render_template("list_of_all_registered_students.html", students=students)
        else:
            return render_template("wrong_pass_for_listof_registered_stu.html", error="Invalid credentials")

    return render_template("teacher_check_allregister_student_login_form.html")

@app.route("/student_role_authentication", methods=["GET", "POST"])
def student_role_authentication():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "student" and password == "stu123":
            return render_template("student_role.html")
        else:
            return render_template("wrong_pass_for_student_role_aut.html", error="Invalid credentials")

    return render_template("student_role_authentication.html")

@app.route("/teacher_role_authenticate", methods=["GET", "POST"])
def teacher_role_authenticate():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":
            students = get_registered_students()
            return render_template("index.html", students=students)
        else:
            return render_template("wrong_pass_for_teacher_role_aut.html", error="Invalid credentials")

    return render_template("teacher_role_authenticate.html")




if __name__ == '__main__':
    app.run(debug=True)
