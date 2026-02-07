import sqlite3
import pandas as pd
from datetime import datetime
import os

class DatabaseManager:
    def __init__(self, db_name="reometria.db"):
        self.db_name = db_name
        self.conn = None
        self.init_db()

    def connect(self):
        """Establish connection to the database."""
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row # Access columns by name

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def init_db(self):
        """Initialize the database with the required tables."""
        self.connect()
        cursor = self.conn.cursor()

        # Table: Amostras
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS amostras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                descricao TEXT,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                d_capilar_mm REAL,
                l_capilar_mm REAL,
                densidade_g_cm3 REAL
            )
        ''')

        # Table: Calibracoes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calibracoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data DATETIME DEFAULT CURRENT_TIMESTAMP,
                slope_linha REAL NOT NULL,
                intercept_linha REAL NOT NULL,
                slope_pasta REAL NOT NULL,
                intercept_pasta REAL NOT NULL,
                ativa INTEGER DEFAULT 1
            )
        ''')

        # Table: Ensaios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ensaios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amostra_id INTEGER NOT NULL,
                ponto_n INTEGER NOT NULL,
                pressao_linha_bar REAL,
                pressao_pasta_bar REAL,
                massa_g REAL,
                duracao_s REAL,
                tensao_linha_v REAL,
                tensao_pasta_v REAL,
                data_coleta DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (amostra_id) REFERENCES amostras (id)
            )
        ''')

        self.conn.commit()
        self.close()

    # --- Amostras ---

    def add_amostra(self, nome, descricao, d_capilar, l_capilar, densidade):
        """Adds a new sample to the database."""
        self.connect()
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO amostras (nome, descricao, d_capilar_mm, l_capilar_mm, densidade_g_cm3)
                VALUES (?, ?, ?, ?, ?)
            ''', (nome, descricao, d_capilar, l_capilar, densidade))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Erro: Amostra com nome '{nome}' já existe.")
            return None
        finally:
            self.close()

    def get_amostra_by_name(self, nome):
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM amostras WHERE nome = ?", (nome,))
        row = cursor.fetchone()
        self.close()
        return dict(row) if row else None

    def list_amostras(self):
        """Returns a list of all samples."""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM amostras ORDER BY data_criacao DESC")
        rows = cursor.fetchall()
        self.close()
        return [dict(row) for row in rows]

    # --- Calibracoes ---

    def add_calibracao(self, slope_l, intercept_l, slope_p, intercept_p):
        """Adds a new calibration and sets it as active (logic to handle 'active' can be refined)."""
        self.connect()
        cursor = self.conn.cursor()
        
        # Optional: Set previous calibrations to inactive if we want to track 'current' in DB
        # For now, we just insert. The most recent one can be considered active.
        cursor.execute('''
            INSERT INTO calibracoes (slope_linha, intercept_linha, slope_pasta, intercept_pasta)
            VALUES (?, ?, ?, ?)
        ''', (slope_l, intercept_l, slope_p, intercept_p))
        
        calib_id = cursor.lastrowid
        self.conn.commit()
        self.close()
        return calib_id

    def get_latest_calibracao(self):
        """Returns the most recent calibration."""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM calibracoes ORDER BY data DESC LIMIT 1")
        row = cursor.fetchone()
        self.close()
        return dict(row) if row else None

    # --- Ensaios ---

    def add_ensaio(self, amostra_id, ponto_n, p_linha, p_pasta, massa, duracao, v_linha, v_pasta):
        """Adds a test point (ensaio) to a sample."""
        self.connect()
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ensaios (amostra_id, ponto_n, pressao_linha_bar, pressao_pasta_bar, 
                                     massa_g, duracao_s, tensao_linha_v, tensao_pasta_v)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (amostra_id, ponto_n, p_linha, p_pasta, massa, duracao, v_linha, v_pasta))
            self.conn.commit()
            return cursor.lastrowid
        finally:
            self.close()

    def get_ensaios_by_amostra(self, amostra_id):
        """Returns all test points for a given sample as a DataFrame (useful for analysis)."""
        self.connect()
        query = "SELECT * FROM ensaios WHERE amostra_id = ? ORDER BY ponto_n"
        df = pd.read_sql_query(query, self.conn, params=(amostra_id,))
        self.close()
        return df

    # --- Import Legacy JSON ---
    
    def import_json_legado(self, json_path):
        """
        Importa um arquivo JSON legado (do sistema de scripts) para o banco SQLite.
        
        Parâmetros:
            json_path : str - Caminho completo para o arquivo JSON
            
        Retorna:
            tuple: (sucesso: bool, mensagem: str, amostra_id: int ou None)
        """
        import json
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return False, f"Erro ao ler JSON: {e}", None
        
        # Extrair metadados da amostra
        nome = data.get('id_amostra', os.path.basename(json_path).replace('.json', ''))
        descricao = data.get('descricao', f"Importado de {os.path.basename(json_path)}")
        d_capilar = data.get('diametro_capilar_mm', 1.0)
        l_capilar = data.get('comprimento_capilar_mm', 43.0)
        densidade = data.get('densidade_pasta_g_cm3', 1.5)
        
        # Verificar se amostra já existe
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM amostras WHERE nome = ?', (nome,))
        existing = cursor.fetchone()
        
        if existing:
            self.close()
            return False, f"Amostra '{nome}' já existe no banco", None
        
        # Criar amostra
        try:
            cursor.execute('''
                INSERT INTO amostras (nome, descricao, d_capilar_mm, l_capilar_mm, densidade_g_cm3)
                VALUES (?, ?, ?, ?, ?)
            ''', (nome, descricao, d_capilar, l_capilar, densidade))
            amostra_id = cursor.lastrowid
        except Exception as e:
            self.close()
            return False, f"Erro ao criar amostra: {e}", None
        
        # Importar ensaios
        testes = data.get('testes', [])
        imported_count = 0
        
        for teste in testes:
            ponto_n = teste.get('ponto_n', imported_count + 1)
            
            # Usar pressao específica (pasta ou linha) ou fallback para pressao geral
            p_linha = teste.get('media_pressao_linha_bar', 
                               teste.get('media_pressao_final_ponto_bar', 0))
            p_pasta = teste.get('media_pressao_pasta_bar',
                               teste.get('media_pressao_final_ponto_bar', 0))
            
            massa = teste.get('massa_g_registrada', teste.get('massa_g', 0))
            duracao = teste.get('duracao_real_s', teste.get('duracao_s', 30.0))
            
            v_linha = teste.get('media_tensao_linha_V', 0)
            v_pasta = teste.get('media_tensao_pasta_V', 0)
            
            try:
                cursor.execute('''
                    INSERT INTO ensaios (amostra_id, ponto_n, pressao_linha_bar, pressao_pasta_bar,
                                        massa_g, duracao_s, tensao_linha_v, tensao_pasta_v)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (amostra_id, ponto_n, p_linha, p_pasta, massa, duracao, v_linha, v_pasta))
                imported_count += 1
            except Exception as e:
                print(f"Erro ao importar ponto {ponto_n}: {e}")
        
        self.conn.commit()
        self.close()
        
        return True, f"Importado: {nome} ({imported_count} pontos)", amostra_id
    
    def import_folder_json(self, folder_path):
        """
        Importa todos os arquivos JSON de uma pasta.
        
        Parâmetros:
            folder_path : str - Caminho da pasta
            
        Retorna:
            list: Lista de tuplas (arquivo, sucesso, mensagem)
        """
        import glob
        
        results = []
        json_files = glob.glob(os.path.join(folder_path, "*.json"))
        
        for json_file in json_files:
            success, msg, _ = self.import_json_legado(json_file)
            results.append((os.path.basename(json_file), success, msg))
        
        return results

if __name__ == "__main__":
    # Simple test
    db = DatabaseManager()
    print("Banco de dados inicializado.")
    
    # Test adding sample
    sid = db.add_amostra("Teste_01", "Amostra de teste", 1.0, 40.0, 1.5)
    if sid:
        print(f"Amostra criada com ID: {sid}")
        # Test adding data
        db.add_ensaio(sid, 1, 10.5, 10.2, 5.0, 30.0, 0.05, 0.05)
        print("Ensaio adicionado.")
        
        # Test retrieval
        df = db.get_ensaios_by_amostra(sid)
        print(df)
    else:
        print("Amostra já existia ou erro.")
