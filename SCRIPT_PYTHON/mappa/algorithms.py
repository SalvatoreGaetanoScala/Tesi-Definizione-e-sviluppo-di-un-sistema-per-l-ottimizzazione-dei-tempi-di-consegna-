#Contiene la logica matematica per la generazione 
# del grafo e il calcolo del percorso (Dijkstra), 
# separandola dall'interfaccia grafica.

import random
import math
import heapq

def genera_grafo_mappa(rows, cols, cell_size, num_stelle, num_connessioni, nomi_vie_source):
    """
    Genera i dati della mappa: nodi (vie), adiacenze e segmenti da disegnare.
    """
    mappa_dati = {}
    adj = {}
    coords = []
    
    # Copia per non modificare l'originale
    nomi_disponibili = list(nomi_vie_source)
    random.shuffle(nomi_disponibili)
    
    # 1. Generazione Nodi
    for _ in range(num_stelle):
        r, c = random.randint(0, rows-1), random.randint(0, cols-1)
        if (r,c) not in mappa_dati:
            if nomi_disponibili:
                nome_via = nomi_disponibili.pop()
            else:
                nome_via = f"Via_{len(coords)}"
            
            mappa_dati[(r,c)] = {"via": nome_via}
            coords.append((r,c))
            adj[(r,c)] = set() 
    
    # 2. Generazione Connessioni e Segmenti Grafici
    visual_edges = []
    drawn_edges = set()
    
    for i, (r1, c1) in enumerate(coords):
        # Trova i nodi più vicini
        dists = sorted([( (r1-r2)**2+(c1-c2)**2, r2, c2) for j,(r2,c2) in enumerate(coords) if i!=j])
        
        for _, r2, c2 in dists[:num_connessioni]:
            adj[(r1,c1)].add((r2,c2))
            adj[(r2,c2)].add((r1,c1)) 

            edge_sig = tuple(sorted(((r1,c1), (r2,c2))))
            
            if edge_sig not in drawn_edges:
                x1 = c1 * cell_size + cell_size // 2
                y1 = r1 * cell_size + cell_size // 2
                x2 = c2 * cell_size + cell_size // 2
                y2 = r2 * cell_size + cell_size // 2
                
                visual_edges.append((x1, y1, x2, y2))
                drawn_edges.add(edge_sig)

    return mappa_dati, adj, visual_edges

def dijkstra_shortest_path(start, end, adj, mappa_dati):
    """
    Calcola il percorso più breve tra due nodi usando l'algoritmo di Dijkstra.
    """
    # Inizializza distanze per tutti i nodi conosciuti
    tutti_i_nodi = list(mappa_dati.keys())
    distanze = {node: float('inf') for node in tutti_i_nodi}
    distanze[start] = 0
    padri = {node: None for node in tutti_i_nodi}
    visited = set()
    
    pq = [(0, start)]

    while pq:
        d_corr, u = heapq.heappop(pq)
        
        if u == end: 
            break
        
        if u in visited: 
            continue
        visited.add(u)
        
        for v in adj.get(u, []):
            peso = math.sqrt((u[0]-v[0])**2 + (u[1]-v[1])**2)
            nuova_dist = d_corr + peso
            
            if new_dist_val := nuova_dist < distanze.get(v, float('inf')): # Controllo sicurezza su v
                distanze[v] = nuova_dist
                padri[v] = u
                heapq.heappush(pq, (nuova_dist, v))
                
    # Ricostruzione percorso
    path = []
    curr = end
    if padri.get(curr) is None and curr != start:
        return [] # Nessun percorso trovato
        
    while curr is not None:
        path.append(curr)
        curr = padri.get(curr)
        
    return path[::-1]