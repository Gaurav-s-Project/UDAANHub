import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time
import os
import csv
from collections import Counter

# --- Configuration ---
JSON_KEYFILE = 'creds.json' 
SPREADSHEET_NAME = 'CampusArrival2025' 

# --- Headers Configuration ---
STUDENT_HEADERS = [
    'student_identifier', 'student_name', 
    'stage0_entry_status', 'stage0_entry_by', 'stage0_entry_ts',
    'stage1_hostel_status', 'stage1_hostel_by', 'stage1_hostel_ts',
    'stage2_insurance_status', 'stage2_insurance_by', 'stage2_insurance_ts',
    'stage3_lhc_docs_status', 'stage3_lhc_docs_by', 'stage3_lhc_docs_ts',
    'stage4_doaa_status', 'stage4_doaa_by', 'stage4_doaa_ts',
    'Notes', 'flagged','verified_10th_marksheet', 'verified_12th_marksheet', 'verified_caste_certificate', 
    'verified_iat_admit_card', 'verified_transfer_certificate','verified_fee_receipt'
]
VOLUNTEER_HEADERS = ['username', 'password', 'role']
FAQ_HEADERS = ['question', 'answer']
ANNOUNCEMENT_HEADERS = ['message']
# ADD this new header list
DOC_RESPONSE_HEADERS = ['Timestamp', 'Application No', 'Documents Available']

# --- Connection Functions ---
def connect_to_spreadsheet(spreadsheet_name):
    """ Connects to a Google Spreadsheet file and returns the spreadsheet object. """
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
        client = gspread.authorize(creds)
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
            expected_set = set(headers)
            actual_set = set(actual_headers)
            missing = expected_set - actual_set
            extra = actual_set - expected_set
            if missing:
                print(f"   Missing headers in Sheet: {sorted(list(missing))}")
            if extra:
                print(f"   Unexpected headers in Sheet: {sorted(list(extra))}")
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
        'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', '', 'no','no', 'no', 'no', 'no', 'no','no'
    ]
    sheet.append_row(new_row_data)
    print(f"✅ New student '{student_name}' ({app_id}) added via web app.")

# ADD this new function to backend_logic.py
def update_student_flag(sheet, student_id, flag_status):
    """ Updates the 'flagged' status for a student. """
    row_num = find_student_row(sheet, student_id)
    if not row_num: return False
    # Column S is the 19th column
    sheet.update_cell(row_num, 19, flag_status)
    return True

# ADD these new functions to backend_logic.py

def get_document_responses(sheet, app_id):
    """ Fetches a student's self-reported document checklist from the form responses. """
    try:
        all_responses = get_all_records_safely(sheet, DOC_RESPONSE_HEADERS)
        for response in all_responses:
            if str(response.get('Application No')) == str(app_id):
                # The responses are in a single comma-separated string
                return response.get('Documents Available', '').split(', ')
        return [] # Return empty list if not found
    except Exception:
        return []

def update_verified_documents(sheet, student_id, verified_docs):
    """ Updates the verified document status in the main Students sheet. """
    row_num = find_student_row(sheet, student_id)
    if not row_num: return False

    # Dynamically update based on the docs provided
    doc_map = {
        '10th Marksheet': 20, '12th Marksheet': 21, 'Caste Certificate': 22,
        'IAT Admit Card': 23, 'Transfer Certificate': 24, 'Fee Receipt': 25
    }

    for doc_name, status in verified_docs.items():
        if doc_name in doc_map:
            sheet.update_cell(row_num, doc_map[doc_name], status)
    return True

# --- User Management Functions ---
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

def update_user(sheet, original_username, new_username, new_password, new_role):
    """ Updates a user's details, checking for duplicate usernames. """
    if original_username != new_username and find_user_row(sheet, new_username):
        return "duplicate"
    row_num = find_user_row(sheet, original_username)
    if not row_num: return "not_found"
    sheet.update_cell(row_num, 1, new_username)
    sheet.update_cell(row_num, 2, new_password)
    sheet.update_cell(row_num, 3, new_role)
    return "success"

def delete_user(sheet, username):
    """ Deletes a user from the Volunteers sheet. """
    row_num = find_user_row(sheet, username)
    if not row_num: return False
    sheet.delete_rows(row_num)
    return True

# --- FAQ Management Functions ---
def get_all_faqs(sheet):
    """ Fetches all FAQs from the FAQ sheet. """
    return get_all_records_safely(sheet, FAQ_HEADERS)

def add_faq(sheet, question, answer):
    """ Adds a new FAQ to the sheet. """
    sheet.append_row([question, answer])
    return True

def delete_faq(sheet, row_id):
    """ Deletes an FAQ by its row number. """
    try:
        sheet.delete_rows(int(row_id))
        return True
    except (ValueError, gspread.exceptions.APIError):
        return False

# --- Leaderboard Function ---
def get_volunteer_leaderboard(sheet):
    """ Calculates the number of students processed by each volunteer. """
    all_students = get_all_records_safely(sheet, STUDENT_HEADERS)
    volunteer_updates = []
    
    for student in all_students:
        for i in range(5):
            volunteer = student.get(f'stage{i}_{"entry" if i==0 else "hostel" if i==1 else "insurance" if i==2 else "lhc_docs" if i==3 else "doaa"}_by')
            if volunteer:
                volunteer_updates.append(volunteer)
                
    leaderboard = Counter(volunteer_updates).most_common()
    return leaderboard

# --- Announcement Functions ---
def get_announcement(sheet):
    """ Gets the current announcement message from cell A2. """
    try:
        if sheet.row_count >= 2:
            return sheet.cell(2, 1).value
        return None
    except Exception:
        return None

def update_announcement(sheet, message):
    """ Updates or clears the announcement message in cell A2. """
    try:
        sheet.update_cell(2, 1, message)
        return True
    except Exception:
        return False

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
        'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', '', 'no'
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
                    new_students.append([row[0], row[1], 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', 'Pending', '', '', '', 'no'])
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

def show_volunteer_faq(faq_sheet):
    """ Displays a pre-written FAQ for the CLI. """
    print("\n--- Volunteer FAQ ---")
    faqs = get_all_faqs(faq_sheet)
    if not faqs:
        print("No FAQs found.")
        return
    for i, faq in enumerate(faqs, 1):
        print(f"\nQ{i}: {faq['question']}")
        print(f"A{i}: {faq['answer']}")

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
        faq_sheet = spreadsheet.worksheet("FAQ")
    except gspread.WorksheetNotFound as e:
        print(f"❌ CRITICAL ERROR: A required worksheet was not found: {e}")
        time.sleep(5)
        return

    if not verify_headers(student_sheet, STUDENT_HEADERS) or not verify_headers(faq_sheet, FAQ_HEADERS):
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
        elif choice == 8: show_volunteer_faq(faq_sheet)
        elif choice == 9: generate_end_of_day_report(student_sheet)
        elif choice == 0: print("Exiting program. Goodbye!"); break
        else: print("Invalid choice.")
        
        input("\nPress Enter to return to the main menu...")

if __name__ == "__main__":
    main()
