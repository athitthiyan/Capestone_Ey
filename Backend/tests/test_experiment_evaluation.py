from scripts.evaluate_experiments import classification_metrics, rule_baseline, split_for


def test_metrics_use_standard_binary_definitions():
    result = classification_metrics([True, True, False, False], [True, False, True, False])
    assert result["accuracy"] == 0.5
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["confusion_matrix"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}


def test_split_is_stable():
    assert split_for("TRX-000001") == split_for("TRX-000001")


def test_rule_baseline_does_not_read_label():
    row = {
        "amount_usd": "1",
        "risk_hint": "materiality",
        "document_status": "complete",
        "po_number": "PO-1",
        "payment_method": "ACH",
    }
    assert rule_baseline(row) is False
    row["risk_hint"] = "normal"
    assert rule_baseline(row) is False
