"""Recorte visual: monta um PDF novo com os pedaços originais das cláusulas."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol, Sequence

import pymupdf

from contratos.estrutura.clausulas import Contrato, calcular_trechos
from contratos.ingestao.leitor import Linha

A4 = pymupdf.paper_rect("a4")
MARGEM = 36  # 0,5 polegada
ESPACO_ENTRE_TRECHOS = 14
ALTURA_TITULO = 18
AMARELO = (1, 0.88, 0.3)


class Recortavel(Protocol):
    """Qualquer coisa com linhas: uma Clausula inteira ou um Dispositivo (§, inciso...)."""
    linhas: list[Linha]


def abrir_com_destaque(original: str | Path, destaques: Mapping[int, set[str]] | None) -> pymupdf.Document:
    """Abre o PDF em memória com marca-texto nas palavras pedidas.

    `destaques` = {página: {"multa", "Multa"}}. O destaque é "assado" no conteúdo
    da página (bake), senão ele some quando a página é recortada com show_pdf_page.
    """
    doc = pymupdf.open(original)
    if destaques:
        for numero, palavras in destaques.items():
            pagina = doc[numero]
            for palavra in palavras:
                for quad in pagina.search_for(palavra, quads=True):
                    anotacao = pagina.add_highlight_annot(quad)
                    anotacao.set_colors(stroke=AMARELO)
                    anotacao.update()
        doc.bake()
    return doc


def recortar(
    original: str | Path,
    contrato: Contrato,
    itens: Sequence[Recortavel],
    destino: str | Path,
    titulos: Sequence[str] | None = None,
    destaques: Mapping[int, set[str]] | None = None,
    nome_original: str | None = None,
) -> Path:
    """Empilha os recortes em páginas A4, quebrando página quando não couber.

    titulos: um título por item, escrito acima do recorte (opcional).
    destaques: palavras para marcar em amarelo, por página (opcional).
    nome_original: nome mostrado no rodapé (padrão: nome do arquivo de origem).
    """
    if titulos is not None and len(titulos) != len(itens):
        raise ValueError("Informe um título para cada item.")
    destino = Path(destino)
    with abrir_com_destaque(original, destaques) as src, pymupdf.open() as novo:
        pagina = None
        y = 0.0
        largura_util = A4.width - 2 * MARGEM

        for i, item in enumerate(itens):
            trechos = calcular_trechos(item.linhas, contrato.x0, contrato.x1)
            for j, trecho in enumerate(trechos):
                escala = min(1.0, largura_util / trecho.area.width)
                altura = trecho.area.height * escala
                com_titulo = titulos is not None and j == 0
                altura_total = altura + (ALTURA_TITULO if com_titulo else 0)

                if pagina is None or y + altura_total > A4.height - MARGEM:
                    pagina = novo.new_page(width=A4.width, height=A4.height)
                    y = MARGEM

                if com_titulo:
                    pagina.insert_text((MARGEM, y + 11), titulos[i], fontsize=10,
                                       fontname="hebo", color=(0.15, 0.15, 0.4))
                    y += ALTURA_TITULO

                alvo = pymupdf.Rect(MARGEM, y, MARGEM + trecho.area.width * escala, y + altura)
                pagina.show_pdf_page(alvo, src, trecho.pagina, clip=trecho.area)
                y += altura

            y += ESPACO_ENTRE_TRECHOS  # respiro entre itens diferentes

        rodape = f"Recortado de: {nome_original or Path(original).name}"
        for p in novo:
            p.insert_text((MARGEM, A4.height - 18), rodape, fontsize=7, color=(0.5, 0.5, 0.5))
        novo.save(destino, garbage=3, deflate=True)
    return destino
