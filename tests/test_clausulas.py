"""Testes com um contrato fictício gerado na hora (sem dados reais)."""

import pymupdf

from contratos.estrutura.clausulas import estruturar
from contratos.exportacao.recorte import recortar
from contratos.ingestao.leitor import extrair_linhas, tem_texto

def test_detecta_texto_digital(contrato_pdf):
    assert tem_texto(contrato_pdf)


def test_encontra_clausulas_por_extenso_e_numeral(contrato_pdf):
    contrato = estruturar(extrair_linhas(contrato_pdf))
    numeros = [c.numero for c in contrato.clausulas]
    assert numeros == [None, 1, 2, 3, 4]
    assert contrato.clausula(4).titulo == "DO FORO"


def test_clausula_que_atravessa_paginas(contrato_pdf):
    contrato = estruturar(extrair_linhas(contrato_pdf))
    terceira = contrato.clausula(3)
    assert terceira.paginas == [0, 1]
    assert len(terceira.trechos(contrato.x0, contrato.x1)) == 2
    assert "primeiros 30 dias" in terceira.texto


def test_para_nas_assinaturas(contrato_pdf):
    contrato = estruturar(extrair_linhas(contrato_pdf))
    texto_foro = contrato.clausula(4).texto
    assert "Testemunhas" not in texto_foro
    assert "janeiro de 2026" not in texto_foro


def test_junta_pedacos_na_mesma_altura(contrato_pdf):
    textos = [l.texto for l in extrair_linhas(contrato_pdf)]
    assert "Salvo expressa" in textos


def test_busca_ignora_acentos(contrato_pdf):
    contrato = estruturar(extrair_linhas(contrato_pdf))
    achados = contrato.buscar("RESCISAO")
    assert [c.numero for c, _ in achados] == [3]


def test_recorte_gera_pdf_com_texto_da_clausula(contrato_pdf, tmp_path):
    contrato = estruturar(extrair_linhas(contrato_pdf))
    saida = recortar(contrato_pdf, contrato, [contrato.clausula(2)], tmp_path / "r.pdf")
    with pymupdf.open(saida) as doc:
        texto = doc[0].get_text()
    assert "R$ 1.000,00" in texto
    assert "Do objeto" not in texto  # não vazou a cláusula vizinha


def test_subdivide_incisos_e_alineas(contrato_pdf):
    contrato = estruturar(extrair_linhas(contrato_pdf))
    rotulos = [d.rotulo for d in contrato.clausula(2).dispositivos]
    assert rotulos == ["Caput", "I", "I, a", "I, b", "II", "II, a"]
    assert "IPCA" in contrato.clausula(2).dispositivo("II,a").texto


def test_subdivide_paragrafos_mesmo_entre_paginas(contrato_pdf):
    contrato = estruturar(extrair_linhas(contrato_pdf))
    terceira = contrato.clausula(3)
    assert [d.rotulo for d in terceira.dispositivos] == ["Caput", "§1º"]
    assert "30 dias" in terceira.dispositivo("§1").texto


def test_recorte_de_um_paragrafo_so(contrato_pdf, tmp_path):
    contrato = estruturar(extrair_linhas(contrato_pdf))
    paragrafo = contrato.clausula(3).dispositivo("1")
    saida = recortar(contrato_pdf, contrato, [paragrafo], tmp_path / "p.pdf")
    with pymupdf.open(saida) as doc:
        texto = doc[0].get_text()
    assert "30 dias" in texto
    assert "rescindir" not in texto  # o caput ficou de fora
