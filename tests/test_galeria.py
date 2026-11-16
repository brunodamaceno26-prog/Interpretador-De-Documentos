"""Testes da galeria da busca (contrato fictício do conftest)."""

import io
import zipfile

import pymupdf

from contratos.estrutura.clausulas import estruturar
from contratos.exportacao.galeria import (
    agrupar_resultados, destaques_de, gerar_imagens, nome_de_arquivo, zip_de_imagens,
)
from contratos.exportacao.recorte import recortar
from contratos.ingestao.leitor import extrair_linhas


def _contrato(pdf):
    return estruturar(extrair_linhas(pdf))


def test_agrupa_pelo_dispositivo_onde_esta(contrato_pdf):
    resultados = agrupar_resultados(_contrato(contrato_pdf), "multa")
    assert [r.local for r in resultados] == ["Cláusula 3ª, caput", "Cláusula 3ª, §1º"]


def test_titulo_traz_termo_local_e_pagina(contrato_pdf):
    resultado = agrupar_resultados(_contrato(contrato_pdf), "multa")[1]
    assert resultado.titulo == '"multa" · Cláusula 3ª, §1º (pág. 2)'


def test_termo_no_titulo_da_clausula_nao_repete_as_partes(contrato_pdf):
    contrato = _contrato(contrato_pdf)
    resultados = agrupar_resultados(contrato, "rescis")  # título "Da rescisão" + caput "rescindir"
    assert len(resultados) == 1
    assert resultados[0].item is contrato.clausula(3)
    assert resultados[0].local == "Cláusula 3ª"


def test_busca_sem_acento_destaca_a_grafia_original(contrato_pdf):
    resultado = agrupar_resultados(_contrato(contrato_pdf), "rescisao")[0]
    assert resultado.palavras_no_original() == {"rescisão"}


def test_gera_uma_imagem_png_por_resultado(contrato_pdf):
    contrato = _contrato(contrato_pdf)
    resultados = agrupar_resultados(contrato, "multa")
    imagens = gerar_imagens(contrato_pdf, contrato, resultados)
    assert len(imagens) == 2
    assert all(img.startswith(b"\x89PNG") for img in imagens)


def test_pdf_com_titulos_e_destaque(contrato_pdf, tmp_path):
    contrato = _contrato(contrato_pdf)
    resultados = agrupar_resultados(contrato, "multa")
    saida = recortar(
        contrato_pdf, contrato, [r.item for r in resultados], tmp_path / "b.pdf",
        titulos=[r.titulo for r in resultados], destaques=destaques_de(resultados),
        nome_original="meu_contrato.pdf",
    )
    with pymupdf.open(saida) as doc:
        texto = doc[0].get_text()
    assert '"multa" · Cláusula 3ª, §1º (pág. 2)' in texto
    assert "meu_contrato.pdf" in texto


def test_zip_com_nomes_pelo_titulo(contrato_pdf):
    contrato = _contrato(contrato_pdf)
    resultados = agrupar_resultados(contrato, "multa")
    dados = zip_de_imagens(resultados, gerar_imagens(contrato_pdf, contrato, resultados))
    nomes = zipfile.ZipFile(io.BytesIO(dados)).namelist()
    assert nomes == [
        "01_multa_clausula_3a_caput_pag_1.png",
        "02_multa_clausula_3a_par1o_pag_2.png",
    ]


def test_nome_de_arquivo_seguro():
    assert nome_de_arquivo('"Rescisão" – §2º / pág. 3') == "rescisao_par2o_pag_3"
