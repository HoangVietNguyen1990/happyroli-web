import hashlib
import os
import time
import asyncio
import edge_tts

text = 'Xong chị ơi! Joy đổi ca thứ Hai của Elizabeth qua cho Jane rồi nghen!'
cache_dir = '/opt/project-rostering/static/audio/cache'
os.makedirs(cache_dir, exist_ok=True)
h = hashlib.md5(text.encode('utf-8')).hexdigest()
out_path = os.path.join(cache_dir, f'{h}.mp3')

t0 = time.time()
asyncio.run(edge_tts.Communicate(text, 'vi-VN-HoaiMyNeural', rate='+16%', pitch='+24Hz').save(out_path))
dt = time.time() - t0
print(f'Edge-TTS generated in {dt:.2f}s, size: {os.path.getsize(out_path)} bytes')
