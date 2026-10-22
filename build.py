"""Build the kawaii Japan trip page from a TripIt iCal feed.

Usage: python build.py feed.ics site/index.html
Hand-written touches (nicer names, little descriptions, extra rows) live in extras.json.
Only names and times are published: addresses, phone numbers and notes from TripIt are never shown.
"""
import html, json, os, re, sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
X = json.loads((HERE / "extras.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(X["trip_tz"])
esc = html.escape


# ---------- iCal parsing ----------
def unfold(text):
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def unescape(v):
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), v)


def parse_dt(value, params):
    v = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", v):
        return date(int(v[:4]), int(v[4:6]), int(v[6:8])), True
    dt = datetime.strptime(v.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if v.endswith("Z"):
        dt = dt.replace(tzinfo=timezone.utc)
    elif "TZID" in params:
        try:
            dt = dt.replace(tzinfo=ZoneInfo(params["TZID"]))
        except Exception:
            dt = dt.replace(tzinfo=TZ)
    else:
        dt = dt.replace(tzinfo=TZ)
    return dt, False


def parse_ics(text):
    events, cur = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, value = line.split(":", 1)
            name, *ps = head.split(";")
            params = dict(p.split("=", 1) for p in ps if "=" in p)
            name = name.upper()
            if name in ("DTSTART", "DTEND"):
                cur[name], cur[name + "_ALLDAY"] = parse_dt(value, params)
            else:
                cur[name] = unescape(value)
    out = []
    for e in events:
        if "DTSTART" not in e:
            continue
        e.setdefault("SUMMARY", "")
        e.setdefault("LOCATION", "")
        e.setdefault("DESCRIPTION", "")
        e.setdefault("DTEND", e["DTSTART"])
        out.append(e)
    return out


# ---------- formatting ----------
def hm(dt):
    return dt.strftime("%I:%M %p").lstrip("0")


def hm_short(dt):
    s = hm(dt)
    return s.replace(":00 ", " ")


def md(d):
    return d.strftime("%b ") + str(d.day)


def local(dt, tz=TZ):
    return dt.astimezone(tz)


# ---------- markup pieces (match the hand-built page) ----------
SAKURA_RAIL = ('<svg width="26" height="26" viewBox="0 0 26 26" style="position: absolute; left: 0; top: 12px"><g fill="{mid}" stroke="#FFFFFF" stroke-width="1.5">'
               '<circle cx="13" cy="6.5" r="5"></circle><circle cx="19.2" cy="11" r="5"></circle><circle cx="16.8" cy="18.3" r="5"></circle>'
               '<circle cx="9.2" cy="18.3" r="5"></circle><circle cx="6.8" cy="11" r="5"></circle></g><circle cx="13" cy="13" r="3" fill="#FFFFFF"></circle></svg>')
DOT_RAIL = '<div style="position: absolute; left: 4px; top: 16px; width: 18px; height: 18px; border-radius: 50%; background: #FFFFFF; border: 5px solid {mid}"></div>'
RECHECK = ('<span style="font-size: 12px; font-weight: 900; line-height: 1.3; letter-spacing: 0.04em; padding: 3px 10px; border-radius: 999px; '
           'background: #FFF1A8; color: #6B5200">RECHECK!</span>')
ICONS = {
    "warn": '<path d="M12 3 2 21h20L12 3z"></path><path d="M12 10v5"></path><path d="M12 18h.01"></path>',
    "bag": '<rect x="5" y="7" width="14" height="13" rx="2"></rect><path d="M9 7V4h6v3"></path><path d="M9 11v5"></path><path d="M15 11v5"></path>',
    "clock": '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>',
}


def photos_html(paths, title):
    """A row of rounded thumbnails; tapping one opens the full photo."""
    if not paths:
        return ""
    style = ('height: 120px; width: auto; max-width: 200px; object-fit: cover; border-radius: 14px; '
             'box-shadow: 0 2px 8px rgba(80, 40, 70, 0.15)')

    def one(p):
        if p.lower().endswith(".mp4"):
            return (f'<video src="{esc(p)}" autoplay muted loop playsinline preload="metadata" '
                    f'aria-label="{esc(title)}" style="flex: none; {style}"></video>')
        return (f'<a href="{esc(p)}" target="_blank" rel="noopener" style="flex: none; display: block; line-height: 0">'
                f'<img src="{esc(p)}" alt="{esc(title)}" loading="lazy" style="{style}"></a>')

    imgs = "".join(one(p) for p in paths)
    return ('\n<div style="display: flex; gap: 8px; margin-top: 8px; overflow-x: auto; padding-bottom: 4px; '
            f'-webkit-overflow-scrolling: touch">{imgs}</div>')


def row_html(r, leg):
    title = esc(r["title"])
    badge = RECHECK if r.get("recheck") else (
        ('<span style="font-size: 12px; font-weight: 900; line-height: 1.3; letter-spacing: 0.04em; padding: 3px 10px; border-radius: 999px; '
         f'background: #FFE3EB; color: #A3214A">{esc(r["badge"])}</span>') if r.get("badge") else "")
    if badge:
        title_html = ('<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px">\n'
                      f'<span style="font-size: 17px; font-weight: 700; line-height: 1.35">{title}</span>\n{badge}\n</div>')
    else:
        title_html = f'<div style="font-size: 17px; font-weight: 700; line-height: 1.35">{title}</div>'
    sub = (f'\n<div style="font-size: 14px; font-weight: 500; line-height: 1.45; color: #6E5A6E">{esc(r["sub"])}</div>'
           if r.get("sub") else "")
    kids = ""
    if r.get("children"):
        items = []
        for c in r["children"]:
            cb = ('<span style="font-size: 11px; font-weight: 900; line-height: 1.3; letter-spacing: 0.04em; padding: 2px 8px; border-radius: 999px; '
                  f'background: #FFE3EB; color: #A3214A">{esc(c["badge"])}</span>') if c.get("badge") else ""
            csub = (f'<div style="font-size: 13px; font-weight: 500; line-height: 1.4; color: #6E5A6E">{esc(c["sub"])}</div>' if c.get("sub") else "")
            items.append('<li style="display: flex; gap: 8px; align-items: flex-start">'
                         f'<span aria-hidden="true" style="flex: none; width: 8px; height: 8px; margin-top: 7px; border-radius: 50%; background: {leg["mid"]}"></span>'
                         '<div style="min-width: 0"><div style="display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px">'
                         f'<span style="font-size: 15px; font-weight: 700; line-height: 1.4">{esc(c["title"])}</span>{cb}</div>{csub}'
                         f'{photos_html(c.get("photos"), c["title"])}</div></li>')
        kids = (f'\n<ul style="list-style: none; margin: 8px 0 0; padding: 10px 12px; border-radius: 14px; background: {leg["pastel"]}; '
                'display: flex; flex-direction: column; gap: 8px">' + "".join(items) + '</ul>')
    return ('<div style="display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px">\n'
            f'<span style="flex: 0 0 84px; text-align: center; padding: 4px 0; border-radius: 999px; background: {leg["pastel"]}; '
            f'color: {leg["text"]}; font-size: 13px; font-weight: 900; line-height: 1.3">{esc(r["time"])}</span>\n'
            f'<div style="flex: 1 1 200px; min-width: 0">\n{title_html}{sub}{photos_html(r.get("photos"), r["title"])}{kids}\n</div>\n</div>\n')


def day_html(d, rows, leg, travel):
    rail = (SAKURA_RAIL if travel else DOT_RAIL).format(mid=leg["mid"])
    body = "".join(row_html(r, leg) for r in rows)
    return (f'<li id="day-{d.day}" style="display: flex; gap: 10px; scroll-margin-top: 16px">\n'
            '<div style="flex: none; padding: 12px 0">\n'
            f'<div style="width: 56px; height: 60px; border-radius: 16px; background: {leg["pastel"]}; color: {leg["text"]}; '
            'display: flex; flex-direction: column; align-items: center; justify-content: center">\n'
            f'<span style="font-size: 12px; font-weight: 900; line-height: 1.2; letter-spacing: 0.06em">{d.strftime("%a").upper()}</span>\n'
            f'<span style="font-family: \'Mochiy Pop One\', sans-serif; font-size: 22px; font-weight: 400; line-height: 1.1">{d.day}</span>\n'
            '</div>\n</div>\n'
            '<div aria-hidden="true" style="width: 26px; flex: none; position: relative">\n'
            f'<div style="position: absolute; left: 10px; top: 0; bottom: 0; width: 6px; background: {leg["mid"]}"></div>\n'
            f'{rail}\n</div>\n'
            '<div style="flex: 1; min-width: 0; padding: 12px 0; display: flex; flex-direction: column; gap: 10px">\n'
            f'{body}</div>\n</li>\n')


def note_html(icon, inner):
    return ('<li style="display: flex; gap: 12px; align-items: flex-start">\n'
            '<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#8A6A00" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" style="flex: none; margin-top: 1px">{ICONS.get(icon, ICONS["warn"])}</svg>\n'
            f'<div style="font-size: 15px; font-weight: 500; line-height: 1.5">{inner}</div>\n</li>\n')


PLANE = ('<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
         'stroke-linejoin="round"><path d="M12 2c1 0 1.5 1 1.5 2.5V9l7.5 4.5V16l-7.5-2.5V18l2 1.5V21L12 20l-3.5 1v-1.5l2-1.5v-4.5L3 16v-2.5L10.5 9V4.5C10.5 3 11 2 12 2z"></path></svg>')


def flight_card(label, href, route, when, lands, crew_lines):
    crew = "".join('<span style="display: block; margin-top: 8px; padding-top: 8px; border-top: 2px dotted #CFE7F4; font-size: 13px; '
                   f'font-weight: 700; line-height: 1.4; color: #1E5A7A">{esc(c)}</span>\n' for c in crew_lines)
    return (f'<a href="{href}" style="flex: 1 1 260px; display: block; padding: 16px 18px; border-radius: 22px; background: #FFFFFF; '
            'border: 3px dashed #9CCFEA; color: #3D2B3D; text-decoration: none">\n'
            '<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; background: #DFF1FB; '
            'color: #1E5A7A; font-size: 12px; font-weight: 900; line-height: 1.3; letter-spacing: 0.06em">\n'
            f'{PLANE}\n<span>{esc(label)}</span>\n</span>\n'
            f'<span style="display: block; margin-top: 8px; font-family: \'Mochiy Pop One\', sans-serif; font-size: 24px; font-weight: 400; line-height: 1.2">{esc(route)}</span>\n'
            f'<span style="display: block; margin-top: 6px; font-size: 15px; font-weight: 900; line-height: 1.4">{esc(when)}</span>\n'
            f'<span style="display: block; margin-top: 2px; font-size: 14px; font-weight: 500; line-height: 1.4; color: #6E5A6E">{esc(lands)}</span>\n'
            f'{crew}</a>\n')


# ---------- flights ----------
FLIGHT_RE = re.compile(r"^([A-Z0-9]{2}\d{1,4})\s+([A-Z]{3})\s+to\s+([A-Z]{3})", re.I)


def flight_info(e):
    m = FLIGHT_RE.match(e["SUMMARY"].strip())
    if not m:
        return None
    code, frm, to = m.group(1).upper(), m.group(2).upper(), m.group(3).upper()
    ap = X["airports"]
    ftz = ZoneInfo(ap.get(frm, {}).get("tz", X["trip_tz"]))
    ttz = ZoneInfo(ap.get(to, {}).get("tz", X["trip_tz"]))
    dep = local(e["DTSTART"], ftz)
    arr = local(e["DTEND"], ttz)
    # TripIt's end time can be a few minutes off; prefer an arrival time written in the description.
    am = (re.search(r"(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?\s*[A-Z]{0,5}\s*\n\s*Arriv", e["DESCRIPTION"], re.I)
          or re.search(r"arr(?:ive|ives|ival)?[^0-9]{0,40}?(\d{1,2}):(\d{2})\s*([ap])\.?m", e["DESCRIPTION"], re.I))
    if am:
        h, mi, ap_ = int(am.group(1)), int(am.group(2)), am.group(3).lower()
        h = h % 12 + (12 if ap_ == "p" else 0)
        cand = arr.replace(hour=h, minute=mi)
        if abs((cand - arr).total_seconds()) < 3 * 3600:
            arr = cand
    conf = X["flights"].get(code, {})
    return {"code": code, "frm": frm, "to": to, "dep": dep, "arr": arr, "conf": conf,
            "name": conf.get("name", code), "to_jp": to in ("HND", "NRT")}


def ap_name(c):
    return X["airports"].get(c, {}).get("name", c)


# ---------- main ----------
STOP = {"the", "a", "an", "at", "in", "on", "of", "to", "and", "hike", "visit", "trip", "walk", "tour"}


def words(t):
    return {w for w in re.findall(r"[a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", t.lower()) if w not in STOP}


def same_thing(a, b):
    wa, wb = words(a), words(b)
    return bool(wa and wb) and (wa <= wb or wb <= wa)


def dedupe(day_rows):
    """One row per thing: when a hand-added row and a TripIt row describe the same place,
    keep the hand-added one (it has our notes and badges) and take TripIt's exact time."""
    feed = [r for r in day_rows if r.get("src") == "feed"]
    out = [r for r in day_rows if r.get("src") != "feed"]
    for f in feed:
        twin = next((m for m in out if m.get("src") != "feed" and not m.get("under") and same_thing(m["title"], f["title"])), None)
        if twin:
            twin["time"], twin["sort"] = f["time"], f["sort"]
            if f.get("recheck"):
                twin["recheck"] = True
        else:
            out.append(f)
    # exact repeats of the same title on the same day (any source)
    seen, final = set(), []
    for r in out:
        k = (" ".join(sorted(words(r["title"]))), r.get("under", ""))
        if k in seen:
            continue
        seen.add(k)
        final.append(r)
    return final


def build(feed_text):
    events = parse_ics(feed_text)
    legs = X["legs"]
    rows = {}            # date -> list of rows
    travel = set()
    notes = [note_html(n.get("icon"), n["html"]) for n in X.get("notes", [])]
    flights = []

    checkins = {}
    checkouts = {}
    for e in events:
        if e["SUMMARY"].strip() in X.get("skip", []) or e.get("DTSTART_ALLDAY"):
            continue
        s = e["SUMMARY"].strip()
        for lg in legs:
            if s == lg["checkin"]:
                checkins[lg["id"]] = local(e["DTSTART"]).date()
            if s == lg["checkout"]:
                checkouts[lg["id"]] = local(e["DTSTART"]).date()
    leg_start = [(checkins[lg["id"]], lg) for lg in legs if lg["id"] in checkins]
    leg_start.sort(key=lambda x: x[0])
    first_day = leg_start[0][0] if leg_start else None

    def leg_for(d):
        cur = None
        for start, lg in leg_start:
            if d >= start:
                cur = lg
        return cur

    def add(d, r):
        rows.setdefault(d, []).append(r)

    for e in events:
        s = e["SUMMARY"].strip()
        if s in X.get("skip", []) or e.get("DTSTART_ALLDAY"):
            continue
        f = flight_info(e)
        if f:
            flights.append(f)
            if f["to_jp"]:
                d = f["arr"].date(); travel.add(d)
                add(d, {"sort": f["arr"].strftime("%H:%M"), "time": hm(f["arr"]), "title": f["conf"].get("row", f"Land at {ap_name(f['to'])}, {f['name']}")})
            else:
                dj = local(e["DTSTART"]); d = dj.date(); travel.add(d)
                add(d, {"sort": dj.strftime("%H:%M"), "time": hm(dj), "title": f["conf"].get("row", f"Fly home, {f['name']}"),
                        "sub": f"Lands {ap_name(f['to'])} {hm(f['arr'])}" + (" the same day" if f["arr"].date() == f["dep"].date() else "")})
            continue
        st, en = local(e["DTSTART"]), local(e["DTEND"])
        d = st.date()
        low = s.lower()
        if low.startswith(("check-in", "check-out")):
            travel.add(d)
        conf = next((c for c in X["events"] if (low == c["match"] if c.get("exact") else c["match"] in low)
                     and c.get("if_location", "").lower() in e["LOCATION"].lower()), {})
        if conf.get("hide"):
            continue
        rng = f"{hm_short(st)}–{hm_short(en)}".replace(" PM–", "–").replace(" AM–", "–") if en > st else hm(st)
        if st.strftime("%p") != en.strftime("%p"):
            rng = f"{hm_short(st)}–{hm_short(en)}"
        fill = lambda t: t.replace("{end}", hm(en)).replace("{range}", rng).replace("{start}", hm(st))
        label = conf.get("time", hm(st))
        sort = conf.get("sort") or {"Morning": "08:00", "Midday": "12:00", "Afternoon": "14:00", "Evening": "18:00"}.get(label, st.strftime("%H:%M"))
        r = {"sort": sort, "time": label, "title": conf.get("title", s),
             "sub": fill(conf.get("sub", f"Until {hm(en)}" if (en - st) >= timedelta(minutes=90) else "")),
             "badge": conf.get("badge", ""), "under": conf.get("under", "").lower(), "src": "feed",
             "photos": conf.get("photos", [])}
        # Flag plans whose address is in a different city from where you're staying that night.
        lg = leg_for(d)
        loc = e["LOCATION"].replace("東京都", "東京")  # 東京都 (Tokyo-to) contains 京都 (Kyoto)
        moving = low.startswith(("check-in", "check-out")) or "shinkansen" in low or "train" in low
        if (lg and loc and not moving and d.isoformat() not in X.get("recheck_ok_dates", [])
                and not any(c.lower() in loc.lower() for c in lg["cities"])):
            other = next((L["cities"][0] for L in legs for c in L["cities"] if c.lower() in loc.lower()), None)
            if other:
                r["recheck"] = True
                r["sub"] = f"Listed in {other}, but you're staying in {lg['cities'][0]} that night"
                notes.insert(0, note_html("warn", f"<strong>{md(d)}:</strong> {esc(r['title'])} is listed in {esc(other)}, "
                                          f"but you'll be in {esc(lg['cities'][0])}. Double-check the booking in TripIt."))
        add(d, r)

    for m in X.get("manual", []):
        d = date.fromisoformat(m["date"])
        add(d, {"sort": m.get("sort", "00:00"), "time": m.get("time", ""), "title": m["title"], "sub": m.get("sub", ""),
                "badge": m.get("badge", ""), "under": m.get("under", "").lower(), "photos": m.get("photos", [])})

    # Days, grouped into legs
    days_by_leg = {lg["id"]: [] for lg in legs}
    for d in sorted(rows):
        if first_day and d < first_day:
            continue
        lg = leg_for(d)
        if not lg:
            continue
        rs = dedupe(rows[d])
        rs = sorted(rs, key=lambda r: (r["time"] not in ("All day",), r["sort"]))
        if os.environ.get("GITHUB_ACTIONS"):
            # Same names/times the public page shows; lets the trip assistant read the agenda.
            lines = [f'{r["time"] or "-"} | {r["title"]}' + (f' | {r["sub"]}' if r.get("sub") else "") for r in rs]
            msg = "%0A".join(l.replace("%", "%25").replace("\n", " ") for l in lines)
            print(f"::notice title=Agenda {d.isoformat()}::{msg}")
        parents = [r for r in rs if not r.get("under")]
        for c in [r for r in rs if r.get("under")]:
            host = next((p for p in parents if c["under"] in p["title"].lower()), None)
            if host:
                host.setdefault("children", []).append(c)
            else:
                parents.append(c)  # no matching place that day: show it on its own
        rs = sorted(parents, key=lambda r: (r["time"] not in ("All day",), r["sort"]))
        days_by_leg[lg["id"]].append(day_html(d, rs, lg, d in travel))

    page = (HERE / "template.html").read_text(encoding="utf-8")
    for lg in legs:
        i = lg["id"]
        ci, co = checkins.get(i), checkouts.get(i)
        if i == legs[-1]["id"] and not co:
            co = max(rows) if rows else ci
        nights = (co - ci).days if ci and co else 0
        nl = f"{nights} night" + ("" if nights == 1 else "s")
        span = f"{md(ci)}–{co.day if co and co.month == ci.month else md(co)}" if ci and co else ""
        page = page.replace("{{DAYS:%s}}" % i, "".join(days_by_leg[i]))
        page = page.replace("{{NIGHTS:%s}}" % i, nl)
        page = page.replace("{{SUB:%s}}" % i, esc(f"{lg['stay']} · {span} · {nl}"))

    # Flight cards
    def first(card):
        return next((f for f in flights if f["conf"].get("card") == card), None)
    cards = []
    out, outc = first("out"), first("out-crew")
    if out:
        crew = [f"{outc['conf'].get('crew', 'Also')}: {outc['name']} · {hm(outc['dep'])} from {outc['frm']}, lands {ap_name(outc['to'])} "
                f"{hm(outc['arr'])} {md(outc['arr'])}"] if outc else []
        cards.append(flight_card(f"OUTBOUND · {out['name']}", f"#day-{out['arr'].day}", f"{out['frm']} → {out['to']}",
                                 f"{out['dep'].strftime('%a')}, {md(out['dep'])} · {hm(out['dep'])}",
                                 f"Lands {out['arr'].strftime('%a')}, {md(out['arr'])} · {hm(out['arr'])}{out['conf'].get('arrive_note', '')}", crew))
    home, homec = first("home"), first("home-crew")
    if home:
        crew = [f"{homec['conf'].get('crew', 'Also')}: {homec['name']} · {hm(homec['dep'])} from {ap_name(homec['frm'])}, lands {homec['to']} "
                f"{hm(homec['arr'])}"] if homec else []
        same = home["arr"].date() == home["dep"].date()
        cards.append(flight_card(f"HOMEBOUND · {home['name']}", f"#day-{home['dep'].day}", f"{home['frm']} → {home['to']}",
                                 f"{home['dep'].strftime('%a')}, {md(home['dep'])} · {hm(home['dep'])}",
                                 f"Lands {ap_name(home['to'])} {hm(home['arr'])}" + (" the same day" if same else f" {md(home['arr'])}"), crew))
    page = page.replace("{{FLIGHTS}}", '<div style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 36px">\n' + "".join(cards) + "</div>")
    page = page.replace("{{NOTES}}", "".join(notes))
    now = datetime.now(TZ)
    page = page.replace("{{UPDATED}}", f"All times local · Synced with TripIt {md(now)}, {hm(now)} Japan time")
    return page


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(build(Path(src).read_text(encoding="utf-8")), encoding="utf-8")
    print("built", dst)
