import pytest
from PIL import Image

import comum
import video


def slides(pasta, n=2):
    for i in range(1, n + 1):
        Image.new("RGB", (1080, 1350), (30 * i, 60, 90)).save(pasta / f"slide_{i:02d}.jpg", "JPEG")


def test_quadro_centraliza_slide_no_formato_vertical(tmp_path):
    slides(tmp_path, 1)
    quadro = video.quadro(tmp_path / "slide_01.jpg", "#0F3D2E")
    assert quadro.size == (1080, 1920)
    assert quadro.getpixel((540, 100)) == (15, 61, 46)  # faixa superior na cor da marca
    assert quadro.getpixel((540, 960))[0] == 30  # o slide ocupa o centro


def test_lista_de_concatenacao_da_a_mesma_duracao_a_cada_quadro(tmp_path):
    texto = video.lista_concat([tmp_path / "a.png", tmp_path / "b.png"], 3.5)
    linhas = texto.strip().splitlines()
    assert linhas.count("duration 3.5") == 2
    assert len(linhas) == 4  # sem repetir o último quadro, que somaria um quadro extra


def test_gera_reel_vertical_com_a_duracao_esperada(tmp_path):
    slides(tmp_path, 2)
    saida = video.gerar_reel(tmp_path, "#0F3D2E", tmp_path / "reel.mp4", segundos=2.0)
    info = video.inspecionar(saida)
    assert (info["largura"], info["altura"]) == (1080, 1920)
    assert 3.5 <= info["duracao"] <= 4.5
    assert saida.stat().st_size < 50 * 1024 * 1024


def test_sem_narracao_todos_os_slides_tem_o_tempo_base(post):
    assert video.duracoes(post, 3.5) == [3.5] * 6


def test_fala_longa_estende_o_tempo_do_slide(post):
    post["narracao"] = ["Oi."] + [" ".join(["palavra"] * 20)] + ["Oi."] * 4
    tempos = video.duracoes(post, 3.5)
    assert tempos[0] == 3.5
    assert tempos[1] == 8.6  # 20 palavras / 2,5 por segundo + 0,6 de respiro


def test_lista_aceita_um_tempo_por_quadro(tmp_path):
    texto = video.lista_concat([tmp_path / "a.png", tmp_path / "b.png"], [2.0, 5.5])
    assert "duration 2.0" in texto and "duration 5.5" in texto


def test_sem_slides_gera_erro(tmp_path):
    with pytest.raises(ValueError):
        video.gerar_reel(tmp_path, "#000000", tmp_path / "reel.mp4")


def test_post_unico_nao_gera_reel(post):
    post["formato"] = "post_unico"
    assert video.deve_gerar(post, comum.limites()) is False


def test_carrossel_gera_reel(post):
    assert video.deve_gerar(post, comum.limites()) is True
