def make_intelligent_clarification(user_message, found_emps, day):
    if found_emps:
        emp = found_emps[0]
        return f"Dạ chị Nhi ơi, Joy nghe chị nhắc tới bạn {emp} rồi nè, mà Joy chưa rõ chị muốn làm gì á (cho {emp} nghỉ ca, đổi ca, hay sửa mấy giờ)? Chị dặn rõ lại xíu Joy làm liền nghen! 🥖"
    elif day:
        return f"Dạ chị Nhi ơi, Joy nghe chị nhắc tới ngày {day} rồi nè, mà chưa rõ chị muốn chỉnh ca của bạn nào á? Chị dặn Joy tên bạn với nghen! 🥖"
    else:
        return "Dạ chị Nhi ơi, câu này Joy chưa hiểu rõ ý chị lắm á! Chị nói lại giúp Joy với nghen (ví dụ: 'Cho Jane nghỉ thứ Hai', 'Đổi ca của Robert qua cho Viet', hay 'Số điện thoại của Ainsley') để Joy làm cho chuẩn nè! 🥖✨"

print(make_intelligent_clarification('bạn Robert gì đó', ['Robert'], None))
print(make_intelligent_clarification('thứ tư này làm sao', [], 'thứ Tư'))
print(make_intelligent_clarification('blabla alo 123', [], None))
