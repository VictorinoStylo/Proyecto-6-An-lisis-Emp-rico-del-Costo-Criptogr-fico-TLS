import argparse
import glob
import math
import os

import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_PATTERN = "data/final_tls13/raw_results_final_tls13_*.csv"
RESULTS_DIR = "results/final_combined"


def ensure_results_directory():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def load_files(pattern):
    files = sorted(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(f"No se encontraron archivos con patrón: {pattern}")

    frames = []

    for file in files:
        df = pd.read_csv(file)
        df["source_file"] = os.path.basename(file)

        if "tls_config" not in df.columns:
            if "tls_versiones" in df.columns:
                df["tls_config"] = df["tls_versiones"]
            else:
                df["tls_config"] = "unknown"

        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    numeric_columns = [
        "repeticion",
        "num_requests",
        "num_requests_exitosos",
        "num_requests_fallidos",
        "dns_total_s",
        "tcp_total_s",
        "tls_handshake_total_s",
        "connection_setup_total_s",
        "http_total_s",
        "wall_total_s",
        "cpu_total_s",
        "tls_handshake_por_request_s",
        "setup_por_request_s",
        "http_por_request_s",
        "tls_como_porcentaje_wall_total",
        "setup_como_porcentaje_wall_total",
        "http_como_porcentaje_wall_total",
        "bytes_recibidos_total",
    ]

    for column in numeric_columns:
        if column in combined.columns:
            combined[column] = pd.to_numeric(combined[column], errors="coerce")

    combined = combined[combined["num_requests_exitosos"] > 0].copy()

    return combined, files


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


def build_general_summary(df):
    grouped = df.groupby(["tls_config", "tipo_sesion", "num_requests"])

    summary = grouped.agg(
        observaciones=("source_file", "count"),
        archivos=("source_file", "nunique"),
        servidores=("target_host", "nunique"),

        wall_total_promedio_s=("wall_total_s", "mean"),
        wall_total_mediana_s=("wall_total_s", "median"),
        wall_total_p95_s=("wall_total_s", p95),
        wall_total_std_s=("wall_total_s", "std"),

        tls_total_promedio_s=("tls_handshake_total_s", "mean"),
        tls_total_mediana_s=("tls_handshake_total_s", "median"),
        tls_total_p95_s=("tls_handshake_total_s", p95),
        tls_total_std_s=("tls_handshake_total_s", "std"),

        tls_por_request_promedio_s=("tls_handshake_por_request_s", "mean"),
        tls_porcentaje_wall_promedio=("tls_como_porcentaje_wall_total", "mean"),

        setup_total_promedio_s=("connection_setup_total_s", "mean"),
        http_total_promedio_s=("http_total_s", "mean"),
        cpu_total_promedio_s=("cpu_total_s", "mean"),

        bytes_recibidos_promedio=("bytes_recibidos_total", "mean"),
    ).reset_index()

    ci_rows = []

    for (tls_config, tipo, n), group in grouped:
        ci_rows.append({
            "tls_config": tls_config,
            "tipo_sesion": tipo,
            "num_requests": n,
            "wall_total_ci95_s": ci95(group["wall_total_s"]),
            "tls_total_ci95_s": ci95(group["tls_handshake_total_s"]),
            "cpu_total_ci95_s": ci95(group["cpu_total_s"]),
        })

    ci_df = pd.DataFrame(ci_rows)

    summary = summary.merge(
        ci_df,
        on=["tls_config", "tipo_sesion", "num_requests"],
        how="left",
    )

    return summary.fillna(0)


def build_general_comparison(df):
    rows = []

    for tls_config in sorted(df["tls_config"].dropna().unique()):
        tls_df = df[df["tls_config"] == tls_config]

        for n in sorted(tls_df["num_requests"].dropna().unique()):
            short = tls_df[
                (tls_df["tipo_sesion"] == "corta") &
                (tls_df["num_requests"] == n)
            ]

            long = tls_df[
                (tls_df["tipo_sesion"] == "larga") &
                (tls_df["num_requests"] == n)
            ]

            if short.empty or long.empty:
                continue

            wall_short = short["wall_total_s"].mean()
            wall_long = long["wall_total_s"].mean()

            tls_short = short["tls_handshake_total_s"].mean()
            tls_long = long["tls_handshake_total_s"].mean()

            cpu_short = short["cpu_total_s"].mean()
            cpu_long = long["cpu_total_s"].mean()

            rows.append({
                "tls_config": tls_config,
                "num_requests": n,

                "wall_total_corta_s": wall_short,
                "wall_total_larga_s": wall_long,
                "wall_ahorro_larga_pct":
                    ((wall_short - wall_long) / wall_short * 100)
                    if wall_short > 0 else 0,

                "tls_total_corta_s": tls_short,
                "tls_total_larga_s": tls_long,
                "tls_ahorro_larga_pct":
                    ((tls_short - tls_long) / tls_short * 100)
                    if tls_short > 0 else 0,

                "cpu_total_corta_s": cpu_short,
                "cpu_total_larga_s": cpu_long,
                "cpu_ahorro_larga_pct":
                    ((cpu_short - cpu_long) / cpu_short * 100)
                    if cpu_short > 0 else 0,
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

        target_corr.columns = [
            "variable",
            f"correlacion_con_{target}"
        ]
    else:
        target_corr = pd.DataFrame()

    return covariance, correlation, target_corr


def plot_general_total(summary):
    plt.figure(figsize=(10, 6))

    for tls_config in sorted(summary["tls_config"].unique()):

        for tipo in ["corta", "larga"]:

            sub = summary[
                (summary["tls_config"] == tls_config) &
                (summary["tipo_sesion"] == tipo)
            ]

            if sub.empty:
                continue

            plt.plot(
                sub["num_requests"],
                sub["wall_total_promedio_s"],
                marker="o",
                label=f"{tls_config} - {tipo}",
            )

    plt.xlabel("Número de requests")
    plt.ylabel("Tiempo total observable (s)")
    plt.title("Tiempo total combinado")
    plt.legend(fontsize=8)
    plt.grid(True)
    plt.tight_layout()

    plt.savefig(
        os.path.join(
            RESULTS_DIR,
            "combined_01_tiempo_total.png"
        ),
        dpi=300,
    )

    plt.close()


def plot_general_tls(summary):
    plt.figure(figsize=(10, 6))

    for tls_config in sorted(summary["tls_config"].unique()):

        for tipo in ["corta", "larga"]:

            sub = summary[
                (summary["tls_config"] == tls_config) &
                (summary["tipo_sesion"] == tipo)
            ]

            if sub.empty:
                continue

            plt.plot(
                sub["num_requests"],
                sub["tls_total_promedio_s"],
                marker="o",
                label=f"{tls_config} - {tipo}",
            )

    plt.xlabel("Número de requests")
    plt.ylabel("Handshake TLS total (s)")
    plt.title("Costo criptográfico combinado")
    plt.legend(fontsize=8)
    plt.grid(True)
    plt.tight_layout()

    plt.savefig(
        os.path.join(
            RESULTS_DIR,
            "combined_02_tls_handshake.png"
        ),
        dpi=300,
    )

    plt.close()


def plot_general_savings(comparison):
    plt.figure(figsize=(10, 6))

    for tls_config in sorted(comparison["tls_config"].unique()):

        sub = comparison[
            comparison["tls_config"] == tls_config
        ]

        if sub.empty:
            continue

        plt.plot(
            sub["num_requests"],
            sub["wall_ahorro_larga_pct"],
            marker="o",
            label=f"Ahorro wall - {tls_config}",
        )

        plt.plot(
            sub["num_requests"],
            sub["tls_ahorro_larga_pct"],
            marker="s",
            linestyle="--",
            label=f"Ahorro TLS - {tls_config}",
        )

    plt.xlabel("Número de requests")
    plt.ylabel("Ahorro usando sesión larga (%)")
    plt.title("Ahorro combinado por reutilización de sesión")
    plt.legend(fontsize=8)
    plt.grid(True)
    plt.tight_layout()

    plt.savefig(
        os.path.join(
            RESULTS_DIR,
            "combined_03_ahorro.png"
        ),
        dpi=300,
    )

    plt.close()


def write_report(df, files, comparison, target_corr):
    path = os.path.join(
        RESULTS_DIR,
        "combined_report.txt"
    )

    text = []

    text.append("Reporte combinado del Proyecto 6")
    text.append("================================")
    text.append("")

    text.append("Archivos tomados en cuenta:")

    for file in files:
        text.append(f"- {file}")

    text.append("")
    text.append("Servidores usados en el análisis:")

    for host in sorted(df["target_host"].dropna().unique()):
        text.append(f"- {host}")

    if not comparison.empty:

        last = (
            comparison
            .sort_values(["tls_config", "num_requests"])
            .groupby("tls_config")
            .tail(1)
        )

        text.append("")
        text.append(
            "Conclusión por configuración TLS "
            "en el mayor n observado:"
        )

        for _, row in last.iterrows():

            text.append(
                f"- {row['tls_config']}: "
                f"ahorro wall={row['wall_ahorro_larga_pct']:.2f}%, "
                f"ahorro TLS={row['tls_ahorro_larga_pct']:.2f}%, "
                f"ahorro CPU={row['cpu_ahorro_larga_pct']:.2f}%."
            )

    if not target_corr.empty:

        text.append("")
        text.append(
            "Variables más correlacionadas "
            "con tls_handshake_total_s:"
        )

        text.append(
            target_corr.head(10).to_string(index=False)
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(text))

    return path


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Combina CSVs finales del Proyecto 6 "
            "y genera análisis estadístico global."
        )
    )

    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
    )

    args = parser.parse_args()

    ensure_results_directory()

    df, files = load_files(args.pattern)

    summary = build_general_summary(df)

    comparison = build_general_comparison(df)

    covariance, correlation, target_corr = (
        build_covariance_and_correlation(df)
    )

    df.to_csv(
        os.path.join(
            RESULTS_DIR,
            "combined_raw_results.csv"
        ),
        index=False,
    )

    summary.to_csv(
        os.path.join(
            RESULTS_DIR,
            "combined_summary.csv"
        ),
        index=False,
    )

    comparison.to_csv(
        os.path.join(
            RESULTS_DIR,
            "combined_comparison.csv"
        ),
        index=False,
    )

    covariance.to_csv(
        os.path.join(
            RESULTS_DIR,
            "combined_covariance_matrix.csv"
        )
    )

    correlation.to_csv(
        os.path.join(
            RESULTS_DIR,
            "combined_correlation_matrix.csv"
        )
    )

    target_corr.to_csv(
        os.path.join(
            RESULTS_DIR,
            "combined_target_correlations.csv"
        ),
        index=False,
    )

    plot_general_total(summary)
    plot_general_tls(summary)
    plot_general_savings(comparison)

    report = write_report(
        df,
        files,
        comparison,
        target_corr,
    )

    print("\nArchivos combinados:")

    for file in files:
        print(f"- {file}")

    print("\nServidores usados en el análisis:")

    for host in sorted(df["target_host"].dropna().unique()):
        print(f"- {host}")

    print("\nArchivos generados en results/final_combined/")

    print("- combined_raw_results.csv")
    print("- combined_summary.csv")
    print("- combined_comparison.csv")
    print("- combined_covariance_matrix.csv")
    print("- combined_correlation_matrix.csv")
    print("- combined_target_correlations.csv")
    print("- combined_report.txt")
    print("- combined_01_tiempo_total.png")
    print("- combined_02_tls_handshake.png")
    print("- combined_03_ahorro.png")

    print("\nReporte:\n")

    with open(report, "r", encoding="utf-8") as f:
        print(f.read())


if __name__ == "__main__":
    main()