import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time
import os
import csv

# --- Configuration ---
JSON_KEYFILE = 'creds.json' 
SHEET_NAME = 'CampusArrival2025'

# --- Advanced Feature Configuration ---
STUCK_THRESHOLD_MINUTES = 45

# --- UPDATED: Headers list now includes a new 'Entry' stage ---
EXPECTED_HEADERS = [
    'student_identifier', 'student_name', 
    'stage0_entry_status', 'stage0_entry_by', 'stage0_entry_ts',
    'stage1_hostel_status', 'stage1_hostel_by', 'stage1_hostel_ts',
    'stage2_insurance_status', 'stage2_insurance_by', 'stage2_insurance_ts',
    'stage3_lhc_docs_status', 'stage3_lhc_docs_by', 'stage3_lhc_docs_ts',
    'stage4_doaa_status', 'stage4_doaa_by', 'stage4_doaa_ts',
    'Notes'
]

# --- Connection to Google Sheets ---
def connect_to_sheet():
    """ Connects to the Google Sheet using service account credentials. """
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        print("✅ Successfully connected to Google Sheet.")
        return sheet
    except Exception as e:
        print(f"❌ An error occurred during connection: {e}")
        return None

# --- Header Verification Tool ---
def verify_headers(sheet):
    """ Checks if the headers in the Google Sheet match the expected headers. """
    try:
        actual_headers = sheet.row_values(1)
        if set(EXPECTED_HEADERS) == set(actual_headers):
            print("✅ Headers verified successfully.")
            return True
        else:
            print("❌ CRITICAL ERROR: Google Sheet headers do not match.")
            # Provide a detailed error for the developer in the console
            expected_set = set(EXPECTED_HEADERS)
            actual_set = set(actual_headers)
            missing = expected_set - actual_set
            extra = actual_set - expected_set
            if missing:
                print(f"   Missing headers in Sheet: {sorted(list(missing))}")
            if extra:
                print(f"   Unexpected headers in Sheet: {sorted(list(extra))}")
            return False
    except Exception:
        print("❌ Could not verify headers. The sheet might be empty.")
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
def get_all_records_safely(sheet):
    """ A robust function to fetch all records for the web app. """
    try:
        if sheet.row_count > 1:
            return sheet.get_all_records(expected_headers=EXPECTED_HEADERS)
        else:
            return []
    except Exception:
        return []

def add_student_from_webapp(sheet, app_id, student_name):
    """ Adds a new student record to the sheet. Called by the web app. """
    if find_student_row(sheet, app_id):
        print(f"⚠️ Attempted to add duplicate student from web app: {app_id}")
        return
    # UPDATED: New row now has 18 columns for the new stage
    new_row_data = [
        app_id, student_name,
        'Pending', '', '',  # Entry Gate
        'Pending', '', '',  # Hostel
        'Pending', '', '',  # Insurance
        'Pending', '', '',  # LHC Docs
        'Pending', '', '',  # DOAA
        ''                 # Notes
    ]
    sheet.append_row(new_row_data)
    print(f"✅ New student '{student_name}' ({app_id}) added via web app.")


# --- Command-Line Tool Functions (Preserved and Updated) ---
def add_student(sheet):
    """ Adds a new student via command line input. """
    print("\n--- Add New Student ---")
    app_id = input("Enter Student's unique Application ID: ").strip()
    if find_student_row(sheet, app_id):
        print(f"⚠️ Error: A student with Application ID '{app_id}' already exists.")
        return
    student_name = input("Enter Student's Full Name: ").strip()
    # UPDATED: New row now has 18 columns
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
    # UPDATED: Stages list now includes Entry Gate
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

    # UPDATED: DoAA check now includes the new Entry Gate stage
    if choice == 5:
        entry_done = student_data[2] == 'Done'
        hostel_done = student_data[5] == 'Done'
        insurance_done = student_data[8] == 'Done'
        lhc_docs_done = student_data[11] == 'Done'
        if not (entry_done and hostel_done and insurance_done and lhc_docs_done):
            print("\n❌ ERROR: Cannot give Final DoAA approval.")
            print("   All previous stages must be 'Done'.")
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
    """ Displays a live summary dashboard. """
    print("\n--- Live Registration Dashboard ---")
    all_records = get_all_records_safely(sheet)
    if not all_records: 
        print("No student data found to generate a dashboard.")
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
    """ Displays a list of students currently in the LHC queue. """
    print("\n--- Students in LHC Verification Queue ---")
    all_records = get_all_records_safely(sheet)
    if not all_records: 
        print("No student data found.")
        return

    queue = [r for r in all_records if r.get('stage3_lhc_docs_status') == 'In Queue']
    if not queue: print("The LHC queue is currently empty. Great work!"); return
    for i, student in enumerate(queue, 1):
        print(f"  {i}. {student.get('student_name')} (ID: {student.get('student_identifier')})")

def bulk_upload_students(sheet):
    """ Uploads students from a CSV file with the new 18-column structure. """
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
    """ Identifies students who have been in a stage for too long. """
    print(f"\n--- Flagged Students (Stuck for > {STUCK_THRESHOLD_MINUTES} mins) ---")
    all_records = get_all_records_safely(sheet)
    if not all_records: 
        print("No student data found.")
        return
    
    flagged_count = 0
    now = datetime.now()
    for student in all_records:
        if student.get('stage4_doaa_status') == 'Done': continue
        
        # UPDATED: Logic now correctly checks all 5 stages for timestamps
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
    """ Displays a pre-written FAQ for volunteers. """
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
    """ Generates a summary text file of the day's activities. """
    print("\n--- Generating End-of-Day Report ---")
    all_records = get_all_records_safely(sheet)
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

# --- Main Application Loop ---
def main():
    """ The main function that runs the command-line interface menu. """
    sheet = connect_to_sheet()
    if not sheet: 
        time.sleep(5)
        return

    if not verify_headers(sheet):
        print("\nProgram cannot continue due to header mismatch. Please fix the sheet and restart.")
        time.sleep(10)
        return

    while True:
        os.system('cls' if os.name == 'nt' else 'clear') 
        
        print("\n===== UDAAN: Volunteer Coordination System (v3.4) =====")
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

        if choice == 1: add_student(sheet)
        elif choice == 2: search_and_update_student(sheet)
        elif choice == 3: delete_student(sheet)
        elif choice == 4: show_dashboard(sheet)
        elif choice == 5: view_lhc_queue(sheet)
        elif choice == 6: view_flagged_students(sheet)
        elif choice == 7: bulk_upload_students(sheet)
        elif choice == 8: show_volunteer_faq()
        elif choice == 9: generate_end_of_day_report(sheet)
        elif choice == 0: print("Exiting program. Goodbye!"); break
        else: print("Invalid choice.")
        
        input("\nPress Enter to return to the main menu...")

if __name__ == "__main__":
    main()
