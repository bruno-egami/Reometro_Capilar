import traceback
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
    print('HistoricoFrame')
    f2 = HistoricoFrame(app, c)
    print('CalibracaoFrame')
    f3 = CalibracaoFrame(app, c)
    print('AnaliseFrame')
    f4 = AnaliseFrame(app, c)
    print('CorrecoesFrame')
    f5 = CorrecoesFrame(app, c)
except Exception as e:
    print("Error during frame creation:", e)
    traceback.print_exc()

print('Done frames')
