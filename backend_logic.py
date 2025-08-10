import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time
import os
import csv

# --- Configuration ---
JSON_KEYFILE = 'creds.json' 
# UPDATED: This is now the name of the single spreadsheet FILE
SPREADSHEET_NAME = 'CampusArrival2025' 

# --- Advanced Feature Configuration ---
STUCK_THRESHOLD_MINUTES = 45

# --- Headers Configuration ---
STUDENT_HEADERS = [
    'student_identifier', 'student_name', 
    'stage0_entry_status', 'stage0_entry_by', 'stage0_entry_ts',
    'stage1_hostel_status', 'stage1_hostel_by', 'stage1_hostel_ts',
    'stage2_insurance_status', 'stage2_insurance_by', 'stage2_insurance_ts',
    'stage3_lhc_docs_status', 'stage3_lhc_docs_by', 'stage3_lhc_docs_ts',
    'stage4_doaa_status', 'stage4_doaa_by', 'stage4_doaa_ts',
    'Notes'
]
# NEW: Headers for the Volunteers sheet
VOLUNTEER_HEADERS = ['username', 'password', 'role']

# --- Connection to Google Sheets ---
def connect_to_spreadsheet(spreadsheet_name):
    """ Connects to a Google Spreadsheet file and returns the spreadsheet object. """
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
        client = gspread.authorize(creds)
        # This now opens the entire spreadsheet, not just the first sheet
        spreadsheet = client.open(spreadsheet_name)
        print(f"✅ Successfully connected to Google Sheet: {spreadsheet_name}")
        return spreadsheet
    except Exception as e:
        print(f"❌ An error occurred connecting to {spreadsheet_name}: {e}")
        return None

# --- Header Verification Tool ---
def verify_headers(sheet, headers):
    """ Checks if the headers in a given sheet match the expected headers. """
    try:
        actual_headers = sheet.row_values(1)
        if set(headers) == set(actual_headers):
            print(f"✅ Headers for '{sheet.title}' verified successfully.")
            return True
        else:
            print(f"❌ CRITICAL ERROR: Headers in '{sheet.title}' do not match.")
            return False
    except Exception:
        print(f"❌ Could not verify headers for '{sheet.title}'. The sheet might be empty.")
        return False

# --- Core Functions ---
def find_student_row(sheet, search_term):
    """ Finds a student by their Application ID or Name and returns the row number. """
    try:
        cell = sheet.find(search_term)
        return cell.row if cell else None
    except Exception:
        return None

# --- Functions for Web App ---
def get_all_records_safely(sheet, headers):
    """ A robust function to fetch all records for the web app. """
    try:
        if sheet.row_count > 1:
            return sheet.get_all_records(expected_headers=headers)
        else:
            return []
    except Exception:
        return []

def add_student_from_webapp(sheet, app_id, student_name):
    """ Adds a new student record to the sheet. Called by the web app. """
    if find_student_row(sheet, app_id):
        return
    new_row_data = [
        app_id, student_name,
        'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', ''
    ]
    sheet.append_row(new_row_data)

# --- NEW: User Management Functions ---
def get_all_users(sheet):
    """ Fetches all users from the Volunteers sheet. """
    return get_all_records_safely(sheet, VOLUNTEER_HEADERS)

def find_user_row(sheet, username):
    """ Finds a user by their username in the first column. """
    try:
        cell = sheet.find(username, in_column=1)
        return cell.row if cell else None
    except Exception: return None

def add_user(sheet, username, password, role):
    """ Adds a new user to the Volunteers sheet. """
    if find_user_row(sheet, username):
        return False # User already exists
    sheet.append_row([username, password, role])
    return True

# In backend_logic.py, REPLACE the existing update_user function with this one

def update_user(sheet, original_username, new_username, new_password, new_role):
    """ Updates a user's details, checking for duplicate usernames. """
    # Check if the new username already exists, but only if the username is being changed.
    if original_username != new_username and find_user_row(sheet, new_username):
        return "duplicate" # Return a specific string for a duplicate error

    row_num = find_user_row(sheet, original_username)
    if not row_num:
        return "not_found" # Return a string if the original user isn't found
    
    # If checks pass, update the cells
    sheet.update_cell(row_num, 1, new_username)
    sheet.update_cell(row_num, 2, new_password)
    sheet.update_cell(row_num, 3, new_role)
    return "success" # Return a success message

def delete_user(sheet, username):
    """ Deletes a user from the Volunteers sheet. """
    row_num = find_user_row(sheet, username)
    if not row_num: return False
    sheet.delete_rows(row_num)
    return True


# --- Command-Line Tool Functions (Preserved and Updated) ---
def add_student(sheet):
    """ Adds a new student via command line input. """
    print("\n--- Add New Student ---")
    app_id = input("Enter Student's unique Application ID: ").strip()
    if find_student_row(sheet, app_id):
        print(f"⚠️ Error: A student with Application ID '{app_id}' already exists.")
        return
    student_name = input("Enter Student's Full Name: ").strip()
    new_row_data = [
        app_id, student_name,
        'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', ''
    ]
    sheet.append_row(new_row_data)
    print(f"✅ Success: Student '{student_name}' ({app_id}) has been added.")

def search_and_update_student(sheet):
    """ Searches for a student and provides a menu to update their status. """
    print("\n--- Search & Update Student Status ---")
    search_term = input("Enter Student's Application ID or Full Name to search: ").strip()
    row_number = find_student_row(sheet, search_term)
    if not row_number:
        print(f"❌ Error: No student found with search term '{search_term}'.")
        return
    
    student_data = sheet.row_values(row_number)
    
    print("\n--- Current Student Status ---")
    print(f"  ID:   {student_data[0]}")
    print(f"  Name: {student_data[1]}")
    print("-" * 50)
    stages = ["Entry Gate", "Hostel/Mess", "Insurance", "LHC Docs", "Final DoAA"]
    for i, stage_name in enumerate(stages):
        status_col = 2 + (i * 3)
        by_col = 3 + (i * 3)
        ts_col = 4 + (i * 3)
        status = student_data[status_col] if len(student_data) > status_col else "N/A"
        updated_by = student_data[by_col] if len(student_data) > by_col and student_data[by_col] else ""
        timestamp = student_data[ts_col] if len(student_data) > ts_col and student_data[ts_col] else ""
        
        if updated_by:
            print(f"  {stage_name+':':<14} {status:<10} (by {updated_by} at {timestamp})")
        else:
            print(f"  {stage_name+':':<14} {status}")
    
    notes = student_data[17] if len(student_data) > 17 and student_data[17] else ""
    if notes:
        print(f"  {'Notes:':<14} {notes}")
    print("-" * 50)

    print("\nSelect the update point:")
    print("  1. Update Entry Gate Status")
    print("  2. Update Hostel/Mess Status")
    print("  3. Update Insurance Status")
    print("  4. Update LHC Docs Status")
    print("  5. Update Final DoAA Status")
    print("  6. Add/Update a Note")
    print("  0. Back to Main Menu")
    
    try: choice = int(input("Enter your choice: "));
    except ValueError: print("Invalid input."); return

    if choice == 0: return

    if choice == 5:
        entry_done = student_data[2] == 'Done'
        hostel_done = student_data[5] == 'Done'
        insurance_done = student_data[8] == 'Done'
        lhc_docs_done = student_data[11] == 'Done'
        if not (entry_done and hostel_done and insurance_done and lhc_docs_done):
            print("\n❌ ERROR: Cannot give Final DoAA approval.")
            return

    volunteer_name = input("Enter your name (volunteer): ").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if 1 <= choice <= 5:
        status_col = 2 + ((choice - 1) * 3)
        new_status = 'Done'
        if choice == 4: # LHC Docs
            lhc_choice = input("   Enter status (a: In Queue, b: Done): ").lower()
            if lhc_choice == 'a': new_status = 'In Queue'
            elif lhc_choice == 'b': new_status = 'Done'
            else: print("Invalid choice."); return
        
        cells_to_update = [
            gspread.Cell(row_number, status_col + 1, new_status),
            gspread.Cell(row_number, status_col + 2, volunteer_name),
            gspread.Cell(row_number, status_col + 3, timestamp)
        ]
        sheet.update_cells(cells_to_update)
        print("✅ Status updated successfully.")
    elif choice == 6:
        note = input("Enter note: ").strip()
        sheet.update_cell(row_number, 18, note)
        print("✅ Note updated successfully.")
    else:
        print("Invalid choice.")

def delete_student(sheet):
    """ Deletes a student's record from the sheet. """
    print("\n--- Delete Student Record ---")
    app_id = input("Enter Student's Application ID to DELETE: ").strip()
    row_number = find_student_row(sheet, app_id)
    
    if not row_number:
        print(f"❌ Error: No student found with Application ID '{app_id}'."); return
        
    student_name = sheet.cell(row_number, 2).value
    confirm = input(f"⚠️ Are you sure you want to permanently delete '{student_name}' ({app_id})? (yes/no): ").lower()
    
    if confirm == 'yes':
        sheet.delete_rows(row_number)
        print(f"✅ Success: Record for '{app_id}' has been deleted.")
    else:
        print("Deletion cancelled.")

def show_dashboard(sheet):
    """ Displays a live summary dashboard for the CLI. """
    print("\n--- Live Registration Dashboard ---")
    all_records = get_all_records_safely(sheet, STUDENT_HEADERS)
    if not all_records: 
        print("No student data found.")
        return

    total = len(all_records)
    completed = sum(1 for r in all_records if r.get('stage4_doaa_status') == 'Done')
    at_hostel = sum(1 for r in all_records if r.get('stage1_hostel_status') == 'Pending')
    in_lhc_queue = sum(1 for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue')

    print(f"  Total Students in System:  {total}")
    print(f"  Process Fully Completed:   {completed} / {total}")
    print("-" * 30)
    print(f"  Students at Hostel/Mess:   {at_hostel}")
    print(f"  Students in LHC Queue:     {in_lhc_queue}  <-- CURRENT BOTTLENECK")

def view_lhc_queue(sheet):
    """ Displays a list of students currently in the LHC queue for the CLI. """
    print("\n--- Students in LHC Verification Queue ---")
    all_records = get_all_records_safely(sheet, STUDENT_HEADERS)
    if not all_records: 
        print("No student data found.")
        return

    queue = [r for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue']
    if not queue: print("The LHC queue is currently empty."); return
    for i, student in enumerate(queue, 1):
        print(f"  {i}. {student.get('student_name')} (ID: {student.get('student_identifier')})")

def bulk_upload_students(sheet):
    """ Uploads students from a CSV file for the CLI. """
    print("\n--- Bulk Student Upload ---")
    filename = 'students.csv'
    print(f"Looking for '{filename}' with columns: application_id,student_name (no header).")
    try:
        with open(filename, 'r', newline='') as f:
            reader = csv.reader(f)
            new_students = []
            for row in reader:
                if len(row) == 2:
                    new_students.append([row[0], row[1], 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', ''])
            if new_students:
                sheet.append_rows(new_students, value_input_option='USER_ENTERED')
                print(f"✅ Success: {len(new_students)} students uploaded.")
            else: print("⚠️ No valid student data found in the file.")
    except FileNotFoundError: print(f"❌ Error: '{filename}' not found.")

def view_flagged_students(sheet):
    """ Identifies students who have been in a stage for too long for the CLI. """
    print(f"\n--- Flagged Students (Stuck for > {STUCK_THRESHOLD_MINUTES} mins) ---")
    all_records = get_all_records_safely(sheet, STUDENT_HEADERS)
    if not all_records: 
        print("No student data found.")
        return
    
    flagged_count = 0
    now = datetime.now()
    for student in all_records:
        if student.get('stage4_doaa_status') == 'Done': continue
        
        stage_names = ['entry', 'hostel', 'insurance', 'lhc_docs', 'doaa']
        timestamps = [student.get(f'stage{i}_{name}_ts') for i, name in enumerate(stage_names)]
        valid_timestamps = [ts for ts in timestamps if ts]
        
        if not valid_timestamps: continue
        
        last_update_str = max(valid_timestamps)
        try:
            last_update_time = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
            if now - last_update_time > timedelta(minutes=STUCK_THRESHOLD_MINUTES):
                print(f"  - {student.get('student_name')} (ID: {student.get('student_identifier')})")
                flagged_count += 1
        except (ValueError, TypeError): continue
    
    if flagged_count == 0: print("No students are currently flagged as stuck.")

def show_volunteer_faq():
    """ Displays a pre-written FAQ for the CLI. """
    print("\n--- Volunteer FAQ ---")
    faq_text = """
    Q1: What documents are required at LHC?
    A1: Original Class 10/12 mark sheets, IAT admit card, photo ID, fee receipt.

    Q2: What if a student hasn't paid for health insurance?
    A2: Direct them to the SBI branch on campus first.

    Q3: What if a student is missing a document?
    A3: Use the 'Add Note' function to record the missing document and escalate.
    """
    print(faq_text)

def generate_end_of_day_report(sheet):
    """ Generates a summary text file of the day's activities for the CLI. """
    print("\n--- Generating End-of-Day Report ---")
    all_records = get_all_records_safely(sheet, STUDENT_HEADERS)
    if not all_records: 
        print("No student data found to generate a report.")
        return

    report_name = f"report_{datetime.now().strftime('%Y-%m-%d')}.txt"
    with open(report_name, 'w') as f:
        f.write(f"UDAAN Campus Arrival - End of Day Report: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write("="*50 + "\n\n")
        total = len(all_records)
        completed = sum(1 for r in all_records if r.get('stage4_doaa_status') == 'Done')
        f.write(f"Overall Summary:\n")
        f.write(f"  - Total Students in System: {total}\n")
        f.write(f"  - Students Fully Registered: {completed}\n\n")
        flagged_with_notes = [r for r in all_records if r.get('Notes')]
        if flagged_with_notes:
            f.write("Students with Special Notes:\n")
            for r in flagged_with_notes:
                f.write(f"  - {r.get('student_name')} (ID: {r.get('student_identifier')}): {r.get('Notes')}\n")
        
    print(f"✅ Success: Report saved as '{report_name}'.")

# --- Main Application Loop for Command-Line Tool ---
def main():
    """ The main function that runs the command-line interface menu. """
    spreadsheet = connect_to_spreadsheet(SPREADSHEET_NAME)
    if not spreadsheet: 
        time.sleep(5)
        return

    try:
        student_sheet = spreadsheet.worksheet("Students")
    except gspread.WorksheetNotFound:
        print("❌ CRITICAL ERROR: 'Students' worksheet not found.")
        time.sleep(5)
        return

    if not verify_headers(student_sheet, STUDENT_HEADERS):
        print("\nProgram cannot continue due to header mismatch. Please fix the sheet and restart.")
        time.sleep(10)
        return

    while True:
        os.system('cls' if os.name == 'nt' else 'clear') 
        
        print("\n===== UDAAN: Volunteer CLI System =====")
        print("\n--- Core Actions ---")
        print("  1. Add Student              2. Search & Update        3. Delete Student")
        print("\n--- Reporting & Intelligence ---")
        print("  4. Show Live Dashboard      5. View LHC Queue           6. View Flagged Students")
        print("\n--- Support & Admin ---")
        print("  7. Bulk Upload from CSV     8. Volunteer FAQs           9. Generate End-of-Day Report")
        print("\n  0. Exit")
        print("="*55)
        
        try: choice = int(input("Enter your choice: "))
        except ValueError: print("Invalid input."); time.sleep(2); continue

        if choice == 1: add_student(student_sheet)
        elif choice == 2: search_and_update_student(student_sheet)
        elif choice == 3: delete_student(student_sheet)
        elif choice == 4: show_dashboard(student_sheet)
        elif choice == 5: view_lhc_queue(student_sheet)
        elif choice == 6: view_flagged_students(student_sheet)
        elif choice == 7: bulk_upload_students(student_sheet)
        elif choice == 8: show_volunteer_faq()
        elif choice == 9: generate_end_of_day_report(student_sheet)
        elif choice == 0: print("Exiting program. Goodbye!"); break
        else: print("Invalid choice.")
        
        input("\nPress Enter to return to the main menu...")

if __name__ == "__main__":
    main()
