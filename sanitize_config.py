import json, re, sys
from pathlib import Path

def sanitize_config(input_path: str, output_path: str):
    raw = Path(input_path).read_text(encoding="utf-8")
    
    # 1. Remover comentários de linha (# e //)
    lines = []
    for line in raw.splitlines():
        lines.append(re.sub(r'\s*[#//].*$', '', line))
    text = "\n".join(lines)
    
    # 2. Remover trailing commas antes de ] ou }
    text = re.sub(r',\s*([\]}])', r'\1', text)
    
    # 3. Sanitizar caracteres de controlo invisíveis (causa comum do erro)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\u2028\u2029]', '', text)
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        sys.exit(f"❌ JSON inválido após limpeza: {e}")
        
    # 4. Strip recursivo de chaves e valores string
    def strip_obj(obj):
        if isinstance(obj, dict):
            return {k.strip(): strip_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [strip_obj(i) for i in obj]
        if isinstance(obj, str):
            return obj.strip()
        return obj

    clean_data = strip_obj(data)
    
    # 5. Corrigir espaços acidentais em URLs (ex: files/ SNIAMB → files/SNIAMB)
    if "api" in clean_data and "snirh_pdf_urls" in clean_data["api"]:
        clean_data["api"]["snirh_pdf_urls"] = [
            u.replace("files/ SNIAMB", "files/SNIAMB") 
            for u in clean_data["api"]["snirh_pdf_urls"]
        ]

    Path(output_path).write_text(json.dumps(clean_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Config limpo e validado: {output_path}")
    return clean_data

if __name__ == "__main__":
    sanitize_config("config_v3_1.json", "config_v3_1_clean.json")