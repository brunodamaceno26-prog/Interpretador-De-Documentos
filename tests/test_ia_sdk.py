"""Usa o SDK real da Anthropic com o HTTP simulado: valida o formato da
requisição e a leitura dos tipos reais de citação, sem gastar créditos."""

import json

import pytest

try:  # SDKs mais novos usam httpx2
    import httpx2 as httpx
except ImportError:
    import httpx

anthropic = pytest.importorskip("anthropic")

from contratos.estrutura.clausulas import estruturar  # noqa: E402
from contratos.ia.perguntas import Conversa  # noqa: E402
from contratos.ingestao.leitor import extrair_linhas  # noqa: E402

RESPOSTA_API = {
    "id": "msg_teste",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-5-5",
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 100, "output_tokens": 20},
    "content": [
        {"type": "text", "text": "A multa por rescisão é de ", "citations": None},
        {
            "type": "text",
            "text": "10%",
            "citations": [{
                "type": "content_block_location",
                "cited_text": "Qualquer parte pode rescindir com multa de 10%.",
                "document_index": 0,
                "document_title": "ficticio",
                "start_block_index": 3,
                "end_block_index": 4,
            }],
        },
        {"type": "text", "text": ".", "citations": None},
    ],
}


def test_fluxo_completo_com_sdk_real(contrato_pdf):
    enviado = {}

    def responder(request: httpx.Request) -> httpx.Response:
        enviado.update(json.loads(request.content))
        return httpx.Response(200, json=RESPOSTA_API)

    cliente = anthropic.Anthropic(
        api_key="chave-falsa",
        http_client=httpx.Client(transport=httpx.MockTransport(responder)),
    )
    contrato = estruturar(extrair_linhas(contrato_pdf))
    resposta = Conversa(contrato, titulo="ficticio", cliente=cliente).perguntar("Qual a multa?")

    documento = enviado["messages"][0]["content"][0]
    assert documento["source"]["type"] == "content"
    assert documento["citations"] == {"enabled": True}
    assert resposta.texto == "A multa por rescisão é de 10%[1]."
    assert resposta.clausulas_citadas[0].numero == 3


def test_segunda_pergunta_reenvia_historico_valido(contrato_pdf):
    corpos = []

    def responder(request):
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json=RESPOSTA_API)

    cliente = anthropic.Anthropic(
        api_key="chave-falsa",
        http_client=httpx.Client(transport=httpx.MockTransport(responder)),
    )
    conversa = Conversa(estruturar(extrair_linhas(contrato_pdf)), cliente=cliente)
    conversa.perguntar("Qual a multa?")
    conversa.perguntar("E se eu atrasar?")

    assistente = corpos[1]["messages"][1]
    assert assistente["role"] == "assistant"
    assert assistente["content"][1]["citations"][0]["start_block_index"] == 3
