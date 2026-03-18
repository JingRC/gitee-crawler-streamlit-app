import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import requests


@dataclass
class ProxyItem:
    host: str
    port: int
    source: str


PROXY_POOL = [
    ProxyItem("222.184.87.63", 8989, "222.184.87.63:8989"),
    ProxyItem("140.246.125.194", 9099, "140.246.125.194:9099"),
    ProxyItem("36.110.143.55", 8080, "36.110.143.55:8080"),
    ProxyItem("129.204.7.66", 8082, "129.204.7.66:8082"),
    ProxyItem("129.204.7.66", 8082, "129.204.7.66:8082"),
    ProxyItem("221.225.50.59", 89889, "221.225.50.59:89889"),
    ProxyItem("116.232.169.230", 1080, "116.232.169.230:1080"),
    ProxyItem("180.127.140.216", 8989, "180.127.140.216:8989"),
    ProxyItem("221.223.163.135", 3128, "221.223.163.135:3128"),
    ProxyItem("119.6.178.76", 1080, "119.6.178.76:1080"),
    ProxyItem("116.132.0.134", 8060, "116.132.0.134:8060"),
    ProxyItem("103.119.1.110", 3131, "103.119.1.110:3131"),
    ProxyItem("114.218.88.160", 8989, "114.218.88.160:8989"),
    ProxyItem("171.41.150.93", 2324, "171.41.150.93:2324"),
    ProxyItem("114.237.77.220", 1080, "114.237.77.220:1080"),
    ProxyItem("183.247.199.114", 30001, "183.247.199.114:30001"),
    ProxyItem("112.5.33.179", 999, "112.5.33.179:999"),
    ProxyItem("222.59.173.105", 44077, "222.59.173.105:44077"),
    ProxyItem("49.232.59.192", 1080, "49.232.59.192:1080"),
    ProxyItem("14.155.205.217", 8888, "14.155.205.217:8888"),
    ProxyItem("152.136.41.178", 8081, "152.136.41.178:8081"),
    ProxyItem("36.138.53.26", 10019, "36.138.53.26:10019"),
    ProxyItem("106.75.71.155", 8443, "106.75.71.155:8443"),
    ProxyItem("103.36.165.6", 1080, "103.36.165.6:1080"),
    ProxyItem("8.140.235.207", 9001, "8.140.235.207:9001"),
    ProxyItem("47.120.26.153", 8888, "47.120.26.153:8888"),
    ProxyItem("171.105.22.54", 9909, "171.105.22.54:9909"),
    ProxyItem("116.204.113.40", 10809, "116.204.113.40:10809"),
    ProxyItem("111.177.48.18", 9501, "111.177.48.18:9501"),
    ProxyItem("222.184.87.71", 8989, "222.184.87.71:8989"),
]

TARGETS = {
    "gitee_gvp": "https://gitee.com/gvp?utf8=%E2%9C%93&q=ssm&page=1",
    "gitee_repo_api": "https://gitee.com/api/v5/repos/noear/snackjson",
}

PROTOCOL_CANDIDATES = ["http", "socks5"]


def proxy_url(host: str, port: int, protocol: str) -> str:
    if protocol.lower() == "socks5":
        return f"socks5h://{host}:{port}"
    return f"http://{host}:{port}"


def is_port_valid(port: int) -> bool:
    return 1 <= port <= 65535


def is_connect_error(error_text: str) -> bool:
    msg = (error_text or "").lower()
    keys = ["timed out", "unable to connect", "connection refused", "connecttimeout", "proxyerror"]
    return any(k in msg for k in keys)


def test_proxy_with_protocol(host: str, port: int, protocol: str, timeout: int = 4) -> Dict:
    purl = proxy_url(host, port, protocol)
    proxies = {"http": purl, "https": purl}

    result = {
        "proxy": purl,
        "protocol": protocol,
        "ok_all": True,
        "targets": {},
    }

    short_circuit = False
    short_circuit_reason = ""

    for name, target in TARGETS.items():
        if short_circuit:
            result["targets"][name] = {
                "ok": False,
                "status": None,
                "elapsed_sec": 0,
                "error": f"skip: {short_circuit_reason}",
            }
            result["ok_all"] = False
            continue

        t0 = time.time()
        row = {
            "ok": False,
            "status": None,
            "elapsed_sec": None,
            "error": "",
        }
        try:
            resp = requests.get(
                target,
                proxies=proxies,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            row["status"] = resp.status_code
            row["elapsed_sec"] = round(time.time() - t0, 3)
            row["ok"] = 200 <= resp.status_code < 400
        except Exception as exc:
            row["elapsed_sec"] = round(time.time() - t0, 3)
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["ok"] = False

        if not row["ok"]:
            result["ok_all"] = False
            if is_connect_error(row["error"]):
                short_circuit = True
                short_circuit_reason = row["error"]

        result["targets"][name] = row

    return result


def test_proxy(item: ProxyItem, timeout: int = 4) -> List[Dict]:
    if not is_port_valid(item.port):
        rows = []
        for protocol in PROTOCOL_CANDIDATES:
            purl = proxy_url(item.host, item.port, protocol)
            rows.append(
                {
                    "proxy": purl,
                    "protocol": protocol,
                    "source": item.source,
                    "ok_all": False,
                    "targets": {
                        target_name: {
                            "ok": False,
                            "status": None,
                            "elapsed_sec": 0,
                            "error": "invalid port (must be 1-65535)",
                        }
                        for target_name in TARGETS
                    },
                }
            )
        return rows

    rows: List[Dict] = []
    for protocol in PROTOCOL_CANDIDATES:
        row = test_proxy_with_protocol(item.host, item.port, protocol, timeout=timeout)
        row["source"] = item.source
        rows.append(row)
    return rows


def dedupe_proxy_items(items: List[ProxyItem]) -> List[ProxyItem]:
    seen = set()
    result = []
    for item in items:
        key = (item.host, item.port)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def write_reports(output_dir: Path, rows: List[Dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "proxy_test_report.json"
    csv_path = output_dir / "proxy_test_report.csv"
    usable_path = output_dir / "usable_proxies.json"

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "proxy", "protocol", "target", "ok", "status", "elapsed_sec", "error"])
        for row in rows:
            for target, detail in row["targets"].items():
                writer.writerow(
                    [
                        row["source"],
                        row["proxy"],
                        row["protocol"],
                        target,
                        detail["ok"],
                        detail["status"],
                        detail["elapsed_sec"],
                        detail["error"],
                    ]
                )

    usable = [row["proxy"] for row in rows if row["ok_all"]]
    usable_path.write_text(json.dumps(usable, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[INFO] 已写入: {json_path}")
    print(f"[INFO] 已写入: {csv_path}")
    print(f"[INFO] 已写入: {usable_path}")
    print(f"[INFO] 可用代理数量: {len(usable)}")


def main() -> None:
    print("[INFO] 开始测试代理可用性...")
    pool = dedupe_proxy_items(PROXY_POOL)
    print(f"[INFO] 输入代理数量: {len(PROXY_POOL)}，去重后: {len(pool)}")

    results = []
    for item in pool:
        print(f"\n[INFO] 测试代理: {item.source}")
        rows = test_proxy(item)
        for row in rows:
            results.append(row)
            print(f"[INFO] 协议 {row['protocol']} -> {'可用' if row['ok_all'] else '不可用'}")

    write_reports(Path(r"D:\file\python网络爬虫\实验二\爬取内容"), results)


if __name__ == "__main__":
    main()
