"""Génération des rapports de résultats (texte + figure) à partir d'un `ModelData` résolu.

Extrait de `run_single.py` pour être partagé avec l'interface Streamlit (`app.py`),
sans dupliquer la logique d'affichage.
"""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np


def format_solution_text(model_data):
    """Construit le rapport texte de la solution (une ligne par vol/avion)."""
    m = model_data.model
    if m.SolCount == 0:
        return "Aucune solution trouvée."

    lines = [
        f"Statut Gurobi: {m.Status} (2 = optimal, 9 = limite de temps atteinte)",
        f"Coût total de la solution retenue: {m.ObjVal:.2f}",
    ]

    for a in model_data.planes:
        start_airport = model_data.start_airports[a][1]
        lines.append(f"\nAvion {a} (départ de {start_airport}):")

        assigned_flights = [f for f in model_data.flight_indices if model_data.x[a, f].X > 0.5]
        maintenance = [
            (v, j)
            for j in model_data.days
            for v in model_data.airports_maintenance
            if model_data.z[v, a, j].X > 0.5
        ]

        if assigned_flights:
            assigned_flights.sort(key=lambda f: model_data.dep_times[f])
            for f in assigned_flights:
                index, orig, dest, dep, arr, _ = model_data.flights[f]
                lines.append(f"  Vol {index}: {orig} -> {dest} (dep {dep:.0f} min, arr {arr:.0f} min)")
        else:
            lines.append("  Aucun vol effectué.")

        if maintenance:
            lines.append(f"  Maintenance: {maintenance}")

        for v in model_data.airports:
            if model_data.y[a, v].X > 0.5:
                lines.append(f"  Fin de la tournée à {v}")

    return "\n".join(lines)


def build_schedule_figure(model_data):
    """Construit la figure matplotlib du planning des avions, sans l'afficher ni la sauvegarder."""
    planes = model_data.planes
    colors = matplotlib.colormaps["tab10"].resampled(len(planes))
    fig, ax = plt.subplots(figsize=(12, 6))

    for a in planes:
        assigned_flights = sorted(
            (f for f in model_data.flight_indices if model_data.x[a, f].X > 0.5),
            key=lambda f: model_data.dep_times[f],
        )
        color = colors(a)

        for idx, f in enumerate(assigned_flights):
            _, orig, dest, dep, arr, _ = model_data.flights[f]
            ax.plot(
                [dep / 1440, arr / 1440], [a, a], marker=".", color=color, linewidth=2,
                label=f"Avion {a}" if idx == 0 else "",
            )
            ax.text(dep / 1440, a, orig, verticalalignment="bottom", fontsize=5)
            ax.text(arr / 1440, a, dest, verticalalignment="top", fontsize=5)

        for j in model_data.days:
            for v in model_data.airports_maintenance:
                if model_data.z[v, a, j].X > 0.5:
                    maintenance_time = (model_data.night_flights[v][j][0][3] - 5) / 1440
                    ax.scatter(
                        maintenance_time, a, color="red", marker="|", s=100,
                        label="Maintenance" if j == 0 and a == planes[0] else "",
                    )
                    ax.text(
                        maintenance_time, a, v, verticalalignment="bottom",
                        horizontalalignment="left", fontsize=5, color="red",
                    )

    ax.set_xlabel("Temps (jours)")
    ax.set_ylabel("Avions")
    ax.set_title("Trajets des avions avec maintenances")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.xaxis.set_major_locator(plt.MultipleLocator(1))
    ax.set_xticks(np.arange(0, max(model_data.arr_times) / 1440 + 1, 1))

    return fig
