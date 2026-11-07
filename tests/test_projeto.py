"""Confere a estrutura de agentes, skills, hooks e workflows."""
import json
import re
import subprocess
import sys

import pytest
import yaml

import comum

RAIZ = comum.RAIZ
AGENTES = {
    "analista": ({"Read", "Write"}, "haiku"),
    "pesquisador": ({"Read", "Write", "WebSearch", "WebFetch"}, "sonnet"),
    "pauteiro": ({"Read", "Edit", "Bash"}, "sonnet"),
    "roteirista": ({"Read", "Write", "Edit"}, "sonnet"),
    "revisor": ({"Read", "Grep", "Glob"}, "sonnet"),
    "legendista": ({"Read", "Edit"}, "haiku"),
    "qa-visual": ({"Read"}, "sonnet"),
}
SKILLS = ["semana", "validar", "status", "post", "evento", "noticia"]
WORKFLOWS = ["ci", "publicar", "renovar-token", "insights", "radar"]


def frontmatter(caminho):
    texto = caminho.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.S)
    assert m, f"{caminho} sem frontmatter"
    return yaml.safe_load(m.group(1)), m.group(2)


def test_claude_md_tem_menos_de_80_linhas():
    assert len((RAIZ / "CLAUDE.md").read_text(encoding="utf-8").splitlines()) < 80


def test_prompt_original_fora_do_contexto_automatico():
    assert not (RAIZ / "prompt-instagram-automacao.md").exists()
    assert (RAIZ / "docs" / "referencia" / "prompt-instagram-automacao.md").exists()


@pytest.mark.parametrize("nome", AGENTES)
def test_agente_tem_modelo_e_ferramentas(nome):
    fm, corpo = frontmatter(RAIZ / ".claude" / "agents" / f"{nome}.md")
    ferramentas, modelo = AGENTES[nome]
    assert fm["name"] == nome
    assert fm["description"]
    assert fm["model"] == modelo
    assert {f.strip() for f in fm["tools"].split(",")} == ferramentas
    assert len(corpo.splitlines()) < 60


def test_revisor_e_qa_nao_podem_escrever():
    for nome in ("revisor", "qa-visual"):
        fm, _ = frontmatter(RAIZ / ".claude" / "agents" / f"{nome}.md")
        assert not {"Write", "Edit", "Bash"} & {f.strip() for f in fm["tools"].split(",")}


def test_agentes_que_leem_terceiros_tem_aviso_de_dado_nao_confiavel():
    for nome in ("pesquisador", "pauteiro", "roteirista"):
        _, corpo = frontmatter(RAIZ / ".claude" / "agents" / f"{nome}.md")
        assert "não confiável" in corpo.lower() or "não confiáveis" in corpo.lower()


@pytest.mark.parametrize("nome", SKILLS)
def test_skill_tem_frontmatter(nome):
    fm, corpo = frontmatter(RAIZ / ".claude" / "skills" / nome / "SKILL.md")
    assert fm["name"] == nome
    assert fm["description"]
    assert corpo.strip()


def _caminhos_citados():
    alvos = [RAIZ / "CLAUDE.md", *(RAIZ / ".claude").rglob("*.md"), RAIZ / "docs" / "operacao.md"]
    padrao = re.compile(r"`((?:scripts|config|marcas|schemas|templates|docs|exemplos|\.claude)/[\w./-]+\.(?:py|yaml|json|html|md))`")
    for arquivo in alvos:
        for citado in padrao.findall(arquivo.read_text(encoding="utf-8")):
            yield arquivo.relative_to(RAIZ).as_posix(), citado


def test_caminhos_citados_nas_instrucoes_existem():
    faltando = [(a, c) for a, c in _caminhos_citados() if not (RAIZ / c).exists()]
    assert faltando == []


def test_settings_nega_segredos_e_tem_hook():
    s = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
    negados = " ".join(s["permissions"]["deny"])
    assert ".env" in negados
    assert "gh secret" in negados
    comando = s["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    assert "validar_post.py" in comando


def rodar_hook(caminho):
    entrada = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(caminho)}})
    return subprocess.run([sys.executable, str(RAIZ / ".claude" / "hooks" / "validar_post.py")], input=entrada, capture_output=True, text=True, encoding="utf-8")


def test_hook_ignora_outros_arquivos():
    assert rodar_hook(RAIZ / "README.md").returncode == 0


def test_hook_devolve_erro_para_post_invalido(tmp_path, post):
    post["slides"][1]["texto"] = "Fique rico com isto"
    caminho = tmp_path / "fila" / "2026-11-09" / "FIN" / "post.json"
    comum.gravar_json(caminho, post)
    r = rodar_hook(caminho)
    assert r.returncode == 2
    assert "promessa" in r.stderr


@pytest.mark.parametrize("nome", WORKFLOWS)
def test_workflow_fixa_actions_por_sha(nome):
    texto = (RAIZ / ".github" / "workflows" / f"{nome}.yml").read_text(encoding="utf-8")
    yaml.safe_load(texto)
    for uso in re.findall(r"uses:\s*(\S+)", texto):
        assert re.search(r"@[0-9a-f]{40}$", uso), uso


@pytest.mark.parametrize("nome", WORKFLOWS)
def test_workflow_declara_permissoes_minimas(nome):
    assert "permissions" in yaml.safe_load((RAIZ / ".github" / "workflows" / f"{nome}.yml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("nome", WORKFLOWS)
def test_workflow_nao_injeta_entrada_em_comando_de_shell(nome):
    dados = yaml.safe_load((RAIZ / ".github" / "workflows" / f"{nome}.yml").read_text(encoding="utf-8"))
    for job in dados["jobs"].values():
        for passo in job["steps"]:
            assert "${{" not in passo.get("run", ""), passo.get("name")


def test_horarios_de_publicacao():
    dados = yaml.safe_load((RAIZ / ".github" / "workflows" / "publicar.yml").read_text(encoding="utf-8"))
    crons = {c["cron"] for c in dados[True]["schedule"]}
    assert crons == {"30 11 * * *", "30 15 * * *", "0 21 * * *"}


def test_publicar_tem_concorrencia_por_perfil():
    dados = yaml.safe_load((RAIZ / ".github" / "workflows" / "publicar.yml").read_text(encoding="utf-8"))
    assert dados["concurrency"]["cancel-in-progress"] is False


def test_historico_inicial_existe():
    assert (RAIZ / "historico" / "aprendizados.md").exists()
    linhas = (RAIZ / "historico" / "publicacoes.csv").read_text(encoding="utf-8").splitlines()
    assert linhas[0].split(",") == comum.COLUNAS_PUBLICACOES
