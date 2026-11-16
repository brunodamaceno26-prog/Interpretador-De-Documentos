"""Galeria da busca: uma imagem por trecho encontrado, com título e palavra destacada."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from contratos.estrutura.clausulas import Clausula, Contrato, Dispositivo, calcular_trechos, sem_acento
from contratos.exportacao.recorte import abrir_com_destaque
from contratos.ingestao.leitor import Linha


@dataclass
class ResultadoBusca:
    """Um trecho com o termo: o menor pedaço que faz sentido sozinho (§, alínea...)."""
    clausula: Clausula
    item: Clausula | Dispositivo
    termo: str
    linhas_encontradas: list[Linha] = field(default_factory=list)

    @property
    def paginas(self) -> list[int]:
        return sorted({l.pagina for l in self.item.linhas})

    @property
    def local(self) -> str:
        """Ex.: "Cláusula 3ª, §1º" ou "Cláusula 2ª, II, b"."""
        if self.clausula.numero is None:
            return "Preâmbulo"
        base = f"Cláusula {self.clausula.numero}ª"
        if isinstance(self.item, Dispositivo):
            return f"{base}, {'caput' if self.item.tipo == 'caput' else self.item.rotulo}"
        return base  # cláusula inteira (o termo está no título dela)

    @property
    def titulo(self) -> str:
        paginas = ", ".join(str(p + 1) for p in self.paginas)
        vezes = len(self.linhas_encontradas)
        extra = f" ({vezes}x)" if vezes > 1 else ""
        # "·" em vez de "–": a fonte padrão do PDF não tem o travessão
        return f'"{self.termo}" · {self.local} (pág. {paginas}){extra}'

    def palavras_no_original(self) -> set[str]:
        """A grafia exata usada no PDF (a busca ignora acento; o marca-texto não)."""
        alvo = sem_acento(self.termo)
        achadas = set()
        for linha in self.linhas_encontradas:
            normal = sem_acento(linha.texto)
            # sem_acento mantém o tamanho do texto, então os índices batem com o original
            if len(normal) != len(linha.texto):
                achadas.add(self.termo)
                continue
            for m in re.finditer(re.escape(alvo), normal):
                achadas.add(linha.texto[m.start():m.end()])
        return achadas


def agrupar_resultados(contrato: Contrato, termo: str) -> list[ResultadoBusca]:
    """Busca o termo e agrupa as ocorrências pelo dispositivo onde estão."""
    resultados: dict[int, ResultadoBusca] = {}
    for clausula, linha in contrato.buscar(termo):
        item: Clausula | Dispositivo = clausula
        if clausula.numero is not None:
            item = next((d for d in clausula.dispositivos if linha in d.linhas), clausula)
        chave = id(item)
        if chave not in resultados:
            resultados[chave] = ResultadoBusca(clausula, item, termo)
        resultados[chave].linhas_encontradas.append(linha)

    # Se a cláusula inteira já entrou (termo no título), as partes dela seriam repetidas.
    inteiras = {id(r.clausula): r for r in resultados.values() if r.item is r.clausula}
    final = []
    for r in resultados.values():
        dona = inteiras.get(id(r.clausula))
        if dona is not None and dona is not r:
            dona.linhas_encontradas.extend(r.linhas_encontradas)
        else:
            final.append(r)
    return final


def destaques_de(resultados: list[ResultadoBusca]) -> dict[int, set[str]]:
    por_pagina: dict[int, set[str]] = {}
    for r in resultados:
        for linha in r.linhas_encontradas:
            por_pagina.setdefault(linha.pagina, set()).update(r.palavras_no_original())
    return por_pagina


def gerar_imagens(
    original: str | Path,
    contrato: Contrato,
    resultados: list[ResultadoBusca],
    dpi: int = 150,
) -> list[bytes]:
    """Uma imagem PNG por resultado, com o termo marcado em amarelo.

    Se o trecho atravessa páginas, os pedaços são empilhados numa imagem só.
    """
    imagens = []
    with abrir_com_destaque(original, destaques_de(resultados)) as src:
        for r in resultados:
            trechos = calcular_trechos(r.item.linhas, contrato.x0, contrato.x1, margem=6)
            largura = max(t.area.width for t in trechos)
            altura = sum(t.area.height for t in trechos)
            with pymupdf.open() as tela:
                pagina = tela.new_page(width=largura, height=altura)
                y = 0.0
                for t in trechos:
                    alvo = pymupdf.Rect(0, y, t.area.width, y + t.area.height)
                    pagina.show_pdf_page(alvo, src, t.pagina, clip=t.area)
                    y += t.area.height
                imagens.append(pagina.get_pixmap(dpi=dpi).tobytes("png"))
    return imagens


def nome_de_arquivo(titulo: str) -> str:
    limpo = sem_acento(titulo).replace("§", "par")
    limpo = re.sub(r"[^a-z0-9]+", "_", limpo).strip("_")
    return limpo[:80] or "trecho"


def zip_de_imagens(resultados: list[ResultadoBusca], imagens: list[bytes]) -> bytes:
    """ZIP com as imagens nomeadas pelo título (ex.: 01_multa_clausula_3a_par1o_pag_1.png)."""
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for i, (r, png) in enumerate(zip(resultados, imagens), 1):
            z.writestr(f"{i:02d}_{nome_de_arquivo(r.titulo)}.png", png)
    return memoria.getvalue()
