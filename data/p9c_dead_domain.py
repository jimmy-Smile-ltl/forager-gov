# -*- coding: utf-8 -*-
"""P9c: 死域名门户清理（p9a 后仍无 xxgk 且 DNS 解析失败的行 → 清门户重排队）。"""
import json
import socket
import sys
from urllib.parse import urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))


def dns_ok(host):
    try:
        socket.getaddrinfo(host, 443, socket.AF_INET)
        return True
    except Exception:
        return False


def main():
    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
    cleaned = 0
    for r in cc:
        if r.get("portal_url") and not r.get("xxgk_url"):
            host = urlparse(r["portal_url"]).netloc
            if not dns_ok(host):
                r["portal_url"] = ""
                r["how"] = "死域名清除"
                r["xxgk_url"] = ""
                r["xxgk_src"] = ""
                cleaned += 1
                print("清除死域名:", r["name"], r.get("portal_url", ""), flush=True)
    with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(cc, key=lambda x: x["code"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"p9c 清除 {cleaned} 行", flush=True)


if __name__ == "__main__":
    main()
