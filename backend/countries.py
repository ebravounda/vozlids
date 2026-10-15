import re
from fastapi import HTTPException

COUNTRIES = {
    "ES": {"name": "España", "prefix": "+34", "regex": r"^\+34[6789]\d{8}$", "national": r"[6789]\d{8}",
           "tz": "Europe/Madrid", "city": "Madrid", "currency": "EUR", "stt": "es", "line_rate": 0.025,
           "example": "+34 600 000 000",
           "style": "Español de España, tuteo cercano y profesional (pasa a \"usted\" si el lead lo usa). De vez en cuando "
                    "usa expresiones como \"vale\", \"perfecto\", \"genial\", \"entiendo\" o \"mmm, déjame ver\", sin exagerar."},
    "CL": {"name": "Chile", "prefix": "+56", "regex": r"^\+56[2-9]\d{8}$", "national": r"[29]\d{8}",
           "tz": "America/Santiago", "city": "Santiago de Chile", "currency": "CLP", "stt": "es-419", "line_rate": 0.05,
           "example": "+56 9 1234 5678",
           "style": "Español de Chile, cercano y profesional; tutea salvo que el lead use \"usted\". Usa expresiones naturales "
                    "chilenas con moderación como \"ya\", \"perfecto\", \"súper\", \"bacán\" solo si el tono es informal. "
                    "Nunca uses expresiones de España (\"vale\", \"vosotros\", \"guay\"). Los precios son en pesos chilenos."},
}
CountryCode = str


def norm_phone(p: str, country: str) -> str:
    c = COUNTRIES[country]
    cc = c["prefix"][1:]
    p = re.sub(r"[\s\-\.\(\)]", "", p or "")
    if p.startswith("00" + cc):
        p = "+" + p[2:]
    elif p.startswith(cc) and len(p) == len(cc) + 9:
        p = "+" + p
    elif re.fullmatch(c["national"], p):
        p = c["prefix"] + p
    if not re.match(c["regex"], p):
        raise HTTPException(422, f"Teléfono no válido para {c['name']}: usa el formato {c['example']}.")
    return p


def norm_any_phone(p: str) -> str:
    for code in COUNTRIES:
        try:
            return norm_phone(p, code)
        except HTTPException:
            continue
    raise HTTPException(422, "Teléfono no válido: usa +34 (España) o +56 (Chile).")


DEMO_DIALS = {"ES": "34", "CL": "56", "AR": "54", "BO": "591", "CO": "57", "CR": "506", "DO": "1", "EC": "593", "SV": "503",
              "GT": "502", "HN": "504", "MX": "52", "NI": "505", "PA": "507", "PY": "595", "PE": "51", "UY": "598", "VE": "58"}


def norm_demo_phone(p: str, country: str) -> str:
    if country in COUNTRIES:
        return norm_phone(p, country)
    cc = DEMO_DIALS[country]
    p = re.sub(r"[\s\-\.\(\)]", "", p or "")
    if p.startswith("00"):
        p = "+" + p[2:]
    if not p.startswith("+"):
        p = f"+{cc}{p.lstrip('0')}"
    if not p.startswith(f"+{cc}") or not re.fullmatch(r"\+\d{8,15}", p) or len(p) - len(cc) - 1 < 7:
        raise ValueError(f"El teléfono no parece un número válido de este país (debe empezar por +{cc}).")
    if country == "DO" and p[2:5] not in ("809", "829", "849"):
        raise ValueError("El teléfono de República Dominicana debe empezar por 809, 829 u 849.")
    return p
