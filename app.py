from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from functools import wraps
import gspread

# Import the functions from your backend script
import backend_logic as backend

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_12345'

# --- Connect to Sheets on App Startup ---
spreadsheet = backend.connect_to_spreadsheet(backend.SPREADSHEET_NAME)
if spreadsheet:
    try:
        student_sheet = spreadsheet.worksheet('Students')
        volunteer_sheet = spreadsheet.worksheet('Volunteers')
        faq_sheet = spreadsheet.worksheet('FAQ')
        announcement_sheet = spreadsheet.worksheet('Announcements')
        # Verify headers for all sheets
        backend.verify_headers(student_sheet, backend.STUDENT_HEADERS)
        backend.verify_headers(volunteer_sheet, backend.VOLUNTEER_HEADERS)
        backend.verify_headers(faq_sheet, backend.FAQ_HEADERS)
        backend.verify_headers(announcement_sheet, backend.ANNOUNCEMENT_HEADERS)
    except gspread.WorksheetNotFound as e:
        print(f"❌ CRITICAL ERROR: A required worksheet was not found: {e}")
        student_sheet, volunteer_sheet, faq_sheet, announcement_sheet = None, None, None, None
else:
    student_sheet, volunteer_sheet, faq_sheet, announcement_sheet = None, None, None, None

# --- Context Processor to make announcement available to all templates ---
@app.context_processor
def inject_announcement():
    if 'username' in session and announcement_sheet:
        announcement = backend.get_announcement(announcement_sheet)
        return dict(announcement=announcement)
    return dict(announcement=None)

# --- Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Main & Auth Routes ---
@app.route('/')
def index():
    if 'username' not in session:
        return render_template('index.html')
    if not student_sheet: return "Error: Could not connect to the Student Data Sheet. Please check server logs."
    
    new_student_id = request.args.get('new_student_id')
    all_records = backend.get_all_records_safely(student_sheet, backend.STUDENT_HEADERS)
    stats = {
        'total': len(all_records),
        'completed': sum(1 for r in all_records if r.get('stage4_doaa_status') == 'Done'),
        'in_lhc_queue': sum(1 for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue'),
        'flagged': sum(1 for r in all_records if r.get('flagged') == 'yes')
    }
    new_faq_notification = session.pop('new_faq_added', False)
    return render_template('index.html', dashboard_stats=stats, new_student_id=new_student_id, new_faq_notification=new_faq_notification)

@app.route('/login', methods=['POST'])
def login():
    if not volunteer_sheet: return "Error: Could not connect to the Volunteer Data Sheet."
    username = request.form.get('username').lower().strip()
    password = request.form.get('password')
    
    users = backend.get_all_users(volunteer_sheet)
    user = next((u for u in users if u['username'] == username and str(u['password']) == password), None)

    if user:
        session['username'] = user['username']
        session['role'] = user['role']
    else:
        flash('Invalid username or password.', 'error')
    return redirect(url_for('index'))

# ADD this new route to app.py

@app.route('/flagged')
@login_required
def flagged_students():
    if not student_sheet: 
        return "Error: Student Sheet not connected."
    
    all_records = backend.get_all_records_safely(student_sheet, backend.STUDENT_HEADERS)
    # Filter the list to find students who are flagged
    flagged_list = [r for r in all_records if r.get('flagged') == 'yes']
    
    return render_template('flagged_students.html', students=flagged_list)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- Profile Page Routes ---
@app.route('/profile')
@login_required
def profile():
    users = backend.get_all_users(volunteer_sheet)
    current_user = next((u for u in users if u['username'] == session['username']), None)
    
    if not current_user:
        flash("Could not find your user profile.", "error")
        return redirect(url_for('index'))
        
    return render_template('profile.html', user=current_user)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    new_password = request.form.get('password')
    current_username = session['username']
    current_role = session.get('role', 'volunteer')

    if not new_password:
        flash("Password cannot be empty.", "error")
        return redirect(url_for('profile'))

    result = backend.update_user(volunteer_sheet, current_username, current_username, new_password, current_role)
    if result == "success":
        flash("Your password has been updated successfully.", "success")
    else:
        flash("An error occurred while updating your password.", "error")
    return redirect(url_for('profile'))

# --- Student Management Routes ---
@app.route('/students')
@login_required
def students_list():
    if not student_sheet: return "Error: Student Sheet not connected."
    all_students = backend.get_all_records_safely(student_sheet, backend.STUDENT_HEADERS)
    return render_template('students_list.html', students=all_students)

@app.route('/search', methods=['POST'])
@login_required
def search_student():
    search_term = request.form['search_term'].strip()
    row_number = backend.find_student_row(student_sheet, search_term)
    if not row_number:
        flash(f"Student '{search_term}' not found. You can add them as a new entry.", "error")
        return redirect(url_for('index', new_student_id=search_term))
    return redirect(url_for('search_student_get', search_term=search_term))

@app.route('/add', methods=['POST'])
@login_required
def add_student():
    app_id, student_name = request.form['app_id'].strip(), request.form['student_name'].strip()
    backend.add_student_from_webapp(student_sheet, app_id, student_name)
    flash(f"New student '{student_name}' was added successfully!", "success")
    return redirect(url_for('search_student_get', search_term=app_id))

@app.route('/update_status', methods=['POST'])
@login_required
def update_status():
    student_id, action = request.form['student_id'], request.form['action']
    volunteer_name = session['username'].capitalize()
    row_number = backend.find_student_row(student_sheet, student_id)
    if not row_number: return "Student not found."
    action_type, stage_name = action.split('_', 1)
    stage_map = {'entry': 3, 'hostel': 6, 'insurance': 9, 'lhc_docs': 12, 'doaa': 15}
    cols_start = stage_map.get(stage_name.replace('_done','').replace('_queue',''))
    if not cols_start: return "Invalid action."
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if action_type == 'unmark': new_status, update_by, update_ts = 'Pending', '', ''
    else:
        update_by, update_ts = volunteer_name, timestamp
        new_status = 'In Queue' if 'queue' in action else 'Done'
    if stage_name == 'doaa' and action_type == 'mark':
        student_data = student_sheet.row_values(row_number)
        if not all(s == 'Done' for s in [student_data[2], student_data[5], student_data[8], student_data[11]]):
             flash("Error: All previous stages must be 'Done'.", "error")
             return redirect(url_for('search_student_get', search_term=student_id))
    student_sheet.update_cells([gspread.Cell(row_number, i, v) for i, v in enumerate([new_status, update_by, update_ts], start=cols_start)])
    flash(f"Status for {student_id} updated.", "success")
    return redirect(url_for('search_student_get', search_term=student_id))

@app.route('/update_note', methods=['POST'])
@login_required
def update_note():
    student_id, notes = request.form['student_id'], request.form['notes']
    row_number = backend.find_student_row(student_sheet, student_id)
    if not row_number: return "Student not found."
    student_sheet.update_cell(row_number, 18, notes)
    flash("Note updated successfully.", "success")
    return redirect(url_for('search_student_get', search_term=student_id))

@app.route('/update_student_details', methods=['POST'])
@login_required
def update_student_details():
    original_id = request.form.get('original_student_id')
    new_name = request.form.get('student_name').strip()
    new_id = request.form.get('student_identifier').strip()
    if original_id != new_id and backend.find_student_row(student_sheet, new_id):
        flash(f"Error: Application ID '{new_id}' already exists.", "error")
        return redirect(url_for('search_student_get', search_term=original_id))
    row_number = backend.find_student_row(student_sheet, original_id)
    if not row_number:
        flash(f"Could not find original student '{original_id}'.", "error")
        return redirect(url_for('index'))
    student_sheet.update_cell(row_number, 1, new_id)
    student_sheet.update_cell(row_number, 2, new_name)
    flash("Student details updated successfully.", "success")
    return redirect(url_for('search_student_get', search_term=new_id))
    
@app.route('/flag_student', methods=['POST'])
@login_required
def flag_student():
    student_id, current_flag = request.form['student_id'], request.form.get('current_flag', 'no')
    new_flag = 'no' if current_flag == 'yes' else 'yes'
    backend.update_student_flag(student_sheet, student_id, new_flag)
    flash_message = f"Flag for student {student_id} has been removed." if new_flag == 'no' else f"Student {student_id} has been flagged for assistance."
    flash(flash_message, "success")
    return redirect(url_for('search_student_get', search_term=student_id))

@app.route('/search_get')
@login_required
def search_student_get():
    search_term = request.args.get('search_term')
    row_number = backend.find_student_row(student_sheet, search_term)
    if not row_number: return f"Student '{search_term}' not found. <a href='/'>Go back</a>."
    student_data_list = student_sheet.row_values(row_number)
    student_dict = dict(zip(backend.STUDENT_HEADERS, student_data_list))
    return render_template('student_details.html', student=student_dict)

# --- Feature Routes ---
@app.route('/lhc_queue')
@login_required
def lhc_queue():
    all_records = backend.get_all_records_safely(student_sheet, backend.STUDENT_HEADERS)
    queue_list = [r for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue']
    return render_template('lhc_queue.html', queue=queue_list, now=datetime.now())

@app.route('/lhc_queue/mark_done', methods=['POST'])
@login_required
def lhc_mark_done():
    student_id = request.form['student_id']
    volunteer_name = session['username'].capitalize()
    row_number = backend.find_student_row(student_sheet, student_id)
    if not row_number: 
        flash(f"Student '{student_id}' not found.", "error")
        return redirect(url_for('lhc_queue'))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cells_to_update = [
        gspread.Cell(row_number, 12, 'Done'),
        gspread.Cell(row_number, 13, volunteer_name),
        gspread.Cell(row_number, 14, timestamp)
    ]
    student_sheet.update_cells(cells_to_update)
    flash(f"Student {student_id} marked as done for LHC.", "success")
    return redirect(url_for('lhc_queue'))

@app.route('/faq')
@login_required
def faq():
    if not faq_sheet: return "Error: FAQ Sheet not connected."
    faqs = backend.get_all_faqs(faq_sheet)
    return render_template('faq.html', faqs=faqs)

@app.route('/leaderboard')
@login_required
def leaderboard():
    if not student_sheet: return "Error: Student Sheet not connected."
    board = backend.get_volunteer_leaderboard(student_sheet)
    return render_template('leaderboard.html', leaderboard=board)

# --- ADMIN PANEL ROUTES ---
@app.route('/admin')
@admin_required
def admin_panel():
    if not volunteer_sheet: return "Error: Volunteer Sheet not connected."
    users = backend.get_all_users(volunteer_sheet)
    return render_template('admin.html', users=users)

@app.route('/admin/faq')
@admin_required
def admin_faq():
    if not faq_sheet: return "Error: FAQ Sheet not connected."
    faqs = backend.get_all_faqs(faq_sheet)
    faqs_with_rows = [dict(faq, row_id=i+2) for i, faq in enumerate(faqs)]
    return render_template('admin_faq.html', faqs=faqs_with_rows)

@app.route('/admin/faq/add', methods=['POST'])
@admin_required
def add_faq():
    question, answer = request.form['question'], request.form['answer']
    backend.add_faq(faq_sheet, question, answer)
    session['new_faq_added'] = True # Set the notification flag
    flash("New FAQ added successfully.", "success")
    return redirect(url_for('admin_faq'))

@app.route('/admin/faq/delete/<row_id>')
@admin_required
def delete_faq(row_id):
    backend.delete_faq(faq_sheet, row_id)
    flash("FAQ deleted successfully.", "success")
    return redirect(url_for('admin_faq'))

@app.route('/admin/announcement')
@admin_required
def admin_announcement():
    if not announcement_sheet: return "Error: Announcement Sheet not connected."
    current_message = backend.get_announcement(announcement_sheet)
    return render_template('admin_announcement.html', message=current_message)

@app.route('/admin/announcement/update', methods=['POST'])
@admin_required
def update_announcement():
    new_message = request.form.get('message', '')
    backend.update_announcement(announcement_sheet, new_message)
    flash("Announcement has been updated successfully.", "success")
    return redirect(url_for('admin_announcement'))

@app.route('/admin/add_user', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username').lower().strip()
    password = request.form.get('password')
    role = request.form.get('role', 'volunteer')
    if backend.add_user(volunteer_sheet, username, password, role):
        flash(f"User '{username}' added successfully.", "success")
    else:
        flash(f"User '{username}' already exists.", "error")
    return redirect(url_for('admin_panel'))

@app.route('/admin/edit_user/<username>')
@admin_required
def edit_user_page(username):
    users = backend.get_all_users(volunteer_sheet)
    user = next((u for u in users if u['username'] == username), None)
    if not user: return redirect(url_for('admin_panel'))
    return render_template('edit_user.html', user=user)

@app.route('/admin/update_user', methods=['POST'])
@admin_required
def update_user():
    original_username = request.form.get('original_username')
    new_username = request.form.get('username').lower().strip()
    new_password = request.form.get('password')
    new_role = request.form.get('role', 'volunteer')
    if original_username == 'admin' and session['username'] != 'admin':
        flash("You do not have permission to edit the primary admin account.", "error")
        return redirect(url_for('admin_panel'))
    result = backend.update_user(volunteer_sheet, original_username, new_username, new_password, new_role)
    if result == "success":
        flash(f"User '{original_username}' updated successfully.", "success")
        return redirect(url_for('admin_panel'))
    elif result == "duplicate":
        flash(f"Error: Username '{new_username}' already exists.", "error")
        return redirect(url_for('edit_user_page', username=original_username))
    else:
        flash(f"Error: Could not find user '{original_username}'.", "error")
        return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<username>')
@admin_required
def delete_user(username):
    if username == 'admin':
        flash("The primary admin account cannot be deleted.", "error")
        return redirect(url_for('admin_panel'))
    backend.delete_user(volunteer_sheet, username)
    flash(f"User '{username}' deleted successfully.", "success")
    return redirect(url_for('admin_panel'))

# --- Main execution block ---
if __name__ == '__main__':
    app.run(debug=True)
