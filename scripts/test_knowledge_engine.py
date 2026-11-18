import sqlite3
import json
import sys
sys.path.append('happyrolly_web')
from core_engine import VIC_PUBLIC_HOLIDAYS, VIC_SCHOOL_HOLIDAYS

conn = sqlite3.connect('vps_happyrolly.db')
c = conn.cursor()

c.execute('SELECT payload_json FROM system_store WHERE doc_key=?', ('user_profiles',))
profs = json.loads(c.fetchone()[0])

c.execute('SELECT records_json FROM datasets WHERE collection_name=?', ('unavailability',))
unav = json.loads(c.fetchone()[0])

c.execute('SELECT records_json FROM datasets WHERE collection_name=?', ('employees',))
emps = json.loads(c.fetchone()[0])

# Helper to find profile for any employee name
def find_profile(name):
    low = name.lower()
    for u, data in profs.items():
        emp_n = (data.get('employee_name') or '').lower()
        if low == u or low in u or low == emp_n or low in emp_n:
            return data
    return None

p_ainsley = find_profile('Ainsley')
print("Found Ainsley:", p_ainsley.get('employee_name'), p_ainsley.get('profile', {}).get('mobile'), p_ainsley.get('profile', {}).get('email'))

p_shaelyn = find_profile('Shaelyn')
print("Found Shaelyn:", p_shaelyn.get('employee_name'), p_shaelyn.get('profile', {}).get('mobile'), p_shaelyn.get('profile', {}).get('email'))

# Unavailability for Violet
violet_u = [r for r in unav if 'violet' in str(r.get('Employee')).lower()]
print("Violet unav:", len(violet_u), violet_u[:2])

# Public holidays
print("Upcoming public holidays:", list(VIC_PUBLIC_HOLIDAYS.items())[:3])
