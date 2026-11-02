"""Config-driven behaviour: the repo's pipeline/ config is valid, and adding an entity/report is YAML-only."""
import os
import shutil

import pytest
import yaml

from conftest import CONFIG
from mcds_config import PipelineConfig, layer_sql
import mcds_engine as E


def test_repo_config_is_valid():
    cfg = PipelineConfig(CONFIG)
    assert len(cfg.sources) == 8
    order = cfg.entity_order()
    assert order.index("person") < order.index("student") < order.index("unit_of_learning_enrolment")
    assert cfg.report_order()[0] == "fact_student_load"


def test_tokens_resolve_from_rules():
    cfg = PipelineConfig(CONFIG)
    assert cfg.resolve("${rules.load.standard_annual_load_cp}") == "24"
    with pytest.raises(KeyError):
        cfg.resolve("${rules.load.does_not_exist}")


def test_layer_references_are_rewritten():
    assert layer_sql("FROM silver.student s JOIN bronze.person p") == "FROM silver__student s JOIN bronze__person p"


def test_every_entity_and_report_generates_sql():
    cfg = PipelineConfig(CONFIG)
    for n in cfg.entities:
        assert "${" not in E.entity_sql(cfg, n)
    for n in cfg.reports:
        assert "${" not in E.report_sql(cfg, n)


def test_new_entity_and_report_need_no_code(tmp_path):
    root = tmp_path / "pipeline"
    shutil.copytree(CONFIG, root)
    (root / "silver" / "faculty.yaml").write_text(yaml.safe_dump({
        "entity": "faculty", "description": "faculties only", "primary_key": ["organisation_id"],
        "from": "silver.organisation o", "where": "o.organisation_level = 'FACULTY'",
        "columns": {"organisation_id": {"expr": "o.organisation_id"}, "name": {"expr": "o.organisation_name"}}}))
    (root / "gold" / "faculty_count.yaml").write_text(yaml.safe_dump({
        "report": "faculty_count", "description": "count", "from": "silver.faculty f",
        "dimensions": {"one": "1"}, "measures": {"n": "COUNT(*)"}}))
    cfg = PipelineConfig(str(root))
    assert cfg.entity_order().index("organisation") < cfg.entity_order().index("faculty")
    assert "FROM silver__faculty f" in E.report_sql(cfg, "faculty_count")


def test_broken_config_is_rejected(tmp_path):
    root = tmp_path / "pipeline"
    shutil.copytree(CONFIG, root)
    bad = yaml.safe_load((root / "silver" / "student.yaml").read_text())
    bad["foreign_keys"] = {"student_id": "nowhere.id"}
    (root / "silver" / "student.yaml").write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="foreign key"):
        PipelineConfig(str(root))
