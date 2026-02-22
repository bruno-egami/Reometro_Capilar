def read_reference_csv(filepath):
    """
    Lê um arquivo CSV exportado de reômetros rotacionais (ex: Anton Paar MCR)
    e retorna um dicionário com arrays numpy (Taxa, Tensão, Viscosidade).
    Tolerante a formatos numéricos pt-BR e nomes de colunas ruidosos.
    """
    import pandas as pd
    try:
        # A detecção com pandas resolve a maioria dos problemas de formatação
        df = pd.read_csv(filepath, sep=';', decimal=',', encoding='utf-8')
        df.columns = [str(c).strip() for c in df.columns]
        
        if len(df.columns) < 3:
            return None
            
        col_gd = df.columns[0]
        col_tau = df.columns[1]
        col_eta = df.columns[2]
        
        # Converte para numérico limpando strings de formatação BR
        for col in [col_gd, col_tau, col_eta]:
            if df[col].dtype == 'O':
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        df = df.dropna(subset=[col_gd, col_tau, col_eta])
        if len(df) == 0: return None
        
        return {
            'nome': os.path.basename(filepath),
            'gd': df[col_gd].values,
            'tau': df[col_tau].values,
            'eta': df[col_eta].values
        }
    except Exception as e:
        print(f"Erro ao carregar referência: {e}")
        return None
