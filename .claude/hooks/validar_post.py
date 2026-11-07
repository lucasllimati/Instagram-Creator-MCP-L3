"""Hook do Claude Code: valida fila/**/post.json logo depois de cada edição.

Sair com código 2 devolve a mensagem de erro ao Claude, que corrige na hora.
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def main() -> int:
    try:
        entrada = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    caminho = (entrada.get("tool_input") or {}).get("file_path", "")
    if not re.search(r"[\\/]fila[\\/][^\\/]+[\\/][^\\/]+[\\/]post\.json$", caminho):
        return 0

    import validar

    try:
        post = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"post.json inválido: {e}", file=sys.stderr)
        return 2
    erros = validar.validar_post(post, validar.carregar_contexto())
    if erros:
        print(f"Validação reprovou {caminho}:", file=sys.stderr)
        for e in erros:
            print(f"  {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
