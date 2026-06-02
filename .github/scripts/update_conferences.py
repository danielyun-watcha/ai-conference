import yaml
import requests
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

# ccfddl categories to scan
CCFDDL_CATEGORIES = ["AI", "CG", "DB", "DS", "HI", "MX", "NW", "SC", "SE"]

# Map our YAML filenames to ccfddl category/filename
# Format: our_filename -> (ccfddl_category, ccfddl_filename)
# Only conferences that exist in ccfddl are listed here.
CCFDDL_MAP = {
    # AI category
    "aaai": ("AI", "aaai"),
    "acl": ("AI", "acl"),
    "aistats": ("AI", "aistats"),
    "alt": ("AI", "alt"),
    "cec": ("AI", "cec"),
    "coling": ("AI", "coling"),
    "colm": ("AI", "colm"),
    "conll": ("AI", "conll"),
    "corl": ("AI", "corl"),
    "cpal": ("AI", "cpal"),
    "cvpr": ("AI", "cvpr"),
    "eacl": ("AI", "eacl"),
    "ecai": ("AI", "ecai"),
    "eccv": ("AI", "eccv"),
    "emnlp": ("AI", "emnlp"),
    "esann": ("AI", "esann"),
    "fg": ("AI", "fg"),
    "icann": ("AI", "icann"),
    "iccv": ("AI", "iccv"),
    "iclr": ("AI", "iclr"),
    "icml": ("AI", "icml"),
    "icra": ("AI", "icra"),
    "ijcai": ("AI", "ijcai"),
    "ijcnn": ("AI", "ijcnn"),
    "ksem": ("AI", "ksem"),
    "naacl": ("AI", "naacl"),
    "neurips": ("AI", "nips"),
    "ruleml+rr": ("AI", "rulemlrr"),
    "uai": ("AI", "uai"),
    "wacv": ("AI", "wacv"),
    "aamas": ("AI", "aamas"),
    "colt": ("AI", "colt"),
    "icdar": ("AI", "icdar"),
    # CG category
    "acm_mm": ("CG", "mm"),
    "icassp": ("CG", "icassp"),
    "interspeech": ("CG", "interspeech"),
    "sgp": ("CG", "SGP"),
    "siggraph": ("CG", "sig"),
    # DB category
    "cikm": ("DB", "cikm"),
    "dasfaa": ("DB", "dasfaa"),
    "ecir": ("DB", "ecir"),
    "icde": ("DB", "icde"),
    "icdm": ("DB", "icdm"),
    "kdd": ("DB", "sigkdd"),
    "pakdd": ("DB", "pakdd"),
    "recsys": ("DB", "recsys"),
    "sdm": ("DB", "sdm"),
    "sigir": ("DB", "sigir"),
    "vldb": ("DB", "vldb"),
    "wsdm": ("DB", "wsdm"),
    # HI category
    "chi": ("HI", "chi"),
    "cscw": ("HI", "cscw"),
    "iui": ("HI", "iui"),
    # MX category
    "bis": ("MX", "bis"),
    "www": ("MX", "www"),
    "miccai": ("MX", "miccai"),
    # SE category
    "icra": ("AI", "icra"),
    "rss": ("AI", "rss"),
}

# Conferences NOT in ccfddl (manual-only, no auto-update)
# chiir, collas, chil, ecml_pkdd, emnlp_industry_track,
# emnlp_system_demonstrations_track, eurographics, facct, ht, icomp,
# ijcnlp_and_aacl, lrec, mathai, nlbse, rlc, sac, umap, websci, wise


def fetch_ccfddl_file(category: str, filename: str) -> Optional[Dict[str, Any]]:
    """Fetch a single conference YAML from ccfddl."""
    url = f"https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference/{category}/{filename}.yml"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"  Warning: Could not fetch {category}/{filename}.yml (HTTP {resp.status_code})")
        return None
    data = yaml.safe_load(resp.text)
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    return data


MONTH_MAP = {
    "Sept": "September",
    "Jan": "January",
    "Feb": "February",
    "Mar": "March",
    "Apr": "April",
    "Jun": "June",
    "Jul": "July",
    "Aug": "August",
    "Sep": "September",
    "Oct": "October",
    "Nov": "November",
    "Dec": "December",
}


def expand_month(text: str) -> str:
    """Expand abbreviated month names to full names without double-replacing."""
    import re as _re
    # Match word boundaries to avoid partial replacements
    for abbr, full in MONTH_MAP.items():
        # Only replace if it's an abbreviation (not already the full name)
        text = _re.sub(rf'\b{abbr}\b', full, text)
    return text


def parse_date_range(date_str: str, year: str) -> tuple:
    """Parse ccfddl date format -> (start, end) as YYYY-MM-DD strings."""
    date_str = date_str.replace(f", {year}", "")
    if date_str.strip().upper() == "TBD":
        raise ValueError("TBD date")
    try:
        if " - " in date_str:
            start, end = date_str.split(" - ", 1)
        elif "–" in date_str:
            start, end = date_str.split("–", 1)
        elif "-" in date_str:
            start, end = date_str.split("-", 1)
        else:
            start = end = date_str

        start = expand_month(start)
        end = expand_month(end)

        all_months = set(MONTH_MAP.values()) | {"May"}
        has_month = any(m in end for m in all_months)
        if not has_month:
            start_parts = start.split()
            if len(start_parts) >= 1:
                end = f"{start_parts[0]} {end.strip()}"

        start = " ".join(start.split())
        end = " ".join(end.split())

        start_date = datetime.strptime(f"{start}, {year}", "%B %d, %Y")
        end_date = datetime.strptime(f"{end}, {year}", "%B %d, %Y")
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
    except Exception as e:
        raise ValueError(f"Could not parse date: {date_str} ({e})")


def build_deadlines_from_timeline(timeline: List[Dict], timezone: str) -> List[Dict]:
    """Convert ccfddl timeline to our deadlines format."""
    deadlines = []
    tz = timezone if timezone else "AoE"

    for entry in timeline:
        if "abstract_deadline" in entry:
            deadlines.append({
                "type": "abstract",
                "label": "Abstract Deadline",
                "date": entry["abstract_deadline"],
                "timezone": tz,
            })
        if "deadline" in entry:
            deadlines.append({
                "type": "submission",
                "label": "Paper Submission",
                "date": entry["deadline"],
                "timezone": tz,
            })
        if "notification_date" in entry:
            deadlines.append({
                "type": "notification",
                "label": "Notification",
                "date": entry["notification_date"],
                "timezone": tz,
            })
        if "camera_ready_deadline" in entry:
            deadlines.append({
                "type": "camera_ready",
                "label": "Camera Ready",
                "date": entry["camera_ready_deadline"],
                "timezone": tz,
            })

    return deadlines


def transform_ccfddl_instance(conf_meta: Dict, instance: Dict) -> Dict:
    """Transform a single ccfddl conference instance to our format."""
    year = instance["year"]
    conf_id = instance.get("id", f"{conf_meta.get('title', 'unknown').lower()}{str(year)[2:]}")
    timezone = instance.get("timezone", "AoE")
    timeline = instance.get("timeline", [{}])

    result = {
        "title": conf_meta.get("title", ""),
        "year": year,
        "id": conf_id,
        "full_name": conf_meta.get("description", ""),
        "link": instance.get("link", ""),
        "date": instance.get("date", ""),
    }

    # Parse deadlines from timeline
    deadlines = build_deadlines_from_timeline(timeline, timezone)
    if deadlines:
        result["deadlines"] = deadlines

    # Parse place
    place = instance.get("place", "")
    if place and "," in place:
        city, country = place.split(",", 1)
        result["city"] = city.strip()
        result["country"] = country.strip()
    elif place:
        result["country"] = place.strip()

    # Parse date range
    try:
        if result["date"]:
            start, end = parse_date_range(result["date"], str(year))
            result["start"] = start
            result["end"] = end
    except Exception as e:
        print(f"  Warning: Could not parse date for {result.get('title', '?')} {year}: {e}")

    # Rankings from conf_meta
    if "rank" in conf_meta:
        rankings = []
        for rank_type, rank_value in conf_meta["rank"].items():
            rankings.append(f"{rank_type.upper()}: {rank_value}")
        if rankings:
            result["rankings"] = ", ".join(rankings)

    return result


def load_our_yaml(filepath: str) -> List[Dict]:
    """Load our YAML conference file."""
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)
    return data if data else []


def save_our_yaml(filepath: str, conferences: List[Dict]):
    """Save conferences to YAML preserving our format."""
    with open(filepath, "w") as f:
        yaml.dump(
            conferences,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=200,
        )


# Fields we preserve from our existing data (never overwritten by ccfddl)
PRESERVED_FIELDS = [
    "tags",
    "venue",
    "hindex",
    "note",
    "era_rating",
    "paperslink",
    "pwclink",
]


def merge_conference(existing: Dict, new_data: Dict) -> Dict:
    """Merge new ccfddl data into existing conference, preserving our fields."""
    merged = dict(new_data)

    # Preserve our manually set fields
    for field in PRESERVED_FIELDS:
        if field in existing:
            merged[field] = existing[field]

    # If we have manual deadlines with more detail, keep ours
    # But if ccfddl has newer/updated deadlines, use those
    if "deadlines" in existing and "deadlines" in new_data:
        # Keep ours if we have more deadline types (e.g., rebuttal)
        our_types = {d.get("type") for d in existing["deadlines"]}
        new_types = {d.get("type") for d in new_data["deadlines"]}
        if len(our_types) > len(new_types):
            merged["deadlines"] = existing["deadlines"]
    elif "deadlines" in existing and "deadlines" not in new_data:
        merged["deadlines"] = existing["deadlines"]

    # Preserve city/country if we have them and ccfddl doesn't
    if "city" in existing and "city" not in new_data:
        merged["city"] = existing["city"]
    if "country" in existing and "country" not in new_data:
        merged["country"] = existing["country"]

    return merged


def main():
    conferences_dir = "src/data/conferences"
    if not os.path.exists(conferences_dir):
        print(f"Error: {conferences_dir} not found")
        return

    current_year = datetime.now().year
    updated_files = 0
    new_entries = 0

    # Process each of our conference YAML files
    for filename in sorted(os.listdir(conferences_dir)):
        if not filename.endswith(".yml"):
            continue

        our_name = filename.replace(".yml", "")

        # Check if this conference has a ccfddl mapping
        if our_name not in CCFDDL_MAP:
            print(f"[SKIP] {our_name}: no ccfddl mapping (manual-only)")
            continue

        category, ccfddl_name = CCFDDL_MAP[our_name]
        print(f"[FETCH] {our_name} <- ccfddl/{category}/{ccfddl_name}.yml")

        # Fetch from ccfddl
        ccfddl_data = fetch_ccfddl_file(category, ccfddl_name)
        if not ccfddl_data:
            continue

        # Load our current data
        filepath = os.path.join(conferences_dir, filename)
        our_confs = load_our_yaml(filepath)
        our_by_year = {c["year"]: c for c in our_confs}

        # Get ccfddl instances for current and future years
        instances = ccfddl_data.get("confs", [])
        relevant = [inst for inst in instances if inst["year"] >= current_year - 1]

        if not relevant:
            print(f"  No relevant instances found")
            continue

        changed = False
        for instance in relevant:
            year = instance["year"]
            new_conf = transform_ccfddl_instance(ccfddl_data, instance)

            if year in our_by_year:
                # Update existing entry
                merged = merge_conference(our_by_year[year], new_conf)
                if merged != our_by_year[year]:
                    our_by_year[year] = merged
                    changed = True
                    print(f"  Updated {year}")
            else:
                # Add new year entry
                our_by_year[year] = new_conf
                changed = True
                new_entries += 1
                print(f"  Added {year}")

        if changed:
            # Sort by year and save
            all_confs = sorted(our_by_year.values(), key=lambda x: x.get("year", 0))
            save_our_yaml(filepath, all_confs)
            updated_files += 1

    print(f"\nDone: {updated_files} files updated, {new_entries} new entries added")


if __name__ == "__main__":
    main()
