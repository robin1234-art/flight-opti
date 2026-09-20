"""Interface Streamlit : lancer l'optimisation sur un fichier .dat et exporter les résultats.

Usage:
    streamlit run app/app.py
"""

import io
import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metier.data_loader import lire_data
from metier.optimization_model import build_model
from metier.reporting import build_schedule_figure, format_solution_text

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"

STATUS_LABELS = {2: "Optimal", 3: "Infaisable", 9: "Limite de temps atteinte"}


def list_sample_files():
    files = {}
    if SAMPLE_DATA_DIR.exists():
        for d_folder in sorted(SAMPLE_DATA_DIR.iterdir()):
            if d_folder.is_dir():
                for f in sorted(d_folder.glob("*.dat")):
                    files[f"{d_folder.name}/{f.name}"] = f
    return files


def guess_d_from_label(label):
    try:
        return int(label.split("d=", 1)[1].split("/", 1)[0])
    except (IndexError, ValueError):
        return 4


def save_uploaded_file(uploaded):
    tmp_dir = Path(tempfile.mkdtemp(prefix="flight_opti_"))
    tmp_path = tmp_dir / uploaded.name
    tmp_path.write_bytes(uploaded.getvalue())
    return tmp_path


def run_optimization(data_path, d, time_limit, mip_gap):
    data = lire_data(str(data_path))
    model_data = build_model(data, d, time_limit=time_limit, mip_gap=mip_gap)
    model_data.model.setParam("OutputFlag", 0)
    log_path = Path(tempfile.mkstemp(suffix=".log")[1])
    model_data.model.setParam("LogFile", str(log_path))
    model_data.model.optimize()
    log_text = log_path.read_text() if log_path.exists() else ""
    return model_data, log_text


def main():
    st.set_page_config(page_title="Flight Opti", layout="wide")
    st.title("Optimisation de tournées d'avions")

    sample_files = list_sample_files()

    st.sidebar.header("Données")
    source = st.sidebar.radio("Source des données", ["Jeu d'exemple", "Importer un fichier .dat"])

    data_path = None
    default_d = 4

    if source == "Jeu d'exemple":
        if not sample_files:
            st.sidebar.warning("Aucun fichier d'exemple dans sample_data/.")
        else:
            label = st.sidebar.selectbox("Fichier", list(sample_files.keys()))
            data_path = sample_files[label]
            default_d = guess_d_from_label(label)
    else:
        uploaded = st.sidebar.file_uploader(
            "Fichier .dat (le nom doit contenir 'p=<N>_', format CPLEX attendu)", type=["dat"]
        )
        if uploaded is not None:
            data_path = save_uploaded_file(uploaded)

    st.sidebar.header("Paramètres du modèle")
    d = st.sidebar.number_input("d (jours max entre deux maintenances)", min_value=1, max_value=30, value=default_d)
    time_limit = st.sidebar.number_input("Limite de temps (s)", min_value=1, max_value=3600, value=120)
    mip_gap = st.sidebar.number_input(
        "Gap MIP cible", min_value=0.0, max_value=1.0, value=0.2, step=0.01, format="%.2f"
    )

    run = st.sidebar.button("Lancer l'optimisation", type="primary", disabled=data_path is None)

    if run:
        with st.spinner("Résolution en cours (Gurobi)..."):
            try:
                model_data, log_text = run_optimization(data_path, d, time_limit, mip_gap)
            except Exception as exc:
                st.session_state.pop("result", None)
                st.error(f"Échec de l'optimisation : {exc}")
                st.stop()

        source_label = Path(data_path).stem

        if model_data.model.SolCount == 0:
            st.session_state["result"] = {
                "status": model_data.model.Status,
                "no_solution": True,
                "log": log_text,
            }
        else:
            fig = build_schedule_figure(model_data)
            svg_buf = io.BytesIO()
            fig.savefig(svg_buf, format="svg")

            st.session_state["result"] = {
                "status": model_data.model.Status,
                "no_solution": False,
                "obj_val": model_data.model.ObjVal,
                "mip_gap": model_data.model.MIPGap,
                "fig": fig,
                "svg_bytes": svg_buf.getvalue(),
                "text": format_solution_text(model_data),
                "log": log_text,
                "source_label": source_label,
            }

    result = st.session_state.get("result")
    if result is None:
        st.info("Choisissez un fichier de données puis lancez l'optimisation.")
        return

    status_label = STATUS_LABELS.get(result["status"], f"Statut {result['status']}")

    if result["no_solution"]:
        st.error(f"Aucune solution trouvée (statut Gurobi : {status_label}).")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Statut", status_label)
        col2.metric("Coût total", f"{result['obj_val']:.2f}")
        col3.metric("Gap MIP", f"{result['mip_gap'] * 100:.2f} %")

        st.subheader("Planning des avions")
        st.pyplot(result["fig"])
        st.download_button(
            "Télécharger le planning (SVG)",
            data=result["svg_bytes"],
            file_name=f"planning_{result['source_label']}.svg",
            mime="image/svg+xml",
        )

        st.subheader("Détail texte de la solution")
        st.text_area("Résultats", result["text"], height=400)
        st.download_button(
            "Télécharger le détail (TXT)",
            data=result["text"],
            file_name=f"resultats_{result['source_label']}.txt",
            mime="text/plain",
        )

    with st.expander("Log Gurobi"):
        st.text(result["log"] or "(vide)")


if __name__ == "__main__":
    main()
