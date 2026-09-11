import pytest

from bloomboss.ingest import load_history_csv


def test_invalid_date_reports_source_row(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,purchase_date\n"
        "B1,U1,Cuprea,growing,not-a-date\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"row 2: invalid ISO date: not-a-date"):
        load_history_csv(path)


def test_invalid_integer_reports_source_row(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,batch_quantity\n"
        "B1,U1,Cuprea,growing,many\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"row 2: invalid integer: many"):
        load_history_csv(path)


def test_invalid_money_reports_source_row(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,allocated_landed_cost\n"
        "B1,U1,Cuprea,growing,nope\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"row 2: invalid decimal: nope"):
        load_history_csv(path)
