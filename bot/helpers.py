import html
from config import ADMIN_IDS


def _format_date(start: str | None, end: str | None) -> str:
    if not start and not end:
        return "empty"
    if start and end and end != start:
        return f"{start} - {end}"
    return start or "empty"


def format_event(event: dict) -> str:
    title = html.escape(event.get("title", "Unknown Event"))
    date = html.escape(_format_date(event.get("start_date"), event.get("end_date")))

    st = event.get("start_time")
    et = event.get("end_time")
    if st and et:
        time_str = f"{html.escape(st)} – {html.escape(et)}"
    elif st:
        time_str = html.escape(st)
    else:
        time_str = "empty"

    fee = html.escape(event.get("fee") or "empty")
    venue = html.escape(event.get("venue") or "empty")

    link_raw = event.get("registration_link")
    if link_raw:
        link = html.escape(str(link_raw))
        link_line = f'\U0001f517 <b>Link:</b> <a href="{link}">Register/More Info</a>'
    else:
        link_line = "\U0001f517 <b>Link:</b> empty"

    mycsd = "Yes" if event.get("has_mycsd") else "No"
    status = event.get("status", "upcoming")
    icon = {"active": "\U0001f7e2", "expired": "\U0001f534", "upcoming": "\U0001f7e1"}
    default_icon = "\U0001f7e1"
    badge = f"{icon.get(status, default_icon)} <b>{status.upper()}</b>\n"

    return (
        f"\U0001f4c5 <b>{title}</b>\n"
        f"{badge}"
        f"\U0001f5d3 <b>Date:</b> {date}\n"
        f"\U0001f552 <b>Time:</b> {time_str}\n"
        f"\U0001f4b0 <b>Fee:</b> {fee}\n"
        f"\U0001f4cd <b>Venue:</b> {venue}\n"
        f"\U0001f31f <b>MyCSD:</b> {mycsd}\n"
        f"{link_line}\n"
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def format_event_compact(event: dict) -> str:
    title = event.get("title", "?")
    status = event.get("status", "upcoming").upper()
    st = event.get("start_time")
    et = event.get("end_time")
    time_str = f"{st} – {et}" if st and et else (st or "-")
    fee = event.get("fee") or "-"
    venue = event.get("venue") or "-"
    link = event.get("registration_link") or "-"

    return (
        f"{title}\n"
        f"  Status: {status}\n"
        f"  Date: {_format_date(event.get('start_date'), event.get('end_date'))}\n"
        f"  Time: {time_str}\n"
        f"  Fee: {fee}\n"
        f"  Venue: {venue}\n"
        f"  Link: {link}"
    )
