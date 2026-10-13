import os
import sqlite3
import pandas as pd
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PASTA, "semaforo.db")
NOME_SAIDA = os.path.join(PASTA, f"dados_semaforo_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")

def exportar():
    conn = sqlite3.connect(DB_PATH)

    # Cada leitura vira um DataFrame do pandas (tabela em memória, fácil de manipular)
    df_deteccoes = pd.read_sql_query("SELECT * FROM deteccoes ORDER BY id", conn)

    # Os tempos de verde são calculados pelo ESP32 e devolvidos ao servidor.
    # A coluna enviado_com_sucesso fica de fora: o registro só existe quando o ESP32
    # devolveu os tempos, então ela vale sempre 1 e não traz informação para a análise.
    df_tempos = pd.read_sql_query(
        """SELECT id, tempo_via1, tempo_via2, carros_via1, carros_via2, timestamp
           FROM tempos_calculados ORDER BY id""",
        conn,
    )

    conn.close()

    # ExcelWriter permite escrever várias abas (sheets) no mesmo arquivo
    with pd.ExcelWriter(NOME_SAIDA, engine="openpyxl") as writer:
        df_deteccoes.to_excel(writer, sheet_name="Deteccoes", index=False)
        df_tempos.to_excel(writer, sheet_name="Tempos Calculados", index=False)

    print(f"Arquivo gerado: {NOME_SAIDA}")
    print(f"  - Deteccoes: {len(df_deteccoes)} linhas")
    print(f"  - Tempos Calculados: {len(df_tempos)} linhas")


if __name__ == "__main__":
    exportar()