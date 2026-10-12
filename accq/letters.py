"""Channel rules (AVG / Telecommunicatiewet) and the Dutch letter template."""
from __future__ import annotations

from accq.signals import is_natural_person_form


def channels(legal_form: str | None, email: str | None, phone: str | None) -> dict:
    """Letter is always allowed. Email/phone only for BV/NV; unknown form is treated as natural person."""
    if is_natural_person_form(legal_form):
        why = "rechtsvorm onbekend: strikt behandeld" if legal_form is None else f"{legal_form}: natuurlijk persoon"
        return {"letter": True, "email": False, "phone": False,
                "note": f"Alleen brief ({why}). E-mail vereist voorafgaande toestemming (Tw art. 11.7); bellen alleen met opt-in."}
    return {"letter": True, "email": bool(email), "phone": bool(phone),
            "note": f"{legal_form}: e-mail en bellen toegestaan met duidelijke opt-out; brief blijft de eerste stap."}


def letter(c: dict, sender: dict) -> str:
    placeholders = [k for k, v in sender.items() if "[" in str(v)]
    warn = ("> **CONCEPT. Nog niet goedgekeurd. Niet versturen.**\n" +
            (f"> Afzendergegevens nog invullen: {', '.join(placeholders)}\n" if placeholders else "") + "\n")
    addr = ", ".join(x for x in (c.get("street"), f"{c.get('postcode') or ''} {c.get('city') or ''}".strip()) if x)
    return f"""{warn}{sender['sender_company']}
{sender['sender_address']}

Aan: de eigenaar van {c['name']}
{addr}

Onderwerp: een vrijblijvende vraag over de toekomst van {c['name']}

Geachte eigenaar,

Mijn naam is {sender['sender_name']}. Ik schrijf u persoonlijk, omdat {c['name']} volgens ons een bedrijf is dat met vakmanschap en over een lange periode is opgebouwd.

Wij zoeken geen bedrijf om uit elkaar te halen. Wij zoeken ondernemingen om voort te zetten: met behoud van de naam, het team en de klanten. Daarom een eenvoudige vraag: staat u open voor een vrijblijvend gesprek over wat u met uw bedrijf voorheeft, nu of over een aantal jaren? Ook als het antwoord nee is, stellen wij het op prijs als u ons dat laat weten.

U kunt mij bereiken via {sender['sender_contact']}. Alles wat u vertelt, blijft vertrouwelijk.

Met vriendelijke groet,

{sender['sender_name']}
{sender['sender_company']}

---
Waarom ontvangt u deze brief? Uw bedrijfsgegevens (naam en vestigingsadres) komen uit openbare bronnen, zoals uw eigen website en openbare bedrijfsregisters. Wij gebruiken ze alleen om u deze ene brief te sturen. Wilt u geen verdere post van ons ontvangen of wilt u dat wij uw gegevens verwijderen, laat het ons dan weten via {sender['sender_contact']}; wij zetten u direct op onze uitsluitingslijst.
"""
