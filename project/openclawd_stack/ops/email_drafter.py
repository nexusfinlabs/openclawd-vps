import os
import json
import logging
from app.llm import generateWithFallback

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def draft_email_for_company(company_name, decision_maker_name, context, persona="M&A_Financial"):
    """
    Uses the Multi-LLM strategy to draft a highly personalized outreach email based on the persona.
    """
    # Load style guide
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        style_path = os.path.join(current_dir, "email_style_guide.json")
        with open(style_path, 'r') as f:
            styles = json.load(f)
            
        persona_data = styles.get("personas", {}).get(persona)
        if not persona_data:
            logger.warning(f"Persona '{persona}' not found. Falling back to M&A_Financial.")
            persona_data = styles["personas"]["M&A_Financial"]
            
        tone = persona_data["tone"]
        signature = persona_data["signature"]
        examples = "\n\n---\n\n".join(persona_data["examples"])
        
    except Exception as e:
        logger.error(f"Failed to load style guide: {e}")
        return None
    
    system_prompt = f"""
    Eres el asistente ejecutivo experto en M&A y Ventas de Alberto.
    Tu objetivo es redactar un borrador de correo electrónico persuasivo y directo para dueños de empresas o tomadores de decisión.
    
    REGLAS ESTRICTAS DE TONO:
    - Sigue estrictamente esta indicación de tono: {tone}
    - Firma siempre exactamente como:
    {signature}
    
    A continuación se muestran ejemplos del estilo de escritura que debes imitar escrupulosamente:
    ---
    {examples}
    ---
    """
    
    user_prompt = f"""
    Escribe un correo para {decision_maker_name}, líder en {company_name}.
    Contexto sobre la empresa o persona: {context}.
    Motivo del correo: Iniciar una conversación de valor según el tono y contexto establecido.
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    logger.info(f"Drafting email for {company_name} ({decision_maker_name}) using persona {persona}...")
    
    try:
        response = generateWithFallback(
            messages=messages,
            strategy="smart" # Opus primero, luego OpenAI
        )
        return response
    except Exception as e:
        logger.error(f"Failed to draft email: {e}")
        return None

if __name__ == "__main__":
    # Test script locally
    draft = draft_email_for_company(
        company_name="Acme Tech",
        decision_maker_name="Juan Pérez",
        context="Hacen software de pagos y acaban de abrir mercado en España.",
        persona="Sales_Marketing"
    )
    print("\n--- DRAFT GENERADO ---")
    print(draft)
