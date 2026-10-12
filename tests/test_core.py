from datetime import date

from accq import signals as s
from accq.core import norm_city, norm_name
from accq.letters import channels, letter
from accq.scoring import hard_filter, score

F = dict(founded_by=1996, employees_min=5, employees_max=50)


def test_norm_name_strips_legal_suffix_and_filler():
    assert norm_name("Jansen Installatietechniek B.V.") == norm_name("Jansen")
    assert norm_city("Zwolle ") == "zwolle"


def test_founding_year_prefers_earliest_explicit():
    assert s.founding_year("Sinds 1978 uw loodgieter. Sinds 2019 ook airco.")[0] == 1978
    assert s.founding_year("Het bedrijf is opgericht in 1985 door de heer Bos")[0] == 1985


def test_founding_year_ignores_copyright_and_flags_weak():
    assert s.founding_year("© 2021 Bos Installatie")[0] is None
    y, basis = s.founding_year("Al 40 jaar ervaring in de installatiebranche")
    assert y == s.THIS_YEAR - 40 and "weak" in basis


def test_kvk_and_legal_form():
    assert s.kvk_number("Kamer van Koophandel nummer: 12345678 BTW NL") == "12345678"
    assert s.kvk_number("Telefoon 0612345678") is None
    assert s.legal_form("Bos Installatie B.V.") == ("BV", "name")
    assert s.legal_form("Bos Installatie") == (None, None)
    assert s.is_natural_person_form(None) and s.is_natural_person_form("VOF") and not s.is_natural_person_form("BV")


def test_headcount():
    assert s.headcount("Wij zijn met 14 medewerkers en 3 stagiairs")[0] == 14


def test_hard_filter_unknown_is_not_a_pass():
    assert hard_filter(dict(founded_year=1980, employees=12), F)[0] == "qualified"
    assert hard_filter(dict(founded_year=2005, employees=12), F)[0] == "excluded"
    assert hard_filter(dict(founded_year=1980, employees=80), F)[0] == "excluded"
    assert hard_filter(dict(founded_year=None, employees=12), F)[0] == "needs_check"
    assert hard_filter(dict(founded_year=None, employees=12), {**F, "unknown_founded": "drop"})[0] == "excluded"


W = dict(owner_60_plus=3, owner_active=3, no_successor=2.5, now_received=1, stale_website=1, multi_source=1,
         successor_named=-6, recent_ownership_change=-6, new_hires=-1)


def test_successor_counts_heavily_against():
    good = dict(owner_age_hint="60+", owner_active="yes", successor_named="no", recent_ownership_change="no", new_hires="no")
    bad = {**good, "successor_named": "yes"}
    assert score({}, good, W)[0] - score({}, bad, W)[0] == 8.5


def test_absence_of_successor_evidence_is_half_weight():
    silent = dict(owner_age_hint="unknown", owner_active="unknown", successor_named="unknown")
    assert score({}, silent, W)[0] == 1.25
    assert score({}, None, W)[0] == 0  # unclassified gets nothing


def test_stale_website_uses_year():
    assert score(dict(website_last_year=2015), None, W, date(2026, 1, 1))[0] == 1
    assert score(dict(website_last_year=2025), None, W, date(2026, 1, 1))[0] == 0


def test_channels_follow_legal_form():
    assert not channels("VOF", "a@b.nl", "06")["email"]
    assert not channels(None, "a@b.nl", "06")["email"]
    assert channels("BV", "a@b.nl", "06")["email"] and not channels("BV", None, None)["email"]


def test_letter_is_draft_and_has_optout():
    sender = dict(sender_name="[X]", sender_company="Co", sender_address="a", sender_contact="c")
    txt = letter(dict(name="Bos", street="Weg 1", postcode="8000AA", city="Zwolle"), sender)
    assert "Niet versturen" in txt and "uitsluitingslijst" in txt and "sender_name" in txt


def test_weak_experience_estimate_never_becomes_founding_year():
    assert s.split_weak(*s.founding_year("Ruim 30 jaar ervaring"))[0] is None
    assert s.split_weak(*s.founding_year("Sinds 1985"))[0] == 1985
