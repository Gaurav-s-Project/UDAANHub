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
        print("✅ Successfully accessed 'Students' and 'Volunteers' worksheets.")
        # Verify headers for both sheets
        backend.verify_headers(student_sheet, backend.STUDENT_HEADERS)
        backend.verify_headers(volunteer_sheet, backend.VOLUNTEER_HEADERS)
    except gspread.WorksheetNotFound as e:
        print(f"❌ CRITICAL ERROR: A required worksheet was not found: {e}")
        student_sheet = None
        volunteer_sheet = None
else:
    student_sheet = None
    volunteer_sheet = None

# --- Decorator for Admin-Only Routes ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Main Dashboard / Login Route ---
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
        'in_lhc_queue': sum(1 for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue')
    }
    return render_template('index.html', dashboard_stats=stats, new_student_id=new_student_id)

# --- Login and Logout Routes ---
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- Profile Page Routes ---
@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    users = backend.get_all_users(volunteer_sheet)
    current_user = next((u for u in users if u['username'] == session['username']), None)
    
    if not current_user:
        flash("Could not find your user profile.", "error")
        return redirect(url_for('index'))
        
    return render_template('profile.html', user=current_user)

@app.route('/profile/update', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return redirect(url_for('index'))

    new_password = request.form.get('password')
    current_username = session['username']
    current_role = session.get('role', 'volunteer')

    if not new_password:
        flash("Password cannot be empty.", "error")
        return redirect(url_for('profile'))

    backend.update_user(volunteer_sheet, current_username, current_username, new_password, current_role)
    
    flash("Your password has been updated successfully.", "success")
    return redirect(url_for('profile'))

# --- Student Management Routes ---
@app.route('/search', methods=['POST'])
def search_student():
    if 'username' not in session: return redirect(url_for('index'))
    if not student_sheet: return "Error: Could not connect to Student Sheet."
    
    search_term = request.form['search_term'].strip()
    row_number = backend.find_student_row(student_sheet, search_term)
    
    if not row_number:
        flash(f"Student '{search_term}' not found. You can add them as a new entry.", "error")
        return redirect(url_for('index', new_student_id=search_term))
        
    student_data_list = student_sheet.row_values(row_number)
    student_dict = dict(zip(backend.STUDENT_HEADERS, student_data_list))
    return render_template('student_details.html', student=student_dict)

@app.route('/add', methods=['POST'])
def add_student_route():
    if 'username' not in session: return redirect(url_for('index'))
    if not student_sheet: return "Error: Could not connect to Student Sheet."

    app_id = request.form['app_id'].strip()
    student_name = request.form['student_name'].strip()

    backend.add_student_from_webapp(student_sheet, app_id, student_name)
    flash(f"New student '{student_name}' was added successfully!", "success")
    
    return redirect(url_for('search_student_get', search_term=app_id))

@app.route('/update_status', methods=['POST'])
def update_status():
    if 'username' not in session: return redirect(url_for('index'))
    if not student_sheet: return "Error: Could not connect to Student Sheet."

    student_id = request.form['student_id']
    action = request.form['action']
    volunteer_name = session['username'].capitalize()
    
    row_number = backend.find_student_row(student_sheet, student_id)
    if not row_number: return "Student not found during update."

    action_type, stage_name = action.split('_', 1)
    
    stage_map = {'entry': 3, 'hostel': 6, 'insurance': 9, 'lhc_docs': 12, 'doaa': 15}
    cols_to_update_start = stage_map.get(stage_name.replace('_done','').replace('_queue',''))

    if not cols_to_update_start: return "Invalid action."

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if action_type == 'unmark':
        new_status, update_by, update_ts = 'Pending', '', ''
    else:
        update_by, update_ts = volunteer_name, timestamp
        if 'queue' in action: new_status = 'In Queue'
        else: new_status = 'Done'

    if stage_name == 'doaa' and action_type == 'mark':
        student_data_list = student_sheet.row_values(row_number)
        if not (student_data_list[2] == 'Done' and student_data_list[5] == 'Done' and student_data_list[8] == 'Done' and student_data_list[11] == 'Done'):
             flash("Error: All previous stages must be 'Done' before final approval.", "error")
             return redirect(url_for('search_student_get', search_term=student_id))

    cells_to_update = [
        gspread.Cell(row_number, cols_to_update_start, new_status),
        gspread.Cell(row_number, cols_to_update_start + 1, update_by),
        gspread.Cell(row_number, cols_to_update_start + 2, update_ts)
    ]
    student_sheet.update_cells(cells_to_update)
    flash(f"Status for {student_id} updated successfully.", "success")
    return redirect(url_for('search_student_get', search_term=student_id))

@app.route('/update_note', methods=['POST'])
def update_note():
    if 'username' not in session: return redirect(url_for('index'))
    if not student_sheet: return "Error: Could not connect to Student Sheet."
    student_id = request.form['student_id']
    notes = request.form['notes']
    row_number = backend.find_student_row(student_sheet, student_id)
    if not row_number: return "Student not found."
    student_sheet.update_cell(row_number, 18, notes)
    flash("Note updated successfully.", "success")
    return redirect(url_for('search_student_get', search_term=student_id))

@app.route('/search_get')
def search_student_get():
    if 'username' not in session: return redirect(url_for('index'))
    if not student_sheet: return "Error: Could not connect to Student Sheet."
    search_term = request.args.get('search_term')
    row_number = backend.find_student_row(student_sheet, search_term)
    if not row_number: return f"Student '{search_term}' not found. <a href='/'>Go back</a>."
    student_data_list = student_sheet.row_values(row_number)
    student_dict = dict(zip(backend.STUDENT_HEADERS, student_data_list))
    return render_template('student_details.html', student=student_dict)

# --- Feature Routes ---
@app.route('/lhc_queue')
def lhc_queue():
    if 'username' not in session: return redirect(url_for('index'))
    if not student_sheet: return "Error: Could not connect to Student Sheet."
    all_records = backend.get_all_records_safely(student_sheet, backend.STUDENT_HEADERS)
    queue_list = [r for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue']
    now = datetime.now()
    return render_template('lhc_queue.html', queue=queue_list, now=now)

# --- NEW: Route to handle marking LHC as done from the queue page ---
@app.route('/lhc_queue/mark_done', methods=['POST'])
def lhc_mark_done():
    if 'username' not in session: return redirect(url_for('index'))
    if not student_sheet: return "Error: Could not connect to Student Sheet."

    student_id = request.form['student_id']
    volunteer_name = session['username'].capitalize()
    
    row_number = backend.find_student_row(student_sheet, student_id)
    if not row_number: 
        flash(f"Student '{student_id}' not found during update.", "error")
        return redirect(url_for('lhc_queue'))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Columns for stage3_lhc_docs are 12, 13, 14
    cells_to_update = [
        gspread.Cell(row_number, 12, 'Done'),
        gspread.Cell(row_number, 13, volunteer_name),
        gspread.Cell(row_number, 14, timestamp)
    ]
    student_sheet.update_cells(cells_to_update)
    flash(f"Student {student_id} marked as done for LHC.", "success")
    return redirect(url_for('lhc_queue'))

@app.route('/faq')
def faq():
    if 'username' not in session: return redirect(url_for('index'))
    return render_template('faq.html')

# --- ADMIN PANEL ROUTES ---
@app.route('/admin')
@admin_required
def admin_panel():
    if not volunteer_sheet: return "Error: Could not connect to Volunteer Sheet."
    users = backend.get_all_users(volunteer_sheet)
    return render_template('admin.html', users=users)

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
    backend.update_user(volunteer_sheet, original_username, new_username, new_password, new_role)
    flash(f"User '{original_username}' updated successfully.", "success")
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
