import asyncio
import os
import edge_tts

async def gen():
    os.makedirs('/opt/project-rostering/static/audio/cache', exist_ok=True)
    print("Generating da.mp3...")
    await edge_tts.Communicate('Dạ!', 'vi-VN-HoaiMyNeural', rate='+18%', pitch='+26Hz').save('/opt/project-rostering/static/audio/da.mp3')
    print("Generating bye.mp3...")
    await edge_tts.Communicate('Dạ Joy tắt đây, chào chị Nhi nghen!', 'vi-VN-HoaiMyNeural', rate='+16%', pitch='+24Hz').save('/opt/project-rostering/static/audio/bye.mp3')
    print("Done! Files generated successfully.")

if __name__ == '__main__':
    asyncio.run(gen())
