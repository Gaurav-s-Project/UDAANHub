from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import gspread

# Import the functions from your backend script
import backend_logic as backend

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_12345'

# --- User Authentication Data ---
VALID_USERS = { 'gaurav': '12345', 'naman': '12345' }

# --- Main Dashboard / Login Route ---
@app.route('/')
def index():
    if 'username' not in session:
        return render_template('index.html')

    if not sheet: return "Error: Could not connect to Google Sheet."
    
    # Get the new student ID from the URL if it exists (after a failed search)
    new_student_id = request.args.get('new_student_id')
    
    all_records = backend.get_all_records_safely(sheet)
    stats = {
        'total': len(all_records),
        'completed': sum(1 for r in all_records if r.get('stage4_doaa_status') == 'Done'),
        'in_lhc_queue': sum(1 for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue')
    }
    return render_template('index.html', dashboard_stats=stats, new_student_id=new_student_id)

# --- Login and Logout Routes ---
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username').lower()
    password = request.form.get('password')
    if username in VALID_USERS and VALID_USERS[username] == password:
        session['username'] = username
    else:
        flash('Invalid username or password.', 'error')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

# --- Route to handle the student search ---
@app.route('/search', methods=['POST'])
def search_student():
    if 'username' not in session: return redirect(url_for('index'))
    if not sheet: return "Error: Could not connect to Google Sheet."
    
    search_term = request.form['search_term'].strip()
    row_number = backend.find_student_row(sheet, search_term)
    
    if not row_number:
        # NEW: If not found, flash a message and redirect to the index page
        # with a query parameter to show the 'add student' form.
        flash(f"Student '{search_term}' not found. You can add them as a new entry.", "error")
        return redirect(url_for('index', new_student_id=search_term))
        
    student_data_list = sheet.row_values(row_number)
    student_dict = dict(zip(backend.EXPECTED_HEADERS, student_data_list))
    return render_template('student_details.html', student=student_dict)

# --- NEW: Route to add a new student ---
@app.route('/add', methods=['POST'])
def add_student_route():
    if 'username' not in session: return redirect(url_for('index'))
    if not sheet: return "Error: Could not connect to Google Sheet."

    app_id = request.form['app_id'].strip()
    student_name = request.form['student_name'].strip()

    # Call a backend function to add the student
    backend.add_student_from_webapp(sheet, app_id, student_name)
    flash(f"New student '{student_name}' was added successfully!", "success")
    
    # Redirect to the new student's details page
    return redirect(url_for('search_student_get', search_term=app_id))

# --- ADD THIS NEW ROUTE ---
@app.route('/lhc_queue')
def lhc_queue():
    if 'username' not in session: return redirect(url_for('index'))
    if not sheet: return "Error: Could not connect to Google Sheet."
    
    all_records = backend.get_all_records_safely(sheet)
    # Filter for students whose status is exactly 'In Queue'
    queue_list = [r for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue']
    
    # Get the current time to display on the page
    now = datetime.now()
    
    return render_template('lhc_queue.html', queue=queue_list, now=now)


# --- ADD THIS NEW ROUTE ---
@app.route('/faq')
def faq():
    if 'username' not in session: return redirect(url_for('index'))
    return render_template('faq.html')

# --- Route to handle status updates ---
@app.route('/update_status', methods=['POST'])
def update_status():
    if 'username' not in session: return redirect(url_for('index'))
    if not sheet: return "Error: Could not connect to Google Sheet."

    student_id = request.form['student_id']
    action = request.form['action']
    volunteer_name = session['username'].capitalize()
    row_number = backend.find_student_row(sheet, student_id)
    if not row_number: return "Student not found during update."

    action_type, stage_name = action.split('_', 1)
    stage_map = {'hostel': 3, 'insurance': 6, 'lhc_docs': 9, 'doaa': 12}
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
        student_data_list = sheet.row_values(row_number)
        if not (student_data_list[2] == 'Done' and student_data_list[5] == 'Done' and student_data_list[8] == 'Done'):
             flash("Error: All previous stages must be 'Done' before final approval.", "error")
             return redirect(url_for('search_student_get', search_term=student_id))

    cells_to_update = [
        gspread.Cell(row_number, cols_to_update_start, new_status),
        gspread.Cell(row_number, cols_to_update_start + 1, update_by),
        gspread.Cell(row_number, cols_to_update_start + 2, update_ts)
    ]
    sheet.update_cells(cells_to_update)
    flash(f"Status for {student_id} updated successfully.", "success")
    return redirect(url_for('search_student_get', search_term=student_id))

# --- Route to handle note updates ---
@app.route('/update_note', methods=['POST'])
def update_note():
    if 'username' not in session: return redirect(url_for('index'))
    if not sheet: return "Error: Could not connect to Google Sheet."
    student_id = request.form['student_id']
    notes = request.form['notes']
    row_number = backend.find_student_row(sheet, student_id)
    if not row_number: return "Student not found."
    sheet.update_cell(row_number, 15, notes)
    flash("Note updated successfully.", "success")
    return redirect(url_for('search_student_get', search_term=student_id))

# --- Helper route to redirect back to search result ---
@app.route('/search_get')
def search_student_get():
    if 'username' not in session: return redirect(url_for('index'))
    if not sheet: return "Error: Could not connect to Google Sheet."
    search_term = request.args.get('search_term')
    row_number = backend.find_student_row(sheet, search_term)
    if not row_number: return f"Student '{search_term}' not found. <a href='/'>Go back</a>."
    student_data_list = sheet.row_values(row_number)
    student_dict = dict(zip(backend.EXPECTED_HEADERS, student_data_list))
    return render_template('student_details.html', student=student_dict)

# --- Main execution block ---
if __name__ == '__main__':
    sheet = backend.connect_to_sheet()
    if sheet:
        backend.verify_headers(sheet)
    app.run(debug=True)
