import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "semaforo.db"
NOME_SAIDA = f"dados_semaforo_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"


def exportar():
    conn = sqlite3.connect(DB_PATH)

    # Cada leitura vira um DataFrame do pandas (tabela em memória, fácil de manipular)
    df_deteccoes = pd.read_sql_query("SELECT * FROM deteccoes ORDER BY id", conn)
    df_tempos = pd.read_sql_query("SELECT * FROM tempos_calculados ORDER BY id", conn)
    df_sync = pd.read_sql_query("SELECT * FROM sincronizacoes_horario ORDER BY id", conn)

    conn.close()

    # ExcelWriter permite escrever várias abas (sheets) no mesmo arquivo
    with pd.ExcelWriter(NOME_SAIDA, engine="openpyxl") as writer:
        df_deteccoes.to_excel(writer, sheet_name="Deteccoes", index=False)
        df_tempos.to_excel(writer, sheet_name="Tempos Calculados", index=False)
        df_sync.to_excel(writer, sheet_name="Sincronizacoes Horario", index=False)

    print(f"Arquivo gerado: {NOME_SAIDA}")
    print(f"  - Deteccoes: {len(df_deteccoes)} linhas")
    print(f"  - Tempos Calculados: {len(df_tempos)} linhas")
    print(f"  - Sincronizacoes Horario: {len(df_sync)} linhas")


if __name__ == "__main__":
    exportar()