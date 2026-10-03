import pandas as pd

from skidsignal.config import load_settings
from skidsignal.index.bm25 import BM25
from skidsignal.index.store import HybridIndex
from skidsignal.index.text import STOP_WORDS


def _kb() -> pd.DataFrame:
    rows = [
        ("C:1", "complaint", "2015 HYUNDAI SANTA FE", "The ABS module caught fire while the car was parked in the garage.", "|HYUNDAI|", "|HYUNDAI SANTA FE|", "2023-10-01"),
        ("C:2", "complaint", "2018 RAM 2500", "ABS and traction control lights are on. Dealer says the hydraulic control unit failed.", "|RAM|", "|RAM 2500|", "2024-03-01"),
        ("C:3", "complaint", "2018 RAM 2500", "ABS light on again, the part is on back order for months.", "|RAM|", "|RAM 2500|", "2025-06-01"),
        ("C:4", "complaint", "2024 HYUNDAI PALISADE", "Brake pedal pulsates and grinds at low speed when stopping on dry pavement.", "|HYUNDAI|", "|HYUNDAI PALISADE|", "2025-07-01"),
        ("R:23V651", "recall", "Recall 23V651", "The ABS module may leak brake fluid and short circuit which can cause an engine compartment fire.", "|HYUNDAI|", "|HYUNDAI SANTA FE|", "2023-09-20"),
        ("K:note", "reference", "Thermal events", "A powered hydraulic unit can short circuit and start a fire while parked.", "", "", None),
    ]
    kb = pd.DataFrame(rows, columns=["doc_id", "source", "title", "text", "makes", "vehicles", "date"])
    kb["date"] = pd.to_datetime(kb["date"])
    kb["model_year"] = pd.array([2015, 2018, 2018, 2024, None, None], dtype="Int64")
    kb["is_abs"], kb["is_brake"], kb["chunk_id"] = True, True, kb["doc_id"] + "#0"
    return kb


def _index(**overrides) -> HybridIndex:
    cfg = load_settings(overrides={"retrieval.lsa_dim": 4, "retrieval.candidate_k": 10, **overrides})
    return HybridIndex.build(_kb(), cfg)


def test_fire_is_not_a_stop_word():
    assert "fire" not in STOP_WORDS and "front" not in STOP_WORDS
    bm25 = BM25().fit(["the module caught fire", "the module failed", "front brakes squeal"])
    scores = bm25.scores("fire")
    assert scores[0] > 0 and scores[1] == 0


def test_bm25_ranks_the_matching_document_first():
    hits = _index().search("module fire while parked", k=3, mode="bm25", sources=["complaint"])
    assert hits[0].doc_id == "C:1"


def test_filters_by_source_vehicle_and_date():
    index = _index()
    assert {h.source for h in index.search("ABS fire", k=5, sources=["recall"])} == {"recall"}
    ram = index.search("ABS light", k=5, vehicle="ram 2500", sources=["complaint"])
    assert {h.doc_id for h in ram} == {"C:2", "C:3"}
    early = index.search("ABS light", k=5, vehicle="RAM 2500", date_to="2024-12-31")
    assert [h.doc_id for h in early] == ["C:2"]            # the 2025 complaint is in the future of this as of date
    assert index.search("ABS light", k=5, make="TOYOTA") == []


def test_single_channel_modes_work_when_fusion_weight_is_zero():
    index = _index(**{"retrieval.rrf_weight_dense": 0.0})
    assert index.search("pedal pulsates at low speed", k=2, mode="dense")
    assert index.search("pedal pulsates at low speed", k=2, mode="hybrid")[0].doc_id == "C:4"


def test_index_round_trip(tmp_path):
    index = _index()
    index.save(tmp_path)
    loaded = HybridIndex.load(tmp_path, index.cfg)
    assert [h.doc_id for h in loaded.search("back order part", k=2)] == [h.doc_id for h in index.search("back order part", k=2)]
