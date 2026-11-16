"""Contrato fictício compartilhado pelos testes (sem dados reais)."""

import pymupdf
import pytest

LINHAS_PAG1 = [
    "CONTRATO DE PRESTAÇÃO DE SERVIÇOS",
    "CONTRATANTE: EMPRESA FICTÍCIA LTDA",
    "Cláusula Primeira: Do objeto",
    "Prestação de serviços de consultoria.",
    "Cláusula Segunda: Do preço",
    "O valor mensal é de R$ 1.000,00.",
    "I. Da forma de pagamento:",
    "a. à vista, com desconto;",
    "b. parcelado.",
    "II. Do reajuste:",
    "a. anual pelo IPCA.",
    "Cláusula Terceira: Da rescisão",
    "Qualquer parte pode rescindir com multa de 10%.",
]
LINHAS_PAG2 = [
    "§1º. A multa não se aplica nos primeiros 30 dias.",
    "CLÁUSULA 4ª - DO FORO",
    "Fica eleito o foro da Comarca de Exemplo.",
    "Exemplo, 01 de janeiro de 2026",
    "Testemunhas:",
]


@pytest.fixture
def contrato_pdf(tmp_path):
    caminho = tmp_path / "ficticio.pdf"
    doc = pymupdf.open()
    for linhas in (LINHAS_PAG1, LINHAS_PAG2):
        pagina = doc.new_page()
        for i, texto in enumerate(linhas):
            pagina.insert_text((72, 80 + i * 20), texto, fontsize=10)
    # Linha "justificada" quebrada em pedaços na mesma altura
    doc[1].insert_text((72, 300), "Salvo", fontsize=10)
    doc[1].insert_text((150, 300), "expressa", fontsize=10)
    doc.save(caminho)
    return caminho
