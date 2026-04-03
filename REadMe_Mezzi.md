Documentazione DSS Mobilità e RiscaldamentoBenvenuti nel sistema di supporto alle decisioni (DSS) per i Comuni.   
Questi strumenti permettono di confrontare diverse tecnologie per la mobilità e il riscaldamento degli edifici, valutando l'impatto economico (TCO) e ambientale (CO2).  
1. Strumento Mobilità (car_code.py)Questo tool analizza la flotta comunale (Auto, Camion, Autobus) per guidare la transizione verso l'elettrico o l'idrogeno.
2. Funzionamento
3. Il modello calcola i costi e le emissioni basandosi su:Dati di Input:
4. Consumi ($kWh/km$), costo d'acquisto (CAPEX) e manutenzione ($€/km$) estratti direttamente dal database Excel.
5. Variabili Dinamiche: L'utente può variare tramite cursori la percorrenza annua [km/y] e gli anni di ammortamento [y].
6. Costi Carburante: I prezzi sono inseribili nelle unità di misura comuni (€/l per benzina/diesel, €/kg per H2, €/kWh per elettrico).
7. Limiti e Assunzioni
8. Ammortamento Lineare: Il CAPEX è diviso equamente per gli anni di vita utile impostati.
9. Manutenzione: Il costo di manutenzione è scalato linearmente in base ai chilometri percorsi rispetto alla base di riferimento (15.000 km).
10. Emissioni WtW: Include sia la produzione del carburante (Well-to-Tank) che l'utilizzo allo scarico (Tank-to-Wheel).
