import tkinter as tk
import tkinter.messagebox as messagebox
import os
import re

# CLASSE PER LANCIARE LA SIMULAZIONE E GESTIRE LA CONFIGURAZIONE
class ConfigDialog:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Setup mappa")
        self.root.geometry("400x380") 
        
        tk.Label(self.root, text="Configurazione iniziale", font=("Arial", 14, "bold")).pack(pady=10)
        
        # PARAMETRI
        self.e_nodi = self._make_entry("Numero vie (1-800):", "50")
        self.e_conn = self._make_entry("Connessioni/Nodo (1-20):", "3")
        self.e_corrieri = self._make_entry("Numero corrieri (1-10):", "1")
        
        # NUOVO CAMPO LINK
        self.e_link = self._make_entry("Link Webhook:", "")
        
        # Checkbox
        self.var_centro = tk.BooleanVar(value=False)
        self.chk_centro = tk.Checkbutton(self.root, text="Partire dal centro", 
                                         variable=self.var_centro, font=("Arial", 10))
        self.chk_centro.pack(pady=5)
        
        tk.Button(self.root, text="AVVIA SISTEMA", bg="#27ae60", fg="white", 
                  font=("Arial", 11, "bold"), command=self.go).pack(pady=15)
        
        self.res = None

    def _make_entry(self, txt, val):
        f = tk.Frame(self.root); f.pack(pady=4)
        tk.Label(f, text=txt, width=22, anchor="e").pack(side="left")
        e = tk.Entry(f, width=25); e.insert(0, val); e.pack(side="left")
        return e

    def aggiorna_files_con_link(self, link):
        """
        Modifica fisicamente i file config.py e funzioni_esp.h con il nuovo link.
        """
        # 1. Aggiorna Python (mappa/config.py)
        try:
            path_py = os.path.join(os.path.dirname(__file__), "mappa", "config.py")
            if os.path.exists(path_py):
                with open(path_py, 'r') as f: content = f.read()
                # Sostituisce WEBHOOK_URL = "..." con il nuovo link
                new_content = re.sub(r'WEBHOOK_URL\s*=\s*".*"', f'WEBHOOK_URL = "{link}"', content)
                with open(path_py, 'w') as f: f.write(new_content)
                print("[LAUNCHER] Link aggiornato in config.py")
        except Exception as e:
            print(f"[ERROR] Impossibile aggiornare config.py: {e}")

        # 2. Aggiorna C++ (../src/funzioni_esp.h)
        try:
            # Risale di una cartella da SCRIPT_PYTHON e entra in src
            path_cpp = os.path.join(os.path.dirname(__file__), "..", "src", "funzioni_esp.h")
            if os.path.exists(path_cpp):
                with open(path_cpp, 'r') as f: content = f.read()
                # Sostituisce const char* serverUrl = "..." con il nuovo link
                new_content = re.sub(r'const char\*\s*serverUrl\s*=\s*".*";', f'const char* serverUrl = "{link}";', content)
                with open(path_cpp, 'w') as f: f.write(new_content)
                print("[LAUNCHER] Link aggiornato in funzioni_esp.h")
        except Exception as e:
            print(f"[ERROR] Impossibile aggiornare funzioni_esp.h: {e}")

    def go(self):
        try:
            n = int(self.e_nodi.get())
            k = int(self.e_conn.get())
            c = int(self.e_corrieri.get())
            link = self.e_link.get().strip()

            # --- CORREZIONE AUTOMATICA LINK WEBHOOK ---
            # Se l'utente incolla il link della dashboard (con #!/view/), lo ripuliamo
            # Esempio input errato: https://webhook.site/#!/view/ID-UNICO/altro-id
            # Output corretto: https://webhook.site/ID-UNICO
            if "#!/view/" in link:
                try:
                    parts = link.split("#!/view/")
                    base_url = parts[0] # es: https://webhook.site/
                    ids = parts[1].split("/")
                    if ids:
                        # Ricostruisce il link corretto usando solo il primo ID (il token univoco)
                        link = base_url + ids[0]
                        print(f"[LAUNCHER] Link corretto automaticamente: {link}")
                except Exception as e:
                    print(f"[LAUNCHER] Errore nella pulizia del link: {e}")
            # ------------------------------------------

            start_center = self.var_centro.get()
            
            errori = []
            
            if not (1 <= n <= 800): errori.append("- Vie tra 1 e 800.")
            if not (1 <= k <= 20): errori.append("- Connessioni tra 1 e 20.")
            if not (1 <= c <= 10): errori.append("- Corrieri tra 1 e 10.")
            if not link.startswith("http"): errori.append("- Inserire un Link valido (http).")
            
            if errori:
                messagebox.showerror("Errore Parametri", "\n".join(errori))
                return 

            # AGGIORNA I FILE SORGENTI PRIMA DI PARTIRE
            self.aggiorna_files_con_link(link)

            # Restituisce i parametri incluso il link PULITO
            self.res = (n, k, c, start_center, link)
            self.root.destroy()
            
        except ValueError:
            messagebox.showerror("Errore", "Per favore inserisci solo numeri interi validi nei campi numerici.")

    def run(self):
        self.root.mainloop()
        return self.res