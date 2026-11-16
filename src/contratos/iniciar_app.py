"""Comando `contratos-app`: abre a interface no navegador."""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PORTA = 8501


def main() -> int:
    app = Path(__file__).with_name("app.py")
    # headless=true evita o Streamlit pedir e-mail no terminal na primeira vez;
    # o navegador é aberto por nós logo abaixo.
    processo = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", str(app),
        f"--server.port={PORTA}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",
    ])
    time.sleep(3)
    webbrowser.open(f"http://localhost:{PORTA}")
    print(f"\nInterpretador aberto em http://localhost:{PORTA}")
    print("Para fechar o programa, feche esta janela.\n")
    try:
        return processo.wait()
    except KeyboardInterrupt:
        processo.terminate()
        return 0


if __name__ == "__main__":
    sys.exit(main())
