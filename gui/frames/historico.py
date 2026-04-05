import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from gui.utils import adjust_column_widths

class HistoricoFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.db = controller.db
        
        self.label = ctk.CTkLabel(self, text="Histórico de Amostras", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20, padx=20, anchor="w")
        
        # Treeview Scrollbar
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Define columns
        cols = ("ID", "Nome", "Descrição", "Data", "Ensaios")
        
        # Configure Treeview Style for larger font
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 12), rowheight=30)
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"))
        
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings")
        
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Button frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=10)
        
        self.btn_refresh = ctk.CTkButton(btn_frame, text="Atualizar", command=self.refresh_list)
        self.btn_refresh.pack(side="left", padx=5)
        
        self.btn_import_file = ctk.CTkButton(btn_frame, text="Importar JSON / CSV", 
                                              command=self.import_single_file, fg_color="green")
        self.btn_import_file.pack(side="left", padx=5)
        
        self.btn_import_folder = ctk.CTkButton(btn_frame, text="Importar Pasta", 
                                                command=self.import_folder_json, fg_color="orange")
        self.btn_import_folder.pack(side="left", padx=5)

        self.btn_delete = ctk.CTkButton(btn_frame, text="Excluir Amostra", 
                                         command=self.delete_sample, fg_color="red")
        self.btn_delete.pack(side="left", padx=5)

        self.btn_edit = ctk.CTkButton(btn_frame, text="Editar Amostra", 
                                         command=self.edit_sample, fg_color="#3b8ed0")
        self.btn_edit.pack(side="left", padx=5)
        
        self.tree.bind("<Double-1>", lambda e: self.edit_sample())

        self.refresh_list()
    
    def import_single_file(self):
        """Import a single JSON or CSV file."""
        filepath = filedialog.askopenfilename(
            title="Selecionar Arquivo",
            initialdir="resultados_processados_interativo",
            filetypes=[("Arquivos", "*.json *.csv"), ("JSON files", "*.json"), ("CSV files", "*.csv")]
        )
        
        if filepath:
            if filepath.lower().endswith('.csv'):
                success, msg, _ = self.db.import_csv_rotacional(filepath)
            else:
                success, msg, _ = self.db.import_json_legado(filepath)
                
            if success:
                messagebox.showinfo("Sucesso", msg)
                self.refresh_list()
            else:
                messagebox.showerror("Erro", msg)
    
    def import_folder_json(self):
        """Import all JSON files from a folder."""
        folder = filedialog.askdirectory(
            title="Selecionar Pasta com JSONs",
            initialdir="resultados_testes_reometro"
        )
        
        if folder:
            results = self.db.import_folder_json(folder)
            
            # Build summary
            success_count = sum(1 for _, s, _ in results if s)
            fail_count = len(results) - success_count
            
            # Build detailed message
            details = "\n".join([f"{'✓' if s else '✗'} {f}: {m}" for f, s, m in results[:10]])
            if len(results) > 10:
                details += f"\n... e mais {len(results) - 10} arquivos"
            
            messagebox.showinfo("Importação Concluída", 
                               f"Importados: {success_count}\nFalhas: {fail_count}\n\n{details}")
            self.refresh_list()

    def refresh_list(self):
        # Clear
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Fetch data in two efficient queries
        amostras = self.db.list_amostras()
        counts = self.db.get_ensaio_counts()
        
        for a in amostras:
            count = counts.get(a['id'], 0)
            self.tree.insert("", "end", iid=str(a['id']), values=(a['id'], a['nome'], a['descricao'], a['data_criacao'], count))
        
        # Auto-adjust column widths
        adjust_column_widths(self.tree)

    def delete_sample(self):
        """Deletes the selected sample from the history."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione uma amostra para excluir.")
            return
            
        amostra_id = int(selected[0])
        amostra_nome = self.tree.item(selected[0], "values")[1]
        
        if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir a amostra '{amostra_nome}'?\n\nIsso apagará permanentemente todos os ensaios e análises vinculadas!"):
            if self.db.delete_amostra(amostra_id):
                messagebox.showinfo("Sucesso", f"Amostra '{amostra_nome}' excluída.")
                self.refresh_list()
            else:
                messagebox.showerror("Erro", "Não foi possível excluir a amostra.")
    
    def edit_sample(self):
        """Opens a dialog to edit the selected sample's name and description."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione uma amostra para editar.")
            return
            
        amostra_id = int(selected[0])
        item_vals = self.tree.item(selected[0], "values")
        current_nome = item_vals[1]
        current_desc = item_vals[2]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Editar Amostra")
        dialog.geometry("400x300")
        dialog.grab_set()
        
        # Centraliza a janela em relação ao aplicativo principal
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 200
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 150
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dialog, text="Nome da Amostra:").pack(pady=(20, 5), padx=20, anchor="w")
        entry_nome = ctk.CTkEntry(dialog, width=360)
        entry_nome.pack(pady=5, padx=20)
        entry_nome.insert(0, current_nome)

        ctk.CTkLabel(dialog, text="Descrição:").pack(pady=(10, 5), padx=20, anchor="w")
        entry_desc = ctk.CTkTextbox(dialog, width=360, height=80)
        entry_desc.pack(pady=5, padx=20)
        entry_desc.insert("1.0", current_desc)

        def save_changes():
            new_nome = entry_nome.get().strip()
            new_desc = entry_desc.get("1.0", "end-1c").strip()
            
            if not new_nome:
                messagebox.showerror("Erro", "O nome da amostra não pode ser vazio.", parent=dialog)
                return
                
            if self.db.update_amostra(amostra_id, new_nome, new_desc):
                messagebox.showinfo("Sucesso", "Amostra atualizada com sucesso.", parent=dialog)
                dialog.destroy()
                self.refresh_list()
            else:
                messagebox.showerror("Erro", "Falha ao atualizar a amostra. Verifique se o nome já existe e é válido.", parent=dialog)

        btn_save = ctk.CTkButton(dialog, text="Salvar", command=save_changes)
        btn_save.pack(pady=20)

    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        self.refresh_list() # Auto refresh when shown
