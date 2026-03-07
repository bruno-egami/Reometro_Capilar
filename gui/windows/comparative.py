import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from customtkinter import CTkInputDialog
import pandas as pd
import numpy as np
import os
import tempfile
import shutil
from datetime import datetime
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

# Internal modules
import reologia_plot
import reologia_report_pdf
from reologia_io import carregar_csv_resultados, mapear_colunas_para_padrao, carregar_modelo_associado
from reologia_fitting import calcular_mape

class ComparativeAnalysisWindow(ctk.CTkToplevel):
    """Secondary window for comparing multiple rheological datasets."""
    
    def __init__(self, parent, dataset_list):
        super().__init__(parent)
        self.title("Análise Reológica Comparativa")
        self.geometry("1100x850")
        
        # Primary datasets from DB (as list of dicts)
        self.datasets = dataset_list
        self.external_datasets = [] # For rotational data
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # --- Top Panel: Selection and Actions ---
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        
        self.lbl_title = ctk.CTkLabel(self.top_frame, text="Configuração da Comparação", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title.pack(pady=10)
        
        self.ctrl_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.ctrl_frame.pack(fill="x", padx=10, pady=5)
        
        # Reference Selection for MAPE
        ctk.CTkLabel(self.ctrl_frame, text="Amostra de Referência (MAPE):").pack(side="left", padx=5)
        self.combo_ref = ctk.CTkComboBox(self.ctrl_frame, values=[d['nome'] for d in self.datasets], width=250)
        self.combo_ref.pack(side="left", padx=5)
        
        self.btn_add_ext = ctk.CTkButton(self.ctrl_frame, text="+ Adicionar Rotacional", 
                                          command=self._add_external_data, fg_color="#c45c22")
        self.btn_add_ext.pack(side="right", padx=5)
        
        # --- Middle Panel: Visualization Buttons ---
        self.viz_frame = ctk.CTkFrame(self)
        self.viz_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        self.lbl_info = ctk.CTkLabel(self.viz_frame, text="Selecione o tipo de gráfico comparativo:", font=ctk.CTkFont(size=14))
        self.lbl_info.pack(pady=10)
        
        self.btn_grid = ctk.CTkFrame(self.viz_frame, fg_color="transparent")
        self.btn_grid.pack(pady=10)
        
        plots = [
            ("Curva de Fluxo", "fluxo"),
            ("Viscosidade", "viscosidade"),
            ("Índice n'", "n_prime"),
            ("Pressão vs Visc", "pressao")
        ]
        
        for text, mode in plots:
            btn = ctk.CTkButton(self.btn_grid, text=text, height=60, width=200, 
                                 font=ctk.CTkFont(size=16, weight="bold"),
                                 command=lambda m=mode: self._show_plot(m))
            btn.pack(side="left", padx=10)
            
        # Analysis Stats Display
        self.txt_mape = ctk.CTkTextbox(self.viz_frame, height=150, font=("Consolas", 14))
        self.txt_mape.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt_mape.insert("1.0", "Execute um gráfico para ver a análise de erro (MAPE).")
        self.txt_mape.configure(state="disabled")
        
        # --- Bottom Panel: Export ---
        self.bot_frame = ctk.CTkFrame(self)
        self.bot_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        
        self.btn_export_pdf = ctk.CTkButton(self.bot_frame, text="Gerar Relatório PDF Comparativo", 
                                             command=self._export_pdf, fg_color="green", height=45)
        self.btn_export_pdf.pack(fill="x", padx=100)
        
        self.lift()
        self.focus_force()

    def _get_combined_data(self):
        """Combines DB datasets and external datasets for plotting/analysis."""
        all_data = {}
        all_models = {}
        
        # DB Data
        for d in self.datasets:
            nome = d['nome']
            data = d['data']
            # Reconstruct DataFrame
            n_val = data.get('n_prime', 1.0)
            
            # Safe retrieval of pressure mean (must match length of gamma_dot)
            pres_mean = data.get('pressao_mean')
            if pres_mean is None or len(pres_mean) != len(data['gamma_dot']):
                # Fallback: create array of same length using mean of raw pressure
                mean_p = data.get('raw_pressure', np.array([0])).mean()
                if np.isnan(mean_p): mean_p = 0
                pres_mean = np.full_like(data['gamma_dot'], mean_p)
            
            df = pd.DataFrame({
                'γ̇w (s⁻¹)': data['gamma_dot'],
                'τw (Pa)': data['tau_w'],
                'η (Pa·s)': data['eta'],
                'γ̇aw (s⁻¹)': data['gamma_dot'] / ((3*n_val+1)/(4*n_val)),
                'η_a (Pa·s)': data['tau_w'] / (data['gamma_dot'] / ((3*n_val+1)/(4*n_val))),
                'P (bar)': pres_mean
            })
            df['n_prime'] = n_val # Same for all points in this sample
            
            # Std Devs
            if 'tau_w_std' in data: df['τw_std (Pa)'] = data['tau_w_std']
            if 'eta_std' in data: df['η_std (Pa·s)'] = data['eta_std']
            
            all_data[nome] = df
            
            # Models
            best_model = data.get('best_model')
            if best_model and best_model in data.get('model_fits', {}):
                fit = data['model_fits'][best_model]
                if fit.get('params') is not None:
                    all_models[nome] = {
                        'Melhor Modelo': best_model,
                        'Parametros': fit['params'],
                        'R2': fit.get('r2', 0.0)
                    }
                    
        # External Data
        for d in self.external_datasets:
            all_data[d['nome']] = d['df']
            if d.get('modelo'):
                all_models[d['nome']] = d['modelo']
                
        return all_data, all_models

    def _add_external_data(self):
        """Opens file dialog to load processed rotational rheometer data."""
        
        initial_dir = os.path.join(os.getcwd(), "resultados_processados_interativo")
        if not os.path.exists(initial_dir): initial_dir = os.getcwd()
        
        filepath = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Selecionar Resultado Processado (Rotacional)",
            filetypes=[("CSV Files", "*.csv")]
        )
        
        if not filepath: return
        
        df = carregar_csv_resultados(filepath)
        if df is None:
            tk.messagebox.showerror("Erro", "Falha ao carregar o arquivo CSV.")
            return
            
        # Standardize
        df.columns = [c.lower() for c in df.columns]
        df_std, tipo = mapear_colunas_para_padrao(df, df.columns.tolist())
        
        # Load associated model
        modelo = carregar_modelo_associado(filepath)
        
        nome_sugerido = os.path.basename(filepath).replace("_processado.csv", "").replace(".csv", "")
        nome_legenda = CTkInputDialog(text=f"Nome para a legenda (Tipo: {tipo}):", title="Legenda").get_input()
        if not nome_legenda: nome_legenda = nome_sugerido
        
        self.external_datasets.append({
            'nome': nome_legenda,
            'df': df_std,
            'modelo': modelo
        })
        
        # Update combo values
        current_vals = list(self.combo_ref.cget("values"))
        current_vals.append(nome_legenda)
        self.combo_ref.configure(values=current_vals)
        
        tk.messagebox.showinfo("Sucesso", f"Dataset '{nome_legenda}' adicionado com sucesso.")
        self.lift()
        self.focus_force()

    def _show_plot(self, mode):
        """Generates and shows a comparative plot with error analysis."""
        
        all_data, all_models = self._get_combined_data()
        if not all_data: 
            tk.messagebox.showwarning("Aviso", "Nenhum dado disponível para plotagem.")
            return
        
        # 1. Update MAPE analysis
        self._update_mape_display(all_data)
        
        # 2. Configure plot based on mode
        config_map = {
            'fluxo': {
                'col_x': 'γ̇w (s⁻¹)', 'col_y': 'τw (Pa)', 'title': 'Curva de Fluxo (Comparativo)',
                'xl': r'$\dot{\gamma}$ (s$^{-1}$)', 'yl': r'$\tau_w$ (Pa)', 'log': True
            },
            'viscosidade': {
                'col_x': 'γ̇w (s⁻¹)', 'col_y': 'η (Pa·s)', 'title': 'Viscosidade vs Taxa (Comparativo)',
                'xl': r'$\dot{\gamma}$ (s$^{-1}$)', 'yl': r'$\eta$ (Pa·s)', 'log': True
            },
            'n_prime': {
                'col_x': 'γ̇w (s⁻¹)', 'col_y': 'n_prime', 'title': 'Índice n\' (Comparativo)',
                'xl': r'$\dot{\gamma}$ (s$^{-1}$)', 'yl': "Índice n\'", 'log': False
            },
            'pressao': {
                'col_x': 'η (Pa·s)', 'col_y': 'P (bar)', 'title': 'Pressão vs Viscosidade (Comparativo)',
                'xl': r'$\eta$ (Pa·s)', 'yl': 'Pressão (bar)', 'log': False
            }
        }
        
        cfg = config_map.get(mode)
        if not cfg: return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = tempfile.gettempdir()
        
        try:
            reologia_plot.plotar_comparativo_multiplo(
                dados_analises=all_data,
                coluna_x=cfg['col_x'],
                coluna_y=cfg['col_y'],
                titulo=cfg['title'],
                xlabel=cfg['xl'],
                ylabel=cfg['yl'],
                output_folder=temp_dir,
                timestamp_str=timestamp,
                usar_log=cfg['log'],
                show_plots=True,
                only_show=True,
                modelos_dict=all_models
            )
        except Exception as e:
            tk.messagebox.showerror("Erro ao Plotar", f"Ocorreu um erro ao gerar o gráfico:\n{str(e)}")
            # Print trace for debugging
            import traceback
            traceback.print_exc()

    def _update_mape_display(self, all_data):
        """Calculates and displays MAPE relative to chosen reference."""
        ref_name = self.combo_ref.get()
        if ref_name not in all_data:
            self._set_mape("Selecione uma amostra de referência válida para análise MAPE.")
            return
            
        ref_df = all_data[ref_name]
        # Reference values for Viscosity
        y_ref = ref_df['η (Pa·s)'].values
        x_ref = ref_df['γ̇w (s⁻¹)'].values
        
        text = f"--- ANÁLISE DE DISCREPÂNCIA (MAPE) ---\n"
        text += f"Referência: {ref_name}\n\n"
        text += f"{'Amostra':<30} | {'MAPE (%)':<10}\n"
        text += "─" * 45 + "\n"
        
        for name, df in all_data.items():
            if name == ref_name: continue
            
            # To compare, we need to interpolate the other data to the same reference X-points
            # or vice versa. Let's interpolate target onto reference points.
            x_target = df['γ̇w (s⁻¹)'].values
            y_target = df['η (Pa·s)'].values
            
            try:
                # Use interpolation to align points
                f_interp = interp1d(x_target, y_target, bounds_error=False, fill_value="extrapolate")
                y_compared = f_interp(x_ref)
                
                mape = calcular_mape(y_ref, y_compared)
                text += f"{name:<30} | {mape:>8.2f}%\n"
            except Exception:
                text += f"{name:<30} | Erro no cálculo\n"
                
        self._set_mape(text)

    def _set_mape(self, text):
        self.txt_mape.configure(state="normal")
        self.txt_mape.delete("1.0", "end")
        self.txt_mape.insert("1.0", text)
        self.txt_mape.configure(state="disabled")

    def _export_pdf(self):
        """Generates a complete comparative PDF report."""
        
        all_data, all_models = self._get_combined_data()
        if not all_data: return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_name = f"Relatorio_Comparativo_{timestamp}.pdf"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf", 
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=suggested_name,
            title="Salvar Relatório Comparativo"
        )
        if not filepath: return
        
        folder = os.path.dirname(filepath)
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Generate all 4 comparative plots as PNG using reologia_plot API
            lista_imgs = []
            
            configs = [
                ('γ̇w (s⁻¹)', 'τw (Pa)', 'Curva de Fluxo', r'$\dot{\gamma}$ (s$^{-1}$)', r'$\tau_w$ (Pa)', True),
                ('γ̇w (s⁻¹)', 'η (Pa·s)', 'Viscosidade', r'$\dot{\gamma}$ (s$^{-1}$)', r'$\eta$ (Pa·s)', True),
                ('γ̇w (s⁻¹)', 'n_prime', 'n_prime', r'$\dot{\gamma}$ (s$^{-1}$)', "Índice n\'", False),
                ('η (Pa·s)', 'P (bar)', 'Pressao_vs_Visc', r'$\eta$ (Pa·s)', 'Pressão (bar)', False)
            ]
            
            for cx, cy, tit, xl, yl, log in configs:
                f_name = reologia_plot.plotar_comparativo_multiplo(
                    dados_analises=all_data,
                    coluna_x=cx,
                    coluna_y=cy,
                    titulo=tit,
                    xlabel=xl,
                    ylabel=yl,
                    output_folder=temp_dir,
                    timestamp_str=timestamp,
                    usar_log=log,
                    show_plots=False,
                    only_show=False,
                    modelos_dict=all_models
                )
                if f_name: lista_imgs.append(f_name)
            
            # Prepare MAPE info for PDF
            ref_name = self.combo_ref.get()
            mape_rows = []
            if ref_name in all_data:
                ref_df = all_data[ref_name]
                x_ref, y_ref = ref_df['γ̇w (s⁻¹)'].values, ref_df['η (Pa·s)'].values
                for name, df in all_data.items():
                    if name == ref_name: continue
                    try:
                        f_interp = interp1d(df['γ̇w (s⁻¹)'].values, df['η (Pa·s)'].values, bounds_error=False, fill_value="extrapolate")
                        mape = calcular_mape(y_ref, f_interp(x_ref))
                        mape_rows.append({'Amostra': name, 'Referência': ref_name, 'MAPE (%)': mape})
                    except Exception: pass
            
            df_mape = pd.DataFrame(mape_rows)
            
            reologia_report_pdf.gerar_pdf_comparativo(
                output_folder=folder,
                timestamp_str=timestamp,
                dados_analises=all_data,
                lista_imgs=lista_imgs,
                df_mape=df_mape
            )
            
            # File renaming is handled by gerar_pdf_comparativo if we provide output_folder
            # but we might want to ensure it matches the user's picked name.
            # gerar_pdf_comparativo uses: f"{timestamp_str}_relatorio_comparativo.pdf"
            expected_name = os.path.join(folder, f"{timestamp}_relatorio_comparativo.pdf")
            if os.path.exists(expected_name) and expected_name != filepath:
                if os.path.exists(filepath): os.remove(filepath)
                os.rename(expected_name, filepath)

            tk.messagebox.showinfo("Sucesso", f"Relatório Comparativo PDF gerado em:\n{filepath}")
            
        except Exception as e:
            tk.messagebox.showerror("Erro ao Gerar PDF", f"Falha: {e}")
        finally:
            shutil.rmtree(temp_dir)
