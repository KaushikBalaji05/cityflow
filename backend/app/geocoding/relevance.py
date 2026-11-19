import re
import unicodedata
from app.geocoding.models import Place
from app.geocoding.providers import in_region
from app.routing.graph import haversine_distance_meters

GENERIC_TOKENS = {
    "university", "college", "campus", "institute", "school", "engineering",
    "hospital", "clinic", "healthcare", "medical", "center", "centre",
    "bus", "stop", "stand", "station", "metro", "ttmc", "railway", "terminal",
    "road", "street", "cross", "main", "layout", "block", "phase", "stage",
    "apartment", "apartments", "tower", "towers", "residency", "enclave",
    "bengaluru", "bangalore", "karnataka", "india", "near", "opp", "opposite"
}


def normalize(query: str) -> str:
    text = unicodedata.normalize("NFKC", query).casefold()
    # Combining vowel signs are essential in Kannada and other Indian scripts.
    return " ".join("".join(c if unicodedata.category(c)[0] in "LMN" or c == "_" else " "
                            for c in text).split())


def clean_tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if len(t) > 1]


def token_in_text(token: str, text: str) -> bool:
    if token in text:
        return True
    # Transliteration aliases common in Bengaluru (th <-> t, e.g. Thavarekere / Tavarekere)
    if token.startswith("th") and ("t" + token[2:]) in text:
        return True
    if token.startswith("t") and ("th" + token[1:]) in text:
        return True
    # Abbreviation matching (e.g. rr <-> ring road, orr <-> outer ring road)
    if token == "rr" and ("ring road" in text or "ring" in text):
        return True
    if token == "orr" and ("outer ring road" in text or "ring road" in text):
        return True
    return False


def query_variants(query: str) -> list[str]:
    """Generates clean base entity variants for qualified queries during fallback."""
    variants = []
    # 1. Comma separation: 'PES University, RR Campus' -> 'PES University'
    if "," in query:
        base = query.split(",")[0].strip()
        if len(base) >= 3:
            variants.append(base)
    # 2. Transit facility suffix: 'Murugeshpalya Bus Stop' -> 'Murugeshpalya'
    stripped = re.sub(r"\b(bus stop|bus stand|bus station|metro station|railway station|ttmc)\b", "", query, flags=re.I).strip()
    if stripped and stripped != query and len(stripped) >= 3:
        variants.append(stripped)
    # 3. Transliteration variants (e.g. Thavarekere <-> Tavarekere)
    for q in [query] + list(variants):
        if re.search(r"\bth", q, re.I):
            t_var = re.sub(r"\bth", "t", q, flags=re.I)
            variants.append(t_var)
            if "," in t_var:
                variants.append(t_var.split(",")[0].strip())
    seen = {query.lower()}
    result = []
    for v in variants:
        v_clean = v.strip(" ,")
        if v_clean.lower() not in seen and len(v_clean) >= 3:
            seen.add(v_clean.lower())
            result.append(v_clean)
    return result


def is_auxiliary_map(query: str, place: Place) -> bool:
    """Detects map boards, guideposts, and layout information signs."""
    if "map" in query.lower():
        return False
    name_l = (place.name or "").lower()
    cat_l = (place.category or "").lower()
    return "layout map" in name_l or "information board" in name_l or cat_l in ("map", "information")


def relevance(query: str, place: Place) -> float:
    tokens = set(normalize(query).split()) - {"bengaluru", "bangalore", "karnataka", "india"}
    text = normalize((place.name or "") + " " + (place.category or "") + " " + (place.display_address or ""))
    return sum(token_in_text(t, text) for t in tokens) / max(1, len(tokens))


def intent_matches(query: str, place: Place) -> bool:
    q = normalize(query)
    c = normalize((place.category or "") + " " + (place.name or ""))
    groups = [({"road", "street", "cross", "main"}, {"road", "street", "residential", "house", "building"}),
              ({"university", "college", "campus"}, {"university", "college", "education", "campus"}),
              ({"hospital", "clinic", "nimhans"}, {"hospital", "clinic", "healthcare", "medical"}),
              ({"apartment", "apartments", "tower"}, {"apartment", "apartments", "building", "house", "residential", "tower"}),
              ({"bus", "ttmc", "metro", "station", "stop", "stand"}, {"bus", "ttmc", "metro", "station", "transport", "public", "subway", "platform"})]
    return all(not (set(q.split()) & triggers) or any(t in c for t in matches)
               for triggers, matches in groups)


def suitable(query: str, places: list[Place], overall: float, street: float, building: float) -> bool:
    for p in places:
        if not in_region(p) or relevance(query, p) < .6 or not intent_matches(query, p):
            continue
        if p.confidence is None or p.confidence < overall:
            continue
        if p.street_confidence is not None and p.street_confidence < street:
            continue
        if p.building_confidence is not None and p.building_confidence < building:
            continue
        # Similar names far apart with similar scores are ambiguous.
        ambiguous = any(other.place_id != p.place_id and
                        relevance(query, other) >= .6 and
                        abs((other.confidence or 0) - p.confidence) < .03 and
                        normalize(other.name) == normalize(p.name) and
                        haversine_distance_meters(p.lat, p.lon, other.lat, other.lon) > 2000
                        for other in places)
        if not ambiguous:
            return True
    return False


def rank_unique(query: str, places: list[Place]) -> list[Place]:
    q_norm = normalize(query)
    q_tokens = set(q_norm.split()) - {"bengaluru", "bangalore", "karnataka", "india"}
    distinctive = q_tokens - GENERIC_TOKENS

    if "," in query:
        primary_part = query.split(",")[0].strip()
        primary_tokens = set(clean_tokens(primary_part)) - GENERIC_TOKENS
        if not primary_tokens:
            primary_tokens = set(clean_tokens(primary_part))
    else:
        primary_tokens = distinctive

    def sort_key(p: Place):
        map_penalty = 1 if is_auxiliary_map(query, p) else 0
        name_norm = normalize(p.name or "")
        addr_norm = normalize(p.display_address or "")
        cat_norm = normalize(p.category or "")

        high_conf_primary = (p.provider == "geoapify" and p.confidence is not None and p.confidence >= 0.85)
        name_matches_primary = bool(primary_tokens and any(token_in_text(t, name_norm) or token_in_text(t, cat_norm) for t in primary_tokens))
        primary_match = 1 if (high_conf_primary or name_matches_primary) else 0

        name_dist_hits = sum(token_in_text(t, name_norm) for t in distinctive) if distinctive else 0
        addr_dist_hits = sum(token_in_text(t, addr_norm) for t in distinctive) if distinctive else 0
        dist_score = (name_dist_hits * 2.0 + addr_dist_hits) / (2.0 * len(distinctive)) if distinctive else 1.0

        is_road = any(cat_norm.startswith(r) for r in ["street", "primary", "secondary", "tertiary", "residential", "service", "road"])
        road_penalty = 1 if (is_road and not name_matches_primary and not high_conf_primary and primary_tokens) else 0

        im = 1 if intent_matches(query, p) else 0
        rel = relevance(query, p)
        conf = p.confidence if p.confidence is not None else 0.5
        return (-map_penalty, primary_match, -road_penalty, dist_score, im, rel, conf)

    ordered = sorted((p for p in places if in_region(p) and relevance(query, p) >= .3),
                     key=sort_key, reverse=True)
    results = []
    for p in ordered:
        if any(p.place_id == old.place_id or
               (normalize(p.name) == normalize(old.name) and
                haversine_distance_meters(p.lat, p.lon, old.lat, old.lon) < 100)
               for old in results):
            continue
        results.append(p)
    return results
