# force_fix_config.py
import json, re, sys
from pathlib import Path

CONFIG_PATH = Path("config_v3_1.json")

if not CONFIG_PATH.exists():
    sys.exit("❌ config_v3_1.json não encontrado.")

# 1. Ler com suporte a BOM (comum em editores Windows)
raw = CONFIG_PATH.read_text(encoding="utf-8-sig")

# 2. Remover comentários # (preservando URLs que não os usam)
lines = []
for line in raw.splitlines():
    if '#' in line and 'http' not in line:
        line = line.split('#')[0]
    lines.append(line)
text = '\n'.join(lines)

# 3. Remover trailing commas antes de } ou ]
text = re.sub(r',\s*([\]}])', r'\1', text)

# 4. 🛡️ Substituir TODOS os caracteres de controlo JSON-illegais por espaço
text = re.sub(r'[\x00-\x1F\u2028\u2029]', ' ', text)

try:
    cfg = json.loads(text)
except json.JSONDecodeError as e:
    sys.exit(f"❌ JSON ainda inválido após limpeza: {e}")

# 5. Strip recursivo de chaves e valores
def strip_obj(obj):
    if isinstance(obj, dict): return {str(k).strip(): strip_obj(v) for k, v in obj.items()}
    if isinstance(obj, list): return [strip_obj(i) for i in obj]
    if isinstance(obj, str): return obj.strip()
    return obj

clean_cfg = strip_obj(cfg)

# 6. Corrigir espaço acidental na URL do SNIRH
if "api" in clean_cfg and "snirh_pdf_urls" in clean_cfg["api"]:
    clean_cfg["api"]["snirh_pdf_urls"] = [
        u.replace("files/ SNIAMB", "files/SNIAMB") for u in clean_cfg["api"]["snirh_pdf_urls"]
    ]

# 7. Reescrever ficheiro limpo
CONFIG_PATH.write_text(json.dumps(clean_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
print("✅ config_v3_1.json forçado para JSON 100% válido. Pronto para execução.")