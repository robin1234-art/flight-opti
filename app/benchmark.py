"""Benchmark des temps de résolution sur un ensemble de fichiers de données .dat.

Reprend la logique de `benchmark()` dans "Optimization avec maintenances V2 .py"
(fichier original, non modifié), en s'appuyant sur `data_loader` et
`optimization_model` plutôt que sur une fonction monolithique.

Usage:
    python app/benchmark.py --folder /chemin/vers/dossier --d 3
"""

import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metier.data_loader import lire_data
from metier.optimization_model import build_model

DEFAULT_FOLDER = "data/d=4"
DEFAULT_D = 4


def run_benchmark(dossier=DEFAULT_FOLDER, d=DEFAULT_D):
    """Résout chaque fichier .dat du dossier et chronomètre la construction + résolution du modèle."""
    resultats = defaultdict(list)

    for fichier in os.listdir(dossier):
        if not fichier.endswith(".dat"):
            continue
        chemin_complet = os.path.join(dossier, fichier)
        if not os.path.isfile(chemin_complet):
            continue

        density, p, h, x, t = fichier[18:-4].split("_")
        p = int(p.split("=")[-1])
        h = int(h.split("=")[-1])
        t = int(t.split("=")[-1])

        data = lire_data(chemin_complet)
        print(chemin_complet)

        t1 = time.time()
        model_data = build_model(data, d)
        model_data.model.optimize()
        t2 = time.time()

        key = (d, p, h)
        resultats[key].append((t2 - t1, t))

    return resultats


def compute_stats(resultats):
    """Statistiques (moyenne/min/max/std) du temps d'exécution par combinaison (d, p, h)."""
    stats = {}
    for key, temps_list in resultats.items():
        temps_values = [temps for temps, _ in temps_list]
        stats[key] = {
            "mean": np.mean(temps_values),
            "min": np.min(temps_values),
            "max": np.max(temps_values),
            "std": np.std(temps_values),
        }

    df_stats = pd.DataFrame([
        {
            "d": d,
            "p": p,
            "h": h,
            "temps_moyen": s["mean"],
            "temps_min": s["min"],
            "temps_max": s["max"],
            "temps_std": s["std"],
        }
        for (d, p, h), s in stats.items()
    ])
    return df_stats.sort_values(by=["d", "p", "h"])


def plot_errorbar(df_stats):
    plt.figure(figsize=(14, 8))
    for p_val in sorted(df_stats["p"].unique()):
        df_p = df_stats[df_stats["p"] == p_val].sort_values(by="h")
        plt.errorbar(
            df_p["h"],
            df_p["temps_moyen"],
            yerr=[df_p["temps_moyen"] - df_p["temps_min"], df_p["temps_max"] - df_p["temps_moyen"]],
            marker="o",
            markersize=8,
            linewidth=2,
            capsize=6,
            label=f"p={p_val}",
        )
    plt.xlabel("Valeur de h", fontsize=12)
    plt.ylabel("Temps d'exécution (secondes)", fontsize=12)
    plt.title("Performances avec barres min/max", fontsize=14)
    plt.legend(fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()
    plt.savefig("benchmark_errorbar.png", dpi=300, bbox_inches="tight")


def plot_boxplot(df_stats, resultats):
    plt.figure(figsize=(14, 8))
    box_data, box_labels = [], []
    for p_val in sorted(df_stats["p"].unique()):
        for h_val in sorted(df_stats["h"].unique()):
            for key in resultats:
                if key[1] == p_val and key[2] == h_val:
                    box_data.append([temps for temps, _ in resultats[key]])
                    box_labels.append(f"p={p_val}, h={h_val}")

    plt.boxplot(box_data, labels=box_labels, patch_artist=True)
    plt.xticks(rotation=45, ha="right")
    plt.xlabel("Paramètres (p, h)", fontsize=12)
    plt.ylabel("Temps d'exécution (secondes)", fontsize=12)
    plt.title("Distribution des temps de résolution par configuration", fontsize=14)
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    plt.savefig("benchmark_boxplot.png", dpi=300, bbox_inches="tight")


def plot_barplot(df_stats):
    p_values = sorted(df_stats["p"].unique())
    plt.figure(figsize=(15, 10))
    for i, p_val in enumerate(p_values):
        plt.subplot(1, len(p_values), i + 1)
        df_p = df_stats[df_stats["p"] == p_val].sort_values(by="h")

        bars = plt.bar(
            df_p["h"].astype(str),
            df_p["temps_moyen"],
            color=plt.cm.viridis(i / len(p_values)),
            alpha=0.7,
        )
        plt.errorbar(
            range(len(df_p)),
            df_p["temps_moyen"],
            yerr=[df_p["temps_moyen"] - df_p["temps_min"], df_p["temps_max"] - df_p["temps_moyen"]],
            fmt="none",
            capsize=5,
            ecolor="black",
            elinewidth=1.5,
        )

        for bar, value in zip(bars, df_p["temps_moyen"]):
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.05,
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        plt.xlabel("Valeur de h")
        plt.ylabel("Temps d'exécution (secondes)")
        plt.title(f"p={p_val}")
        plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    plt.savefig("benchmark_barplot.png", dpi=300, bbox_inches="tight")


def main():
    parser = argparse.ArgumentParser(description="Benchmark des temps de résolution du modèle.")
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help="Dossier contenant les fichiers .dat")
    parser.add_argument("--d", type=int, default=DEFAULT_D, help="Nombre max de jours entre deux maintenances")
    args = parser.parse_args()

    resultats = run_benchmark(args.folder, args.d)
    df_stats = compute_stats(resultats)

    print("Résultats du benchmark (statistiques sur t):")
    print(df_stats[["d", "p", "h", "temps_moyen", "temps_min", "temps_max", "temps_std"]])

    matrice_resultats = pd.pivot_table(
        df_stats, values=["temps_moyen", "temps_min", "temps_max"], index=["p"], columns=["h"], aggfunc=np.mean,
    )
    print("\nMatrice des temps d'exécution (p en lignes, h en colonnes):")
    print(matrice_resultats.round(3))

    plot_errorbar(df_stats)
    plot_boxplot(df_stats, resultats)
    plot_barplot(df_stats)
    plt.show()


if __name__ == "__main__":
    main()
