import requests

test_msgs = [
    "Số điện thoại của Ainsley là gì",
    "Shaelyn có email là gì",
    "Địa chỉ của Shaelyn ở đâu em",
    "Ai là thợ làm bánh",
    "Jude có bận gì không",
    "Thứ 4 Jude có làm được không",
    "Thứ 2 ai đi làm",
    "Tuần này ai làm nhiều giờ nhất",
    "Sắp tới có ngày lễ gì không",
    "em có thể cho ai mì thêm một ca nữa vào ngày thứ hai 7 giờ tới 12:00 trưa không",
]

for msg in test_msgs:
    r = requests.post("http://127.0.0.1:8080/api/assistant/chat", json={"message": msg, "session_id": "test_api_sess"})
    print(f"Q: '{msg}'\n -> A: {r.json().get('reply')}\n")
