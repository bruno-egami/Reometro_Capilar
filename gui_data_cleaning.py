import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
from gui_utils import adjust_column_widths

class DataCleaningWindow(ctk.CTkToplevel):
    def __init__(self, parent, db, amostra_id, on_save_callback=None):
        super().__init__(parent)
        self.db = db
        self.amostra_id = amostra_id
        self.on_save_callback = on_save_callback
        
        # Sample Info
        amostras = self.db.list_amostras()
        self.amostra = next((a for a in amostras if a['id'] == self.amostra_id), None)
        nome_amostra = self.amostra['nome'] if self.amostra else f"ID {amostra_id}"
        
        self.title(f"Limpeza de Dados - {nome_amostra}")
        self.geometry("900x600")
        self.after(200, lambda: self.focus_force())
        
        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        self.header = ctk.CTkLabel(self, text=f"Gerenciamento de Pontos: {nome_amostra}", 
                                   font=ctk.CTkFont(size=20, weight="bold"))
        self.header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Treeview for points
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        cols = ("ID", "Ponto", "P_Pasta (bar)", "P_Linha (bar)", "Massa (g)", "Duração (s)", "Status")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings")
        
        for col in cols:
            self.tree.heading(col, text=col)
            width = 120 if col not in ["ID", "Ponto", "Status"] else 60
            self.tree.column(col, width=width, anchor="center")
            
        self.tree.pack(side="left", fill="both", expand=True)
        
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Buttons Frame
        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        
        self.btn_toggle = ctk.CTkButton(self.btn_frame, text="Ativar/Desativar Selecionados", 
                                        command=self.toggle_selected, fg_color="gray")
        self.btn_toggle.pack(side="left", padx=10)
        
        self.btn_auto = ctk.CTkButton(self.btn_frame, text="Auto-Detectar Outliers (IQR)", 
                                      command=self.auto_detect_outliers, fg_color="orange")
        self.btn_auto.pack(side="left", padx=10)
        
        self.btn_save = ctk.CTkButton(self.btn_frame, text="Salvar e Fechar", 
                                      command=self.save_and_close, fg_color="green")
        self.btn_save.pack(side="right", padx=10)
        
        self.btn_cancel = ctk.CTkButton(self.btn_frame, text="Cancelar", 
                                        command=self.destroy, fg_color="red")
        self.btn_cancel.pack(side="right", padx=10)
        
        # Load Data
        self.points_data = [] # List of dicts with current state
        self.refresh_tree()

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Get all points (including inactive)
        df = self.db.get_ensaios_by_amostra(self.amostra_id, apenas_ativos=False)
        self.points_data = df.to_dict('records')
        
        for p in self.points_data:
            status = "Ativo" if p.get('ativo', 1) == 1 else "Excluído"
            tags = ("inactive",) if status == "Excluído" else ()
            
            self.tree.insert("", "end", iid=str(p['id']), values=(
                p['id'], p['ponto_n'], 
                f"{p['pressao_pasta_bar']:.3f}", 
                f"{p['pressao_linha_bar']:.3f}", 
                f"{p['massa_g']:.3f}", 
                f"{p['duracao_s']:.1f}",
                status
            ), tags=tags)
            
        self.tree.tag_configure("inactive", foreground="red")
        
        # UI optimization: adjust columns
        adjust_column_widths(self.tree)

    def toggle_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
            
        for sid in selected:
            # Find in local data
            for p in self.points_data:
                if str(p['id']) == sid:
                    p['ativo'] = 0 if p.get('ativo', 1) == 1 else 1
                    break
        
        self.update_tree_visuals()

    def update_tree_visuals(self):
        """Update tags and status column based on local points_data."""
        for p in self.points_data:
            sid = str(p['id'])
            status = "Ativo" if p.get('ativo', 1) == 1 else "Excluído"
            self.tree.set(sid, "Status", status)
            if status == "Excluído":
                self.tree.item(sid, tags=("inactive",))
            else:
                self.tree.item(sid, tags=())

    def auto_detect_outliers(self):
        """Implement IQR method to suggest outliers, grouped by Shear Rate (similar to script 2b)."""
        if len(self.points_data) < 4:
            messagebox.showwarning("Aviso", "Número insuficiente de pontos para detecção estatística (mín. 4).")
            return
            
        try:
            D_mm = self.amostra['d_capilar_mm']
            L_mm = self.amostra['l_capilar_mm']
            Rho = self.amostra['densidade_g_cm3']
            
            if not Rho or Rho <= 0:
                messagebox.showerror("Erro", "Densidade inválida na amostra.")
                return

            R = (D_mm / 2.0) / 1000.0
            L = L_mm / 1000.0
            
            # Prepare data for processing
            processed_data = []
            
            for i, p in enumerate(self.points_data):
                massa = p['massa_g']
                tempo = p['duracao_s']
                p_bar = p['pressao_pasta_bar']
                
                # Skip invalid physics
                if tempo <= 0 or massa <= 0 or p_bar <= 0: 
                    continue
                
                # Calculate fundamental rheological properties
                Q_m3s = (massa / (Rho * tempo)) * 1e-6
                gd_app = (4 * Q_m3s) / (np.pi * R**3)
                p_pa = p_bar * 1e5
                tau_w = (p_pa * R) / (2 * L)
                
                # Log grouping key (round to 1 decimal place)
                log_gd = round(np.log10(gd_app), 1)
                
                processed_data.append({
                    'original_index': i,
                    'log_gd': log_gd,
                    'tau_w': tau_w
                })
            
            df = pd.DataFrame(processed_data)
            
            if df.empty:
                messagebox.showwarning("Aviso", "Não foi possível calcular propriedades reológicas (dados inválidos).")
                return

            outliers_found = 0
            
            # Group by Shear Rate (log_gd) and apply IQR per group
            grouped = df.groupby('log_gd')
            
            for log_val, group in grouped:
                # Need at least 3 points to calculate meaningful statistics
                if len(group) < 3:
                    continue
                    
                vals = group['tau_w'].values
                Q1 = np.percentile(vals, 25)
                Q3 = np.percentile(vals, 75)
                IQR = Q3 - Q1
                
                # Script 2b uses 1.5 * IQR
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                
                # Identify outliers in this group
                outliers_mask = (vals < lower) | (vals > upper)
                outliers_indices = group.loc[outliers_mask, 'original_index'].tolist()
                
                # Deactivate found outliers
                for idx in outliers_indices:
                    # Only count if it was currently active
                    if self.points_data[idx].get('ativo', 1) == 1:
                        self.points_data[idx]['ativo'] = 0
                        outliers_found += 1
            
            self.update_tree_visuals()
            
            if outliers_found > 0:
                messagebox.showinfo("Auto-Detecção", f"Foram detectados e desativados {outliers_found} potenciais outliers.")
            else:
                messagebox.showinfo("Auto-Detecção", "Nenhum outlier estatístico detectado com os critérios atuais (IQR 1.5x por grupo de taxa).")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Erro", f"Erro ao processar outliers: {e}")

    def save_and_close(self):
        # Update database
        success = True
        for p in self.points_data:
            if not self.db.update_ensaio_status(p['id'], p['ativo'] == 1):
                success = False
                
        if success:
            if self.on_save_callback:
                self.on_save_callback()
            self.destroy()
        else:
            messagebox.showerror("Erro", "Ocorreu um erro ao salvar algumas alterações no banco de dados.")
