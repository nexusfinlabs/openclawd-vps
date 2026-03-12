import sys
import os
from sqlalchemy import create_engine, text
from db import DATABASE_URL
from llm import generateWithFallback

def main():
    if len(sys.argv) < 5:
        print("Usage: python email_drafter.py <company_name> <target_email> <target_name> <context_tier> [custom_context]")
        sys.exit(1)

    company = sys.argv[1]
    email = sys.argv[2]
    name = sys.argv[3]
    tier = sys.argv[4] # "high" or "medium"
    context = sys.argv[5] if len(sys.argv) > 5 else ""

    style_guide_path = os.path.join(os.path.dirname(__file__), "email_style_guide.md")
    style_guide = ""
    if os.path.exists(style_guide_path):
        with open(style_guide_path, "r") as f:
            style_guide = f.read()

    system_prompt = f"""You are an expert executive assistant drafting an email for the user (Alberto Lobo).
Your strict goal is to accurately mimic the user's professional tone, greeting style, paragraph structure, and sign-offs based on the examples in the style guide.

### STYLE GUIDE
{style_guide}

### INSTRUCTIONS
1. Analyze the context/objective provided by the user.
2. Select the most appropriate 'Estilo' from the Style Guide above that matches this context (e.g., M&A vs Business Development).
3. Adapt the chosen template to the specific target company and person. Do not just copy-paste; intelligently fill in the details.
4. The FIRST LINE of your response MUST BE the Subject line, prefixed with "Subject: ".
5. Write the body of the email starting on the next line.
6. Write ONLY the final generated text (subject + body). Do not output internal thoughts, confirmations, or markdown code blocks.
"""

    if tier == "high":
        user_prompt = f"Draft a highly personalized B2B outreach email to {name} at {company} ({email}). The context/objective is: '{context}'. Use the style guide to select the right template and maintain the perfect tone."
    else:
        user_prompt = f"Draft a direct and professional B2B outreach email to the team at {company} ({email}). We lack the exact decision-maker name, so address it to the relevant team (e.g. 'Dear [Company] Team,' or similar). The context/objective is: '{context}'. Use the style guide to select the right template and maintain the perfect tone."

    try:
        draft_text = generateWithFallback(system_prompt, user_prompt)
        
        # Parse Subject and Body
        lines = draft_text.strip().split("\n")
        subject = "Propuesta B2B"
        body = draft_text
        if lines[0].lower().startswith("subject:"):
            subject = lines[0][8:].strip()
            body = "\n".join(lines[1:]).strip()
        elif lines[0].lower().startswith("asunto:"):
            subject = lines[0][7:].strip()
            body = "\n".join(lines[1:]).strip()

        # Save to PostgreSQL
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            query = text("""
                INSERT INTO email_drafts (target_email, target_name, company_name, context_tier, original_prompt, subject, body, status)
                VALUES (:e, :n, :c, :t, :p, :s, :b, 'draft')
                RETURNING id;
            """)
            result = conn.execute(query, {"e": email, "n": name, "c": company, "t": tier, "p": user_prompt, "s": subject, "b": body})
            draft_id = result.scalar()
            conn.commit()

        print(f"DRAFT SAVED SUCCESSFULLY!")
        print(f"ID: {draft_id}")
        print(f"Company: {company}")
        print("-" * 20)
        print(f"Subject: {subject}")
        print(f"\n{body}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
