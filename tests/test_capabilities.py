import unittest

from pydantic import BaseModel, ValidationError

from vidxp.capabilities.contracts import (
    CapabilityContext,
    CapabilityDefinition,
    CapabilityInput,
    CapabilityOutput,
    OperationDefinition,
)
from vidxp.capabilities.actor.config import ActorConfig
from vidxp.capabilities.dialogue.config import DialogueConfig
from vidxp.capabilities.registry import (
    CAPABILITIES,
    capability_names,
    collection_names,
    index_capability_names,
    preparable_capability_names,
    validate_capability_options,
)
from vidxp.capabilities.scene.config import SceneConfig
from vidxp.core.contracts import IndexConfig
from vidxp.core.runner import _index_groups


class ExampleInput(CapabilityInput):
    value: int


class ExampleOutput(CapabilityOutput):
    doubled: int


class CapabilityTests(unittest.TestCase):
    def test_registry_is_explicit_and_drives_index_collections(self):
        self.assertEqual(
            capability_names(),
            ("dialogue", "scene", "actor"),
        )
        self.assertEqual(
            index_capability_names(),
            capability_names(),
        )
        self.assertEqual(
            preparable_capability_names(),
            ("dialogue", "scene"),
        )
        self.assertEqual(
            collection_names(),
            {
                "dialogue": "dialogue",
                "scene": "scene",
                "actor": "actor",
            },
        )
        self.assertEqual(collection_names(("scene",)), {"scene": "scene"})

    def test_registered_operations_use_pydantic_contracts(self):
        for capability in CAPABILITIES.values():
            for operation in capability.operations.values():
                self.assertTrue(
                    issubclass(operation.input_model, BaseModel)
                )
                self.assertTrue(
                    issubclass(operation.output_model, BaseModel)
                )

    def test_built_in_settings_are_capability_owned_and_validated(self):
        self.assertIs(CAPABILITIES["dialogue"].config_model, DialogueConfig)
        self.assertIs(CAPABILITIES["scene"].config_model, SceneConfig)
        self.assertIs(CAPABILITIES["actor"].config_model, ActorConfig)

        options = validate_capability_options(
            ("scene",),
            {"scene": {"batch_size": 4, "model": "test-model"}},
        )

        self.assertEqual(
            options["scene"],
            {"batch_size": 4, "model": "test-model"},
        )
        with self.assertRaises(ValidationError):
            validate_capability_options(
                ("actor",),
                {"actor": {"match_threshold": 2}},
            )

    def test_core_config_has_no_built_in_capability_fields(self):
        fields = IndexConfig.__dataclass_fields__
        for name in (
            "sentence_model",
            "whisper_model",
            "clip_model",
            "dialogue_batch_size",
            "scene_batch_size",
            "actor_batch_size",
            "face_match_threshold",
        ):
            self.assertNotIn(name, fields)

    def test_operation_validates_both_input_and_output(self):
        operation = OperationDefinition(
            input_model=ExampleInput,
            output_model=ExampleOutput,
            handler=lambda _context, request: {
                "doubled": request.value * 2
            },
            requires_index=False,
        )

        result = operation.invoke(
            CapabilityContext(config=None),
            {"value": 3},
        )

        self.assertEqual(result, ExampleOutput(doubled=6))
        with self.assertRaises(ValidationError):
            operation.invoke(
                CapabilityContext(config=None),
                {"value": 3, "unexpected": True},
            )

    def test_operation_only_capability_needs_no_dummy_indexer(self):
        capability = CapabilityDefinition(
            name="export",
            description="Export results.",
            extra="export",
            operations={
                "run": OperationDefinition(
                    input_model=ExampleInput,
                    output_model=ExampleOutput,
                    handler=lambda _context, request: {
                        "doubled": request.value * 2
                    },
                    requires_index=False,
                )
            },
        )

        self.assertIsNone(capability.indexer)
        self.assertIsNone(capability.collection_name)

    def test_shared_visual_handler_is_grouped_without_name_switches(self):
        self.assertEqual(
            _index_groups(("dialogue", "scene", "actor")),
            (("dialogue",), ("scene", "actor")),
        )

    def test_capability_options_do_not_require_core_config_fields(self):
        config = IndexConfig(
            enabled_modalities=("ocr",),
            collection_names={"ocr": "ocr"},
            capability_options={"ocr": {"language": "en"}},
        )

        self.assertEqual(
            config.options_for("ocr"),
            {"language": "en"},
        )


if __name__ == "__main__":
    unittest.main()
