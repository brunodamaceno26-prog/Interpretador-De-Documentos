"""Linha de comando do interpretador de contratos.

Exemplos:
    contratos listar contrato.pdf
    contratos ver contrato.pdf 4
    contratos buscar contrato.pdf multa
    contratos recortar contrato.pdf 4 5:§2 2:II,b -o recorte.pdf
    contratos perguntar contrato.pdf "Qual a multa por atraso?" --recortar citadas.pdf
    contratos perguntar contrato.pdf            # modo conversa
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contratos.estrutura.clausulas import Contrato, estruturar
from contratos.exportacao.recorte import recortar
from contratos.ingestao.leitor import extrair_linhas, tem_texto


def _item(contrato: Contrato, spec: str):
    """'4' -> Cláusula 4ª inteira; '5:§2' ou '2:II,b' -> só aquele dispositivo."""
    numero, _, dispositivo = spec.partition(":")
    clausula = contrato.clausula(int(numero))
    return clausula.dispositivo(dispositivo) if dispositivo else clausula


def _mostrar_resposta(resposta, contrato, pdf, destino_recorte):
    print(f"\n{resposta.texto}\n")
    if resposta.citacoes:
        print("Fontes:")
        for i, cit in enumerate(resposta.citacoes, 1):
            trecho = " ".join(cit.trecho_citado.split())
            print(f"  [{i}] {cit.clausula.rotulo}: \"{trecho[:160]}\"")
    if destino_recorte and resposta.clausulas_citadas:
        recortar(pdf, contrato, resposta.clausulas_citadas, destino_recorte)
        print(f"\nRecorte das cláusulas citadas salvo em {destino_recorte}")


def _perguntar(args, contrato) -> int:
    from contratos.ia.perguntas import Conversa, ErroDeConfiguracao

    try:
        conversa = Conversa(contrato, titulo=Path(args.pdf).stem)
    except ErroDeConfiguracao as erro:
        print(erro)
        return 1

    if args.pergunta:
        _mostrar_resposta(conversa.perguntar(args.pergunta), contrato, args.pdf, args.recortar)
        return 0

    print("Modo conversa. Digite sua pergunta (ou 'sair').")
    contador = 0
    while True:
        try:
            pergunta = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in {"sair", "exit", "q"}:
            break
        if not pergunta:
            continue
        contador += 1
        destino = None
        if args.recortar:
            base = Path(args.recortar)
            destino = base.with_name(f"{base.stem}_{contador}{base.suffix}")
        _mostrar_resposta(conversa.perguntar(pergunta), contrato, args.pdf, destino)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contratos", description="Interpretador de contratos")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("listar", help="lista as cláusulas encontradas")
    p.add_argument("pdf")

    p = sub.add_parser("ver", help="mostra uma cláusula dividida em caput, §, incisos e alíneas")
    p.add_argument("pdf")
    p.add_argument("numero", type=int)

    p = sub.add_parser("buscar", help="procura um termo (ignora acentos)")
    p.add_argument("pdf")
    p.add_argument("termo")

    p = sub.add_parser("recortar", help="gera PDF com o recorte visual")
    p.add_argument("pdf")
    p.add_argument("itens", nargs="+", help="ex.: 4  5:§2  2:II,b  3:unico")
    p.add_argument("-o", "--saida", default="recorte.pdf")

    p = sub.add_parser("perguntar", help="tira dúvidas com a IA, citando as cláusulas")
    p.add_argument("pdf")
    p.add_argument("pergunta", nargs="?", help="sem pergunta = modo conversa")
    p.add_argument("--recortar", metavar="SAIDA.pdf",
                   help="gera o recorte das cláusulas citadas na resposta")

    args = parser.parse_args(argv)

    if not Path(args.pdf).is_file():
        print(f"Arquivo não encontrado: {args.pdf}")
        print("Dica: arraste o PDF para dentro do terminal para colar o caminho certo.")
        return 1

    if not tem_texto(args.pdf):
        print("Este PDF não tem texto digital. O suporte a OCR vem numa próxima fase.")
        return 1

    contrato = estruturar(extrair_linhas(args.pdf))

    try:
        if args.comando == "listar":
            for c in contrato.clausulas:
                pags = ", ".join(str(p + 1) for p in c.paginas)
                print(f"{c.rotulo:<70} pág. {pags}")

        elif args.comando == "ver":
            c = contrato.clausula(args.numero)
            print(f"== {c.rotulo} ==")
            for d in c.dispositivos:
                recuo = "    " if d.tipo == "alinea" else "  "
                print(f"\n{recuo}[{d.rotulo}]")
                for linha in d.texto.splitlines():
                    print(f"{recuo}{linha}")

        elif args.comando == "buscar":
            achados = contrato.buscar(args.termo)
            if not achados:
                print("Nada encontrado.")
            for c, linha in achados:
                print(f"[{c.rotulo} | pág. {linha.pagina + 1}] {linha.texto}")

        elif args.comando == "recortar":
            itens = [_item(contrato, s) for s in args.itens]
            destino = recortar(args.pdf, contrato, itens, args.saida)
            print(f"Recorte salvo em {destino}")

        elif args.comando == "perguntar":
            return _perguntar(args, contrato)

    except KeyError as erro:
        print(erro.args[0])
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
