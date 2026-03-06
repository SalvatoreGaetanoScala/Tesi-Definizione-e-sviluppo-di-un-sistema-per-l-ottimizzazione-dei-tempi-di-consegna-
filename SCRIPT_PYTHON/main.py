import tkinter as tk
from launcher import ConfigDialog
from mappa import MappaApp

if __name__ == "__main__":
    conf = ConfigDialog()
    res = conf.run() # Restituisce (nodi, conn, corrieri, start_centro, link)
    
    if res:
        root = tk.Tk()
        # Passiamo anche il link alla MappaApp
        app = MappaApp(root, num_stelle=res[0], num_connessioni=res[1], 
                       num_corrieri=res[2], start_from_center=res[3], 
                       webhook_url=res[4])
        root.mainloop()