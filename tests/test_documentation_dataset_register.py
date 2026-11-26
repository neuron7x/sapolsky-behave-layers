from __future__ import annotations

import json
import unittest

from scripts import check_dataset_register as gate


class DatasetRegisterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads((gate.ROOT / "schemas/dataset.schema.json").read_text(encoding="utf-8"))
        self.payload = gate.load_yaml((gate.ROOT / "docs/data/DATASET_REGISTER.yaml").read_text(encoding="utf-8"))

    def test_actual_synthetic_register(self) -> None:
        gate.validate(self.payload, self.schema, gate.ROOT)

    def test_external_data_cannot_hide_in_synthetic_register(self) -> None:
        self.payload["datasets"][0]["kind"] = "external"
        with self.assertRaisesRegex(ValueError, "invalid dataset field kind"):
            gate.validate(self.payload, self.schema, gate.ROOT)

    def test_declared_generator_must_exist(self) -> None:
        self.payload["datasets"][0]["generator"] = "experiments/nonexistent_generator.py"
        with self.assertRaisesRegex(ValueError, "unbound generator"):
            gate.validate(self.payload, self.schema, gate.ROOT)

    def test_duplicate_yaml_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate YAML field"):
            gate.load_yaml("datasets: []\ndatasets: []\n")
