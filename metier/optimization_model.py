"""Construction du modèle Gurobi : variables, contraintes et objectif.

Reprend exactement la formulation de "Optimization avec maintenances V2 .py"
(fichier original, non modifié), en la décomposant en une fonction par
contrainte pour la lisibilité. Deux corrections mineures, sans impact sur les
résultats, ont été apportées par rapport à l'original :

- `add_maintenance_capacity_constraints` boucle sur `planes` (comme partout
  ailleurs dans le modèle) plutôt que sur `range(num_planes)` : les deux sont
  équivalents tant que les identifiants d'avions sont `0..num_planes-1`, mais
  boucler sur `planes` est cohérent avec le reste du modèle et plus robuste.
- Le nom des contraintes de localisation de maintenance est unifié en
  `maintenance_{k}_{a}_{j}` (l'original nommait par erreur une des deux
  branches `flow_continuity_...`, ce qui ne change rien au solve mais prêtait
  à confusion en debug).

`build_model` ne lance pas l'optimisation : c'est aux scripts appelants
(`run_single.py`, `benchmark.py`) d'appeler `.model.optimize()`, pour séparer
la construction du modèle de sa résolution.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

import gurobipy as gp
import numpy as np
from gurobipy import GRB


@dataclass
class ModelData:
    """Modèle Gurobi construit, avec le contexte nécessaire à l'exploitation de la solution."""

    model: gp.Model
    x: gp.tupledict
    y: gp.tupledict
    z: gp.tupledict
    planes: List[int]
    airports: List[str]
    flights: List[list]
    flight_indices: range
    dep_times: List[float]
    arr_times: List[float]
    start_airports: List[tuple]
    airports_maintenance: List[str]
    days: List[int]
    night_flights: Dict[str, Dict[int, list]]
    cost: Any
    cost_maintenance: Any


def _flights_by_airport(airports, flights):
    """Index des vols au départ / à l'arrivée de chaque aéroport."""
    flights_from = {v: [] for v in airports}
    flights_to = {v: [] for v in airports}
    for f, (index, orig, dest, dep, arr, i) in enumerate(flights):
        flights_from[orig].append(f)
        flights_to[dest].append(f)
    return flights_from, flights_to


def add_flow_conservation_constraints(m, x, y, planes, airports, start_airports, flights_from, flights_to):
    """Conservation du flux : vols entrants = vols sortants (+ arc dummy de fin, + départ initial)."""
    for a in planes:
        for v in airports:
            out_flow = gp.quicksum(x[a, f] for f in flights_from[v])
            in_flow = gp.quicksum(x[a, f] for f in flights_to[v])
            rhs = 1 if v == start_airports[a][1] else 0
            m.addConstr(out_flow + y[a, v] == in_flow + rhs, name=f"flow_{a}_{v}")


def add_tour_end_constraints(m, y, planes, airports):
    """Chaque avion termine sa tournée par un unique arc dummy."""
    for a in planes:
        m.addConstr(gp.quicksum(y[a, v] for v in airports) == 1, name=f"end_once_{a}")


def add_flight_assignment_constraints(m, x, planes, flight_indices):
    """Chaque vol est affecté à exactement un avion."""
    for f in flight_indices:
        m.addConstr(gp.quicksum(x[a, f] for a in planes) == 1, name=f"assign_flight_{f}")


def add_maintenance_capacity_constraints(m, z, days, airports_maintenance, planes, cap_maintenance):
    """Capacité maximale d'avions en maintenance, par aéroport et par jour."""
    for j in days:
        for v in airports_maintenance:
            m.addConstr(
                gp.quicksum(z[v, a, j] for a in planes) <= cap_maintenance,
                name=f"maintenance_capacity_{v}_{j}",
            )


def add_maintenance_spacing_constraints(m, z, planes, days, d, airports_maintenance):
    """Au moins une maintenance dans toute fenêtre glissante de d+1 jours."""
    for a in planes:
        for n in range(len(days) - d):
            m.addConstr(
                gp.quicksum(z[v, a, j] for v in airports_maintenance for j in range(n, n + d + 1)) >= 1,
                name=f"maintenance_spacing_{a}_{n}",
            )


def _continuity_term(x, a, arrivals_before, departures_before):
    return gp.quicksum(x[a, i] for i in arrivals_before) - gp.quicksum(x[a, i] for i in departures_before)


def add_flow_continuity_constraints(
    m, x, planes, airports, start_airports, flights_from, flights_to, dep_times, arr_times
):
    """Équation (4) : un avion ne peut partir de k que s'il y est déjà arrivé (+1 pour l'aéroport de départ initial)."""
    for a in planes:
        for k in airports:
            offset = 1 if k == start_airports[a][1] else 0
            for i in flights_from[k]:
                arrivals_before = [ip for ip in flights_to[k] if arr_times[ip] < dep_times[i]]
                departures_before = [ip for ip in flights_from[k] if dep_times[ip] < dep_times[i]]
                term = _continuity_term(x, a, arrivals_before, departures_before)
                m.addConstr(term + offset >= x[a, i], name=f"flow_continuity_{a}{k}{i}")


def _filter_night_flights(flights, airport, days):
    """Vols de nuit (22h-6h) d'un aéroport, partitionnés par jour, avec un point de repère de fin de nuit."""
    flights = sorted(flights, key=lambda f: f[3])
    start_time = 1320  # 22h00 en minutes
    end_time = 360  # 06h00 en minutes

    partitions = {}
    for i in days:
        night = [
            flight for flight in flights
            if start_time + 1440 * i <= flight[3] <= 1440 * (i + 1) + end_time
        ]
        night.append([None, airport, airport, 1440 * (i + 1) + end_time, 1440 * (i + 1) + end_time, None])
        partitions[i] = night
    return partitions


def build_night_flights(flights, flights_from, days):
    """Vols de nuit par aéroport et par jour (utilisés pour localiser les maintenances)."""
    night_flights = {}
    for airport, indices in flights_from.items():
        flights_for_airport = [flights[i] for i in indices]
        night_flights[airport] = _filter_night_flights(flights_for_airport, airport, days)
    return night_flights


def add_maintenance_location_constraints(
    m, x, z, planes, airports_maintenance, start_airports, days, night_flights, flights_from, flights_to,
    dep_times, arr_times,
):
    """Un avion ne peut être en maintenance à k le jour j que s'il y est présent cette nuit-là."""
    for a in planes:
        for k in airports_maintenance:
            is_start = k == start_airports[a][1]
            offset = 1 if is_start else 0
            # Sur l'aéroport de départ initial, le jour 0 est trivialement satisfait
            # (l'avion y est par construction) : pas besoin de contrainte ce jour-là.
            day_range = range(1, len(days)) if is_start else range(0, len(days))
            for j in day_range:
                for i in night_flights[k][j]:
                    arrivals_before = [ip for ip in flights_to[k] if arr_times[ip] < i[3]]
                    departures_before = [ip for ip in flights_from[k] if dep_times[ip] < i[3]]
                    term = _continuity_term(x, a, arrivals_before, departures_before)
                    m.addConstr(term + offset >= z[k, a, j], name=f"maintenance_{k}_{a}_{j}")


def set_objective(m, x, z, cost, cost_maintenance, planes, flight_indices, airports_maintenance, days):
    """Minimiser le coût total des vols affectés + le coût des maintenances effectuées."""
    flight_cost = gp.quicksum(cost[a][f] * x[a, f] for a in planes for f in flight_indices)
    maintenance_cost = gp.quicksum(
        cost_maintenance[v][a] * z[airports_maintenance[v], a, j]
        for a in planes
        for v in range(len(airports_maintenance))
        for j in days
    )
    m.setObjective(flight_cost + maintenance_cost, GRB.MINIMIZE)


def build_model(data, d, *, time_limit=1800, mip_gap=0.02, write_lp=False, model_name="Flow_Airplanes_with_Time"):
    """Construit le modèle Gurobi complet à partir des données parsées par `data_loader.lire_data`.

    Ne lance pas la résolution : appeler `result.model.optimize()` ensuite.
    """
    airports = data["Airports"]
    flights = data["Flight"]
    num_flights = data["Nbflight"]
    dep_times = [f[3] for f in flights]
    arr_times = [f[4] for f in flights]

    planes = data["Aircrafts"]
    flight_indices = range(num_flights)
    cost = np.array(data["Cost"]).T
    days = data["Days"]

    start_airports = data["Aircraft"]
    airports_maintenance = data["Airportmaintenance"]
    cost_maintenance = data["CostMaintenance"]
    cap_maintenance = data["capmaintenance"]

    m = gp.Model(model_name)

    x = m.addVars(planes, flight_indices, vtype=GRB.BINARY, name="x")
    y = m.addVars(planes, airports, vtype=GRB.BINARY, name="y")
    z = m.addVars(airports_maintenance, planes, days, vtype=GRB.BINARY, name="z")

    flights_from, flights_to = _flights_by_airport(airports, flights)

    add_flow_conservation_constraints(m, x, y, planes, airports, start_airports, flights_from, flights_to)
    add_tour_end_constraints(m, y, planes, airports)
    add_flight_assignment_constraints(m, x, planes, flight_indices)
    add_maintenance_capacity_constraints(m, z, days, airports_maintenance, planes, cap_maintenance)
    add_maintenance_spacing_constraints(m, z, planes, days, d, airports_maintenance)
    add_flow_continuity_constraints(
        m, x, planes, airports, start_airports, flights_from, flights_to, dep_times, arr_times
    )

    night_flights = build_night_flights(flights, flights_from, days)
    add_maintenance_location_constraints(
        m, x, z, planes, airports_maintenance, start_airports, days, night_flights,
        flights_from, flights_to, dep_times, arr_times,
    )

    set_objective(m, x, z, cost, cost_maintenance, planes, flight_indices, airports_maintenance, days)

    if write_lp:
        m.write(write_lp if isinstance(write_lp, str) else "model.lp")

    m.setParam("MIPGap", mip_gap)
    m.setParam("TimeLimit", time_limit)

    return ModelData(
        model=m,
        x=x,
        y=y,
        z=z,
        planes=planes,
        airports=airports,
        flights=flights,
        flight_indices=flight_indices,
        dep_times=dep_times,
        arr_times=arr_times,
        start_airports=start_airports,
        airports_maintenance=airports_maintenance,
        days=days,
        night_flights=night_flights,
        cost=cost,
        cost_maintenance=cost_maintenance,
    )
