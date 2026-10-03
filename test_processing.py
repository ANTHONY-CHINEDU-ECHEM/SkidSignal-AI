import pandas as pd

from skidsignal.ingestion.parsers import COMPLAINT_COLUMNS, COMPLAINT_KEEP
from skidsignal.processing.corpus import chunk_text
from skidsignal.processing.normalise import build_complaints, build_recalls, estimate_campaign_dates


def _row(odino, component, narrative, make="RAM", model="2500", year="2018", ldate="20240115", **extra):
    row = {c: "" for c in COMPLAINT_COLUMNS}
    row.update({"CMPLID": odino + component[:3], "ODINO": odino, "MAKETXT": make, "MODELTXT": model, "YEARTXT": year,
                "COMPDESC": component, "CDESCR": narrative, "LDATE": ldate, "PROD_TYPE": "V", "CRASH": "N", "FIRE": "N",
                "INJURED": "0", "DEATHS": "0"})
    row.update(extra)
    return row


def test_taxonomy_recognises_abs_language_and_ignores_lookalikes(taxonomy):
    text = pd.Series([
        "THE ABS LIGHT CAME ON AND STAYED ON", "anti-lock brakes pulsed at low speed", "I was absolutely terrified",
        "The hydraulic electronic control unit shorted", "wheel speed sensor replaced twice", "The cabs of these trucks leak",
    ])
    assert taxonomy.is_abs_text(text).tolist() == [True, True, False, True, True, False]


def test_failure_mode_tags(taxonomy):
    tags = taxonomy.tag_failure_modes(pd.Series([
        "ABS warning light is on and the ABS module failed. Part is on backorder.",
        "The brake pedal went to the floor and I could not stop",
        "ABS module caught fire while parked",
    ]))
    assert tags.loc[0, ["fm_warning_lamp", "fm_module_or_hydraulic_unit", "fm_remedy_unavailable"]].all()
    assert tags.loc[1, "fm_loss_of_braking"] and not tags.loc[1, "fm_warning_lamp"]
    assert tags.loc[2, "fm_thermal_event"]


def test_complaints_collapse_to_one_row_per_complaint_and_drop_duplicates(taxonomy):
    long_text = "The ABS light came on and the dealer said the ABS module has failed and no part is available."
    raw = pd.DataFrame([
        _row("100", "SERVICE BRAKES", long_text), _row("100", "ELECTRICAL SYSTEM", long_text),
        _row("101", "SERVICE BRAKES", long_text),                      # exact duplicate submission
        _row("102", "ENGINE", "Engine stalls on the highway without any warning at all.", CRASH="Y"),
        _row("103", "SERVICE BRAKES, AIR:ANTILOCK:ABS WARNING LIGHT", "Lamp stays lit.", year="9999"),
    ])[COMPLAINT_KEEP]
    out = build_complaints(raw, taxonomy)
    assert len(out) == 3 and out["complaint_id"].tolist() == ["100", "102", "103"]
    first = out.iloc[0]
    assert first["components"] == "SERVICE BRAKES | ELECTRICAL SYSTEM" and first["vehicle"] == "RAM 2500"
    assert first["is_abs"] and first["fm_remedy_unavailable"] and first["month"] == "2024-01"
    assert not out.iloc[1]["is_abs"] and out.iloc[1]["severe"]
    assert out.iloc[2]["is_abs"] and pd.isna(out.iloc[2]["model_year"])   # flagged by component code alone


def test_campaign_dates_are_ordered_within_a_year():
    campaigns = pd.DataFrame({"year": [2023, 2023, 2023], "rtype": ["V", "V", "V"], "seq": [1, 450, 900]})
    dates = estimate_campaign_dates(campaigns)
    assert dates.is_monotonic_increasing and dates.iloc[0].year == 2023 and dates.iloc[-1].month == 12


def test_recall_roll_up_flags_abs_campaigns(taxonomy):
    docs = pd.DataFrame({
        "CAMPNO": ["23V651", "23V651", "23V100"], "DOCUMENT": ["a.pdf", "b.pdf", "c.pdf"],
        "MAKETXT": ["Hyundai", "Hyundai", "Ford"], "MODELTXT": ["Santa Fe", "Tucson", "Edge"], "YEARTXT": ["2013", "2015", "2020"],
        "SUMMARY": ["The Anti-Lock Brake System (ABS) module may short and cause a fire.", "Owner letter about the ABS module fuse.",
                    "The rear view camera image may not display."],
    })
    campaigns, vehicles = build_recalls(docs, taxonomy)
    flags = campaigns.set_index("campno")["is_abs"]
    assert flags["23V651"] and not flags["23V100"]
    assert set(vehicles.loc[vehicles["campno"] == "23V651", "vehicle"]) == {"HYUNDAI SANTA FE", "HYUNDAI TUCSON"}


def test_chunking_respects_the_size_limit_and_keeps_all_text():
    text = " ".join(f"Sentence number {i} about the brake system." for i in range(120))
    chunks = chunk_text(text, max_chars=400, overlap=60)
    assert len(chunks) > 5 and all(len(c) <= 400 for c in chunks)
    assert "Sentence number 0 " in chunks[0] and "Sentence number 119 " in chunks[-1]
    assert chunk_text("short text") == ["short text"] and chunk_text("") == []
