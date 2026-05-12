def normalize_symbol(code: str) -> str:
    code = str(code).strip().upper()
    if code.endswith(".SH") or code.endswith(".SZ"):
        return code
    if code.startswith(("600", "601", "603", "605", "688")):
        return f"{code}.SH"
    if code.startswith(("000", "001", "002", "003", "300")):
        return f"{code}.SZ"
    return code


def get_market(code: str) -> str:
    symbol = normalize_symbol(code)
    if symbol.endswith(".SH"):
        return "SH"
    if symbol.endswith(".SZ"):
        return "SZ"
    return "UNKNOWN"
