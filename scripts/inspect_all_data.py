import sqlite3
import json

conn = sqlite3.connect('vps_happyrolly.db')
c = conn.cursor()
c.execute('SELECT payload_json FROM system_store WHERE doc_key=?', ('user_profiles',))
row = c.fetchone()
if row:
    profs = json.loads(row[0])
    print(f"Total user profiles: {len(profs)}")
    for u, p in profs.items():
        prof = p.get('profile', {})
        print(f"User: {u} | Emp: {p.get('employee_name')} | Mobile: {prof.get('mobile') or prof.get('phone')} | Email: {prof.get('email')} | Role: {p.get('role')} | DOB: {prof.get('dob')}")

c.execute('SELECT records_json FROM datasets WHERE collection_name=?', ('employees',))
row = c.fetchone()
if row:
    emps = json.loads(row[0])
    print(f"\nTotal employees in dataset: {len(emps)}")
    for e in emps:
        print(f"Name: {e.get('NAME')} | Team: {e.get('Team')} | Pos: {e.get('position')} | Status: {e.get('status')} | Commencing: {e.get('Commencing Date')}")

c.execute('SELECT records_json FROM datasets WHERE collection_name=?', ('unavailability',))
row = c.fetchone()
if row:
    unav = json.loads(row[0])
    print(f"\nTotal unavailability records: {len(unav)}")
    # Print sample by employee
    emp_unav = {}
    for r in unav:
        emp = r.get('Employee')
        emp_unav.setdefault(emp, []).append(f"{r.get('Day')}: {r.get('Time Window')}")
    for emp, windows in list(emp_unav.items())[:6]:
        print(f"Emp: {emp} -> {windows[:2]}")
