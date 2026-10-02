import asyncio
import edge_tts

async def test():
    text = "నమస్తే అర్జున్! మీ EMI చెల్లింపు తేదీ సెప్టెంబర్ 30."

    communicate = edge_tts.Communicate(
        text,
        "te-IN-ShrutiNeural"
    )

    await communicate.save("telugu_test.mp3")

asyncio.run(test())