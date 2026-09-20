# flight-opti

Modèle d'optimisation de tournées d'avions (affectation des vols + planification des
maintenances) pour une compagnie aérienne, formulé en programmation linéaire en
nombres entiers (MILP) et résolu avec [Gurobi](https://www.gurobi.com/).

## Structure du projet

```
metier/                  Fonctions métier (indépendantes de toute interface)
  data_loader.py           Parsing des fichiers de données .dat (format CPLEX)
  optimization_model.py    Construction du modèle Gurobi (variables, contraintes, objectif)
  reporting.py             Mise en forme des résultats (texte + figure du planning)

app/                      Points d'entrée
  app.py                    Interface Streamlit (upload/sélection d'un .dat, lancement, export)
  run_single.py             CLI : résolution d'un seul fichier .dat
  benchmark.py              CLI : benchmark des temps de résolution sur un dossier de fichiers

data/                     Jeu de données complet (non versionné, voir .gitignore)
sample_data/              Sous-ensemble de fichiers .dat versionné, utilisé par l'app Streamlit
requirements.txt         Dépendances Python
gurobi.lic                Licence Gurobi (non versionnée)
```

## Installation

```bash
pyenv install 3.11.6   # si nécessaire
pip install -r requirements.txt
```

Une licence Gurobi valide (`gurobi.lic`) est requise pour résoudre les modèles.

## Utilisation

**Interface Streamlit** (sélection d'un jeu d'exemple ou upload d'un `.dat`, réglage
de `d`/limite de temps/gap MIP, export du planning en SVG et du détail en TXT) :

```bash
streamlit run app/app.py
```

**Résolution en ligne de commande :**

```bash
python app/run_single.py chemin/vers/fichier.dat --d 4 --time-limit 1800 --mip-gap 0.05 --plot
```

**Benchmark des temps de résolution sur un dossier :**

```bash
python app/benchmark.py --folder data/d=4 --d 4
```

## Format des données (`.dat`)

Fichiers texte au format CPLEX, un jeu de données par scénario (`p` avions, `h`
jours d'horizon). Champs principaux :

| Clé | Contenu |
|---|---|
| `Airports` | Liste des aéroports du réseau |
| `Airportmaintenance` | Sous-ensemble d'aéroports disposant d'une base de maintenance |
| `Nbflight` | Nombre de vols |
| `Flight` | Liste des vols `<id, origine, destination, heure_départ, heure_arrivée, jour>` (heures en minutes depuis le début de l'horizon) |
| `Aircrafts` | Identifiants des avions |
| `Aircraft` | Aéroport de départ initial de chaque avion : `<id, aéroport>` |
| `Days` | Jours de l'horizon de planification |
| `Cost` | Coût d'affectation de chaque vol à chaque avion (matrice avion × vol) |
| `CostMaintenance` | Coût d'une maintenance par aéroport de maintenance et par avion |
| `capmaintenance` | Nombre max d'avions pouvant être en maintenance simultanément sur un même aéroport, un même jour |

## Modèle d'optimisation

### Variables de décision

- `x[a, f]` (binaire) : le vol `f` est affecté à l'avion `a`
- `y[a, v]` (binaire) : l'avion `a` termine sa tournée à l'aéroport `v` (arc fictif de fin)
- `z[v, a, j]` (binaire) : l'avion `a` est en maintenance à l'aéroport `v` le jour `j`

### Objectif

Minimiser le coût total = coût des vols affectés + coût des maintenances effectuées.

### Contraintes

- **Affectation des vols** : chaque vol est affecté à exactement un avion.
- **Conservation de flux** : pour chaque avion et chaque aéroport, vols entrants + arc
  de fin = vols sortants (+1 sur l'aéroport de départ initial).
- **Fin de tournée unique** : chaque avion termine sa tournée par exactement un arc
  fictif de fin (il n'est pas obligé de revenir à son aéroport de départ).
- **Continuité temporelle** : un avion ne peut décoller d'un aéroport que s'il y est
  déjà arrivé auparavant (ou s'il s'agit de son aéroport de départ initial).
- **Capacité de maintenance** : nombre d'avions en maintenance simultanément limité
  par aéroport et par jour (`capmaintenance`).
- **Espacement des maintenances** : chaque avion doit subir au moins une maintenance
  dans toute fenêtre glissante de `d + 1` jours (`d` est un paramètre du modèle,
  passé en argument de `build_model` / en entrée de l'app et des CLI).
- **Localisation de la maintenance** : un avion ne peut être en maintenance à un
  aéroport une nuit donnée que s'il y est physiquement présent cette nuit-là
  (déterminé à partir des vols encadrant la plage nocturne 22h–6h).

### Hypothèses de modélisation

- **Aucune contrainte de compatibilité flotte/vol** : n'importe quel avion peut
  effectuer n'importe quel vol ; seule la matrice `Cost` différencie les affectations
  (aucune notion de type d'appareil, de capacité passagers, etc.).
- **Pas de contrainte d'équipage** : le modèle ne planifie que les avions, pas les
  équipages.
- **Temps de rotation au sol implicite** : un avion peut repartir dès qu'il est arrivé
  (comparaison stricte des horaires), aucune marge minimale de connexion n'est ajoutée
  au-delà des horaires du fichier de données.
- **Maintenance ponctuelle et nocturne** : la maintenance est modélisée comme un
  évènement binaire par (avion, aéroport, jour), localisé sur la plage 22h–6h ; sa
  durée réelle et son impact éventuel sur la disponibilité de l'avion en journée ne
  sont pas modélisés au-delà de cette présence nocturne.
- **Maintenance limitée à certains aéroports** : seuls les aéroports listés dans
  `Airportmaintenance` disposent d'une capacité de maintenance ; les autres n'en
  offrent aucune.
- **Position de départ figée** : chaque avion démarre l'horizon à un aéroport connu
  et fixé (`Aircraft`), sans contrainte de retour à ce même aéroport en fin d'horizon.
- **Résolution à l'optimalité relative** : le solveur Gurobi est paramétré avec un
  gap MIP cible (`mip_gap`) et une limite de temps (`time_limit`) ; la solution
  retournée peut donc être une solution admissible proche de l'optimum plutôt que
  l'optimum exact (statut Gurobi `9` = limite de temps atteinte).
