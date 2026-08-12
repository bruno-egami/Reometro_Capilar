import traceback
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("Starting imports")
try:
    import customtkinter as ctk
    from gui.frames.coleta import ColetaFrame
    from gui.frames.historico import HistoricoFrame
    from gui.frames.calibracao import CalibracaoFrame
    from gui.frames.analise import AnaliseFrame
    from gui.frames.correcoes import CorrecoesFrame
    from database_manager import DatabaseManager
    print("Imports done")
except Exception as e:
    print("Import error:", e)
    traceback.print_exc()
    import sys; sys.exit(1)

app = ctk.CTk()

class MockInnerController:
    is_connected = False
    
class MockController:
    def __init__(self):
        self.db = DatabaseManager()
        self.controller = MockInnerController()

c = MockController()
print('Starting creation')
try:
    print('ColetaFrame')
    f1 = ColetaFrame(app, c)
    assert hasattr(f1, 'table_container'), "ColetaFrame should have table_container"
    assert hasattr(f1, 'lbl_table_count'), "ColetaFrame should have lbl_table_count"
    f1.entry_amostra.insert(0, "TestSample")
    f1.update_summary_table()
    assert "coletas" in f1.lbl_table_count.cget("text")
    print('ColetaFrame summary table tests passed!')
    print('HistoricoFrame')
    f2 = HistoricoFrame(app, c)
    print('CalibracaoFrame')
    f3 = CalibracaoFrame(app, c)
    
    # Test label update without active calibration
    c.controller.linha_calibrada = False
    f3._update_labels_live(p_linha=3.5, p_pasta=4.2, v1=1.2345)
    assert f3.lbl_v1.cget("text") == "V_Linha: 1.2345 V", f"Expected 'V_Linha: 1.2345 V', got '{f3.lbl_v1.cget('text')}'"
    
    # Test label update with active calibration
    c.controller.linha_calibrada = True
    f3._update_labels_live(p_linha=3.5, p_pasta=4.2, v1=1.2345)
    assert f3.lbl_v1.cget("text") == "V_Linha: 1.2345 V (3.50 bar)", f"Expected 'V_Linha: 1.2345 V (3.50 bar)', got '{f3.lbl_v1.cget('text')}'"
    print('CalibracaoFrame label update tests passed!')

    print('AnaliseFrame')
    f4 = AnaliseFrame(app, c)
    print('CorrecoesFrame')
    f5 = CorrecoesFrame(app, c)
except Exception as e:
    print("Error during frame creation:", e)
    traceback.print_exc()

print('Done frames')
