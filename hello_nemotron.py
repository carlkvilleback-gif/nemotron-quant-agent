import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")  # Windows console chokes on characters like "≥"
load_dotenv()  # reads NEBIUS_API_KEY from .env

# Token Factory speaks the OpenAI API, so the standard client works with a different base_url
client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)

response = client.chat.completions.create(
    model="nvidia/nemotron-3-super-120b-a12b",
    messages=[{"role": "user", "content": "Give me one testable trading hypothesis about gold, in one sentence."}],
)

print(response.choices[0].message.content)
