"""Interface gráfica (Streamlit) do Interpretador de Contratos.

Abra com:  contratos-app   (ou clique duas vezes em "Abrir Interpretador.bat")
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

import pymupdf
import streamlit as st

from contratos.estrutura.clausulas import Contrato, estruturar
from contratos.exportacao.galeria import (
    agrupar_resultados, destaques_de, gerar_imagens, nome_de_arquivo, zip_de_imagens,
)
from contratos.exportacao.recorte import recortar
from contratos.ingestao.leitor import extrair_linhas, tem_texto

PASTA_TEMP = Path(tempfile.gettempdir()) / "interpretador-contratos"
PASTA_TEMP.mkdir(exist_ok=True)

st.set_page_config(page_title="Interpretador de Contratos", page_icon="📄", layout="wide")


# ---------------------------------------------------------------- utilidades

def carregar_contrato(arquivo) -> tuple[Path, Contrato] | None:
    """Salva o upload num arquivo temporário e estrutura o contrato (uma vez por arquivo)."""
    dados = arquivo.getvalue()
    chave = hashlib.sha256(dados).hexdigest()[:16]
    if st.session_state.get("chave_arquivo") == chave:
        return st.session_state["caminho"], st.session_state["contrato"]

    caminho = PASTA_TEMP / f"{chave}.pdf"
    caminho.write_bytes(dados)
    if not tem_texto(caminho):
        st.error("Este PDF não tem texto digital (parece escaneado). O suporte a OCR vem numa próxima fase.")
        return None

    contrato = estruturar(extrair_linhas(caminho))
    # Arquivo novo: zera a conversa e as seleções do arquivo anterior.
    st.session_state.update(
        chave_arquivo=chave, caminho=caminho, contrato=contrato, nome=arquivo.name,
        conversa=None, mensagens=[],
    )
    return caminho, contrato


def gerar_recorte(caminho: Path, contrato: Contrato, itens, nome: str, **opcoes) -> bytes:
    destino = PASTA_TEMP / f"{nome}.pdf"
    recortar(caminho, contrato, itens, destino, nome_original=st.session_state.get("nome"), **opcoes)
    return destino.read_bytes()


def mostrar_previa(pdf: bytes, limite: int = 3) -> None:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for pagina in list(doc)[:limite]:
            st.image(pagina.get_pixmap(dpi=90).tobytes("png"), use_container_width=True)
        if doc.page_count > limite:
            st.caption(f"... e mais {doc.page_count - limite} página(s) no arquivo.")


def destacar(texto: str, palavras: set[str]) -> str:
    """Destaca as palavras como aparecem no PDF (com acento), ignorando maiúsculas."""
    if not palavras:
        return texto
    padrao = "|".join(re.escape(p) for p in sorted(palavras, key=len, reverse=True))
    return re.sub(f"({padrao})", r"**:orange[\1]**", texto, flags=re.IGNORECASE)


def nome_curto(clausula) -> str:
    return "Preâmbulo" if clausula.numero is None else f"{clausula.numero}ª – {clausula.titulo}"


# ---------------------------------------------------------------- barra lateral

with st.sidebar:
    st.header("📄 Contrato")
    arquivo = st.file_uploader("Escolha o PDF do contrato", type=["pdf"])

    st.divider()
    st.header("🔑 Chave da API")
    chave_api = st.text_input(
        "Chave da API do Claude (só para Perguntas)",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Crie em platform.claude.com. Fica só na memória enquanto o programa está aberto.",
    )
    st.caption("O contrato é processado no seu computador. Só as perguntas enviam o texto para a API.")

st.title("Interpretador de Contratos")

if not arquivo:
    st.info("👈 Comece escolhendo um contrato em PDF na barra lateral.")
    st.stop()

carregado = carregar_contrato(arquivo)
if not carregado:
    st.stop()
caminho, contrato = carregado
numeradas = [c for c in contrato.clausulas if c.numero is not None]

st.caption(f"**{arquivo.name}** · {len(numeradas)} cláusulas encontradas")

aba_clausulas, aba_buscar, aba_recortar, aba_perguntar = st.tabs(
    ["📑 Cláusulas", "🔎 Buscar", "✂️ Recortar", "💬 Perguntar"]
)

# ---------------------------------------------------------------- cláusulas

with aba_clausulas:
    for c in contrato.clausulas:
        paginas = ", ".join(str(p + 1) for p in c.paginas)
        with st.expander(f"**{c.rotulo}**  ·  pág. {paginas}"):
            if c.numero is None:
                st.text(c.texto)
                continue
            for d in c.dispositivos:
                recuo = "&emsp;&emsp;" if d.tipo == "alinea" else ""
                corpo = " ".join(d.texto.split())
                if d.tipo == "caput":
                    st.markdown(corpo)
                else:
                    st.markdown(f"{recuo}{corpo}")

# ---------------------------------------------------------------- busca

with aba_buscar:
    termo = st.text_input("Procurar no contrato", placeholder="ex.: multa, rescisão, prazo, foro").strip()
    if termo:
        resultados = agrupar_resultados(contrato, termo)
        if not resultados:
            st.warning("Nada encontrado.")
        else:
            ocorrencias = sum(len(r.linhas_encontradas) for r in resultados)
            col_info, col_botao = st.columns([3, 1], vertical_alignment="center")
            col_info.success(f"{ocorrencias} ocorrência(s) em {len(resultados)} trecho(s)")

            # A galeria fica guardada até o termo (ou o arquivo) mudar.
            chave_galeria = (st.session_state.chave_arquivo, termo)
            if col_botao.button("✂️ Recortar resultados", type="primary", use_container_width=True):
                with st.spinner("Recortando..."):
                    st.session_state.galeria = (chave_galeria, gerar_imagens(caminho, contrato, resultados))

            galeria = st.session_state.get("galeria")
            if galeria and galeria[0] == chave_galeria:
                imagens = galeria[1]
                st.subheader(f"Galeria: \"{termo}\"")
                st.caption("Desmarque o que não quiser incluir nos downloads.")

                selecionados = []
                colunas = st.columns(2)
                for i, (r, png) in enumerate(zip(resultados, imagens)):
                    with colunas[i % 2].container(border=True):
                        st.markdown(f"**{r.titulo}**")
                        st.image(png, use_container_width=True)
                        if st.checkbox("Incluir", value=True, key=f"incluir_{termo}_{i}"):
                            selecionados.append(i)

                if selecionados:
                    escolhidos = [resultados[i] for i in selecionados]
                    nome_base = f"busca_{nome_de_arquivo(termo)}"
                    pdf = gerar_recorte(
                        caminho, contrato, [r.item for r in escolhidos], nome_base,
                        titulos=[r.titulo for r in escolhidos], destaques=destaques_de(escolhidos),
                    )
                    zip_bytes = zip_de_imagens(escolhidos, [imagens[i] for i in selecionados])
                    c1, c2 = st.columns(2)
                    c1.download_button(
                        f"⬇️ Baixar PDF ({len(escolhidos)} trecho(s))", pdf,
                        file_name=f"{nome_base}.pdf", mime="application/pdf",
                        type="primary", use_container_width=True,
                    )
                    c2.download_button(
                        "🖼️ Baixar imagens (ZIP)", zip_bytes, file_name=f"{nome_base}.zip",
                        mime="application/zip", use_container_width=True,
                    )
                else:
                    st.info("Nenhum trecho selecionado.")
            else:
                for r in resultados:
                    st.markdown(f"**{r.local}**")
                    palavras = r.palavras_no_original()
                    for linha in r.linhas_encontradas:
                        st.markdown(f"- pág. {linha.pagina + 1}: {destacar(linha.texto, palavras)}")

# ---------------------------------------------------------------- recorte

with aba_recortar:
    st.write("Escolha cláusulas inteiras ou só uma parte delas (parágrafo, inciso, alínea).")
    opcoes = {}
    for c in numeradas:
        opcoes[f"Cláusula {nome_curto(c)}"] = c
        for d in c.dispositivos:
            if d.tipo != "caput":
                opcoes[f"   ↳ {c.numero}ª · {d.rotulo}"] = d

    escolhidos = st.multiselect("O que recortar", list(opcoes), placeholder="Selecione...")
    if escolhidos:
        pdf = gerar_recorte(caminho, contrato, [opcoes[e] for e in escolhidos], "recorte")
        st.download_button(
            "⬇️ Baixar recorte em PDF", pdf, file_name=f"recorte_{Path(arquivo.name).stem}.pdf",
            mime="application/pdf", type="primary",
        )
        st.subheader("Prévia")
        mostrar_previa(pdf)

# ---------------------------------------------------------------- perguntas

with aba_perguntar:
    if not chave_api:
        st.info("Para fazer perguntas, coloque sua chave da API do Claude na barra lateral.")
    else:
        from contratos.ia.perguntas import Conversa

        if st.session_state.get("conversa") is None or st.session_state.get("chave_usada") != chave_api:
            import anthropic

            st.session_state.conversa = Conversa(
                contrato, titulo=Path(arquivo.name).stem,
                cliente=anthropic.Anthropic(api_key=chave_api),
            )
            st.session_state.chave_usada = chave_api
            st.session_state.mensagens = []

        if st.button("🗑️ Nova conversa", disabled=not st.session_state.mensagens):
            st.session_state.conversa = None
            st.rerun()

        for i, msg in enumerate(st.session_state.mensagens):
            with st.chat_message(msg["papel"]):
                st.markdown(msg["texto"])
                resposta = msg.get("resposta")
                if resposta and resposta.citacoes:
                    with st.expander(f"📌 Fontes ({len(resposta.citacoes)})"):
                        for n, cit in enumerate(resposta.citacoes, 1):
                            st.markdown(f"**[{n}] {cit.clausula.rotulo}**")
                            st.caption(" ".join(cit.trecho_citado.split()))
                    pdf = gerar_recorte(caminho, contrato, resposta.clausulas_citadas, f"citadas_{i}")
                    st.download_button(
                        "✂️ Baixar recorte das cláusulas citadas", pdf,
                        file_name=f"citadas_{i}.pdf", mime="application/pdf", key=f"baixar_{i}",
                    )

        pergunta = st.chat_input("Pergunte algo sobre o contrato...")
        if pergunta:
            st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
            with st.spinner("Lendo o contrato..."):
                try:
                    resposta = st.session_state.conversa.perguntar(pergunta)
                    st.session_state.mensagens.append(
                        {"papel": "assistant", "texto": resposta.texto, "resposta": resposta}
                    )
                except Exception as erro:  # chave inválida, sem créditos, sem internet...
                    st.session_state.mensagens.pop()
                    st.error(f"Não consegui falar com a API: {erro}")
                    st.stop()
            st.rerun()
