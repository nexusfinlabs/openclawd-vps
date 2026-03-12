import os
from openai import OpenAI
import time

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def generateWithFallback(system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
    """
    Tries OpenRouter first. If it fails or returns empty/error, falls back to OpenAI directly.
    """
    for attempt in range(max_retries):
        try:
            if OPENROUTER_API_KEY:
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=OPENROUTER_API_KEY,
                )
                try:
                    response = client.chat.completions.create(
                        model="openai/gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        timeout=30.0
                    )
                    content = response.choices[0].message.content
                    if content:
                        return content
                except Exception as e:
                    print(f"OpenRouter attempt {attempt+1} failed: {e}")
                    pass # Fallthrough to fallback

            if OPENAI_API_KEY:
                print(f"Falling back to direct OpenAI API logic (attempt {attempt+1})")
                client = OpenAI(
                    api_key=OPENAI_API_KEY,
                )
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    timeout=30.0
                )
                content = response.choices[0].message.content
                if content:
                    return content
                
            time.sleep(1)
        except Exception as e:
            print(f"Fallback attempt {attempt+1} failed: {e}")
            time.sleep(2)

    raise Exception("All LLM attempts failed.")
