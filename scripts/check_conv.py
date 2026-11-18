import sqlite3

conn = sqlite3.connect('/opt/project-rostering/database/happyrolly.db')
c = conn.cursor()
rows = c.execute('SELECT id, session_id, speaker, message_text, action_taken_json, created_at FROM assistant_conversations ORDER BY id DESC LIMIT 30').fetchall()
for r in reversed(rows):
    print(f"[{r[0]}] {r[2]} ({r[5]}): {r[3]} | actions: {r[4]}")
