"""Optimisation unitaire sur un seul fichier de données .dat.

Reprend le bloc d'affichage / de tracé qui était laissé en commentaire dans
"Optimization avec maintenances V2 .py" (fichier original, non modifié),
adapté à `optimization_model.ModelData`.

Usage:
    python app/run_single.py chemin/vers/fichier.dat --p 20 --d 4 --plot
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metier.data_loader import lire_data
from metier.optimization_model import build_model
from metier.reporting import build_schedule_figure, format_solution_text


def print_solution(model_data):
    if model_data.model.SolCount == 0:
        print("Aucune solution trouvée.")
        return
    print(f"\n{format_solution_text(model_data)}")


def plot_schedule(model_data, output_path="planning.svg"):
    fig = build_schedule_figure(model_data)
    fig.savefig(output_path, format="svg")
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Optimisation unitaire sur un fichier de données .dat.")
    parser.add_argument("data_file", help="Chemin du fichier .dat")
    parser.add_argument("--d", type=int, default=4, help="Nombre max de jours entre deux maintenances")
    parser.add_argument("--time-limit", type=int, default=1800, help="Limite de temps Gurobi (secondes)")
    parser.add_argument("--mip-gap", type=float, default=0.2, help="Gap MIP cible")
    parser.add_argument("--plot", action="store_true", help="Générer le diagramme des trajets (planning.svg)")
    args = parser.parse_args()

    data = lire_data(args.data_file)
    model_data = build_model(data, args.d, time_limit=args.time_limit, mip_gap=args.mip_gap)
    model_data.model.optimize()

    print_solution(model_data)

    if args.plot:
        plot_schedule(model_data)


if __name__ == "__main__":
    main()
