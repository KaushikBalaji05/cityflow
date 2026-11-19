import unicodedata
from app.geocoding.models import Place
from app.geocoding.providers import in_region
from app.routing.graph import haversine_distance_meters


def normalize(query: str) -> str:
    text = unicodedata.normalize("NFKC", query).casefold()
    # Combining vowel signs are essential in Kannada and other Indian scripts.
    return " ".join("".join(c if unicodedata.category(c)[0] in "LMN" or c == "_" else " "
                            for c in text).split())


def relevance(query: str, place: Place) -> float:
    tokens = set(normalize(query).split()) - {"bengaluru", "bangalore", "karnataka", "india"}
    text = normalize(place.name + " " + place.display_address)
    return sum(t in text for t in tokens) / max(1, len(tokens))


def intent_matches(query: str, place: Place) -> bool:
    q = normalize(query)
    c = normalize(place.category + " " + place.name)
    groups = [({"road", "street", "cross", "main"}, {"road", "street", "residential", "house", "building"}),
              ({"university", "college", "campus"}, {"university", "college", "education", "campus"}),
              ({"hospital", "clinic"}, {"hospital", "clinic", "healthcare"}),
              ({"apartment", "apartments", "tower"}, {"apartment", "apartments", "building", "house", "residential", "tower"}),
              ({"bus", "ttmc", "metro", "station"}, {"bus", "ttmc", "metro", "station", "transport", "public"})]
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
    ordered = sorted((p for p in places if in_region(p) and relevance(query, p) >= .3),
                     key=lambda p: (intent_matches(query, p), relevance(query, p), p.confidence or 0), reverse=True)
    results = []
    for p in ordered:
        if any(p.place_id == old.place_id or
               (normalize(p.name) == normalize(old.name) and
                haversine_distance_meters(p.lat, p.lon, old.lat, old.lon) < 100)
               for old in results):
            continue
        results.append(p)
    return results
