import os, hashlib

files = [
    r"D:\Work Space\他山之石\微盘股\母版交易记录-20260501-20260623.txt",
    r"D:\Work Space\他山之石\微盘股\母版持仓&资金记录-20260501-20260623.txt",
]

for fp in files:
    print(f"=== {os.path.basename(fp)} ===")
    with open(fp, "rb") as f:
        raw = f.read()
    sz = len(raw)
    print(f"  Path: {fp}")
    print(f"  Size: {sz} bytes")
    mtime = os.path.getmtime(fp)
    from datetime import datetime
    print(f"  Modified: {datetime.fromtimestamp(mtime)}")
    sha = hashlib.sha256(raw).hexdigest()
    print(f"  SHA-256: {sha.upper()}")
    print(f"  First 32 hex: {raw[:32].hex()}")
    print(f"  Last 32 hex: {raw[-32:].hex()}")
    # BOM detection
    if raw[:3] == b"\xef\xbb\xbf":
        print(f"  BOM: UTF-8")
        start = 3
    elif raw[:2] == b"\xff\xfe":
        print(f"  BOM: UTF-16 LE")
        start = 2
    elif raw[:2] == b"\xfe\xff":
        print(f"  BOM: UTF-16 BE")
        start = 2
    else:
        print(f"  BOM: None")
        start = 0
    # Encoding detection
    for enc in ["utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030", "big5", "utf-16", "shift_jis"]:
        try:
            text = raw[start:].decode(enc) if start else raw.decode(enc)
            lines = text.splitlines()
            print(f"  Encoding: {enc}")
            print(f"  Total lines: {len(lines)}")
            non_empty = sum(1 for l in lines if l.strip())
            print(f"  Non-empty: {non_empty}")
            empty = len(lines) - non_empty
            print(f"  Empty: {empty}")
            print(f"  \\r\\n (CRLF): {'\\r\\n' in text}")
            print(f"  \\n only (LF): {'\\n' in text and '\\r\\n' not in text}")
            print(f"  First 5 lines:")
            for i, l in enumerate(lines[:5]):
                print(f"    [{i}] {repr(l[:120])}")
            print(f"  Last 3 lines:")
            for i, l in enumerate(lines[-3:]):
                print(f"    [{len(lines)-3+i}] {repr(l[:120])}")
            break
        except Exception as e:
            print(f"  Encoding {enc}: FAIL - {e}")
    print()
