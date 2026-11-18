import sqlite3

conn = sqlite3.connect('/opt/project-rostering/database/happyrolly.db')
c = conn.cursor()
c.execute('SELECT id, speaker, message_text, action_taken_json, created_at FROM assistant_conversations ORDER BY id DESC LIMIT 15')
for row in reversed(c.fetchall()):
    print(f"[{row[0]}] {row[1]} ({row[4]}): {row[2]}")
    print(f"     Action: {row[3]}")
