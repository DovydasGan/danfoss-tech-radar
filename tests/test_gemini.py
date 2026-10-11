import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_KEY"),
    http_options=types.HttpOptions(
        timeout=60_000,                                   # give up after 60 seconds
        retry_options=types.HttpRetryOptions(attempts=1)  # no hidden retries
    ),
)

print("Flash models available to your key:")
for m in client.models.list():
    if "flash" in m.name:
        print("  ", m.name)

for model in ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]:
    try:
        r = client.models.generate_content(model=model, contents="Reply with just: OK")
        print(f"{model} -> {r.text.strip()}")
    except Exception as e:
        print(f"{model} -> ERROR: {str(e)[:200]}")