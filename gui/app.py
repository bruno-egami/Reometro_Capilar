import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta
import sys
import os

# Add project root to path (gui/app.py → gui/ → project root)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from database_manager import DatabaseManager
from reometer_controller import ReometerController

# Import Frames
from gui.frames.coleta import ColetaFrame
from gui.frames.historico import HistoricoFrame
from gui.frames.calibracao import CalibracaoFrame
from gui.frames.analise import AnaliseFrame
from gui.frames.correcoes import CorrecoesFrame

# Set appearance mode and default color theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Increase global font/widget scaling for better readability
ctk.set_widget_scaling(1.1) 
ctk.set_window_scaling(1.1)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Reômetro Capilar Control System")
        self.geometry("1100x700")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initialize Logic Components
        self.db = DatabaseManager()
        self.controller = ReometerController() 
        
        # Load latest calibration from DB into controller immediately
        cal = self.db.get_latest_calibracao()
        if cal:
            self.controller.load_calibration_linha(
                slope_l=cal.get('slope_linha', 1.0),
                intercept_l=cal.get('intercept_linha', 0.0)
            )
        
        # Grid Layout (1x2)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1) # Spacer row

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Reômetro\nDual Sensor", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_coleta = ctk.CTkButton(self.sidebar_frame, text="Nova Coleta", command=self.show_coleta)
        self.btn_coleta.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_historico = ctk.CTkButton(self.sidebar_frame, text="Histórico", command=self.show_historico)
        self.btn_historico.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_calibracao = ctk.CTkButton(self.sidebar_frame, text="Calibração", command=self.show_calibracao)
        self.btn_calibracao.grid(row=3, column=0, padx=20, pady=10)

        self.btn_analise = ctk.CTkButton(self.sidebar_frame, text="Análise", command=self.show_analise)
        self.btn_analise.grid(row=4, column=0, padx=20, pady=10)
        
        self.btn_correcoes = ctk.CTkButton(self.sidebar_frame, text="Correções", command=self.show_correcoes)
        self.btn_correcoes.grid(row=5, column=0, padx=20, pady=10)
        
        self.btn_conexao = ctk.CTkButton(self.sidebar_frame, text="Conectar Arduino", command=self.toggle_connection, fg_color="#1f6aa5")
        self.btn_conexao.grid(row=6, column=0, padx=20, pady=10)
        
        # Bottom Status
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Status: Inicializando...", text_color="gray")
        self.status_label.grid(row=7, column=0, padx=20, pady=20)

        # --- Main Area ---
        # Container for frames
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (ColetaFrame, HistoricoFrame, CalibracaoFrame, AnaliseFrame, CorrecoesFrame):
            frame_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[frame_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_coleta()
        
        # Start connection status check loop
        self.check_connection()
        
        # Auto-connect on startup
        self.after(500, self.auto_connect)

    def auto_connect(self):
        success, msg = self.controller.find_and_connect()
        if success:
            self.controller.start_reading()
            
    def toggle_connection(self):
        if self.controller.is_connected:
            self.controller.disconnect()
        else:
            success, msg = self.controller.find_and_connect()
            if success:
                self.controller.start_reading()
            else:
                tk.messagebox.showerror("Erro de Conexão", f"Não foi possível conectar: {msg}")

    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()
        
    def show_coleta(self): self.show_frame("ColetaFrame")
    def show_historico(self): self.show_frame("HistoricoFrame")
    def show_calibracao(self): self.show_frame("CalibracaoFrame")
    def show_analise(self): self.show_frame("AnaliseFrame")
    def show_correcoes(self): self.show_frame("CorrecoesFrame")

    def check_connection(self):
        """Periodically updates connection status label and checks calibration state."""
        # 1. Check Arduino Connection
        if self.controller.is_connected:
            self.status_label.configure(text="Arduino: Conectado", text_color="green")
            self.btn_conexao.configure(text="Desconectar Arduino", fg_color="red")
        else:
            self.status_label.configure(text="Arduino: Desconectado", text_color="red")
            self.btn_conexao.configure(text="Conectar Arduino", fg_color="#1f6aa5")
            
        # 2. Check Calibration Status (C11 Alert)
        cal = self.db.get_latest_calibracao()
        needs_cal = False
        msg = "⚠️ Sensor Não Calibrado"
        
        if not cal:
            needs_cal = True
        else:
            try:
                cal_date = datetime.strptime(cal['data'], "%Y-%m-%d %H:%M:%S")
                if datetime.now() - cal_date > timedelta(days=30):
                    needs_cal = True
                    msg = "⚠️ Calibração Antiga (>30 dias)"
            except (ValueError, KeyError):
                pass

        if needs_cal:
            if not hasattr(self, 'cal_alert_label'):
                self.cal_alert_label = ctk.CTkLabel(self.sidebar_frame, text=msg, text_color="orange", font=ctk.CTkFont(weight="bold"))
                self.cal_alert_label.grid(row=8, column=0, padx=20, pady=10)
            else:
                self.cal_alert_label.configure(text=msg)
        else:
            if hasattr(self, 'cal_alert_label'):
                self.cal_alert_label.destroy()
                del self.cal_alert_label

        self.after(2000, self.check_connection)

    def on_close(self):
        if self.controller.is_connected:
            self.controller.disconnect()
        self.destroy()
