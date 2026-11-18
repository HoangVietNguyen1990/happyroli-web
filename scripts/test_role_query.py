import sys, os
sys.path.append('happyrolly_web')
from database.db_manager import HappyRollyDB
from scripts.test_omni_queries import load_all_employee_directory

db = HappyRollyDB()
directory = load_all_employee_directory(db)

def query_employee_role(query_type: str, emp_name: str = '') -> str:
    low = query_type.lower()
    if emp_name:
        emp_key = emp_name.lower().strip()
        matched = None
        for k, v in directory.items():
            if k == emp_key or emp_key in k or k in emp_key:
                matched = v
                break
        if not matched:
            return f"Chị Nhi ơi, Joy hổng tìm thấy hồ sơ của bạn '{emp_name}' trong tiệm á!"
        name = matched['name']
        pos = matched['position']
        team = matched['team']
        status = matched['status']
        return f"Dạ bạn {name} giữ vị trí {pos} ({team}, hình thức {status}) nghen chị Nhi! 🥖"
        
    if any(k in low for k in ['thợ bánh', 'thợ làm bánh', 'baker']) and not 'phụ' in low:
        bakers = [v['name'] for v in directory.values() if 'baker' in v['position'].lower() and 'assitant' not in v['position'].lower() and 'assistant' not in v['position'].lower()]
        assts = [v['name'] for v in directory.values() if 'assitant' in v['position'].lower() or 'assistant' in v['position'].lower()]
        b_str = ", anh ".join(bakers)
        a_str = ", ".join(assts)
        return f"Dạ tiệm mình có anh {b_str} là thợ làm bánh chính, còn bạn {a_str} là thợ phụ bánh nè chị Nhi! 🥐"

    if any(k in low for k in ['phụ bánh', 'baker assistant']):
        assts = [v['name'] for v in directory.values() if 'assitant' in v['position'].lower() or 'assistant' in v['position'].lower()]
        return f"Dạ ở tiệm mình người làm phụ tá thợ bánh là bạn {', '.join(assts)} nghen chị Nhi! 🥐"

    return "Dạ Joy nghe nè chị."

print(query_employee_role('Ai là thợ làm bánh?'))
print(query_employee_role('Ai là phụ bánh?'))
print(query_employee_role('Aroha làm vị trí gì?', 'Aroha'))
print(query_employee_role('Robert làm vị trí gì?', 'Robert'))
