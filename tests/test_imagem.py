import comum
import folha_contato
import validar_imagem as vi
from PIL import Image

LIM = comum.limites()


def criar(pasta, nome, tam=(1080, 1350), fmt="JPEG", modo="RGB"):
    Image.new(modo, tam, (10, 20, 30)).save(pasta / nome, fmt)


def post(slides=2, stories=1):
    return {"slides": [{"n": i + 1} for i in range(slides)], "stories": [{"texto": "x"}] * stories}


def pasta_ok(tmp_path):
    criar(tmp_path, "slide_01.jpg")
    criar(tmp_path, "slide_02.jpg")
    criar(tmp_path, "story_01.jpg", (1080, 1920))
    return tmp_path


def regras(tmp_path, p=None):
    return {e.regra for e in vi.validar_pasta(tmp_path, p or post(), LIM)}


def test_pasta_correta_passa(tmp_path):
    assert regras(pasta_ok(tmp_path)) == set()


def test_imagem_faltando_reprova(tmp_path):
    pasta_ok(tmp_path)
    (tmp_path / "slide_02.jpg").unlink()
    assert "imagem.quantidade" in regras(tmp_path)


def test_imagem_a_mais_reprova(tmp_path):
    pasta_ok(tmp_path)
    criar(tmp_path, "slide_03.jpg")
    assert "imagem.quantidade" in regras(tmp_path)


def test_dimensao_errada_reprova(tmp_path):
    pasta_ok(tmp_path)
    criar(tmp_path, "slide_01.jpg", (1080, 1080))
    assert "imagem.dimensao" in regras(tmp_path)


def test_png_com_nome_jpg_reprova(tmp_path):
    pasta_ok(tmp_path)
    criar(tmp_path, "slide_01.jpg", fmt="PNG")
    assert "imagem.formato" in regras(tmp_path)


def test_cmyk_reprova(tmp_path):
    pasta_ok(tmp_path)
    Image.new("CMYK", (1080, 1350)).save(tmp_path / "slide_01.jpg", "JPEG")
    assert "imagem.cor" in regras(tmp_path)


def test_arquivo_grande_reprova(tmp_path):
    pasta_ok(tmp_path)
    with open(tmp_path / "slide_01.jpg", "ab") as f:
        f.write(b"\0" * (8 * 1024 * 1024 + 1))
    assert "imagem.tamanho" in regras(tmp_path)


def test_arquivo_corrompido_reprova(tmp_path):
    pasta_ok(tmp_path)
    (tmp_path / "slide_01.jpg").write_bytes(b"nao e imagem")
    assert "imagem.formato" in regras(tmp_path)


def test_folha_de_miniaturas_reduz_e_inclui_todos_os_slides(tmp_path):
    pasta_ok(tmp_path)
    saida = folha_contato.gerar(tmp_path)
    with Image.open(saida) as im:
        assert im.width <= 1600
    assert saida.stat().st_size < sum(p.stat().st_size for p in tmp_path.glob("s*.jpg")) * 5
    assert saida.name == "previa.jpg"
    assert folha_contato.miniaturas(tmp_path) == ["slide_01.jpg", "slide_02.jpg", "story_01.jpg"]
