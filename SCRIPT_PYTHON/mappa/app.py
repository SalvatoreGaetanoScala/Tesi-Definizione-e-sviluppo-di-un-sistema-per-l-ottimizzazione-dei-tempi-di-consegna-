# Questo è il file principale che gestisce 
# l'applicazione, importando le funzionalità dagli altri moduli.

import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as messagebox
import random   
import math
import json
import csv
import io
import os
import urllib.request
import urllib.error
from datetime import datetime 
from vie import NOMI_VIE
from seriale import SerialManager

# Import moduli locali
from .config import *
from .algorithms import genera_grafo_mappa, dijkstra_shortest_path
from .gui_utils import mostra_finestra_lista_vie, mostra_finestra_corrieri

class MappaApp:
    def __init__(self, root, num_stelle, num_connessioni, num_corrieri, start_from_center, webhook_url):
        self.root = root
        self.root.title("Digital Twin: Security Control v3")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        
        # PARAMETRI UTENTE
        self.BASE_CELL_SIZE = CELL_SIZE
        self.NUM_STELLE = num_stelle
        self.NUM_CONNESSIONI = num_connessioni
        self.NUM_CORRIERI = num_corrieri
        self.START_FROM_CENTER = start_from_center
        self.WEBHOOK_URL_DYNAMIC = webhook_url # Usa il link passato dal launcher
        
        # DATI MAPPA
        self.mappa_dati = {}
        self.adj = {}
        self.zoom_level = 1.0 
        
        # DATI CORRIERI E STORICO
        self.storico_consegne = [] 
        self.ts1_arrivo = None     
        
        # NAVIGATORE
        self.nav_id = None
        self.nav_node = None
        self.nav_target = None
        self.nav_x = 0.0
        self.nav_y = 0.0
        self.last_node = None
        self.current_angle = 0.0 
        
        # INTERATTIVITÀ UTENTE
        self.selected_node_id = None
        
        # PERCORSO PIANIFICATO
        self.planned_path = []      
        self.final_destination = None 
        
        # STATI
        self.system_active = False       
        self.waiting_for_delivery = False 
        self.pot_speed_kmh = 0.0             
        self.follow_mode = True          
        self.last_sent_status = ""       
        
        # CANVAS
        self.canvas = tk.Canvas(root, bg=BG_CANVAS)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.config(scrollregion=(0, 0, C*self.BASE_CELL_SIZE, R*self.BASE_CELL_SIZE))
        
        # Inizializzazione Logica
        self._init_map_logic()
        self._init_navigator()
        self._setup_gui()
        
        # BINDINGS CANVAS
        self.canvas.bind("<ButtonPress-1>", self.on_down)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.tag_bind("nodo", "<ButtonPress-1>", self.on_node_click)

        self.serial = SerialManager(self)
        self.serial.start()
        self.animate_loop()

    def _init_map_logic(self):
        """Usa il modulo algorithms per generare i dati e poi disegna"""
        self.mappa_dati, self.adj, visual_edges = genera_grafo_mappa(
            R, C, self.BASE_CELL_SIZE, self.NUM_STELLE, self.NUM_CONNESSIONI, NOMI_VIE
        )
        
        # Disegno Connessioni (Strade)
        for (x1, y1, x2, y2) in visual_edges:
            self.canvas.create_line(x1, y1, x2, y2, fill=COLOR_STREET, width=2, tags="strada_base")
            
        # Disegno Nodi
        for (r,c) in self.mappa_dati:
            x = c * self.BASE_CELL_SIZE
            y = r * self.BASE_CELL_SIZE
            self.canvas.create_oval(x+5, y+5, x+self.BASE_CELL_SIZE-5, y+self.BASE_CELL_SIZE-5, 
                                    fill=COLOR_NODE_FILL, outline=COLOR_NODE_OUTLINE, tags=("nodo", f"node_{r}_{c}"))

    def _init_navigator(self):
        """Inizializza la posizione del corriere (Random o Centro)"""
        if not self.mappa_dati: return
        
        start_node = None

        if self.START_FROM_CENTER:
            center_r = R // 2
            center_c = C // 2
            min_dist = float('inf')
            for (r, c) in self.mappa_dati.keys():
                dist = (r - center_r)**2 + (c - center_c)**2
                if dist < min_dist:
                    min_dist = dist
                    start_node = (r, c)
            print(f"Spawn al centro: Nodo {start_node} (distanza {math.sqrt(min_dist):.1f})")
        else:
            start_node = random.choice(list(self.mappa_dati.keys()))
            print(f"Spawn Random: Nodo {start_node}")

        self.nav_node = start_node
        
        tag = f"node_{start_node[0]}_{start_node[1]}"
        bbox = self.canvas.coords(tag)
        if bbox:
            self.nav_x, self.nav_y = (bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2
        else:
            self.nav_x = start_node[1]*self.BASE_CELL_SIZE + self.BASE_CELL_SIZE//2
            self.nav_y = start_node[0]*self.BASE_CELL_SIZE + self.BASE_CELL_SIZE//2
            
        self.nav_id = self.canvas.create_polygon(0,0,0,0,0,0, fill=COLOR_NAVIGATOR, outline="white", width=3)
        self._upd_gfx(0)
        self.root.after(500, self.center_view)

    def _setup_gui(self):
        # Pulsanti controllo sistema (Alto DX)
        f_dx = tk.Frame(self.root, bg=BG_FRAME)
        f_dx.place(relx=0.98, rely=0.02, anchor="ne")
        self.btn_s = tk.Button(f_dx, text="▶ AVVIA MOTORE", bg="green", fg="white", command=self.start_system)
        self.btn_s.pack(pady=2, fill="x")
        self.btn_f = tk.Button(f_dx, text="SBLOCCA VISUALE", bg="red", fg="white", command=self.toggle_follow)
        self.btn_f.pack(pady=2, fill="x")
        
        # --- BARRA SUPERIORE CENTRALE ---
        f_center = tk.Frame(self.root, bg=BG_FRAME, bd=1, relief="raised")
        f_center.place(relx=0.5, rely=0.02, anchor="n")
        
        # 1. Selettore Microcontrollore
        tk.Label(f_center, text="Microcontrollore:", bg=BG_FRAME, fg="white", font=("Arial", 9)).pack(side="left", padx=5, pady=2)
        esp_list = [f"ESP{i+1}" for i in range(self.NUM_CORRIERI)]
        self.combo_esp = ttk.Combobox(f_center, values=esp_list, state="readonly", width=8)
        if esp_list: self.combo_esp.current(0)
        self.combo_esp.pack(side="left", padx=5, pady=2)

        # 2. Selettore Tipo Salvataggio
        tk.Label(f_center, text="| Tipo salvataggio:", bg=BG_FRAME, fg="#ddd", font=("Arial", 9)).pack(side="left", padx=5, pady=2)
        self.combo_tipo_save = ttk.Combobox(f_center, values=["JSON", "CSV"], state="readonly", width=6)
        self.combo_tipo_save.current(0) 
        self.combo_tipo_save.pack(side="left", padx=5, pady=2)

        # Label Stato (Alto SX)
        self.lbl_h = tk.Label(self.root, text="SISTEMA OFF", bg="black", fg="#0f0", font=("Consolas", 10), justify="left")
        self.lbl_h.place(relx=0.02, rely=0.02)

        # Pulsante Lista Vie
        self.btn_list = tk.Button(self.root, text="📜 LISTA VIE", bg="#444", fg="white", font=("Arial", 9), command=lambda: mostra_finestra_lista_vie(self.root, self.mappa_dati))
        self.btn_list.place(relx=0.02, rely=0.08)

        # Pulsante Corrieri
        self.btn_corrieri = tk.Button(self.root, text="🚚 CORRIERI", bg="#d35400", fg="white", font=("Arial", 9), command=lambda: mostra_finestra_corrieri(self.root, self.storico_consegne))
        self.btn_corrieri.place(relx=0.02, rely=0.14)

        # --- AREA DI RICERCA ---
        search_frame = tk.Frame(self.root, bg="#222", bd=2, relief="groove")
        search_frame.place(relx=0.5, rely=0.92, anchor="center")
        
        tk.Label(search_frame, text="Cerca Via:", fg="white", bg="#222").pack(side="left", padx=5)
        self.entry_search = tk.Entry(search_frame, width=25)
        self.entry_search.pack(side="left", padx=5)
        
        self.entry_search.bind("<KeyRelease>", self.aggiorna_suggerimenti)
        self.entry_search.bind("<Return>", self.conferma_selezione_tastiera)
        self.entry_search.bind("<Down>", self.naviga_suggerimenti)
        self.entry_search.bind("<Up>", self.naviga_suggerimenti)
        
        btn_cerca = tk.Button(search_frame, text="Vai a Destinazione", bg="#6a0dad", fg="white", command=self.esegui_ricerca)
        btn_cerca.pack(side="left", padx=5)

        self.lista_suggerimenti = tk.Listbox(self.root, width=35, height=5, font=("Arial", 10))
        self.lista_suggerimenti.bind("<<ListboxSelect>>", self.seleziona_suggerimento_mouse)

        self.lbl_click_info = tk.Label(self.root, text="", bg="#111", fg="yellow", font=("Arial", 11, "bold"))
        self.lbl_click_info.place(relx=0.5, rely=0.97, anchor="center")

    def on_node_click(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(canvas_x, canvas_y)[0]
        tags = self.canvas.gettags(item)
        
        node_tag = None
        for t in tags:
            if t.startswith("node_"):
                node_tag = t
                break
        
        if not node_tag: return "break"

        try:
            _, r_str, c_str = node_tag.split("_")
            r, c = int(r_str), int(c_str)
        except ValueError: return "break"

        if self.selected_node_id:
            self.canvas.itemconfig(self.selected_node_id, fill=COLOR_NODE_FILL, outline=COLOR_NODE_OUTLINE)
        
        self.canvas.itemconfig(item, fill="yellow", outline="orange")
        self.selected_node_id = item
        
        if (r,c) in self.mappa_dati:
            nome_via = self.mappa_dati[(r,c)]["via"]
            self.lbl_click_info.config(text=f"📍 Hai cliccato: {nome_via} (Nodo {r},{c})")
        
        return "break"

    # --- GESTIONE RICERCA ---
    def aggiorna_suggerimenti(self, event):
        if event.keysym in ["Return", "Escape", "Up", "Down"]: return
        digitato = self.entry_search.get().strip().lower()
        if not digitato:
            self.lista_suggerimenti.place_forget()
            return
        vie_disponibili = [info["via"] for info in self.mappa_dati.values()]
        suggerimenti = sorted(list(set([via for via in vie_disponibili if via.lower().startswith(digitato)])))
        self.lista_suggerimenti.delete(0, tk.END)
        for via in suggerimenti: self.lista_suggerimenti.insert(tk.END, via)
        if suggerimenti:
            h = min(len(suggerimenti), 6)
            self.lista_suggerimenti.config(height=h)
            self.lista_suggerimenti.place(relx=0.5, rely=0.89, anchor="s")
            self.lista_suggerimenti.lift()
        else:
            self.lista_suggerimenti.place_forget()

    def naviga_suggerimenti(self, event):
        if not self.lista_suggerimenti.winfo_ismapped(): return
        size = self.lista_suggerimenti.size()
        if size == 0: return
        cur_sel = self.lista_suggerimenti.curselection()
        if not cur_sel:
            index = 0 if event.keysym == 'Down' else size - 1
        else:
            index = cur_sel[0]
            if event.keysym == 'Down': index = min(index + 1, size - 1)
            elif event.keysym == 'Up': index = max(index - 1, 0)
        self.lista_suggerimenti.selection_clear(0, tk.END)
        self.lista_suggerimenti.selection_set(index)
        self.lista_suggerimenti.see(index)
        self.lista_suggerimenti.activate(index)
        return "break"

    def conferma_selezione_tastiera(self, event):
        if self.lista_suggerimenti.winfo_ismapped():
            cur_sel = self.lista_suggerimenti.curselection()
            if cur_sel:
                via_scelta = self.lista_suggerimenti.get(cur_sel[0])
                self.imposta_via_e_cerca(via_scelta)
                return "break"
        self.esegui_ricerca()
        return "break"

    def seleziona_suggerimento_mouse(self, event):
        selezione = self.lista_suggerimenti.curselection()
        if not selezione: return
        via_scelta = self.lista_suggerimenti.get(selezione[0])
        self.imposta_via_e_cerca(via_scelta)

    def imposta_via_e_cerca(self, via):
        self.entry_search.delete(0, tk.END)
        self.entry_search.insert(0, via)
        self.lista_suggerimenti.place_forget()
        self.esegui_ricerca()

    def esegui_ricerca(self):
        self.lista_suggerimenti.place_forget()
        query_raw = self.entry_search.get().strip().lower()
        if not query_raw: return
        parole_da_ignorare = ["via ", "viale ", "piazza ", "corso ", "largo "]
        query_clean = query_raw
        for p in parole_da_ignorare:
            if query_clean.startswith(p):
                query_clean = query_clean.replace(p, "", 1)
        query_clean = query_clean.strip()

        nodo_target = None
        nome_trovato = ""
        for nodo, info in self.mappa_dati.items():
            if query_clean in info["via"].lower():
                nodo_target = nodo
                nome_trovato = info["via"]
                break
        
        if not nodo_target:
            messagebox.showinfo("Ricerca", f"Nessuna via trovata per '{query_raw}'")
            self.canvas.delete("percorso_viola")
            self.planned_path = [] 
            self.final_destination = None
            return
        
        print(f"Destinazione impostata: {nome_trovato}")
        start_node = self.nav_target if self.nav_target else self.nav_node
        full_path = dijkstra_shortest_path(start_node, nodo_target, self.adj, self.mappa_dati)
        if not full_path:
             messagebox.showwarning("Navigatore", "Percorso non disponibile!")
             return

        self.planned_path = full_path[1:]
        self.final_destination = nodo_target
        path_to_draw = [self.nav_node, self.nav_target] + self.planned_path if self.nav_target else [self.nav_node] + self.planned_path
        self.disegna_percorso(path_to_draw)
        self.upd_hud(f"Navigazione verso: {nome_trovato}")

    def disegna_percorso(self, path):
        self.canvas.delete("percorso_viola")
        if len(path) < 2: return
        points = []
        for r, c in path:
            tag = f"node_{r}_{c}"
            bbox = self.canvas.coords(tag)
            if bbox:
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                points.append((cx, cy))
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i+1]
            self.canvas.create_line(x1, y1, x2, y2, fill=COLOR_PATH, width=5, capstyle="round", joinstyle="round", tags="percorso_viola")
        self.canvas.tag_raise("nodo")
        self.canvas.tag_raise(self.nav_id)

    def start_system(self):
        self.system_active = True
        self.btn_s.config(text="ON", state="disabled", bg="#555")

    def set_speed_from_potentiometer(self, kmh): self.pot_speed_kmh = kmh
    
    # --- SISTEMA DI SALVATAGGIO E NOTIFICA ---
    def notify_delivery_completed(self, dati_esp=None):
        self.waiting_for_delivery = False
        
        if dati_esp and self.ts1_arrivo:
            ts2 = datetime.now()
            
            delta = ts2 - self.ts1_arrivo
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            ts_netto_str = f"{hours:02}:{minutes:02}:{seconds:02}"
            
            # --- MODIFICA: AGGIUNTO CAMPO COORDINATE ---
            # Recuperiamo la coordinata dal payload ricevuto dall'ESP
            # o usiamo la posizione attuale del navigatore se disponibile
            coord_val = dati_esp.get('coord', str(self.nav_node) if self.nav_node else "(?,?)")
            
            record = {
                "micro": self.combo_esp.get(),
                "ts1": self.ts1_arrivo.strftime("%H:%M:%S"),
                "ts2": ts2.strftime("%H:%M:%S"),
                "tempo_servizio": dati_esp.get('tempo_sec', 0),
                "ts_netto": ts_netto_str,
                "via": dati_esp.get('via', '?'),
                "coord": coord_val # NUOVO CAMPO
            }
            
            self.storico_consegne.append(record)
            self.salva_dati(record)
            self.invia_dati_online(record)
            
            self.ts1_arrivo = None
            print(f"[MAPPA] Consegna completata e salvata: {record}")

    def salva_dati(self, record):
        tipo = self.combo_tipo_save.get()
        
        if tipo == "JSON":
            nome_file = "Corrieri.json"
            dati_esistenti = []
            if os.path.exists(nome_file):
                try:
                    with open(nome_file, "r") as f: dati_esistenti = json.load(f)
                except: dati_esistenti = []
            
            dati_esistenti.append(record)
            with open(nome_file, "w") as f: json.dump(dati_esistenti, f, indent=4)
            print(f"[LOCAL] Dati salvati su {nome_file}")

        elif tipo == "CSV":
            nome_file = "Corrieri.csv"
            file_esiste = os.path.exists(nome_file)
            # --- MODIFICA: AGGIUNTO 'coord' AI CAMPI CSV ---
            campi = ["micro", "ts1", "ts2", "tempo_servizio", "ts_netto", "via", "coord"]
            
            with open(nome_file, "a", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=campi)
                if not file_esiste: writer.writeheader()
                writer.writerow(record)
            print(f"[LOCAL] Dati salvati su {nome_file}")

    def invia_dati_online(self, record):
        # Utilizza il link passato dinamicamente dal Launcher
        url_target = self.WEBHOOK_URL_DYNAMIC
        tipo = self.combo_tipo_save.get() 
        
        try:
            payload = None
            content_type = ""
            
            if tipo == "JSON":
                payload = json.dumps(record).encode('utf-8')
                content_type = 'application/json'
            
            elif tipo == "CSV":
                output = io.StringIO()
                # --- MODIFICA: AGGIUNTO 'coord' AI CAMPI CSV ONLINE ---
                campi = ["micro", "ts1", "ts2", "tempo_servizio", "ts_netto", "via", "coord"]
                writer = csv.DictWriter(output, fieldnames=campi)
                writer.writeheader()
                writer.writerow(record)
                
                payload = output.getvalue().encode('utf-8')
                content_type = 'text/csv'

            req = urllib.request.Request(url_target, data=payload)
            req.add_header('Content-Type', content_type)
            req.add_header('User-Agent', 'Python-DigitalTwin')
            
            with urllib.request.urlopen(req) as response:
                print(f"[ONLINE] Dati inviati a {url_target} come {tipo}! Status: {response.status}")
                
        except Exception as e:
            print(f"[ONLINE] Errore invio dati: {e}")

    def sync_esp(self, cmd):
        if cmd != self.last_sent_status:
            self.serial.invia_comando(cmd)
            self.last_sent_status = cmd

    def animate_loop(self):
        self.root.after(30, self.animate_loop)
        if not self.system_active: return

        px_speed = (self.pot_speed_kmh / 10.0) * self.zoom_level
        
        if self.waiting_for_delivery:
            nome_via = self.mappa_dati.get(self.nav_node, {}).get("via", "Sconosciuta")
            coord_str = str(self.nav_node) if self.nav_node else "(?,?)"
            self.sync_esp(f"DATI:{nome_via}|{coord_str}")
            self.sync_esp("CMD_ARRIVATO")
            self.upd_hud("DESTINAZIONE RAGGIUNTA (Premi Btn su Wokwi)")
            if self.follow_mode: self.center_view()
            return

        if self.nav_target is None and not self.planned_path and not self.final_destination:
            self.sync_esp("CMD_PAUSE")
            self.upd_hud("IN ATTESA: Cerca una destinazione per partire")
            if self.follow_mode: self.center_view()
            return

        if px_speed <= 0.2:
            self.sync_esp("CMD_PAUSE")
            self.upd_hud("STOP (Aumenta velocità)")
            if self.follow_mode: self.center_view()
            return

        self.sync_esp("CMD_MOVE")
        self.upd_hud(f"NAVIGAZIONE ATTIVA: {self.pot_speed_kmh:.1f} km/h")

        if self.nav_target is None:
            if self.planned_path:
                next_node = self.planned_path.pop(0)
                if next_node in self.adj.get(self.nav_node, []):
                    self.nav_target = next_node
                    self.last_node = self.nav_node
                else:
                    self.planned_path = [] 
                    self.final_destination = None
            if self.nav_target is None: return

        tag = f"node_{self.nav_target[0]}_{self.nav_target[1]}"
        t_coords = self.canvas.coords(tag)
        if not t_coords: return
        tx, ty = (t_coords[0]+t_coords[2])/2, (t_coords[1]+t_coords[3])/2
        dx, dy = tx - self.nav_x, ty - self.nav_y
        dist = math.hypot(dx, dy)
        ang = math.atan2(dy, dx)

        if dist <= px_speed:
            self.nav_x, self.nav_y = tx, ty
            self.nav_node = self.nav_target
            self.nav_target = None
            
            if self.final_destination and self.nav_node == self.final_destination:
                 if not self.waiting_for_delivery:
                     self.waiting_for_delivery = True
                     self.ts1_arrivo = datetime.now() 
                     print(f"[MAPPA] Arrivato a destinazione. ts1: {self.ts1_arrivo.strftime('%H:%M:%S')}")
                     
                 self.final_destination = None 
                 self.canvas.delete("percorso_viola") 
                 self.planned_path = [] 
        else:
            self.nav_x += math.cos(ang)*px_speed
            self.nav_y += math.sin(ang)*px_speed

        self.current_angle = ang
        self._upd_gfx(ang)
        if self.follow_mode: self.center_view()

    def _upd_gfx(self, a):
        sz = 20
        p1 = (self.nav_x + sz*math.cos(a), self.nav_y + sz*math.sin(a))
        p2 = (self.nav_x + sz*math.cos(a+2.6), self.nav_y + sz*math.sin(a+2.6))
        p3 = (self.nav_x + sz*math.cos(a-2.6), self.nav_y + sz*math.sin(a-2.6))
        self.canvas.coords(self.nav_id, p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
        self.canvas.tag_raise(self.nav_id)

    def upd_hud(self, t): 
        v = self.mappa_dati.get(self.nav_node, {}).get("via", "?")
        nodo_str = str(self.nav_node) if self.nav_node else "(?,?)"
        self.lbl_h.config(text=f"Via: {v} | Posizione attuale: {nodo_str}\n{t}")

    def center_view(self):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw<10: return
        bbox = self.canvas.bbox("all")
        if not bbox: return
        try:
            self.canvas.xview_moveto((self.nav_x - bbox[0] - cw/2) / (bbox[2]-bbox[0]))
            self.canvas.yview_moveto((self.nav_y - bbox[1] - ch/2) / (bbox[3]-bbox[1]))
        except: pass

    def toggle_follow(self):
        self.follow_mode = not self.follow_mode
        self.btn_f.config(text="SBLOCCA VISUALE" if self.follow_mode else "SEGUI NAVIGATORE", bg="red" if self.follow_mode else "blue")
        if self.follow_mode: self.center_view()

    def on_down(self, e): self.canvas.scan_mark(e.x, e.y)
    def on_drag(self, e):
        self.canvas.scan_dragto(e.x, e.y, gain=1)
        if self.follow_mode: self.toggle_follow()

    def on_zoom(self, e):
        f = 1.1 if (e.delta>0 or e.num==4) else 0.9
        self.zoom_level *= f
        cx, cy = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self.canvas.scale("all", cx, cy, f, f)
        self.nav_x = cx + (self.nav_x - cx)*f
        self.nav_y = cy + (self.nav_y - cy)*f
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._upd_gfx(self.current_angle)
        if self.follow_mode: self.center_view()