"""Chargement et parsing des fichiers de données .dat (format CPLEX).

Repris de "Optimization avec maintenances V2 .py" (fichier original, non
modifié) : `lire_data` produit le même dictionnaire `data` en sortie. Le
fichier original ré-ouvrait et re-parsait entièrement le fichier à chaque
ligne (boucle imbriquée O(n^2) sans effet sur le résultat) ; ici la lecture
se fait en une seule passe.
"""

import numpy as np


def lire_data(file_path):
    p = int(file_path.split("p=")[1].split("_")[0])
    with open(file_path, "r") as f:
        data = {}
        for ligne in f:
            ligne = ligne.strip()
            # Ignorer les lignes vides ou commentaires (par exemple, commençant par //)
            if not ligne or ligne.startswith("//"):
                continue
            if "=" in ligne:
                # Séparer la clé et la valeur
                cle, valeur = ligne.split("=", 1)
                cle = cle.strip()
                # Retirer le point-virgule à la fin de la ligne
                valeur = valeur.strip().rstrip(";")
                # Vérifier si la valeur est une liste (entre crochets)
                if valeur.startswith("{") and valeur.endswith("}"):
                    # Enlever les crochets et séparer par des virgules
                    valeur_list = valeur.strip("{}").split(",")[0:-1]
                    # Convertir chaque élément en entier (ou float si nécessaire)
                    try:
                        data[cle] = [int(x.strip()) for x in valeur_list if x.strip()]
                    except ValueError:
                        data[cle] = [x.strip() for x in valeur_list if x.strip()]
                else:
                    # Essayer de convertir en nombre
                    try:
                        if "." in valeur:
                            data[cle] = float(valeur)
                        else:
                            data[cle] = int(valeur)
                    except ValueError:
                        data[cle] = valeur  # sinon, on laisse en chaîne de caractères
            else:
                data[cle] += ";" + ligne

        x = data["Flight"].split(";")[-2][:-1]
        data['Flight'] = data['Flight'].split(';')[1:-2]
        data["Flight"].append(x)

        data['Cost'] = data['Cost'].split(';')[1:-1]
        data["Cost"] = np.array([
            float(val)
            for j in range(len(data["Cost"]))
            for val in data["Cost"][j].strip('[]').split(",")
            if val.strip() != ''
        ]).reshape(data["Nbflight"], p)

        data['CostMaintenance'] = data['CostMaintenance'].split(';')[1:-1]
        data["CostMaintenance"] = np.array([
            float(val)
            for j in range(len(data["CostMaintenance"]))
            for val in data["CostMaintenance"][j].strip('[]').split(",")
            if val.strip() != ''
        ]).reshape(len(data["Airportmaintenance"]), p)

        data['Aircraft'] = data['Aircraft'][2:-4].split(" ,")
        liste_tuples = []
        for element in data['Aircraft']:
            element = element.strip(" <>")
            i_str, lettre = element.split(",")
            liste_tuples.append((int(i_str), lettre))
        data['Aircraft'] = liste_tuples

        liste_list = []
        for element in data['Flight']:
            element = element.strip(" <>")
            i_str, lettre1, lettre2, int1, int2, int3 = element.split(",")
            liste_list.append([int(i_str), lettre1, lettre2, float(int1), float(int2), float(int3)])
        data['Flight'] = liste_list

    return data
