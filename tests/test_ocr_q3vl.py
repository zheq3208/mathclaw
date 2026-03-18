from pathlib import Path

from mathclaw.agents.tools import mess_to_clean_q3vl as mod


def test_fuse_candidates_merges_consensus_boxes() -> None:
    cfg = {
        "iou_threshold": 0.55,
        "min_consensus_support": 2,
        "high_confidence_keep": 0.92,
    }
    candidates = [
        {
            "cls": "question",
            "qtype": "MC",
            "bbox": [100, 100, 300, 280],
            "visibility_ratio_est": 0.82,
            "confidence": 0.74,
            "page_index": 0,
            "source_view": "original",
            "source_kind": "proposal",
            "support_tokens": ["original"],
        },
        {
            "cls": "question",
            "qtype": "MC",
            "bbox": [108, 104, 304, 284],
            "visibility_ratio_est": 0.8,
            "confidence": 0.78,
            "page_index": 0,
            "source_view": "contrast_enhanced",
            "source_kind": "proposal",
            "support_tokens": ["contrast_enhanced"],
        },
        {
            "cls": "question",
            "qtype": "MC",
            "bbox": [460, 120, 620, 260],
            "visibility_ratio_est": 0.7,
            "confidence": 0.51,
            "page_index": 0,
            "source_view": "cleaned_grayscale",
            "source_kind": "proposal",
            "support_tokens": ["cleaned_grayscale"],
        },
    ]

    fused = mod._fuse_candidates(candidates, page_width=800, page_height=1200, cfg=cfg)

    assert len(fused) == 1
    assert fused[0]["id"] == "q_001"
    assert fused[0]["support_count"] == 2
    assert fused[0]["support_views"] == ["contrast_enhanced", "original"]


def test_recover_exam_layout_orders_questions_and_binds_figure(tmp_path: Path) -> None:
    page_image = tmp_path / "page-001.png"
    page_image.write_bytes(b"fake")
    payload = {
        "pipeline": "MessToClean-Q3VL",
        "source": "/tmp/sample.png",
        "run_dir": str(tmp_path),
        "pages": [
            {
                "page_index": 0,
                "image_path": str(page_image),
                "width": 1000,
                "height": 1400,
                "boxes": [
                    {"id": "q_001", "cls": "question", "qtype": "MC", "bbox": [80, 100, 440, 320], "visibility_ratio_est": 0.9, "confidence": 0.91},
                    {"id": "q_002", "cls": "question", "qtype": "SA", "bbox": [80, 420, 440, 760], "visibility_ratio_est": 0.9, "confidence": 0.93},
                    {"id": "q_003", "cls": "question", "qtype": "MC", "bbox": [560, 120, 920, 360], "visibility_ratio_est": 0.88, "confidence": 0.9},
                    {"id": "f_001", "cls": "figure", "qtype": "unknown", "bbox": [180, 520, 360, 700], "visibility_ratio_est": 0.98, "confidence": 0.95},
                ],
            }
        ],
    }

    result = mod.recover_exam_layout_from_box_evidence(payload)

    assert [item["id"] for item in result["ordered_questions"]] == ["q_001", "q_002", "q_003"]
    assert result["pages"][0]["layout"]["column_count"] == 2
    assert result["pages"][0]["figure_bindings"][0]["question_id"] == "q_002"
    assert Path(result["stage2_layout_path"]).exists()


def test_extract_math_document_dispatch(monkeypatch) -> None:
    calls: list[tuple[str, int, int | None]] = []

    def fake_stage1(source: str, max_pages: int = 2, run_dir: str | None = None) -> dict:
        calls.append(("stage1", max_pages, None))
        return {"stage": "stage1", "source": source, "run_dir": "/tmp/run", "pages": []}

    def fake_stage2(payload: dict) -> dict:
        calls.append(("stage2", 0, None))
        return {"stage": "stage2", "payload": payload}

    def fake_full(source: str, max_pages: int = 2, max_questions: int | None = None) -> dict:
        calls.append(("full", max_pages, max_questions))
        return {"stage": "full", "source": source, "max_questions": max_questions}

    monkeypatch.setattr(mod, "extract_qwen_box_evidence", fake_stage1)
    monkeypatch.setattr(mod, "recover_exam_layout_from_box_evidence", fake_stage2)
    monkeypatch.setattr(mod, "run_mess_to_clean_q3vl", fake_full)

    stage1 = mod.extract_math_document("sample.png", max_pages=1, mode="stage1")
    stage2 = mod.extract_math_document("sample.png", max_pages=2, mode="layout")
    full = mod.extract_math_document("sample.png", max_pages=3, mode="full", max_questions=4)

    assert stage1["stage"] == "stage1"
    assert stage2["stage"] == "stage2"
    assert full["stage"] == "full"
    assert calls == [("stage1", 1, None), ("stage1", 2, None), ("stage2", 0, None), ("full", 3, 4)]
