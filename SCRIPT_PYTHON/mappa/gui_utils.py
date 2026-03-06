#Contiene funzioni ausiliarie per l'interfaccia 
#grafica, come la finestra della lista vie e la tabella corrieri.

import tkinter as tk
from tkinter import ttk

def mostra_finestra_lista_vie(root, mappa_dati):
    """Apre una finestra popup con l'elenco delle vie e le loro coordinate."""
    win = tk.Toplevel(root)
    win.title("Elenco Vie Disponibili")
    win.geometry("400x500")
    
    lista_vie = []
    for coord, dati in mappa_dati.items():
        lista_vie.append((dati["via"], str(coord)))
    
    lista_vie.sort(key=lambda x: x[0])
    
    cols = ("Nome Via", "Coordinate")
    tree = ttk.Treeview(win, columns=cols, show="headings")
    tree.heading("Nome Via", text="Nome Via")
    tree.heading("Coordinate", text="Coordinate (R, C)")
    tree.column("Nome Via", width=250)
    tree.column("Coordinate", width=120)
    
    scrollbar = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    
    scrollbar.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)
    
    for via, coord in lista_vie:
        tree.insert("", "end", values=(via, coord))

def mostra_finestra_corrieri(root, storico_consegne):
    """Apre una finestra popup con lo storico delle consegne dei corrieri."""
    win = tk.Toplevel(root)
    win.title("Storico Corrieri")
    win.geometry("900x400") # Finestra più larga per ospitare la nuova colonna
    
    # Colonne richieste (AGGIUNTA: Coordinate)
    cols = ("Micro", "ts1 (Arrivo)", "ts2 (Fine)", "T. Servizio (s)", "ts Netto", "Via", "Coordinate")
    
    tree = ttk.Treeview(win, columns=cols, show="headings")
    
    # Configurazione Intestazioni e Larghezze
    tree.heading("Micro", text="Micro")
    tree.column("Micro", width=80, anchor="center")
    
    tree.heading("ts1 (Arrivo)", text="ts1 (Arrivo)")
    tree.column("ts1 (Arrivo)", width=90, anchor="center")
    
    tree.heading("ts2 (Fine)", text="ts2 (Fine)")
    tree.column("ts2 (Fine)", width=90, anchor="center")
    
    tree.heading("T. Servizio (s)", text="T. Serv (s)")
    tree.column("T. Servizio (s)", width=80, anchor="center")
    
    tree.heading("ts Netto", text="ts Netto")
    tree.column("ts Netto", width=100, anchor="center")
    
    tree.heading("Via", text="Via")
    tree.column("Via", width=180, anchor="w")

    # NUOVA COLONNA
    tree.heading("Coordinate", text="Coordinate (R, C)")
    tree.column("Coordinate", width=140, anchor="center")
    
    # Scrollbar
    scrollbar = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    
    scrollbar.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)
    
    # Inserimento Dati (Inseriamo all'inizio così i più recenti sono in alto)
    for record in reversed(storico_consegne):
        # Gestiamo il caso in cui vecchi record non abbiano "coord"
        coord_val = record.get("coord", "N/D") 
        
        vals = (
            record["micro"],
            record["ts1"],
            record["ts2"],
            record["tempo_servizio"],
            record["ts_netto"],
            record["via"],
            coord_val # Valore nuova colonna
        )
        tree.insert("", "end", values=vals)