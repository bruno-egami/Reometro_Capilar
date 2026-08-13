import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
from gui.utils import adjust_column_widths

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
        
        cols = ("ID", "Ponto", "P_Pasta (bar)", "P_Linha (bar)", "Massa (g)", "Duração (s)", "Correção", "Status")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings")
        
        for col in cols:
            self.tree.heading(col, text=col)
            width = 120 if col not in ["ID", "Ponto", "Status", "Correção"] else 65
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
            
            # Show regime values when available, with correction indicator
            ratio = p.get('ratio_integral')
            has_regime = ratio is not None and not (isinstance(ratio, float) and ratio != ratio)  # NaN check
            
            if has_regime:
                correcao_str = f"{ratio*100:.0f}%"
                p_pasta_show = p.get('pressao_pasta_regime_bar') or p['pressao_pasta_bar']
                p_linha_show = p.get('pressao_linha_regime_bar') or p['pressao_linha_bar']
                massa_show = p.get('massa_regime_g') or p['massa_g']
                duracao_show = p.get('duracao_regime_s') or p['duracao_s']
            else:
                correcao_str = "—"
                p_pasta_show = p['pressao_pasta_bar']
                p_linha_show = p['pressao_linha_bar']
                massa_show = p['massa_g']
                duracao_show = p['duracao_s']
            
            self.tree.insert("", "end", iid=str(p['id']), values=(
                p['id'], p['ponto_n'], 
                f"{p_pasta_show:.3f}", 
                f"{p_linha_show:.3f}", 
                f"{massa_show:.3f}", 
                f"{duracao_show:.1f}",
                correcao_str,
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
        """
        Detecta automaticamente outliers combinando dois critérios físicos/estatísticos:
        1. Divergência de vazão/taxa (>35%) entre réplicas no mesmo nível de pressão.
        2. Desvio relativo grave (>30%) em relação à curva de tendência global (Lei da Potência).
        """
        if len(self.points_data) < 3:
            messagebox.showwarning("Aviso", "Número insuficiente de pontos para detecção estatística (mín. 3).")
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
            
            processed_data = []
            
            for i, p in enumerate(self.points_data):
                ratio = p.get('ratio_integral')
                has_regime = ratio is not None and not (isinstance(ratio, float) and ratio != ratio)
                
                if has_regime:
                    massa = p.get('massa_regime_g') or p['massa_g']
                    tempo = p.get('duracao_regime_s') or p['duracao_s']
                    p_bar = p.get('pressao_pasta_regime_bar') or p['pressao_pasta_bar']
                else:
                    massa = p['massa_g']
                    tempo = p['duracao_s']
                    p_bar = p['pressao_pasta_bar']
                
                if tempo <= 0 or massa <= 0 or p_bar <= 0: 
                    continue
                
                Q_m3s = (massa / (Rho * tempo)) * 1e-6
                gd_app = (4 * Q_m3s) / (np.pi * R**3)
                p_pa = p_bar * 1e5
                tau_w = (p_pa * R) / (2 * L)
                
                # Round pressure to 1 decimal place to group replicates
                p_group = round(p_bar, 1)
                
                processed_data.append({
                    'original_index': i,
                    'ponto_n': p.get('ponto_n', i + 1),
                    'p_group': p_group,
                    'gd_app': gd_app,
                    'tau_w': tau_w
                })
            
            df = pd.DataFrame(processed_data)
            
            if df.empty or len(df) < 3:
                messagebox.showwarning("Aviso", "Dados válidos insuficientes para cálculo de outliers.")
                return

            outliers_set = set()
            
            # --- Critério 1: Discrepância entre réplicas no mesmo nível de pressão ---
            grouped_p = df.groupby('p_group')
            for p_val, group in grouped_p:
                if len(group) >= 2:
                    mean_gd = group['gd_app'].mean()
                    if mean_gd > 0:
                        for _, row in group.iterrows():
                            dev = abs(row['gd_app'] - mean_gd) / mean_gd
                            if dev > 0.35:  # Desvio > 35% da média de vazão do grupo
                                outliers_set.add(row['original_index'])
            
            # --- Critério 2: Ajuste inicial de tendência para achar pontos fora da curva geral ---
            try:
                # Regressão linear em log-log para aproximar Lei da Potência
                log_g = np.log(df['gd_app'].values)
                log_t = np.log(df['tau_w'].values)
                slope, intercept = np.polyfit(log_g, log_t, 1)
                
                # Predição de tau e resíduos relativos
                log_t_pred = intercept + slope * log_g
                residuos_rel = np.abs(np.exp(log_t) - np.exp(log_t_pred)) / np.exp(log_t_pred)
                
                for idx, res in zip(df['original_index'], residuos_rel):
                    if res > 0.30:  # Desvio > 30% em relação à tendência geral
                        outliers_set.add(int(idx))
            except Exception:
                pass
            
            # --- Critério 3: Violação de Monotonicidade Física (Efeito de Fim de Barril) ---
            # Em fluidos pseudoplásticos/Newtonianos, maior pressão DEVE gerar maior vazão.
            # Se a pressão aumentou, mas a vazão caiu drasticamente em relação à máxima atingida,
            # indica entupimento, secagem ou fim de material no barril.
            df_sorted = df.sort_values('p_group')
            max_gd_so_far = 0.0
            
            for idx, row in df_sorted.iterrows():
                gd = row['gd_app']
                if gd > max_gd_so_far:
                    max_gd_so_far = gd
                else:
                    # Se a vazão for menor que 70% da máxima já atingida em pressões menores,
                    # é uma queda física muito brusca e injustificada.
                    if gd < max_gd_so_far * 0.70:
                        outliers_set.add(int(row['original_index']))
                        
            outliers_found = 0
            for idx in outliers_set:
                if self.points_data[idx].get('ativo', 1) == 1:
                    self.points_data[idx]['ativo'] = 0
                    outliers_found += 1
            
            self.update_tree_visuals()
            
            if outliers_found > 0:
                messagebox.showinfo("Auto-Detecção", f"Foram detectados e desativados {outliers_found} ponto(s) atípico(s)/outlier(s).")
            else:
                messagebox.showinfo("Auto-Detecção", "Nenhum outlier estatístico detectado com os critérios atuais (desvio > 30% da curva ou > 35% em réplicas).")
            
        except Exception as e:
            messagebox.showerror("Erro", f"Falha na detecção de outliers: {e}")
            
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
