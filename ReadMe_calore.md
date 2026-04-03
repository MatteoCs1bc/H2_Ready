STRUMENTO RISCALDAMENTO
Analisi comparativa per la sostituzione di caldaie e impianti termici negli edifici pubblici.    

FUNZIONAMENTO  
Logica del Fabbisogno:   
1. L'utente imposta il Fabbisogno Termico Annuo [$kWh_{th}/y$].
2. Il sistema calcola il consumo di combustibile necessario dividendo il fabbisogno per l'efficienza ($\eta$) o il COP della macchina.

Interattività COP: È possibile variare il COP delle Pompe di Calore (PdC) per simulare diverse condizioni climatiche o performance stagionali.  
  
COSTI VETTORE  
Supporta unità native (es. €/sacco per il Pellet, €/Sm3 per il Metano) con conversione automatica in €/kWh termico basata sui poteri calorifici impostati nel database.  
  
LIMITI E ASSUNZIONI  
- Efficienza Costante: Il COP e l'efficienza della caldaia sono considerati valori medi stagionali costanti.  
- Manutenzione Fissa: A differenza dei veicoli, la manutenzione degli impianti di riscaldamento è considerata un costo fisso annuo indipendente dal carico di lavoro.  
- Scalabilità Emissioni: Le emissioni sono calcolate proporzionalmente al consumo di vettore energetico generato dal fabbisogno impostato.  

🛠️ NOTE TECNICHE COMUNI  
- Database: Entrambi gli strumenti attingono al file excel. Ogni modifica ai valori base nell'Excel (es. costo CAPEX o fattori di emissione) si riflette automaticamente nelle dashboard.  
- Tecnologie: Sono confrontate soluzioni tradizionali (Gasolio, Metano), rinnovabili (Pellet, PdC con autoconsumo FV) e vettori innovativi (Idrogeno Grigio, Verde, da Rete).  
- LCA Semplificato: Le emissioni includono una quota fissa relativa alla costruzione/produzione della macchina/veicolo, spalmata sulla vita utile.
