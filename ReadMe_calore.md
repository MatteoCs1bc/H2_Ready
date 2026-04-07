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

DESCRIZIONE OUTPUT
- Energia Primaria Richiesta: Indica la quantità totale di energia prelevata "alla fonte" (es. gas estratto, energia solare o combustibile fossile in centrale elettrica) per soddisfare il fabbisogno termico. È un indicatore fondamentale della sostenibilità globale del sistema, poiché tiene conto delle perdite di trasformazione e trasporto lungo tutta la filiera.  
- Efficienza Macchina (eta / COP): Rappresenta il rendimento locale del sistema. Per le caldaie (metano, pellet, gasolio) è indicato come rendimento (eta < 1), mentre per le Pompe di Calore si usa il COP (Coefficient of Performance), che può superare il valore di 3 o 4, indicando che per ogni kWh elettrico consumato ne vengono prodotti molti di più sotto forma di calore.  
- Emissioni WtW (Well-to-Wheel): Misura l'impatto climatico espresso in $kg$ di $CO_2$ equivalente. L'approccio "Well-to-Wheel" (dal pozzo alla ruota) non considera solo le emissioni allo scarico del camino, ma include anche quelle generate durante l'estrazione, la raffinazione e il trasporto del combustibile o la produzione dell'energia elettrica. WtT (Well-to-Tank): Mostra le emissioni "nascoste". Include tutto ciò che serve per estrarre, raffinare e portare l'energia all'edificio. Ad esempio, per una Pompa di Calore alimentata dalla rete, quasi tutte le emissioni saranno qui (produzione di elettricità alla centrale). TtW (Tank-to-Wheel): Mostra le emissioni locali (dal camino). Per le caldaie a metano o biomassa questa barra sarà molto grande. Per una Pompa di Calore questa barra sarà a zero, poiché non c'è combustione locale.
- Costo Annuo (TCO/y): È il "Costo Totale di Possesso" annualizzato. Somma tre componenti: la quota di ammortamento dell'investimento iniziale (CAPEX), i costi di manutenzione ordinaria e il costo variabile legato all'acquisto del combustibile o dell'elettricità (OPEX). Permette un confronto economico reale tra tecnologie con costi d'acquisto diversi.

VETTORI ENERGETICI  

⚡ L'energia elettrica può provenire da due fonti principali, con impatti economici e ambientali molto diversi:  
- Elettrico da Rete: L'energia viene prelevata interamente dalla rete nazionale. Il costo è tipicamente più elevato (soggetto a oneri di sistema e fluttuazioni del mercato), e le emissioni dipendono dal "mix energetico" nazionale (quota di rinnovabili rispetto ai combustibili fossili nelle centrali termoelettriche).  
- Elettrico Autoprodotto (PV): L'energia è generata localmente, tipicamente da pannelli fotovoltaici.Vantaggio Economico: Abbate drasticamente il costo del kWh (si paga solo l'ammortamento dell'impianto solare).Vantaggio Ambientale: Le emissioni operative sono quasi nulle.
  
🔥 Per i sistemi a combustione, l'approvvigionamento segue logiche di mercato e infrastrutturali:  
- Metano (Rete): È l'approvvigionamento standard tramite infrastruttura cittadina. Ha un costo moderato e un'impronta carbonica fissa legata alla combustione del gas fossile.  
- Biomassa legonsa (Pellet): L'approvvigionamento è "puntuale" (acquisto di sacchi o bancali). Sebbene emetta $CO_2$ alla combustione, è considerata neutra o a basse emissioni nel computo globale perché il carbonio emesso è quello assorbito dalla pianta durante la crescita.  
- Gasolio (Diesel): È il vettore solitamente più costoso e inquinante, utilizzato dove non arriva la rete del metano.
  
💧 L'idrogeno non è una fonte, ma un vettore che deve essere prodotto. La sua sostenibilità dipende esclusivamente dal metodo di produzione:  
- Idrogeno Grigio: Prodotto dal metano (SMR - Steam Methane Reforming). È economico ma ha emissioni di $CO_2$ elevate durante la produzione, rendendo il vantaggio ambientale quasi nullo.  
- Idrogeno Verde (Autoprodotto o Rete): Prodotto tramite elettrolisi dell'acqua utilizzando energia rinnovabile. Se autoprodotto, richiede un elettrolizzatore locale e una grande capacità di generazione rinnovabile. Se da rete, si ipotizza il prelievo da una futura "dorsale" dell'idrogeno. È la soluzione a minor impatto emissivo, ma attualmente la più costosa per via delle perdite di conversione.
