import os
import json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def generate_document(data_json_path, template_name="contract.html", output_filename=None):
    """
    Generates a high-quality PDF document parsing the specified Jinja2 template with the given JSON payload.
    Uses WeasyPrint for pixel-perfect HTML/CSS rendering.
    """
    # Load context data
    with open(data_json_path, 'r') as f:
        data = json.load(f)
        
    # Inject generated metadata
    if not output_filename:
        output_filename = f"DOC_{data.get('client_name', 'Client').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
    if 'date' not in data:
        data['date'] = datetime.now().strftime("%B %d, %Y")
        
    if 'ref_code' not in data:
        data['ref_code'] = f"REF-{datetime.now().strftime('%Y%m%d')}-{os.urandom(2).hex().upper()}"

    # Setup Jinja Environment
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template(template_name)
    
    # Render HTML
    print("Generating HTML template...")
    html_out = template.render(**data)
    
    # Generate PDF via WeasyPrint
    output_path = os.path.join(os.path.dirname(__file__), "output_docs")
    os.makedirs(output_path, exist_ok=True)
    final_pdf_path = os.path.join(output_path, output_filename)
    
    print(f"Rendering PDF (Arial 14pt, Uppercase Titles) -> {final_pdf_path}...")
    HTML(string=html_out, base_url=templates_dir).write_pdf(final_pdf_path)
    
    print(f"✓ Document Generated Successfully: {final_pdf_path}")
    return final_pdf_path

if __name__ == "__main__":
    # Test Payload
    test_payload = {
        "title": "Statement of Work (SOW)",
        "doc_type": "Project Charter & Agreement",
        "client_name": "ACME Corporation",
        "jurisdiction": "Madrid, Spain",
        "project_name": "OpenClaw AI Integration",
        "project_purpose": "Deploy a specialized LLM agent framework with WhatsApp integration for document generation",
        "scope_in": [
            {"title": "WhatsApp NLP Parsing", "desc": "Setup the webhook and extraction logic for unstructured messages."},
            {"title": "Jinja2 Engine", "desc": "Develop pixel-perfect templates using WeasyPrint."},
            {"title": "WeasyPrint Rendering", "desc": "Pipeline to transform the parsed data into an Arial 14pt PDF document."}
        ],
        "scope_out": [
            "Hardware provisioning",
            "Ongoing continuous support after Month 1",
            "Custom ML model training from scratch"
        ],
        "total_price": "5,500.00",
        "currency": "EUR",
        "milestones": [
            {"id": "M1", "desc": "Kickoff and Requirements Signing", "amount": "1,500.00"},
            {"id": "M2", "desc": "Template Engine Delivery", "amount": "2,000.00"},
            {"id": "M3", "desc": "Final WhatsApp Integration & Handoff", "amount": "2,000.00"}
        ]
    }
    
    # Write payload to disk temporarily
    temp_json = os.path.join(os.path.dirname(__file__), "test_doc_payload.json")
    with open(temp_json, 'w') as f:
        json.dump(test_payload, f)
        
    generate_document(temp_json)
    os.remove(temp_json)
