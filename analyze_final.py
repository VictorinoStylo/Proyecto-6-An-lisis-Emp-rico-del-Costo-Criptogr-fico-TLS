import argparse
import glob
import math
import os

import pandas as pd
import matplotlib.pyplot as plt


DATA_PATTERN = "data/final_tls13/raw_results_final_tls13_*.csv"
RESULTS_DIR = "results/final_tls13"


def ensure_results_directory():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def latest_file(pattern):
    files = glob.glob(pattern)

    if not files:
        raise FileNotFoundError(f"No se encontraron archivos con patrón: {pattern}")

    return max(files, key=os.path.getmtime)


def load_data(input_file):
    if input_file == "latest":
        input_file = latest_file(DATA_PATTERN)

    df = pd.read_csv(input_file)
    df["source_file"] = os.path.basename(input_file)

    numeric_columns = [
        "repeticion",
        "num_requests",
        "num_requests_exitosos",
        "num_requests_fallidos",
        "dns_total_s",
        "dns_promedio_s",
        "tcp_total_s",
        "tcp_promedio_s",
        "tls_handshake_total_s",
        "tls_handshake_promedio_s",
        "tls_handshake_mediana_s",
        "tls_handshake_p95_s",
        "tls_handshake_std_s",
        "connection_setup_total_s",
        "connection_setup_promedio_s",
        "connection_setup_cpu_total_s",
        "connection_setup_cpu_promedio_s",
        "http_total_s",
        "http_promedio_s",
        "http_mediana_s",
        "http_p95_s",
        "wall_total_s",
        "wall_promedio_s",
        "wall_mediana_s",
        "wall_p95_s",
        "wall_std_s",
        "cpu_total_s",
        "cpu_promedio_s",
        "cpu_mediana_s",
        "cpu_p95_s",
        "cpu_std_s",
        "tls_handshake_por_request_s",
        "setup_por_request_s",
        "http_por_request_s",
        "tls_como_porcentaje_wall_total",
        "setup_como_porcentaje_wall_total",
        "http_como_porcentaje_wall_total",
        "bytes_enviados_total",
        "bytes_recibidos_total",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df[df["num_requests_exitosos"] > 0].copy()

    return df, input_file


def ci95(series):
    series = series.dropna()

    if len(series) <= 1:
        return 0

    return 1.96 * series.std() / math.sqrt(len(series))


def p95(series):
    series = series.dropna()

    if len(series) == 0:
        return None

    return series.quantile(0.95)


def cohen_d(a, b):
    a = a.dropna()
    b = b.dropna()

    if len(a) < 2 or len(b) < 2:
        return 0

    pooled_var = (((len(a) - 1) * a.var()) + ((len(b) - 1) * b.var())) / (len(a) + len(b) - 2)

    if pooled_var <= 0:
        return 0

    return (a.mean() - b.mean()) / math.sqrt(pooled_var)


def build_summary_by_target(df):
    grouped = df.groupby(["target_host", "tipo_sesion", "num_requests"])

    summary = grouped.agg(
        observaciones=("repeticion", "count"),
        requests_exitosos_promedio=("num_requests_exitosos", "mean"),
        requests_fallidos_promedio=("num_requests_fallidos", "mean"),

        wall_total_promedio_s=("wall_total_s", "mean"),
        wall_total_mediana_s=("wall_total_s", "median"),
        wall_total_std_s=("wall_total_s", "std"),
        wall_total_p95_s=("wall_total_s", p95),

        tls_total_promedio_s=("tls_handshake_total_s", "mean"),
        tls_total_mediana_s=("tls_handshake_total_s", "median"),
        tls_total_std_s=("tls_handshake_total_s", "std"),
        tls_total_p95_s=("tls_handshake_total_s", p95),

        tls_por_request_promedio_s=("tls_handshake_por_request_s", "mean"),
        tls_porcentaje_wall_promedio=("tls_como_porcentaje_wall_total", "mean"),

        setup_total_promedio_s=("connection_setup_total_s", "mean"),
        setup_porcentaje_wall_promedio=("setup_como_porcentaje_wall_total", "mean"),

        http_total_promedio_s=("http_total_s", "mean"),
        http_porcentaje_wall_promedio=("http_como_porcentaje_wall_total", "mean"),

        cpu_total_promedio_s=("cpu_total_s", "mean"),
        dns_total_promedio_s=("dns_total_s", "mean"),
        tcp_total_promedio_s=("tcp_total_s", "mean"),

        bytes_recibidos_promedio=("bytes_recibidos_total", "mean"),
    ).reset_index()

    ci_rows = []

    for (host, tipo, n), group in grouped:
        ci_rows.append({
            "target_host": host,
            "tipo_sesion": tipo,
            "num_requests": n,
            "wall_total_ci95_s": ci95(group["wall_total_s"]),
            "tls_total_ci95_s": ci95(group["tls_handshake_total_s"]),
            "cpu_total_ci95_s": ci95(group["cpu_total_s"]),
        })

    ci_df = pd.DataFrame(ci_rows)

    summary = summary.merge(ci_df, on=["target_host", "tipo_sesion", "num_requests"], how="left")
    return summary.fillna(0)


def build_global_summary(df):
    grouped = df.groupby(["tipo_sesion", "num_requests"])

    summary = grouped.agg(
        observaciones=("repeticion", "count"),
        servidores=("target_host", "nunique"),

        wall_total_promedio_s=("wall_total_s", "mean"),
        wall_total_mediana_s=("wall_total_s", "median"),
        wall_total_std_s=("wall_total_s", "std"),
        wall_total_p95_s=("wall_total_s", p95),

        tls_total_promedio_s=("tls_handshake_total_s", "mean"),
        tls_total_mediana_s=("tls_handshake_total_s", "median"),
        tls_total_std_s=("tls_handshake_total_s", "std"),
        tls_total_p95_s=("tls_handshake_total_s", p95),

        tls_por_request_promedio_s=("tls_handshake_por_request_s", "mean"),
        tls_porcentaje_wall_promedio=("tls_como_porcentaje_wall_total", "mean"),

        setup_total_promedio_s=("connection_setup_total_s", "mean"),
        setup_porcentaje_wall_promedio=("setup_como_porcentaje_wall_total", "mean"),

        http_total_promedio_s=("http_total_s", "mean"),
        http_porcentaje_wall_promedio=("http_como_porcentaje_wall_total", "mean"),

        cpu_total_promedio_s=("cpu_total_s", "mean"),
        dns_total_promedio_s=("dns_total_s", "mean"),
        tcp_total_promedio_s=("tcp_total_s", "mean"),
    ).reset_index()

    ci_rows = []

    for (tipo, n), group in grouped:
        ci_rows.append({
            "tipo_sesion": tipo,
            "num_requests": n,
            "wall_total_ci95_s": ci95(group["wall_total_s"]),
            "tls_total_ci95_s": ci95(group["tls_handshake_total_s"]),
            "cpu_total_ci95_s": ci95(group["cpu_total_s"]),
        })

    ci_df = pd.DataFrame(ci_rows)

    summary = summary.merge(ci_df, on=["tipo_sesion", "num_requests"], how="left")
    return summary.fillna(0)


def build_global_comparison(df):
    rows = []

    for n in sorted(df["num_requests"].dropna().unique()):
        short = df[(df["tipo_sesion"] == "corta") & (df["num_requests"] == n)]
        long = df[(df["tipo_sesion"] == "larga") & (df["num_requests"] == n)]

        if short.empty or long.empty:
            continue

        wall_short = short["wall_total_s"].mean()
        wall_long = long["wall_total_s"].mean()

        tls_short = short["tls_handshake_total_s"].mean()
        tls_long = long["tls_handshake_total_s"].mean()

        cpu_short = short["cpu_total_s"].mean()
        cpu_long = long["cpu_total_s"].mean()

        setup_short = short["connection_setup_total_s"].mean()
        setup_long = long["connection_setup_total_s"].mean()

        rows.append({
            "num_requests": n,

            "wall_total_corta_s": wall_short,
            "wall_total_larga_s": wall_long,
            "wall_ahorro_larga_s": wall_short - wall_long,
            "wall_ahorro_larga_pct": ((wall_short - wall_long) / wall_short * 100) if wall_short > 0 else 0,
            "wall_cohen_d": cohen_d(short["wall_total_s"], long["wall_total_s"]),

            "tls_total_corta_s": tls_short,
            "tls_total_larga_s": tls_long,
            "tls_ahorro_larga_s": tls_short - tls_long,
            "tls_ahorro_larga_pct": ((tls_short - tls_long) / tls_short * 100) if tls_short > 0 else 0,
            "tls_cohen_d": cohen_d(short["tls_handshake_total_s"], long["tls_handshake_total_s"]),

            "setup_total_corta_s": setup_short,
            "setup_total_larga_s": setup_long,
            "setup_ahorro_larga_s": setup_short - setup_long,
            "setup_ahorro_larga_pct": ((setup_short - setup_long) / setup_short * 100) if setup_short > 0 else 0,

            "cpu_total_corta_s": cpu_short,
            "cpu_total_larga_s": cpu_long,
            "cpu_ahorro_larga_s": cpu_short - cpu_long,
            "cpu_ahorro_larga_pct": ((cpu_short - cpu_long) / cpu_short * 100) if cpu_short > 0 else 0,
            "cpu_cohen_d": cohen_d(short["cpu_total_s"], long["cpu_total_s"]),
        })

    return pd.DataFrame(rows)


def build_target_comparison(df):
    rows = []

    for host in sorted(df["target_host"].dropna().unique()):
        host_df = df[df["target_host"] == host]

        for n in sorted(host_df["num_requests"].dropna().unique()):
            short = host_df[(host_df["tipo_sesion"] == "corta") & (host_df["num_requests"] == n)]
            long = host_df[(host_df["tipo_sesion"] == "larga") & (host_df["num_requests"] == n)]

            if short.empty or long.empty:
                continue

            wall_short = short["wall_total_s"].mean()
            wall_long = long["wall_total_s"].mean()

            tls_short = short["tls_handshake_total_s"].mean()
            tls_long = long["tls_handshake_total_s"].mean()

            rows.append({
                "target_host": host,
                "num_requests": n,
                "wall_ahorro_larga_pct": ((wall_short - wall_long) / wall_short * 100) if wall_short > 0 else 0,
                "tls_ahorro_larga_pct": ((tls_short - tls_long) / tls_short * 100) if tls_short > 0 else 0,
                "wall_cohen_d": cohen_d(short["wall_total_s"], long["wall_total_s"]),
                "tls_cohen_d": cohen_d(short["tls_handshake_total_s"], long["tls_handshake_total_s"]),
            })

    return pd.DataFrame(rows)


def build_covariance_and_correlation(df):
    metric_columns = [
        "num_requests",
        "dns_total_s",
        "tcp_total_s",
        "tls_handshake_total_s",
        "connection_setup_total_s",
        "http_total_s",
        "wall_total_s",
        "cpu_total_s",
        "tls_handshake_por_request_s",
        "tls_como_porcentaje_wall_total",
        "setup_como_porcentaje_wall_total",
        "http_como_porcentaje_wall_total",
        "bytes_recibidos_total",
    ]

    existing = [c for c in metric_columns if c in df.columns]
    metrics = df[existing].copy()

    covariance = metrics.cov(numeric_only=True)
    correlation = metrics.corr(numeric_only=True)

    target = "tls_handshake_total_s"

    if target in correlation.columns:
        target_corr = correlation[target].dropna()
        ordered = target_corr.abs().sort_values(ascending=False).index
        target_corr = target_corr.loc[ordered].reset_index()
        target_corr.columns = ["variable", f"correlacion_con_{target}"]
    else:
        target_corr = pd.DataFrame()

    return covariance, correlation, target_corr


def plot_line(summary, y_col, ci_col, ylabel, title, output):
    plt.figure(figsize=(9, 5))

    for tipo in ["corta", "larga"]:
        sub = summary[summary["tipo_sesion"] == tipo]

        if sub.empty:
            continue

        plt.errorbar(
            sub["num_requests"],
            sub[y_col],
            yerr=sub[ci_col] if ci_col in sub.columns else None,
            marker="o",
            capsize=4,
            label=f"Sesión {tipo}",
        )

    plt.xlabel("Número de requests")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output, dpi=300)
    plt.close()


def plot_savings(comparison):
    plt.figure(figsize=(9, 5))

    plt.plot(comparison["num_requests"], comparison["wall_ahorro_larga_pct"], marker="o", label="Ahorro en tiempo total")
    plt.plot(comparison["num_requests"], comparison["tls_ahorro_larga_pct"], marker="o", label="Ahorro en handshake TLS")
    plt.plot(comparison["num_requests"], comparison["setup_ahorro_larga_pct"], marker="o", label="Ahorro en setup")
    plt.plot(comparison["num_requests"], comparison["cpu_ahorro_larga_pct"], marker="o", label="Ahorro en CPU")

    plt.xlabel("Número de requests")
    plt.ylabel("Ahorro usando sesión larga (%)")
    plt.title("Beneficio de reutilizar sesión TLS 1.3")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "final_04_ahorro_global.png"), dpi=300)
    plt.close()


def plot_components(global_summary):
    plt.figure(figsize=(9, 5))

    for tipo in ["corta", "larga"]:
        sub = global_summary[global_summary["tipo_sesion"] == tipo]

        if sub.empty:
            continue

        plt.plot(sub["num_requests"], sub["dns_total_promedio_s"], marker="o", linestyle=":", label=f"DNS - {tipo}")
        plt.plot(sub["num_requests"], sub["tcp_total_promedio_s"], marker="o", linestyle="--", label=f"TCP - {tipo}")
        plt.plot(sub["num_requests"], sub["tls_total_promedio_s"], marker="o", linestyle="-.", label=f"TLS - {tipo}")
        plt.plot(sub["num_requests"], sub["http_total_promedio_s"], marker="o", linestyle="-", label=f"HTTP - {tipo}")

    plt.xlabel("Número de requests")
    plt.ylabel("Tiempo acumulado promedio (s)")
    plt.title("Descomposición del costo observable")
    plt.legend(fontsize=8)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "final_05_componentes_costo.png"), dpi=300)
    plt.close()


def plot_tls_share(global_summary):
    plt.figure(figsize=(9, 5))

    for tipo in ["corta", "larga"]:
        sub = global_summary[global_summary["tipo_sesion"] == tipo]

        if sub.empty:
            continue

        plt.plot(sub["num_requests"], sub["tls_porcentaje_wall_promedio"], marker="o", label=f"Sesión {tipo}")

    plt.xlabel("Número de requests")
    plt.ylabel("Handshake TLS como % del tiempo total")
    plt.title("Peso relativo del costo criptográfico TLS 1.3")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "final_06_tls_porcentaje_wall.png"), dpi=300)
    plt.close()


def plot_target_savings(target_comparison):
    if target_comparison.empty:
        return

    largest_n = target_comparison["num_requests"].max()
    sub = target_comparison[target_comparison["num_requests"] == largest_n].copy()

    plt.figure(figsize=(10, 5))
    plt.bar(sub["target_host"], sub["wall_ahorro_larga_pct"])
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Ahorro en tiempo total (%)")
    plt.title(f"Ahorro por servidor con n={int(largest_n)}")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "final_07_ahorro_por_servidor.png"), dpi=300)
    plt.close()


def plot_correlation_heatmap(correlation):
    if correlation.empty:
        return

    plt.figure(figsize=(10, 8))
    plt.imshow(correlation, aspect="auto")
    plt.colorbar(label="Correlación de Pearson")
    plt.xticks(range(len(correlation.columns)), correlation.columns, rotation=90)
    plt.yticks(range(len(correlation.index)), correlation.index)
    plt.title("Matriz de correlación de métricas")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "final_08_matriz_correlacion.png"), dpi=300)
    plt.close()


def write_conclusion(input_file, df, global_comparison, target_corr):
    path = os.path.join(RESULTS_DIR, "final_conclusion.txt")

    if global_comparison.empty:
        text = "No hay datos suficientes para generar conclusión automática."
    else:
        largest = global_comparison.iloc[-1]
        hosts = sorted(df["target_host"].dropna().unique())
        tls_versions = sorted(df["tls_versiones"].dropna().unique())

        text = (
            "Conclusión automática del experimento TLS 1.3\n"
            "================================================\n\n"
            f"Archivo analizado: {input_file}\n"
            f"Servidores incluidos: {', '.join(hosts)}\n"
            f"Versiones TLS registradas: {', '.join(tls_versions)}\n"
            f"Escenario máximo: n={int(largest['num_requests'])} requests.\n\n"
            f"Ahorro en tiempo total usando sesión larga: {largest['wall_ahorro_larga_pct']:.2f}%.\n"
            f"Ahorro en handshake TLS usando sesión larga: {largest['tls_ahorro_larga_pct']:.2f}%.\n"
            f"Ahorro en setup de conexión usando sesión larga: {largest['setup_ahorro_larga_pct']:.2f}%.\n"
            f"Ahorro en CPU usando sesión larga: {largest['cpu_ahorro_larga_pct']:.2f}%.\n\n"
            "Interpretación:\n"
            "El costo criptográfico observable se concentra en el establecimiento inicial de la conexión segura. "
            "En sesiones cortas, ese costo se repite con cada request; en sesiones largas, el costo se paga principalmente una vez "
            "y se amortiza entre varias solicitudes. Por lo tanto, la evidencia empírica responde la pregunta del Proyecto 6: "
            "el impacto del costo criptográfico se percibe más en sesiones efímeras que en sesiones persistentes.\n\n"
        )

        if not target_corr.empty:
            text += "Variables con mayor correlación absoluta respecto a tls_handshake_total_s:\n"
            text += target_corr.head(8).to_string(index=False)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    return path


def main():
    parser = argparse.ArgumentParser(description="Análisis final del Proyecto 6 con TLS 1.3 estricto.")
    parser.add_argument("--input", default="latest", help="Ruta del CSV o 'latest'.")
    args = parser.parse_args()

    ensure_results_directory()

    df, input_file = load_data(args.input)

    summary_by_target = build_summary_by_target(df)
    global_summary = build_global_summary(df)
    global_comparison = build_global_comparison(df)
    target_comparison = build_target_comparison(df)
    covariance, correlation, target_corr = build_covariance_and_correlation(df)

    summary_by_target.to_csv(os.path.join(RESULTS_DIR, "final_summary_by_target.csv"), index=False)
    global_summary.to_csv(os.path.join(RESULTS_DIR, "final_global_summary.csv"), index=False)
    global_comparison.to_csv(os.path.join(RESULTS_DIR, "final_global_comparison.csv"), index=False)
    target_comparison.to_csv(os.path.join(RESULTS_DIR, "final_target_comparison.csv"), index=False)
    covariance.to_csv(os.path.join(RESULTS_DIR, "final_covariance_matrix.csv"))
    correlation.to_csv(os.path.join(RESULTS_DIR, "final_correlation_matrix.csv"))
    target_corr.to_csv(os.path.join(RESULTS_DIR, "final_target_correlations.csv"), index=False)

    plot_line(
        global_summary,
        "wall_total_promedio_s",
        "wall_total_ci95_s",
        "Tiempo total observable (s)",
        "Tiempo total observable global",
        os.path.join(RESULTS_DIR, "final_01_tiempo_total_global.png"),
    )

    plot_line(
        global_summary,
        "tls_total_promedio_s",
        "tls_total_ci95_s",
        "Tiempo total en handshake TLS (s)",
        "Costo criptográfico observable global",
        os.path.join(RESULTS_DIR, "final_02_tls_global.png"),
    )

    plot_line(
        global_summary,
        "tls_por_request_promedio_s",
        "tls_total_ci95_s",
        "Handshake TLS por request (s)",
        "Amortización del handshake TLS",
        os.path.join(RESULTS_DIR, "final_03_tls_por_request.png"),
    )

    plot_savings(global_comparison)
    plot_components(global_summary)
    plot_tls_share(global_summary)
    plot_target_savings(target_comparison)
    plot_correlation_heatmap(correlation)

    conclusion_path = write_conclusion(input_file, df, global_comparison, target_corr)

    print(f"\nArchivo analizado: {input_file}")
    print("\nArchivos generados en results/final_tls13/")
    print("- final_summary_by_target.csv")
    print("- final_global_summary.csv")
    print("- final_global_comparison.csv")
    print("- final_target_comparison.csv")
    print("- final_covariance_matrix.csv")
    print("- final_correlation_matrix.csv")
    print("- final_target_correlations.csv")
    print("- final_conclusion.txt")
    print("- final_01_tiempo_total_global.png")
    print("- final_02_tls_global.png")
    print("- final_03_tls_por_request.png")
    print("- final_04_ahorro_global.png")
    print("- final_05_componentes_costo.png")
    print("- final_06_tls_porcentaje_wall.png")
    print("- final_07_ahorro_por_servidor.png")
    print("- final_08_matriz_correlacion.png")

    print("\nConclusión resumida:")
    with open(conclusion_path, "r", encoding="utf-8") as f:
        print(f.read())


if __name__ == "__main__":
    main()