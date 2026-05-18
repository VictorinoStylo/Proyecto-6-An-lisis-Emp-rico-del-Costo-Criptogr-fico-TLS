import argparse
import os
import ssl
import time
import socket
import platform
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd


TARGET_SETS = {
    "real_world": [
        "https://www.google.com/",
        "https://www.youtube.com/",
        "https://www.wikipedia.org/",
        "https://www.github.com/",
        "https://www.python.org/",
    ]
}

BACKUP_TARGETS = [
    "https://www.apple.com/",
    "https://www.microsoft.com/",
    "https://www.amazon.com/",
    "https://www.linkedin.com/",
    "https://www.bbc.com/",
]

DEFAULT_REQUEST_SIZES = "1,3,5,10,20,50,100"
DEFAULT_REPETITIONS = 15
DEFAULT_TIMEOUT = 10
DEFAULT_DELAY = 0.15

DATA_DIR = "data/final_tls13"
RESULTS_DIR = "results/final_tls13"


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def ensure_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)


def parse_sizes(text):
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def parse_targets(text, target_set):
    if text and text.strip():
        return [x.strip() for x in text.split(",") if x.strip()]
    return TARGET_SETS[target_set]


def parse_url(url):
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError(f"Solo se permiten URLs HTTPS: {url}")

    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path if parsed.path else "/"

    if parsed.query:
        path = path + "?" + parsed.query

    return {
        "target_name": host.replace(".", "_"),
        "url": url,
        "host": host,
        "port": port,
        "path": path,
    }


def create_tls13_context():
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    return context


def open_tls_connection(host, port, timeout):
    setup_wall_start = time.perf_counter()
    setup_cpu_start = time.process_time()

    dns_start = time.perf_counter()
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    dns_end = time.perf_counter()

    last_error = None

    for family, socktype, proto, _, sockaddr in addresses:
        raw_sock = None

        try:
            raw_sock = socket.socket(family, socktype, proto)
            raw_sock.settimeout(timeout)

            tcp_start = time.perf_counter()
            raw_sock.connect(sockaddr)
            tcp_end = time.perf_counter()

            context = create_tls13_context()

            tls_start = time.perf_counter()
            tls_sock = context.wrap_socket(raw_sock, server_hostname=host)
            tls_end = time.perf_counter()

            setup_cpu_end = time.process_time()
            setup_wall_end = time.perf_counter()

            metrics = {
                "dns_time_s": dns_end - dns_start,
                "tcp_connect_time_s": tcp_end - tcp_start,
                "tls_handshake_time_s": tls_end - tls_start,
                "connection_setup_wall_s": setup_wall_end - setup_wall_start,
                "connection_setup_cpu_s": setup_cpu_end - setup_cpu_start,
                "tls_version": tls_sock.version(),
                "cipher_suite": str(tls_sock.cipher()),
            }

            return tls_sock, metrics

        except Exception as error:
            last_error = error
            if raw_sock is not None:
                try:
                    raw_sock.close()
                except Exception:
                    pass

    raise RuntimeError(f"No se pudo abrir conexión TLS 1.3 con {host}: {last_error}")


def build_http_request(host, path, connection_mode):
    return (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"User-Agent: proyecto6-tls13-final/1.0\r\n"
        f"Accept: */*\r\n"
        f"Accept-Encoding: identity\r\n"
        f"Connection: {connection_mode}\r\n"
        f"\r\n"
    ).encode("utf-8")


def recv_more(sock, buffer):
    chunk = sock.recv(4096)

    if not chunk:
        return buffer, False

    return buffer + chunk, True


def read_until_headers(sock):
    data = b""

    while b"\r\n\r\n" not in data:
        data, ok = recv_more(sock, data)

        if not ok:
            break

        if len(data) > 2_000_000:
            raise RuntimeError("Respuesta demasiado grande antes de headers completos.")

    if b"\r\n\r\n" not in data:
        raise RuntimeError("No se recibieron headers HTTP completos.")

    header_bytes, body = data.split(b"\r\n\r\n", 1)
    headers_text = header_bytes.decode("iso-8859-1", errors="replace")

    return header_bytes, headers_text, body


def parse_status_code(headers_text):
    status_line = headers_text.split("\r\n")[0]
    parts = status_line.split(" ")

    if len(parts) < 2:
        raise RuntimeError(f"Status line inválida: {status_line}")

    return int(parts[1])


def parse_content_length(headers_text):
    for line in headers_text.split("\r\n"):
        if line.lower().startswith("content-length:"):
            return int(line.split(":", 1)[1].strip())

    return None


def is_chunked(headers_text):
    for line in headers_text.split("\r\n"):
        if line.lower().startswith("transfer-encoding:") and "chunked" in line.lower():
            return True

    return False


def read_exact(sock, buffer, n):
    while len(buffer) < n:
        buffer, ok = recv_more(sock, buffer)

        if not ok:
            break

    return buffer


def read_chunked_body(sock, buffer):
    body = b""

    while True:
        while b"\r\n" not in buffer:
            buffer, ok = recv_more(sock, buffer)

            if not ok:
                return body

        line_end = buffer.find(b"\r\n")
        size_line = buffer[:line_end]
        buffer = buffer[line_end + 2:]

        chunk_size_text = size_line.split(b";", 1)[0].strip()
        chunk_size = int(chunk_size_text, 16)

        if chunk_size == 0:
            return body

        buffer = read_exact(sock, buffer, chunk_size + 2)

        if len(buffer) < chunk_size:
            return body

        body += buffer[:chunk_size]
        buffer = buffer[chunk_size + 2:]


def read_http_response(sock):
    header_bytes, headers_text, body = read_until_headers(sock)
    status_code = parse_status_code(headers_text)

    if status_code in (204, 304):
        return {
            "status_code": status_code,
            "headers_bytes": len(header_bytes),
            "body_bytes": 0,
            "total_response_bytes": len(header_bytes),
        }

    content_length = parse_content_length(headers_text)

    if content_length is not None:
        body = read_exact(sock, body, content_length)[:content_length]
    elif is_chunked(headers_text):
        body = read_chunked_body(sock, body)
    else:
        body = body[:4096]

    return {
        "status_code": status_code,
        "headers_bytes": len(header_bytes),
        "body_bytes": len(body),
        "total_response_bytes": len(header_bytes) + len(body),
    }


def perform_http_request(sock, host, path, connection_mode):
    request = build_http_request(host, path, connection_mode)

    http_wall_start = time.perf_counter()
    http_cpu_start = time.process_time()

    sock.sendall(request)
    response_info = read_http_response(sock)

    http_cpu_end = time.process_time()
    http_wall_end = time.perf_counter()

    return {
        "http_time_s": http_wall_end - http_wall_start,
        "http_cpu_time_s": http_cpu_end - http_cpu_start,
        "request_bytes": len(request),
        **response_info,
    }


def safe_close(sock):
    if sock is not None:
        try:
            sock.close()
        except Exception:
            pass


def summarize(values):
    values = [v for v in values if v is not None]

    if not values:
        return {
            "total": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
            "p95": None,
            "first": None,
            "after_first_mean": None,
        }

    s = pd.Series(values)

    return {
        "total": float(s.sum()),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "min": float(s.min()),
        "max": float(s.max()),
        "std": float(s.std()) if len(s) > 1 else 0.0,
        "p95": float(s.quantile(0.95)),
        "first": float(values[0]),
        "after_first_mean": float(pd.Series(values[1:]).mean()) if len(values) > 1 else 0.0,
    }


def successful_record(request_index, connection_metrics, http_metrics, total_wall_s, total_cpu_s):
    return {
        "ok": True,
        "request_index": request_index,
        **connection_metrics,
        **http_metrics,
        "total_request_wall_s": total_wall_s,
        "total_request_cpu_s": total_cpu_s,
        "error": "",
    }


def failed_record(request_index, error):
    return {
        "ok": False,
        "request_index": request_index,
        "dns_time_s": None,
        "tcp_connect_time_s": None,
        "tls_handshake_time_s": None,
        "connection_setup_wall_s": None,
        "connection_setup_cpu_s": None,
        "http_time_s": None,
        "http_cpu_time_s": None,
        "total_request_wall_s": None,
        "total_request_cpu_s": None,
        "request_bytes": 0,
        "status_code": "error",
        "headers_bytes": 0,
        "body_bytes": 0,
        "total_response_bytes": 0,
        "tls_version": "",
        "cipher_suite": "",
        "error": str(error),
    }


def build_session_row(run_id, target, session_type, repetition, num_requests, records):
    successful = [r for r in records if r["ok"]]

    dns = summarize([r["dns_time_s"] for r in successful])
    tcp = summarize([r["tcp_connect_time_s"] for r in successful])
    tls = summarize([r["tls_handshake_time_s"] for r in successful])
    setup_wall = summarize([r["connection_setup_wall_s"] for r in successful])
    setup_cpu = summarize([r["connection_setup_cpu_s"] for r in successful])
    http = summarize([r["http_time_s"] for r in successful])
    wall = summarize([r["total_request_wall_s"] for r in successful])
    cpu = summarize([r["total_request_cpu_s"] for r in successful])

    wall_total = wall["total"] or 0
    tls_total = tls["total"] or 0
    setup_total = (dns["total"] or 0) + (tcp["total"] or 0) + (tls["total"] or 0)
    http_total = http["total"] or 0

    return {
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "tls_config": "TLSv1.3_strict",

        "target_set": target["target_set"],
        "target_name": target["target_name"],
        "target_host": target["host"],
        "target_path": target["path"],
        "url": target["url"],

        "tipo_sesion": session_type,
        "repeticion": repetition,
        "num_requests": num_requests,
        "num_requests_exitosos": len(successful),
        "num_requests_fallidos": num_requests - len(successful),

        "dns_total_s": dns["total"],
        "dns_promedio_s": dns["mean"],

        "tcp_total_s": tcp["total"],
        "tcp_promedio_s": tcp["mean"],

        "tls_handshake_total_s": tls["total"],
        "tls_handshake_promedio_s": tls["mean"],
        "tls_handshake_mediana_s": tls["median"],
        "tls_handshake_p95_s": tls["p95"],
        "tls_handshake_std_s": tls["std"],
        "tls_handshake_primer_request_s": tls["first"],
        "tls_handshake_promedio_despues_primero_s": tls["after_first_mean"],

        "connection_setup_total_s": setup_wall["total"],
        "connection_setup_promedio_s": setup_wall["mean"],
        "connection_setup_cpu_total_s": setup_cpu["total"],
        "connection_setup_cpu_promedio_s": setup_cpu["mean"],

        "http_total_s": http["total"],
        "http_promedio_s": http["mean"],
        "http_mediana_s": http["median"],
        "http_p95_s": http["p95"],
        "http_primer_request_s": http["first"],
        "http_promedio_despues_primero_s": http["after_first_mean"],

        "wall_total_s": wall["total"],
        "wall_promedio_s": wall["mean"],
        "wall_mediana_s": wall["median"],
        "wall_p95_s": wall["p95"],
        "wall_std_s": wall["std"],
        "wall_primer_request_s": wall["first"],
        "wall_promedio_despues_primero_s": wall["after_first_mean"],

        "cpu_total_s": cpu["total"],
        "cpu_promedio_s": cpu["mean"],
        "cpu_mediana_s": cpu["median"],
        "cpu_p95_s": cpu["p95"],
        "cpu_std_s": cpu["std"],
        "cpu_primer_request_s": cpu["first"],
        "cpu_promedio_despues_primero_s": cpu["after_first_mean"],

        "tls_handshake_por_request_s": (tls_total / len(successful)) if successful else None,
        "setup_por_request_s": (setup_total / len(successful)) if successful else None,
        "http_por_request_s": (http_total / len(successful)) if successful else None,
        "tls_como_porcentaje_wall_total": (tls_total / wall_total * 100) if wall_total > 0 else None,
        "setup_como_porcentaje_wall_total": (setup_total / wall_total * 100) if wall_total > 0 else None,
        "http_como_porcentaje_wall_total": (http_total / wall_total * 100) if wall_total > 0 else None,

        "bytes_enviados_total": sum(r["request_bytes"] for r in successful),
        "bytes_recibidos_total": sum(r["total_response_bytes"] for r in successful),

        "tls_versiones": "|".join(sorted(set(str(r["tls_version"]) for r in successful if r["tls_version"]))),
        "cipher_suites": "|".join(sorted(set(str(r["cipher_suite"]) for r in successful if r["cipher_suite"]))),
        "status_codes": "|".join(str(r["status_code"]) for r in records),
        "errores": " | ".join(r["error"] for r in records if r["error"]),

        "python_version": platform.python_version(),
        "sistema": platform.system(),
        "plataforma": platform.platform(),
    }


def run_short_session(run_id, target, timeout, delay, repetition, num_requests):
    records = []

    for request_index in range(1, num_requests + 1):
        sock = None

        try:
            request_wall_start = time.perf_counter()
            request_cpu_start = time.process_time()

            sock, connection_metrics = open_tls_connection(target["host"], target["port"], timeout)
            http_metrics = perform_http_request(sock, target["host"], target["path"], connection_mode="close")

            request_cpu_end = time.process_time()
            request_wall_end = time.perf_counter()

            records.append(successful_record(
                request_index,
                connection_metrics,
                http_metrics,
                request_wall_end - request_wall_start,
                request_cpu_end - request_cpu_start,
            ))

        except Exception as error:
            records.append(failed_record(request_index, error))

        finally:
            safe_close(sock)

        time.sleep(delay)

    return build_session_row(run_id, target, "corta", repetition, num_requests, records), records


def run_long_session(run_id, target, timeout, delay, repetition, num_requests):
    records = []
    sock = None

    try:
        sock, connection_metrics = open_tls_connection(target["host"], target["port"], timeout)

        for request_index in range(1, num_requests + 1):
            try:
                connection_mode = "keep-alive" if request_index < num_requests else "close"

                request_wall_start = time.perf_counter()
                request_cpu_start = time.process_time()

                http_metrics = perform_http_request(sock, target["host"], target["path"], connection_mode)

                request_cpu_end = time.process_time()
                request_wall_end = time.perf_counter()

                if request_index == 1:
                    per_request_connection_metrics = connection_metrics
                    setup_wall = connection_metrics["connection_setup_wall_s"]
                    setup_cpu = connection_metrics["connection_setup_cpu_s"]
                else:
                    per_request_connection_metrics = {
                        "dns_time_s": 0.0,
                        "tcp_connect_time_s": 0.0,
                        "tls_handshake_time_s": 0.0,
                        "connection_setup_wall_s": 0.0,
                        "connection_setup_cpu_s": 0.0,
                        "tls_version": connection_metrics["tls_version"],
                        "cipher_suite": connection_metrics["cipher_suite"],
                    }
                    setup_wall = 0.0
                    setup_cpu = 0.0

                records.append(successful_record(
                    request_index,
                    per_request_connection_metrics,
                    http_metrics,
                    (request_wall_end - request_wall_start) + setup_wall,
                    (request_cpu_end - request_cpu_start) + setup_cpu,
                ))

            except Exception as error:
                records.append(failed_record(request_index, error))

            time.sleep(delay)

    except Exception as error:
        for request_index in range(1, num_requests + 1):
            records.append(failed_record(request_index, f"connection setup: {error}"))

    finally:
        safe_close(sock)

    return build_session_row(run_id, target, "larga", repetition, num_requests, records), records


def flatten_request_records(run_id, target, session_type, repetition, num_requests, records):
    rows = []

    for record in records:
        row = {
            "run_id": run_id,
            "timestamp_utc": utc_now_iso(),
            "tls_config": "TLSv1.3_strict",
            "target_set": target["target_set"],
            "target_name": target["target_name"],
            "target_host": target["host"],
            "target_path": target["path"],
            "url": target["url"],
            "tipo_sesion": session_type,
            "repeticion": repetition,
            "num_requests": num_requests,
        }
        row.update(record)
        rows.append(row)

    return rows


def preflight_target(url, timeout, target_set):
    target = parse_url(url)
    target["target_set"] = target_set
    sock = None

    try:
        sock, connection_metrics = open_tls_connection(target["host"], target["port"], timeout)
        http_metrics = perform_http_request(sock, target["host"], target["path"], connection_mode="close")
        status_code = http_metrics["status_code"]
        ok = 200 <= status_code < 500 and connection_metrics["tls_version"] == "TLSv1.3"
        message = f"status={status_code}, tls={connection_metrics['tls_version']}"
        return ok, target, message

    except Exception as error:
        return False, target, str(error)

    finally:
        safe_close(sock)


def select_working_targets(targets, timeout, target_set, desired_count):
    candidates = []
    seen = set()

    for url in targets + BACKUP_TARGETS:
        if url not in seen:
            candidates.append(url)
            seen.add(url)

    selected = []
    status_rows = []

    print("\nPreflight TLS 1.3 estricto:")
    print("-" * 80)

    for url in candidates:
        if len(selected) >= desired_count:
            break

        ok, target, message = preflight_target(url, timeout, target_set)

        status_rows.append({
            "timestamp_utc": utc_now_iso(),
            "target_set": target_set,
            "url": url,
            "target_host": target["host"],
            "preflight_ok": ok,
            "message": message,
        })

        if ok:
            print(f"[OK]   {url} | {message}")
            selected.append(target)
        else:
            print(f"[FAIL] {url} | {message}")

    if len(selected) < desired_count:
        print(f"\nAdvertencia: solo se encontraron {len(selected)} servidores funcionales.")

    return selected, status_rows


def main():
    parser = argparse.ArgumentParser(description="Experimento final TLS 1.3 estricto multi-servidor.")

    parser.add_argument("--target-set", default="real_world", choices=list(TARGET_SETS.keys()))
    parser.add_argument("--targets", default="", help="URLs HTTPS separadas por coma.")
    parser.add_argument("--target-count", type=int, default=5)
    parser.add_argument("--sizes", default=DEFAULT_REQUEST_SIZES)
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)

    args = parser.parse_args()

    ensure_directories()

    request_sizes = parse_sizes(args.sizes)
    input_targets = parse_targets(args.targets, args.target_set)
    run_id = utc_stamp()

    working_targets, preflight_rows = select_working_targets(
        input_targets,
        args.timeout,
        args.target_set,
        args.target_count,
    )

    preflight_output = os.path.join(DATA_DIR, f"target_preflight_tls13_{run_id}.csv")
    pd.DataFrame(preflight_rows).to_csv(preflight_output, index=False, encoding="utf-8")

    if not working_targets:
        raise RuntimeError("No hay servidores funcionales con TLS 1.3 estricto.")

    session_rows = []
    request_rows = []

    print("\nProyecto 6 - run_final.py TLS 1.3 estricto")
    print(f"Target set: {args.target_set}")
    print(f"Servidores usados: {len(working_targets)}")
    print(f"Tamaños de requests: {request_sizes}")
    print(f"Repeticiones por escenario: {args.repetitions}")
    print(f"Delay entre requests: {args.delay} s")
    print("-" * 80)

    for target in working_targets:
        print(f"\nServidor actual: {target['url']}")
        print("-" * 80)

        for num_requests in request_sizes:
            for repetition in range(1, args.repetitions + 1):
                print(
                    f"TLS1.3 corta | servidor={target['host']} | "
                    f"n={num_requests} | rep={repetition}/{args.repetitions}"
                )

                short_row, short_records = run_short_session(
                    run_id,
                    target,
                    args.timeout,
                    args.delay,
                    repetition,
                    num_requests,
                )

                session_rows.append(short_row)
                request_rows.extend(flatten_request_records(
                    run_id,
                    target,
                    "corta",
                    repetition,
                    num_requests,
                    short_records,
                ))

                print(
                    f"TLS1.3 larga | servidor={target['host']} | "
                    f"n={num_requests} | rep={repetition}/{args.repetitions}"
                )

                long_row, long_records = run_long_session(
                    run_id,
                    target,
                    args.timeout,
                    args.delay,
                    repetition,
                    num_requests,
                )

                session_rows.append(long_row)
                request_rows.extend(flatten_request_records(
                    run_id,
                    target,
                    "larga",
                    repetition,
                    num_requests,
                    long_records,
                ))

    raw_output = os.path.join(DATA_DIR, f"raw_results_final_tls13_{run_id}.csv")
    request_output = os.path.join(DATA_DIR, f"request_log_final_tls13_{run_id}.csv")

    pd.DataFrame(session_rows).to_csv(raw_output, index=False, encoding="utf-8")
    pd.DataFrame(request_rows).to_csv(request_output, index=False, encoding="utf-8")

    print("-" * 80)
    print("Experimento TLS 1.3 terminado.")
    print(f"Preflight: {preflight_output}")
    print(f"Datos por sesión: {raw_output}")
    print(f"Datos por request: {request_output}")


if __name__ == "__main__":
    main()